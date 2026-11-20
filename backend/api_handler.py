"""
CloudMart API Handler (cloudmart-api Lambda)
Handles API Gateway HTTP API (payload v2) requests:
- GET /metrics: Returns CloudWatch metrics, Auto Scaling status, instances, scaling timeline, and active load test state.
- POST /load/start: Initiates a synthetic load test via cloudmart-loadgen Lambda and records state in S3.
- POST /load/stop: Cancels running load test by clearing state in S3.
- OPTIONS: Handles CORS preflight.
"""

import os
import json
import time
import uuid
import datetime
import base64
import boto3
from botocore.exceptions import ClientError

# Read configuration from Lambda environment variables
ASG_NAME = os.environ.get("ASG_NAME", "cloudmart-asg")
LB_ARN = os.environ.get("LB_ARN", "")
TG_ARN = os.environ.get("TG_ARN", "")
BUCKET = os.environ.get("BUCKET", "")
LOADGEN_FN = os.environ.get("LOADGEN_FN", "cloudmart-loadgen")
TARGET_URL = os.environ.get("TARGET_URL", "")

cw = boto3.client("cloudwatch", region_name="us-east-1")
asg_client = boto3.client("autoscaling", region_name="us-east-1")
s3 = boto3.client("s3", region_name="us-east-1")
lambda_client = boto3.client("lambda", region_name="us-east-1")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def build_response(status_code, body_dict):
    """Helper to return API Gateway payload v2 JSON responses with CORS."""
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body_dict),
    }


def get_current_load_state():
    """Reads current load generator state from S3 state/load.json."""
    if not BUCKET:
        return {"running": False, "started": 0, "duration": 0, "threads": 0}
    try:
        resp = s3.get_object(Bucket=BUCKET, Key="state/load.json")
        data = json.loads(resp["Body"].read().decode("utf-8"))
        run_id = data.get("run_id")
        started = data.get("started", 0)
        duration = data.get("duration", 0)
        threads = data.get("threads", 0)
        now = int(time.time())
        is_running = bool(run_id) and (now < (started + duration))
        return {
            "running": is_running,
            "started": started,
            "duration": duration,
            "threads": threads,
            "run_id": run_id if is_running else None
        }
    except ClientError as e:
        if e.response["Error"]["Code"] in ["NoSuchKey", "404"]:
            return {"running": False, "started": 0, "duration": 0, "threads": 0}
        raise


def get_asg_details():
    """Fetches ASG bounds, member instances, and the 10 most recent scaling activities."""
    resp = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[ASG_NAME])
    groups = resp.get("AutoScalingGroups", [])
    if not groups:
        return {
            "min": 0, "max": 0, "desired": 0,
            "instances": [], "activities": []
        }

    group = groups[0]
    min_size = group.get("MinSize", 0)
    max_size = group.get("MaxSize", 0)
    desired = group.get("DesiredCapacity", 0)

    instances = []
    for inst in group.get("Instances", []):
        instances.append({
            "id": inst.get("InstanceId"),
            "state": inst.get("LifecycleState"),
            "health": inst.get("HealthStatus"),
            "az": inst.get("AvailabilityZone"),
        })

    # Fetch 10 most recent scaling activities
    act_resp = asg_client.describe_scaling_activities(
        AutoScalingGroupName=ASG_NAME,
        MaxRecords=10
    )
    activities = []
    for act in act_resp.get("Activities", []):
        start_time = act.get("StartTime")
        activities.append({
            "time": start_time.isoformat() if start_time else "",
            "status": act.get("StatusCode"),
            "what": act.get("Description"),
            "cause": act.get("Cause"),
        })

    return {
        "min": min_size,
        "max": max_size,
        "desired": desired,
        "instances": instances,
        "activities": activities,
    }


def get_cloudwatch_series():
    """
    Retrieves the last 30 minutes of metric data at 60s periods:
    - cpu: AWS/EC2 CPUUtilization (Average)
    - req: AWS/ApplicationELB RequestCount (Sum)
    - rt: AWS/ApplicationELB TargetResponseTime (Average)
    - healthy: AWS/ApplicationELB HealthyHostCount (Average)
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - datetime.timedelta(minutes=30)

    lb_dim = LB_ARN.split("loadbalancer/")[1] if "loadbalancer/" in LB_ARN else ""
    tg_dim = TG_ARN.split(":")[-1] if TG_ARN else ""

    queries = [
        {
            "Id": "cpu",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/EC2",
                    "MetricName": "CPUUtilization",
                    "Dimensions": [{"Name": "AutoScalingGroupName", "Value": ASG_NAME}]
                },
                "Period": 60,
                "Stat": "Average"
            },
            "ReturnData": True
        }
    ]

    if lb_dim:
        queries.extend([
            {
                "Id": "req",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/ApplicationELB",
                        "MetricName": "RequestCount",
                        "Dimensions": [{"Name": "LoadBalancer", "Value": lb_dim}]
                    },
                    "Period": 60,
                    "Stat": "Sum"
                },
                "ReturnData": True
            },
            {
                "Id": "rt",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/ApplicationELB",
                        "MetricName": "TargetResponseTime",
                        "Dimensions": [{"Name": "LoadBalancer", "Value": lb_dim}]
                    },
                    "Period": 60,
                    "Stat": "Average"
                },
                "ReturnData": True
            }
        ])

    if lb_dim and tg_dim:
        queries.append({
            "Id": "healthy",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/ApplicationELB",
                    "MetricName": "HealthyHostCount",
                    "Dimensions": [
                        {"Name": "LoadBalancer", "Value": lb_dim},
                        {"Name": "TargetGroup", "Value": tg_dim}
                    ]
                },
                "Period": 60,
                "Stat": "Average"
            },
            "ReturnData": True
        })

    cw_resp = cw.get_metric_data(
        MetricDataQueries=queries,
        StartTime=start_time,
        EndTime=now,
        ScanBy="TimestampAscending"
    )

    series = {"cpu": [], "req": [], "rt": [], "healthy": []}
    for item in cw_resp.get("MetricDataResults", []):
        metric_id = item.get("Id")
        timestamps = item.get("Timestamps", [])
        values = item.get("Values", [])
        datapoints = []
        for ts, val in zip(timestamps, values):
            datapoints.append({
                "t": ts.isoformat(),
                "v": round(float(val), 2)
            })
        if metric_id in series:
            series[metric_id] = datapoints

    return series


def lambda_handler(event, context):
    """Main routing function for cloudmart-api."""
    try:
        # Resolve HTTP method and path from API Gateway v2 payload
        http_ctx = event.get("requestContext", {}).get("http", {})
        method = http_ctx.get("method") or event.get("httpMethod", "GET")
        raw_path = event.get("rawPath") or http_ctx.get("path") or event.get("path", "")

        # 1. CORS Preflight
        if method == "OPTIONS":
            return build_response(200, {"status": "ok"})

        # 2. GET /metrics
        if method == "GET" and (raw_path == "/metrics" or raw_path.endswith("/metrics")):
            series_data = get_cloudwatch_series()
            asg_data = get_asg_details()
            load_data = get_current_load_state()

            payload = {
                "env": "AWS Learner Lab (us-east-1)",
                "target": TARGET_URL,
                "series": series_data,
                "asg": asg_data,
                "load": load_data
            }
            return build_response(200, payload)

        # Parse request body for POST routes
        body = {}
        raw_body = event.get("body")
        if raw_body:
            if event.get("isBase64Encoded", False):
                raw_body = base64.b64decode(raw_body).decode("utf-8")
            try:
                body = json.loads(raw_body)
            except Exception:
                body = {}

        # 3. POST /load/start
        if method == "POST" and (raw_path == "/load/start" or raw_path.endswith("/load/start")):
            duration = int(body.get("duration", 240))
            duration = max(30, min(600, duration))  # Clamp between 30 and 600s
            threads = int(body.get("threads", 30))
            threads = max(1, min(60, threads))      # Clamp between 1 and 60 threads

            run_id = str(uuid.uuid4())
            started_epoch = int(time.time())

            # Write state to S3
            state_data = {
                "run_id": run_id,
                "started": started_epoch,
                "duration": duration,
                "threads": threads
            }
            s3.put_object(
                Bucket=BUCKET,
                Key="state/load.json",
                Body=json.dumps(state_data),
                ContentType="application/json"
            )

            # Trigger cloudmart-loadgen asynchronously
            loadgen_payload = {
                "run_id": run_id,
                "duration": duration,
                "threads": threads,
                "url": TARGET_URL
            }
            lambda_client.invoke(
                FunctionName=LOADGEN_FN,
                InvocationType="Event",
                Payload=json.dumps(loadgen_payload)
            )

            return build_response(200, {
                "status": "started",
                "run_id": run_id,
                "duration": duration,
                "threads": threads
            })

        # 4. POST /load/stop
        if method == "POST" and (raw_path == "/load/stop" or raw_path.endswith("/load/stop")):
            s3.put_object(
                Bucket=BUCKET,
                Key="state/load.json",
                Body=json.dumps({"run_id": None}),
                ContentType="application/json"
            )
            return build_response(200, {"status": "stopped"})

        return build_response(404, {"error": f"Route not found: {method} {raw_path}"})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return build_response(500, {"error": str(e)})
