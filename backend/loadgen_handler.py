"""
CloudMart Synthetic Load Generator (cloudmart-loadgen Lambda)
Runs multi-threaded HTTP traffic against the shop ALB /checkout endpoint:
- Starts specified number of worker threads to generate continuous CPU load.
- Runs a watcher thread that inspects S3 state/load.json every 5 seconds to support early termination.
- Returns total {ok, err} counts.
"""

import os
import json
import time
import threading
import urllib.request
import boto3
from botocore.exceptions import ClientError

BUCKET = os.environ.get("BUCKET", "")
s3 = boto3.client("s3", region_name="us-east-1")


def lambda_handler(event, context):
    """
    Invoked with: {run_id, duration, threads, url}
    """
    run_id = event.get("run_id")
    duration = int(event.get("duration", 240))
    threads_count = int(event.get("threads", 30))
    target_base = event.get("url", "").rstrip("/")
    checkout_url = f"{target_base}/checkout"

    print(f"[LoadGen] Starting test: run_id={run_id}, duration={duration}s, threads={threads_count}, target={checkout_url}")

    stop_event = threading.Event()
    start_time = time.time()
    end_time = start_time + duration

    ok_count = 0
    err_count = 0
    count_lock = threading.Lock()

    def worker_loop(thread_idx):
        nonlocal ok_count, err_count
        while not stop_event.is_set() and time.time() < end_time:
            try:
                req = urllib.request.Request(
                    checkout_url,
                    headers={"User-Agent": f"CloudMart-LoadWorker-{thread_idx}"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        with count_lock:
                            ok_count += 1
                    else:
                        with count_lock:
                            err_count += 1
            except Exception:
                with count_lock:
                    err_count += 1

    def watcher_loop():
        """Checks S3 state/load.json every 5 seconds; signals stop if run_id changed."""
        if not BUCKET or not run_id:
            return
        while not stop_event.is_set() and time.time() < end_time:
            time.sleep(5)
            try:
                resp = s3.get_object(Bucket=BUCKET, Key="state/load.json")
                state = json.loads(resp["Body"].read().decode("utf-8"))
                current_run_id = state.get("run_id")
                if current_run_id != run_id:
                    print(f"[LoadGen] Detected run_id mismatch or cancellation ({current_run_id} != {run_id}). Stopping workers.")
                    stop_event.set()
                    break
            except Exception as e:
                print(f"[LoadGen] Watcher error (non-fatal): {e}")

    # Launch worker threads
    worker_threads = []
    for i in range(threads_count):
        t = threading.Thread(target=worker_loop, args=(i,))
        t.daemon = True
        t.start()
        worker_threads.append(t)

    # Launch watcher thread
    watcher_thread = threading.Thread(target=watcher_loop)
    watcher_thread.daemon = True
    watcher_thread.start()

    # Wait for completion or timeout
    for t in worker_threads:
        t.join(timeout=max(1, end_time - time.time() + 2))
    stop_event.set()

    # If run_id still matches, update state/load.json to clear running status
    if BUCKET and run_id:
        try:
            resp = s3.get_object(Bucket=BUCKET, Key="state/load.json")
            state = json.loads(resp["Body"].read().decode("utf-8"))
            if state.get("run_id") == run_id:
                s3.put_object(
                    Bucket=BUCKET,
                    Key="state/load.json",
                    Body=json.dumps({"run_id": None}),
                    ContentType="application/json"
                )
                print(f"[LoadGen] Cleared run_id {run_id} in S3 state.")
        except Exception as e:
            print(f"[LoadGen] Failed to clear S3 state: {e}")

    elapsed = round(time.time() - start_time, 1)
    print(f"[LoadGen] Finished in {elapsed}s: ok={ok_count}, err={err_count}")

    return {
        "status": "completed",
        "run_id": run_id,
        "duration_sec": elapsed,
        "ok": ok_count,
        "err": err_count
    }
