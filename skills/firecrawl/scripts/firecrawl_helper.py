#!/usr/bin/env python3
import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error

API_BASE = "https://api.firecrawl.dev/v1"

def make_request(endpoint, method="GET", data=None):
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        print("Error: FIRECRAWL_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)
        
    url = f"{API_BASE}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    req_data = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

def scrape(url, extract_prompt=None):
    payload = {"url": url, "formats": ["markdown"]}
    if extract_prompt:
        payload["formats"] = ["extract"]
        payload["extract"] = {"prompt": extract_prompt}
    
    return make_request("scrape", "POST", payload)

def crawl(url, limit=10, wait=False):
    payload = {"url": url, "limit": limit}
    res = make_request("crawl", "POST", payload)
    
    if not wait:
        return res
        
    job_id = res.get("id")
    if not job_id:
        return res
        
    print(f"Crawl job started with ID: {job_id}. Waiting for completion...", file=sys.stderr)
    while True:
        status_res = make_request(f"crawl/{job_id}", "GET")
        status = status_res.get("status")
        if status == "completed":
            return status_res
        elif status in ["failed", "cancelled"]:
            print(f"Crawl failed or cancelled. Status: {status}", file=sys.stderr)
            return status_res
            
        time.sleep(3)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Firecrawl API Helper")
    parser.add_argument("action", choices=["scrape", "crawl"])
    parser.add_argument("url", help="URL to process")
    parser.add_argument("--extract", help="Prompt for structured extraction (scrape only)")
    parser.add_argument("--limit", type=int, default=10, help="Max pages for crawl (crawl only)")
    parser.add_argument("--wait", action="store_true", help="Wait for crawl to complete (crawl only)")
    
    args = parser.parse_args()
    
    if args.action == "scrape":
        result = scrape(args.url, args.extract)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.action == "crawl":
        result = crawl(args.url, args.limit, args.wait)
        print(json.dumps(result, indent=2, ensure_ascii=False))
