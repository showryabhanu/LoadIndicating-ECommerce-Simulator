#!/usr/bin/env python3
"""
CloudMart Infrastructure Automation (infra.py)
Manages the creation and teardown of the AWS infrastructure for CloudMart:
- VPC & Subnet resolution
- Security Groups (ALB SG on port 80, EC2 SG on port 8000)
- Target Group & Application Load Balancer (ALB)
- Launch Template with AL2023, Systemd Gunicorn service, and detailed monitoring
- Auto Scaling Group (min 1, max 4, desired 1) with ELB health checks
- Dynamic Simple Scaling Policies (+1 / -1) and CloudWatch CPU Utilization Alarms
- Outputs infra-output.json and validates health via HTTP curl

All names are prefixed with "cloudmart".
"""

import sys
import os
import json
import time
import base64
import urllib.request
import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
OUTPUT_FILE = "infra-output.json"
CONFIG_FILE = "config.json"

# Load config if present to ensure matching region
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        cfg = json.load(f)
        REGION = cfg.get("region", REGION)

ec2 = boto3.client("ec2", region_name=REGION)
ssm = boto3.client("ssm", region_name=REGION)
elbv2 = boto3.client("elbv2", region_name=REGION)
asg = boto3.client("autoscaling", region_name=REGION)
cw = boto3.client("cloudwatch", region_name=REGION)


def get_default_vpc_and_subnets():
    """Retrieves the default VPC and one subnet per distinct Availability Zone."""
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"]
    if not vpcs:
        raise RuntimeError("No default VPC found in region " + REGION)
    vpc_id = vpcs[0]["VpcId"]

    subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"]
    # Select 1 subnet per AZ to ensure multi-AZ deployment
    az_subnets = {}
    for s in subnets:
        az = s["AvailabilityZone"]
        if az not in az_subnets:
            az_subnets[az] = s["SubnetId"]

    subnet_ids = list(az_subnets.values())
    if len(subnet_ids) < 2:
        raise RuntimeError("Need subnets in at least 2 AZs, found: " + str(len(subnet_ids)))

    print(f"[VPC] Found default VPC {vpc_id} with {len(subnet_ids)} subnets across {len(az_subnets)} AZs")
    return vpc_id, subnet_ids


def get_latest_al2023_ami():
    """Queries AWS SSM for the latest official Amazon Linux 2023 x86_64 AMI ID."""
    param_name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
    resp = ssm.get_parameter(Name=param_name)
    ami_id = resp["Parameter"]["Value"]
    print(f"[AMI] Latest AL2023 AMI: {ami_id}")
    return ami_id


def setup_security_groups(vpc_id):
    """
    Creates cloudmart-alb-sg (inbound 80 from 0.0.0.0/0) and
    cloudmart-ec2-sg (inbound 8000 only from cloudmart-alb-sg).
    """
    # 1. ALB Security Group
    alb_sg_name = "cloudmart-alb-sg"
    try:
        alb_sgs = ec2.describe_security_groups(Filters=[
            {"Name": "group-name", "Values": [alb_sg_name]},
            {"Name": "vpc-id", "Values": [vpc_id]}
        ])["SecurityGroups"]
        if alb_sgs:
            alb_sg_id = alb_sgs[0]["GroupId"]
            print(f"[SG] Found existing ALB SG: {alb_sg_id}")
        else:
            alb_sg = ec2.create_security_group(
                GroupName=alb_sg_name,
                Description="CloudMart ALB SG - allows HTTP port 80",
                VpcId=vpc_id,
                TagSpecifications=[{"ResourceType": "security-group", "Tags": [{"Key": "Name", "Value": alb_sg_name}]}]
            )
            alb_sg_id = alb_sg["GroupId"]
            ec2.authorize_security_group_ingress(
                GroupId=alb_sg_id,
                IpPermissions=[{
                    "IpProtocol": "tcp",
                    "FromPort": 80,
                    "ToPort": 80,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTP from internet"}]
                }]
            )
            print(f"[SG] Created ALB SG: {alb_sg_id}")
    except ClientError as e:
        print(f"[SG] Error configuring {alb_sg_name}: {e}")
        raise

    # 2. EC2 Security Group
    ec2_sg_name = "cloudmart-ec2-sg"
    try:
        ec2_sgs = ec2.describe_security_groups(Filters=[
            {"Name": "group-name", "Values": [ec2_sg_name]},
            {"Name": "vpc-id", "Values": [vpc_id]}
        ])["SecurityGroups"]
        if ec2_sgs:
            ec2_sg_id = ec2_sgs[0]["GroupId"]
            print(f"[SG] Found existing EC2 SG: {ec2_sg_id}")
        else:
            ec2_sg = ec2.create_security_group(
                GroupName=ec2_sg_name,
                Description="CloudMart EC2 SG - allows port 8000 from ALB only",
                VpcId=vpc_id,
                TagSpecifications=[{"ResourceType": "security-group", "Tags": [{"Key": "Name", "Value": ec2_sg_name}]}]
            )
            ec2_sg_id = ec2_sg["GroupId"]
            ec2.authorize_security_group_ingress(
                GroupId=ec2_sg_id,
                IpPermissions=[{
                    "IpProtocol": "tcp",
                    "FromPort": 8000,
                    "ToPort": 8000,
                    "UserIdGroupPairs": [{"GroupId": alb_sg_id, "Description": "Traffic from ALB"}]
                }]
            )
            print(f"[SG] Created EC2 SG: {ec2_sg_id}")
    except ClientError as e:
        print(f"[SG] Error configuring {ec2_sg_name}: {e}")
        raise

    return alb_sg_id, ec2_sg_id


def setup_load_balancer(vpc_id, subnet_ids, alb_sg_id):
    """
    Creates cloudmart-tg target group and cloudmart-alb with HTTP:80 listener.
    """
    tg_name = "cloudmart-tg"
    alb_name = "cloudmart-alb"

    # 1. Target Group
    tgs = elbv2.describe_target_groups(Names=[tg_name])["TargetGroups"] if _tg_exists(tg_name) else []
    if tgs:
        tg_arn = tgs[0]["TargetGroupArn"]
        print(f"[ELB] Found existing Target Group: {tg_arn}")
    else:
        tg = elbv2.create_target_group(
            Name=tg_name,
            Protocol="HTTP",
            Port=8000,
            VpcId=vpc_id,
            HealthCheckProtocol="HTTP",
            HealthCheckPort="8000",
            HealthCheckPath="/health",
            HealthCheckIntervalSeconds=15,
            HealthCheckTimeoutSeconds=5,
            HealthyThresholdCount=2,
            UnhealthyThresholdCount=2,
            TargetType="instance",
            Matcher={"HttpCode": "200"}
        )
        tg_arn = tg["TargetGroups"][0]["TargetGroupArn"]
        print(f"[ELB] Created Target Group: {tg_arn}")

    # 2. ALB
    lbs = elbv2.describe_load_balancers(Names=[alb_name])["LoadBalancers"] if _lb_exists(alb_name) else []
    if lbs:
        lb_arn = lbs[0]["LoadBalancerArn"]
        alb_dns = lbs[0]["DNSName"]
        print(f"[ELB] Found existing ALB: {lb_arn} ({alb_dns})")
    else:
        lb = elbv2.create_load_balancer(
            Name=alb_name,
            Subnets=subnet_ids,
            SecurityGroups=[alb_sg_id],
            Scheme="internet-facing",
            Type="application",
            IpAddressType="ipv4"
        )
        lb_arn = lb["LoadBalancers"][0]["LoadBalancerArn"]
        alb_dns = lb["LoadBalancers"][0]["DNSName"]
        print(f"[ELB] Created ALB: {lb_arn} ({alb_dns})")

    # 3. HTTP:80 Listener
    listeners = elbv2.describe_listeners(LoadBalancerArn=lb_arn)["Listeners"]
    has_listener = any(l.get("Port") == 80 for l in listeners)
    if not has_listener:
        elbv2.create_listener(
            LoadBalancerArn=lb_arn,
            Protocol="HTTP",
            Port=80,
            DefaultActions=[{"Type": "forward", "TargetGroupArn": tg_arn}]
        )
        print("[ELB] Created HTTP:80 forward listener to target group")
    else:
        print("[ELB] HTTP:80 listener already present")

    return lb_arn, tg_arn, alb_dns


def _tg_exists(name):
    try:
        elbv2.describe_target_groups(Names=[name])
        return True
    except ClientError:
        return False


def _lb_exists(name):
    try:
        elbv2.describe_load_balancers(Names=[name])
        return True
    except ClientError:
        return False


def generate_user_data():
    """Reads shop/application.py from local disk and builds the EC2 startup script."""
    app_path = os.path.join(os.path.dirname(__file__), "shop", "application.py")
    if not os.path.exists(app_path):
        raise FileNotFoundError(f"Missing {app_path}")
    with open(app_path, "r") as f:
        app_code = f.read()

    # User data script installs dependencies, places the Flask app, and starts Gunicorn under systemd
    script = f"""#!/bin/bash
set -ex
dnf update -y
dnf install -y python3-pip
pip3 install flask==3.0.3 gunicorn==23.0.0

# Ensure /usr/local/bin/gunicorn symlink exists
if [ ! -f /usr/local/bin/gunicorn ]; then
    GUNICORN_BIN=$(which gunicorn)
    ln -s "$GUNICORN_BIN" /usr/local/bin/gunicorn
fi

mkdir -p /opt/cloudmart
cat <<'EOF' > /opt/cloudmart/application.py
{app_code}
EOF

cat <<'EOF' > /etc/systemd/system/cloudmart.service
[Unit]
Description=CloudMart Gunicorn Application Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/cloudmart
ExecStart=/usr/local/bin/gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 60 application:application
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now cloudmart
"""
    return base64.b64encode(script.encode("utf-8")).decode("utf-8")


def setup_launch_template(ami_id, ec2_sg_id):
    """Creates or updates the EC2 Launch Template cloudmart-lt."""
    lt_name = "cloudmart-lt"
    user_data = generate_user_data()

    lt_data = {
        "ImageId": ami_id,
        "InstanceType": "t3.micro",
        "SecurityGroupIds": [ec2_sg_id],
        "IamInstanceProfile": {"Name": "LabInstanceProfile"},
        "Monitoring": {"Enabled": True},  # Detailed monitoring ON
        "UserData": user_data
    }

    try:
        resp = ec2.describe_launch_templates(LaunchTemplateNames=[lt_name])
        lt_id = resp["LaunchTemplates"][0]["LaunchTemplateId"]
        print(f"[LT] Launch Template {lt_name} exists ({lt_id}). Creating new version...")
        ec2.create_launch_template_version(
            LaunchTemplateName=lt_name,
            LaunchTemplateData=lt_data
        )
    except ClientError as e:
        if "InvalidLaunchTemplateName.NotFoundException" in str(e):
            print(f"[LT] Creating new Launch Template {lt_name}...")
            resp = ec2.create_launch_template(
                LaunchTemplateName=lt_name,
                LaunchTemplateData=lt_data
            )
            lt_id = resp["LaunchTemplate"]["LaunchTemplateId"]
        else:
            raise

    print(f"[LT] Launch template configured: {lt_name}")
    return lt_name


def setup_asg_and_scaling(subnet_ids, tg_arn, lt_name):
    """
    Configures Auto Scaling Group cloudmart-asg and CloudWatch scaling policies & alarms.
    """
    asg_name = "cloudmart-asg"
    subnets_str = ",".join(subnet_ids)

    # 1. ASG Creation / Update
    asgs = asg.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])["AutoScalingGroups"]
    if asgs:
        print(f"[ASG] Found existing ASG {asg_name}, updating config...")
        asg.update_auto_scaling_group(
            AutoScalingGroupName=asg_name,
            LaunchTemplate={"LaunchTemplateName": lt_name, "Version": "$Latest"},
            MinSize=1,
            MaxSize=4,
            DesiredCapacity=1,
            HealthCheckType="ELB",
            HealthCheckGracePeriod=180,
            VPCZoneIdentifier=subnets_str
        )
    else:
        print(f"[ASG] Creating ASG {asg_name}...")
        asg.create_auto_scaling_group(
            AutoScalingGroupName=asg_name,
            LaunchTemplate={"LaunchTemplateName": lt_name, "Version": "$Latest"},
            MinSize=1,
            MaxSize=4,
            DesiredCapacity=1,
            TargetGroupARNs=[tg_arn],
            HealthCheckType="ELB",
            HealthCheckGracePeriod=180,
            VPCZoneIdentifier=subnets_str,
            Tags=[{"Key": "Name", "Value": "cloudmart-instance", "PropagateAtLaunch": True}]
        )

    # 2. Scaling Policies (Simple scaling +1 and -1, cooldown 120s)
    scale_out_resp = asg.put_scaling_policy(
        AutoScalingGroupName=asg_name,
        PolicyName="cloudmart-scale-out",
        PolicyType="SimpleScaling",
        AdjustmentType="ChangeInCapacity",
        ScalingAdjustment=1,
        Cooldown=120
    )
    scale_out_arn = scale_out_resp["PolicyARN"]
    print(f"[Policy] Scale-out (+1) policy: {scale_out_arn}")

    scale_in_resp = asg.put_scaling_policy(
        AutoScalingGroupName=asg_name,
        PolicyName="cloudmart-scale-in",
        PolicyType="SimpleScaling",
        AdjustmentType="ChangeInCapacity",
        ScalingAdjustment=-1,
        Cooldown=120
    )
    scale_in_arn = scale_in_resp["PolicyARN"]
    print(f"[Policy] Scale-in (-1) policy: {scale_in_arn}")

    # 3. CloudWatch Alarms
    # High CPU (>50 for 2 periods of 60s) -> Scale Out
    cw.put_metric_alarm(
        AlarmName="cloudmart-cpu-high",
        MetricName="CPUUtilization",
        Namespace="AWS/EC2",
        Statistic="Average",
        Period=60,
        EvaluationPeriods=2,
        Threshold=50.0,
        ComparisonOperator="GreaterThanThreshold",
        Dimensions=[{"Name": "AutoScalingGroupName", "Value": asg_name}],
        AlarmActions=[scale_out_arn],
        AlarmDescription="Triggers scale out when CPU > 50% for 2 consecutive minutes"
    )
    print("[Alarm] Created/updated cloudmart-cpu-high")

    # Low CPU (<20 for 3 periods of 60s) -> Scale In
    cw.put_metric_alarm(
        AlarmName="cloudmart-cpu-low",
        MetricName="CPUUtilization",
        Namespace="AWS/EC2",
        Statistic="Average",
        Period=60,
        EvaluationPeriods=3,
        Threshold=20.0,
        ComparisonOperator="LessThanThreshold",
        Dimensions=[{"Name": "AutoScalingGroupName", "Value": asg_name}],
        AlarmActions=[scale_in_arn],
        AlarmDescription="Triggers scale in when CPU < 20% for 3 consecutive minutes"
    )
    print("[Alarm] Created/updated cloudmart-cpu-low")

    return asg_name


def wait_for_healthy_target(tg_arn, timeout_sec=360):
    """Polls the Target Group until at least one target is reported healthy."""
    print(f"[Wait] Waiting up to {timeout_sec}s for at least one healthy instance in target group...")
    start = time.time()
    while time.time() - start < timeout_sec:
        health_resp = elbv2.describe_target_health(TargetGroupArn=tg_arn)
        targets = health_resp.get("TargetHealthDescriptions", [])
        for t in targets:
            state = t.get("TargetHealth", {}).get("State")
            tid = t.get("Target", {}).get("Id")
            print(f"[Target Check] Instance {tid}: {state}")
            if state == "healthy":
                print(f"[Wait] Target {tid} is healthy!")
                return True
        time.sleep(15)
    raise TimeoutError(f"No healthy target registered within {timeout_sec} seconds")


def verify_endpoints(alb_dns):
    """Curls http://<alb_dns>/ and http://<alb_dns>/checkout to confirm service."""
    base_url = f"http://{alb_dns}"
    print(f"\n[Verify] Testing endpoints on ALB {base_url}...")
    for endpoint in ["/", "/checkout"]:
        url = base_url + endpoint
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CloudMart-Verifier"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                print(f"[Verify] GET {endpoint} -> HTTP {status}")
                print(f"[Verify] Body preview: {body[:120].strip()}")
        except Exception as e:
            print(f"[Verify] Request failed for {url}: {e}")
            raise


def create():
    """Main entrypoint for infra.py create."""
    print("=== STARTING CLOUDMART INFRASTRUCTURE CREATION ===")
    vpc_id, subnet_ids = get_default_vpc_and_subnets()
    ami_id = get_latest_al2023_ami()
    alb_sg_id, ec2_sg_id = setup_security_groups(vpc_id)
    lb_arn, tg_arn, alb_dns = setup_load_balancer(vpc_id, subnet_ids, alb_sg_id)
    lt_name = setup_launch_template(ami_id, ec2_sg_id)
    asg_name = setup_asg_and_scaling(subnet_ids, tg_arn, lt_name)

    # Write output JSON
    output_data = {
        "asg_name": asg_name,
        "lb_arn": lb_arn,
        "tg_arn": tg_arn,
        "alb_dns": alb_dns
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"[Output] Wrote {OUTPUT_FILE}: {output_data}")

    # Wait for target health and verify HTTP endpoints
    wait_for_healthy_target(tg_arn)
    verify_endpoints(alb_dns)
    print("=== CLOUDMART INFRASTRUCTURE SUCCESSFULLY CREATED ===")


def destroy():
    """Main entrypoint for infra.py destroy with safe order, waits and retries."""
    print("=== STARTING CLOUDMART INFRASTRUCTURE TEARDOWN ===")
    asg_name = "cloudmart-asg"
    alb_name = "cloudmart-alb"
    tg_name = "cloudmart-tg"
    lt_name = "cloudmart-lt"
    ec2_sg_name = "cloudmart-ec2-sg"
    alb_sg_name = "cloudmart-alb-sg"

    # 1. Delete CloudWatch Alarms
    print("[Destroy] Deleting CloudWatch alarms...")
    try:
        cw.delete_alarms(AlarmNames=["cloudmart-cpu-high", "cloudmart-cpu-low"])
        print("[Destroy] Alarms deleted")
    except Exception as e:
        print(f"[Destroy] Alarms delete notice: {e}")

    # 2. Delete Scaling Policies
    print("[Destroy] Deleting scaling policies...")
    for p in ["cloudmart-scale-out", "cloudmart-scale-in"]:
        try:
            asg.delete_policy(AutoScalingGroupName=asg_name, PolicyName=p)
            print(f"[Destroy] Policy {p} deleted")
        except Exception as e:
            print(f"[Destroy] Policy {p} notice: {e}")

    # 3. Delete ASG (ForceDelete=True) & wait for termination
    print(f"[Destroy] Force deleting ASG {asg_name}...")
    try:
        asg.delete_auto_scaling_group(AutoScalingGroupName=asg_name, ForceDelete=True)
        print("[Destroy] Waiting for ASG to terminate completely...")
        while True:
            res = asg.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])["AutoScalingGroups"]
            if not res:
                print("[Destroy] ASG deleted")
                break
            time.sleep(10)
    except Exception as e:
        print(f"[Destroy] ASG notice: {e}")

    # 4. Delete ALB Listener & ALB
    print(f"[Destroy] Deleting ALB {alb_name}...")
    try:
        lbs = elbv2.describe_load_balancers(Names=[alb_name])["LoadBalancers"]
        for lb in lbs:
            lb_arn = lb["LoadBalancerArn"]
            listeners = elbv2.describe_listeners(LoadBalancerArn=lb_arn)["Listeners"]
            for l in listeners:
                elbv2.delete_listener(ListenerArn=l["ListenerArn"])
            elbv2.delete_load_balancer(LoadBalancerArn=lb_arn)
            print("[Destroy] Waiting for ALB deletion...")
            while True:
                try:
                    elbv2.describe_load_balancers(Names=[alb_name])
                    time.sleep(10)
                except ClientError:
                    print("[Destroy] ALB successfully deleted")
                    break
    except ClientError as e:
        print(f"[Destroy] ALB notice: {e}")

    # 5. Delete Target Group
    print(f"[Destroy] Deleting Target Group {tg_name}...")
    try:
        tgs = elbv2.describe_target_groups(Names=[tg_name])["TargetGroups"]
        for tg in tgs:
            elbv2.delete_target_group(TargetGroupArn=tg["TargetGroupArn"])
            print("[Destroy] Target Group deleted")
    except ClientError as e:
        print(f"[Destroy] Target Group notice: {e}")

    # 6. Delete Launch Template
    print(f"[Destroy] Deleting Launch Template {lt_name}...")
    try:
        ec2.delete_launch_template(LaunchTemplateName=lt_name)
        print("[Destroy] Launch template deleted")
    except ClientError as e:
        print(f"[Destroy] Launch template notice: {e}")

    # 7. Delete Security Groups with retries for network interface detachment
    print("[Destroy] Deleting Security Groups (waiting for ENIs to release)...")
    for sg_name in [ec2_sg_name, alb_sg_name]:
        for attempt in range(12):
            try:
                sgs = ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": [sg_name]}])["SecurityGroups"]
                if not sgs:
                    break
                ec2.delete_security_group(GroupId=sgs[0]["GroupId"])
                print(f"[Destroy] Security Group {sg_name} deleted")
                break
            except ClientError as e:
                if "DependencyViolation" in str(e):
                    print(f"[Destroy] Dependency violation for {sg_name}, waiting 10s (attempt {attempt+1}/12)...")
                    time.sleep(10)
                else:
                    print(f"[Destroy] SG notice for {sg_name}: {e}")
                    break

    # 8. Remove local output file
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
        print(f"[Destroy] Removed {OUTPUT_FILE}")

    print("=== CLOUDMART INFRASTRUCTURE TEARDOWN COMPLETE ===")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ["create", "destroy"]:
        print("Usage: python infra.py [create|destroy]")
        sys.exit(1)

    action = sys.argv[1]
    if action == "create":
        create()
    elif action == "destroy":
        destroy()
