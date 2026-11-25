#!/usr/bin/env python3
"""Sync the Aowu TVBox interface into aowu.json.

Source: http://www.嗷呜.cc/tv (主接口, see assets/apis.json on that site)

How the source works (same pattern as qist/tvbox's run.yml):
  * Requesting /tv with a TVBox User-Agent (okhttp/3.12.0) gets a
    302 redirect to a PNG on nos.netease.com. The PNG is not a
    picture - it has the TVBox JSON config embedded as base64.
  * tools/tvbox.py (from qist/tvbox) follows the redirect, extracts
    the base64 from the PNG and decodes it to JSON. No AES key is
    needed for this source - the decoded content is already JSON.

Fallback: if tvbox.py fails, try the site's own decrypt API
  POST https://www.xn--nsr30b.cc/api/decode.php {"url": ".../tv"}
  which returns {"ok": true, "data": "<TVBox JSON string>"}.

Usage: python3 scripts/sync_aowu.py [output.json]
Exit code is non-zero if neither method produced a valid config,
so the GitHub Action fails visibly instead of committing a bad file.
"""
import json
import subprocess
import sys
import urllib.request

SOURCE_URL = "http://www.嗷呜.cc/tv"
DECODE_API = "https://www.xn--nsr30b.cc/api/decode.php"


def try_tvbox_py(out_path):
    """Decrypt with tools/tvbox.py, like qist/tvbox's xiaosa job."""
    r = subprocess.run(
        [sys.executable, "tools/tvbox.py", SOURCE_URL, out_path, "dec"],
        capture_output=True, text=True, timeout=120,
    )
    print(r.stdout)
    if r.stderr:
        print(r.stderr, file=sys.stderr)
    return r.returncode == 0


def try_decode_api(out_path):
    """Decrypt with the site's own decode.php API."""
    data = json.dumps({"url": SOURCE_URL}).encode()
    req = urllib.request.Request(
        DECODE_API, data=data,
        headers={"Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if not body.get("ok") or not body.get("data"):
        raise ValueError(f"decode API failed: {body}")
    inner = json.loads(body["data"])
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(inner, f, ensure_ascii=False, indent=2)
    print("decode API succeeded")
    return True


def validate(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    sites = data.get("sites")
    if not isinstance(sites, list) or not sites:
        raise ValueError("config has no sites")
    if not data.get("spider"):
        raise ValueError("config has no spider")
    print(f"valid: sites={len(sites)} lives={len(data.get('lives', []))} "
          f"parses={len(data.get('parses', []))}")
    return data


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "aowu.json"
    ok = False
    try:
        ok = try_tvbox_py(out)
        if ok:
            validate(out)
    except Exception as e:
        print(f"tvbox.py failed: {e}", file=sys.stderr)
        ok = False
    if not ok:
        print("falling back to decode API ...", file=sys.stderr)
        try_decode_api(out)
        validate(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
