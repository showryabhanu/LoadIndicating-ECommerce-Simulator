#!/usr/bin/env python3
"""
CloudMart Serverless Backend & Web Deployment Automation (deploy.py)
Manages the deployment and teardown of:
- Public S3 Website Bucket for the CloudMart Dashboard
- Lambda Functions: cloudmart-api and cloudmart-loadgen (Python 3.12, LabRole)
- API Gateway HTTP API (cloudmart-api) with CORS and Lambda Proxy Integration
- Automatic injection of window.API_URL into web/config.js and S3 sync
"""

import sys
import os
import io
import json
import time
import zipfile
import mimetypes
import boto3
from botocore.exceptions import ClientError

CONFIG_FILE = "config.json"
INFRA_FILE = "infra-output.json"


def load_configurations():
    """Loads configuration and infrastructure output files."""
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"Missing {CONFIG_FILE}. Run Phase 0 first.")
    if not os.path.exists(INFRA_FILE):
        raise FileNotFoundError(f"Missing {INFRA_FILE}. Run Phase 1 first.")

    with open(CONFIG_FILE, "r") as f:
        cfg = json.load(f)
    with open(INFRA_FILE, "r") as f:
        infra = json.load(f)

    region = cfg.get("region", "us-east-1")
    lab_role_arn = cfg["lab_role_arn"]
    bucket_name = cfg["bucket_name"]

    asg_name = infra["asg_name"]
    lb_arn = infra["lb_arn"]
    tg_arn = infra["tg_arn"]
    alb_dns = infra["alb_dns"]
    target_url = "http://" + alb_dns

    return region, lab_role_arn, bucket_name, asg_name, lb_arn, tg_arn, target_url


def create_zip_bytes(filename_in_zip, local_path):
    """Packages a single Python source file into an in-memory zip archive."""
    with open(local_path, "r") as f:
        content = f.read()
    mem_file = io.BytesIO()
    with zipfile.ZipFile(mem_file, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(filename_in_zip, content)
    mem_file.seek(0)
    return mem_file.read()


def wait_for_lambda(lambda_client, function_name, timeout=120):
    """Waits until Lambda reaches Active state and any update completes."""
    start = time.time()
    while time.time() - start < timeout:
        resp = lambda_client.get_function(FunctionName=function_name)
        state = resp["Configuration"].get("State")
        update_status = resp["Configuration"].get("LastUpdateStatus")
        if state == "Active" and update_status != "InProgress":
            return resp
        time.sleep(2)
    return lambda_client.get_function(FunctionName=function_name)


def setup_s3_bucket(s3_client, bucket_name, region):
    """Creates S3 bucket, disables Block Public Access, adds public-read policy, and enables website."""
    print(f"[S3] Configuring static website bucket: {bucket_name}...")
    try:
        if region == "us-east-1":
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region}
            )
        print(f"[S3] Created bucket {bucket_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] in ["BucketAlreadyOwnedByYou", "BucketAlreadyExists"]:
            print(f"[S3] Bucket {bucket_name} already exists, proceeding...")
        else:
            raise

    # Disable Block Public Access
    print("[S3] Disabling Block Public Access...")
    s3_client.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": False,
            "IgnorePublicAcls": False,
            "BlockPublicPolicy": False,
            "RestrictPublicBuckets": False
        }
    )

    # Attach public-read GetObject policy
    print("[S3] Attaching public read policy...")
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket_name}/*"
            }
        ]
    }
    s3_client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))

    # Enable static website hosting
    print("[S3] Enabling static website hosting (index.html)...")
    s3_client.put_bucket_website(
        Bucket=bucket_name,
        WebsiteConfiguration={"IndexDocument": {"Suffix": "index.html"}}
    )
    website_url = f"http://{bucket_name}.s3-website-{region}.amazonaws.com"
    print(f"[S3] Website URL: {website_url}")
    return website_url


def deploy_lambda_function(lambda_client, function_name, role_arn, handler, zip_bytes, memory_size, timeout, env_vars):
    """Creates or updates a Lambda function with specified parameters."""
    print(f"[Lambda] Deploying {function_name} ({memory_size} MB, {timeout}s)...")
    try:
        lambda_client.get_function(FunctionName=function_name)
        # Update function code
        lambda_client.update_function_code(FunctionName=function_name, ZipFile=zip_bytes)
        wait_for_lambda(lambda_client, function_name)
        # Update function configuration
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Role=role_arn,
            Handler=handler,
            Timeout=timeout,
            MemorySize=memory_size,
            Environment={"Variables": env_vars}
        )
        wait_for_lambda(lambda_client, function_name)
        print(f"[Lambda] Updated existing {function_name}")
    except ClientError as e:
        if "ResourceNotFoundException" in str(e):
            lambda_client.create_function(
                FunctionName=function_name,
                Runtime="python3.12",
                Role=role_arn,
                Handler=handler,
                Code={"ZipFile": zip_bytes},
                Timeout=timeout,
                MemorySize=memory_size,
                Environment={"Variables": env_vars}
            )
            wait_for_lambda(lambda_client, function_name)
            print(f"[Lambda] Created new {function_name}")
        else:
            raise

    resp = lambda_client.get_function(FunctionName=function_name)
    fn_arn = resp["Configuration"]["FunctionArn"]
    return fn_arn


def setup_http_api(apigw_client, lambda_client, api_lambda_arn, region, account_id):
    """Creates or updates API Gateway HTTP API (cloudmart-api) with CORS, integration, and routes."""
    api_name = "cloudmart-api"
    print(f"[APIGW] Configuring HTTP API: {api_name}...")

    # Find or create API
    apis = apigw_client.get_apis()["Items"]
    matching = [a for a in apis if a.get("Name") == api_name and a.get("ProtocolType") == "HTTP"]
    if matching:
        api_id = matching[0]["ApiId"]
        api_endpoint = matching[0]["ApiEndpoint"]
        print(f"[APIGW] Found existing API: {api_id} ({api_endpoint})")
    else:
        resp = apigw_client.create_api(
            Name=api_name,
            ProtocolType="HTTP",
            CorsConfiguration={
                "AllowOrigins": ["*"],
                "AllowMethods": ["GET", "POST", "OPTIONS"],
                "AllowHeaders": ["content-type"],
                "MaxAge": 300
            }
        )
        api_id = resp["ApiId"]
        api_endpoint = resp["ApiEndpoint"]
        print(f"[APIGW] Created API: {api_id} ({api_endpoint})")

    # Setup Lambda Proxy Integration
    integrations = apigw_client.get_integrations(ApiId=api_id)["Items"]
    if integrations:
        integration_id = integrations[0]["IntegrationId"]
        print(f"[APIGW] Reusing integration {integration_id}")
    else:
        resp = apigw_client.create_integration(
            ApiId=api_id,
            IntegrationType="AWS_PROXY",
            IntegrationMethod="POST",
            IntegrationUri=api_lambda_arn,
            PayloadFormatVersion="2.0"
        )
        integration_id = resp["IntegrationId"]
        print(f"[APIGW] Created integration {integration_id}")

    # Setup Routes
    target_integration = f"integrations/{integration_id}"
    desired_routes = [
        "GET /metrics",
        "POST /load/start",
        "POST /load/stop",
        "OPTIONS /{proxy+}"
    ]
    existing_routes = {r["RouteKey"]: r["RouteId"] for r in apigw_client.get_routes(ApiId=api_id)["Items"]}
    for r_key in desired_routes:
        if r_key not in existing_routes:
            apigw_client.create_route(
                ApiId=api_id,
                RouteKey=r_key,
                Target=target_integration
            )
            print(f"[APIGW] Created route: {r_key}")
        else:
            print(f"[APIGW] Route already exists: {r_key}")

    # Setup $default stage with AutoDeploy
    stages = apigw_client.get_stages(ApiId=api_id)["Items"]
    has_default = any(s.get("StageName") == "$default" for s in stages)
    if not has_default:
        apigw_client.create_stage(
            ApiId=api_id,
            StageName="$default",
            AutoDeploy=True
        )
        print("[APIGW] Created auto-deploy $default stage")
    else:
        print("[APIGW] $default stage already present")

    # Authorize API Gateway to invoke cloudmart-api Lambda
    try:
        source_arn = f"arn:aws:execute-api:{region}:{account_id}:{api_id}/*/*"
        lambda_client.add_permission(
            FunctionName="cloudmart-api",
            StatementId="apigateway-invoke-permission",
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=source_arn
        )
        print("[APIGW] Added Lambda invoke permission for API Gateway")
    except ClientError as e:
        if "ResourceConflictException" in str(e):
            print("[APIGW] Lambda invoke permission already configured")
        else:
            raise

    return api_endpoint, api_id


def sync_web_assets(s3_client, bucket_name, api_endpoint):
    """Writes window.API_URL to web/config.js and syncs web/ directory to S3."""
    web_dir = os.path.join(os.path.dirname(__file__), "web")
    os.makedirs(web_dir, exist_ok=True)

    # 1. Write web/config.js
    config_js_path = os.path.join(web_dir, "config.js")
    with open(config_js_path, "w") as f:
        f.write(f'window.API_URL = "{api_endpoint}";\n')
    print(f"[Web] Updated {config_js_path} with API_URL: {api_endpoint}")

    # 2. Upload all files from web/
    print(f"[Web] Syncing files from {web_dir} to s3://{bucket_name}/...")
    for root, _, files in os.walk(web_dir):
        for fname in files:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, web_dir)

            content_type, _ = mimetypes.guess_type(full_path)
            if fname.endswith(".js"):
                content_type = "application/javascript"
            elif fname.endswith(".html"):
                content_type = "text/html"
            elif fname.endswith(".css"):
                content_type = "text/css"
            elif fname.endswith(".json"):
                content_type = "application/json"
            elif not content_type:
                content_type = "binary/octet-stream"

            with open(full_path, "rb") as f_data:
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=rel_path,
                    Body=f_data,
                    ContentType=content_type,
                    CacheControl="no-cache, no-store, must-revalidate"
                )
            print(f"[Web] Uploaded {rel_path} ({content_type})")


def deploy():
    """Main deployment routine for deploy.py."""
    print("=== STARTING CLOUDMART SERVERLESS & WEB DEPLOYMENT ===")
    region, lab_role_arn, bucket_name, asg_name, lb_arn, tg_arn, target_url = load_configurations()

    s3_client = boto3.client("s3", region_name=region)
    lambda_client = boto3.client("lambda", region_name=region)
    apigw_client = boto3.client("apigatewayv2", region_name=region)
    sts_client = boto3.client("sts", region_name=region)

    account_id = sts_client.get_caller_identity()["Account"]

    # 1. Setup S3 website bucket
    website_url = setup_s3_bucket(s3_client, bucket_name, region)

    # 2. Package and deploy cloudmart-loadgen Lambda
    loadgen_code = create_zip_bytes("loadgen_handler.py", os.path.join("backend", "loadgen_handler.py"))
    deploy_lambda_function(
        lambda_client=lambda_client,
        function_name="cloudmart-loadgen",
        role_arn=lab_role_arn,
        handler="loadgen_handler.lambda_handler",
        zip_bytes=loadgen_code,
        memory_size=512,
        timeout=900,
        env_vars={"BUCKET": bucket_name}
    )

    # 3. Package and deploy cloudmart-api Lambda
    api_code = create_zip_bytes("api_handler.py", os.path.join("backend", "api_handler.py"))
    api_arn = deploy_lambda_function(
        lambda_client=lambda_client,
        function_name="cloudmart-api",
        role_arn=lab_role_arn,
        handler="api_handler.lambda_handler",
        zip_bytes=api_code,
        memory_size=256,
        timeout=30,
        env_vars={
            "ASG_NAME": asg_name,
            "LB_ARN": lb_arn,
            "TG_ARN": tg_arn,
            "BUCKET": bucket_name,
            "LOADGEN_FN": "cloudmart-loadgen",
            "TARGET_URL": target_url
        }
    )

    # 4. Setup API Gateway HTTP API
    api_endpoint, _ = setup_http_api(apigw_client, lambda_client, api_arn, region, account_id)

    # 5. Sync Web assets
    sync_web_assets(s3_client, bucket_name, api_endpoint)

    print("\n=======================================================")
    print(f"CloudMart API URL:       {api_endpoint}")
    print(f"CloudMart Dashboard URL: {website_url}")
    print("=======================================================\n")
    print("=== DEPLOYMENT COMPLETED SUCCESSFULLY ===")


def destroy():
    """Tears down API Gateway, Lambdas, and S3 Bucket."""
    print("=== STARTING CLOUDMART SERVERLESS & WEB TEARDOWN ===")
    region, _, bucket_name, _, _, _, _ = load_configurations()

    s3_client = boto3.client("s3", region_name=region)
    lambda_client = boto3.client("lambda", region_name=region)
    apigw_client = boto3.client("apigatewayv2", region_name=region)

    # 1. Delete HTTP API
    print("[Destroy] Deleting HTTP API cloudmart-api...")
    try:
        apis = apigw_client.get_apis()["Items"]
        for a in apis:
            if a.get("Name") == "cloudmart-api":
                apigw_client.delete_api(ApiId=a["ApiId"])
                print(f"[Destroy] Deleted API {a['ApiId']}")
    except Exception as e:
        print(f"[Destroy] API Gateway notice: {e}")

    # 2. Delete Lambdas
    print("[Destroy] Deleting Lambda functions...")
    for fn in ["cloudmart-api", "cloudmart-loadgen"]:
        try:
            lambda_client.delete_function(FunctionName=fn)
            print(f"[Destroy] Deleted function {fn}")
        except Exception as e:
            print(f"[Destroy] Lambda {fn} notice: {e}")

    # 3. Empty and delete S3 bucket
    print(f"[Destroy] Emptying and removing S3 bucket {bucket_name}...")
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket_name):
            objects = page.get("Contents", [])
            delete_keys = [{"Key": obj["Key"]} for obj in objects]
            if delete_keys:
                s3_client.delete_objects(Bucket=bucket_name, Delete={"Objects": delete_keys})
        s3_client.delete_bucket(Bucket=bucket_name)
        print(f"[Destroy] Bucket {bucket_name} deleted")
    except Exception as e:
        print(f"[Destroy] S3 notice: {e}")

    print("=== CLOUDMART SERVERLESS & WEB TEARDOWN COMPLETE ===")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ["deploy", "destroy"]:
        print("Usage: python deploy.py [deploy|destroy]")
        sys.exit(1)

    action = sys.argv[1]
    if action == "deploy":
        deploy()
    elif action == "destroy":
        destroy()
