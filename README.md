# CloudMart Auto-Scaling Dashboard

An end-to-end cloud computing project demonstrating automated infrastructure scaling and real-time observability on AWS. The system deploys an e-commerce shop backend on Amazon EC2 instances inside an Auto Scaling Group behind an Application Load Balancer, accompanied by a serverless analytics engine and a live dark-mode web dashboard.

---

## Architecture Overview

```
                                [ User Web Browser ]
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   │                                           │
         (HTTP Static Assets)                         (JSON REST / CORS)
                   ▼                                           ▼
      [ Amazon S3 Bucket ]                         [ API Gateway HTTP API ]
   Static Website Hosting (web/)                     ($default Stage, CORS)
                                                               │
                                                               ▼
                                                    [ cloudmart-api Lambda ]
                                                    (Python 3.12, 256 MB)
                                                               │
                       ┌───────────────────────────────┬───────┴───────────────────────────────┐
                       │                               │                                       │
                       ▼                               ▼                                       ▼
            [ Amazon CloudWatch ]            [ EC2 Auto Scaling ]                    [ cloudmart-loadgen ]
            - CPUUtilization                 - Desired: 1, Min: 1, Max: 4            (Asynchronous Worker)
            - RequestCount                   - Scaling Policies: +1 / -1                       │
            - TargetResponseTime             - Activities & Instance States                    │ (HTTP /checkout Loop)
            - HealthyHostCount                                                                 ▼
                                                                                   [ Application Load Balancer ]
                                                                                   (cloudmart-alb : Port 80)
                                                                                               │
                                                                                   [ Target Group (Port 8000) ]
                                                                                               │
                                                                                   ┌───────────┴───────────┐
                                                                                   ▼                       ▼
                                                                           [ EC2 Instance 1 ]      [ EC2 Instance 2 ]
                                                                           (AL2023 / Gunicorn)     (Scale-out dynamic)
```

---

## AWS Services Used & Why

1. **Amazon EC2 (Elastic Compute Cloud)**:
   - Hosts the Python Flask e-commerce shop on Amazon Linux 2023 (`t3.micro`).
   - Managed automatically with a systemd Gunicorn service and instance metadata.
2. **EC2 Auto Scaling Group (ASG)**:
   - Maintains high availability and fault tolerance. Dynamically scales instance capacity between 1 (baseline) and 4 (peak load) in response to real-time CPU demands.
3. **Application Load Balancer (ALB / ELBv2)**:
   - Public-facing reverse proxy operating at Layer 7. Distributes incoming customer traffic across target EC2 instances across multiple Availability Zones, performing automated health checks at `/health`.
4. **Amazon CloudWatch**:
   - Collects detailed monitoring metrics (1-minute intervals) for cluster CPU utilization, load balancer request counts, and target health. Triggers auto-scaling alarms.
5. **AWS Lambda**:
   - **`cloudmart-api`**: Serverless REST API handler aggregating CloudWatch metric series, ASG statuses, and test states for the dashboard.
   - **`cloudmart-loadgen`**: Serverless synthetic load generator executing multithreaded requests against the shop `/checkout` endpoint to simulate traffic spikes.
6. **Amazon API Gateway (HTTP API v2)**:
   - Low-latency, cost-effective serverless API frontend providing CORS-enabled REST routing to the backend Lambda function.
7. **Amazon S3 (Simple Storage Service)**:
   - Hosts the responsive single-page dashboard (`web/index.html` and `web/config.js`) via S3 Static Website Hosting. Also stores persistent load generator run state.
8. **AWS Systems Manager (SSM) Parameter Store**:
   - Used for read-only lookups to dynamically retrieve the latest official Amazon Linux 2023 AMI without hardcoding AMI IDs.

---

## Dynamic Auto-Scaling Mechanics

- **Baseline Capacity**: 1 instance (Min: 1, Max: 4, Desired: 1).
- **Health Checks**: Type `ELB` with an interval of 15 seconds and 180 seconds grace period.
- **Scale-Out Alarm (`cloudmart-cpu-high`)**:
  - Triggers when average `CPUUtilization` exceeds **50%** for 2 consecutive 60-second periods.
  - Action: Adds 1 instance (`+1`) with a 120-second cooldown.
- **Scale-In Alarm (`cloudmart-cpu-low`)**:
  - Triggers when average `CPUUtilization` drops below **20%** for 3 consecutive 60-second periods.
  - Action: Removes 1 instance (`-1`) with a 120-second cooldown.

---

## Project Structure

```
cloudmart-dashboard/
├── shop/
│   ├── application.py       # Flask e-commerce application (/api/products, /checkout, /health)
│   ├── requirements.txt     # Python dependencies (Flask==3.0.3, gunicorn==23.0.0)
│   └── Procfile             # Web server entrypoint
├── backend/
│   ├── api_handler.py       # cloudmart-api Lambda function
│   └── loadgen_handler.py   # cloudmart-loadgen Lambda function
├── web/
│   ├── index.html           # Dark-mode responsive dashboard (Chart.js, Gauge, Controls)
│   └── config.js            # Injected API Gateway endpoint URL
├── infra.py                 # Boto3 infrastructure creation & destruction script
├── deploy.py                # Boto3 serverless backend & web asset deployment script
├── config.json              # Local deployment configuration (region, LabRole, bucket)
├── infra-output.json        # Dynamic output data (ALB DNS, ASG Name, Target Group ARN)
└── README.md                # Project documentation and viva guide
```

---

## How to Run & Deploy

### Prerequisites
- AWS Academy Learner Lab credentials configured in `~/.aws/credentials`.
- Python 3.9+ with `boto3` installed in the virtual environment.

### 1. Setup Phase
```bash
# Verify credentials and generate config.json
aws sts get-caller-identity
aws iam get-role --role-name LabRole --query Role.Arn --output text
```

### 2. Infrastructure Creation
```bash
# Deploys VPC Security Groups, ALB, Target Group, Launch Template, and ASG
.venv/bin/python3 infra.py create
```
*Creates `infra-output.json` with the deployed ALB DNS and resource ARNs.*

### 3. Serverless & Web Dashboard Deployment
```bash
# Deploys S3 Website, Lambdas, HTTP API Gateway, and syncs web/
.venv/bin/python3 deploy.py deploy
```

---

## How to Destroy All Resources

To avoid incurring charges on AWS Academy Learner Lab, clean up resources in reverse order:

```bash
# 1. Tear down API Gateway, Lambdas, and S3 Bucket
.venv/bin/python3 deploy.py destroy

# 2. Tear down Alarms, Policies, Auto Scaling Group, ALB, Target Group, Launch Template, and SGs
.venv/bin/python3 infra.py destroy
```

---

## Live Dashboard Walkthrough & Viva Guide

### Active Endpoints
- **Web Dashboard**: [http://cloudmart-dash-183833977366.s3-website-us-east-1.amazonaws.com](http://cloudmart-dash-183833977366.s3-website-us-east-1.amazonaws.com)
- **API Gateway Endpoint**: `https://xdcqnoje72.execute-api.us-east-1.amazonaws.com`
- **Shop ALB Base URL**: `http://cloudmart-alb-1239664865.us-east-1.elb.amazonaws.com`

### How to Test Live in the Viva
1. Open the **Web Dashboard** URL in any modern browser.
2. Observe the initial state:
   - **Current CPU Load**: ~0.2% (Low Load / Green).
   - **InService Instances**: 1 / 4.
   - **Instance Tile**: 1 green `InService` tile with its instance ID and AZ.
3. In the **Synthetic Load Generator Control** panel:
   - Select duration: **4 Minutes** (or 6 Minutes).
   - Set threads slider: **30 - 40 threads**.
   - Click **Generate Load**.
4. Observe the automatic scale-out progression:
   - The countdown bar will display active load testing.
   - Within 1-2 minutes, the needle on the CPU Gauge will sweep into **High Load (>50%)**.
   - CloudWatch alarm `cloudmart-cpu-high` triggers the scale-out policy.
   - A new instance tile appears in pulsing amber (`Pending`).
   - When the instance boots, passes health checks, and registers with the ALB, it turns green (`InService`), and the total instances KPI increments to `2 / 4`.
   - The **Scaling Activities Timeline** logs the launch event with timestamps and causes.
5. When the load test finishes (or if you click **Stop**):
   - CPU drops back below 20%.
   - CloudWatch alarm `cloudmart-cpu-low` triggers the scale-in policy after 3 consecutive evaluation periods.
   - The extra instance transitions to red (`Terminating`) and is safely terminated, returning the cluster to 1 instance.
