"""Preview/send fictional history from A, then read/assess it as consenting B."""
import argparse
import json
import os
import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--attest", action="store_true", help="Requires reviewed A key")
    args = parser.parse_args()
    payload = {"outcomes": [{"source_record_id": f"fictional-demo-{i}", "occurred_at": "2026-10-01T12:00:00+01:00", "status": "completed", "rating": 4, "dispute_resolution": None, "attest": args.attest} for i in range(1, 6)]}
    if not args.send:
        print("Preview only. --send requires two keys and worker-issued consent tokens.")
        print(json.dumps(payload, indent=2))
        return
    base = os.environ.get("TRUST_API", "http://localhost:8000/api/v1")
    keys = [os.environ[f"PLATFORM_{name}_KEY"] for name in ["A", "B"]]
    if keys[0] == keys[1]: parser.error("Use two distinct platform keys")
    with httpx.Client(base_url=base+"/", timeout=15) as client:
        links = []
        for name, key in zip(["A", "B"], keys):
            response = client.post("platform/worker-links", headers={"X-API-Key": key}, json={"external_worker_id": f"demo-worker-{name.lower()}", "consent_token": os.environ[f"PLATFORM_{name}_CONSENT"]})
            response.raise_for_status()
            links.append(response.json())
        if links[0]["worker_id"] != links[1]["worker_id"]: parser.error("Approvals must belong to the same worker")
        response = client.post("platform/workers/demo-worker-a/history/import", headers={"X-API-Key": keys[0], "Idempotency-Key": "fictional-demo-attested" if args.attest else "fictional-demo-declared"}, json=payload)
        response.raise_for_status()
        print("Import:", response.json())
        response = client.get("platform/workers/demo-worker-b/history", headers={"X-API-Key": keys[1]})
        response.raise_for_status()
        print("Receiving platform sees", response.json()["total"], "records with provenance.")
        response = client.post("trust/query", headers={"X-API-Key": keys[1]}, json={"worker_id": links[1]["worker_id"], "platform_type": "generic", "job_context": {"job_type": "cleaning", "value_band": "low"}})
        response.raise_for_status()
        print("Assessment:", response.json())

if __name__ == "__main__": main()
