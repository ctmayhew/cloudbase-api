"""Send one track to Cloudbase as a test jump, with retries.

    CLOUDBASE_TOKEN=cb_pat_... python3 push.py sample-track.csv

Standard library only (Python 3.9+). Drop "isSimulated" once you're sending
real jumps.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

URL = "https://api.getcloudbase.com/jumps/import-gps-csv"


def push_track(token: str, csv_text: str, device_type: str, device_id: str) -> dict:
    body = json.dumps({
        "deviceType": device_type,
        "deviceId": device_id,
        "isSimulated": True,
        "csv": csv_text,
    }).encode()

    for attempt in range(5):
        req = urllib.request.Request(URL, data=body, method="POST", headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                # Every 200 is final, including matchResult "skipped".
                return json.load(res)
        except urllib.error.HTTPError as err:
            if err.code == 401:
                raise SystemExit("Token rejected: ask the user to connect Cloudbase again.")
            if err.code == 429 or err.code >= 500:
                time.sleep(2 ** attempt)  # back off, then retry the same track
                continue
            # 400 / 413: the file itself is the problem, so retrying won't help.
            raise SystemExit(f"Rejected ({err.code}): {err.read().decode()}")
        except urllib.error.URLError:
            time.sleep(2 ** attempt)  # network blip; retrying is safe
    raise SystemExit("Gave up after 5 attempts.")


if __name__ == "__main__":
    token = os.environ["CLOUDBASE_TOKEN"]
    with open(sys.argv[1], encoding="utf-8") as f:
        result = push_track(token, f.read(), "flysight", "flysight:EXAMPLE")
    print(result)  # {'jumpId': '…', 'matchResult': 'created'}
