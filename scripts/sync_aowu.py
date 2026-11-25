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

Spider is also localized:
  The config's spider field is normally a remote URL, e.g.
    https://nos.netease.com/.../8273a7a3-....png;md5;f33fe...
  localize_spider() downloads that file, saves it next to the
  config as aw.png or aw.jar - the extension comes from the
  spider URL itself (.png stays .png, .jar stays .jar) - and
  rewrites the spider field to the local name, keeping the md5:
    aw.png;md5;f33fe0621341289e1491f2ae55b4423b
  If the extension ever changes, the old aw.* file is deleted.
  The downloaded file's md5 is checked against the config's
  hash; if they differ, the computed md5 is used instead.

Usage: python3 scripts/sync_aowu.py [output.json]
Exit code is non-zero if neither method produced a valid config,
so the GitHub Action fails visibly instead of committing a bad file.
"""
import glob
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from urllib.parse import urlparse

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


def localize_spider(config_path):
    """Download the spider file as aw.png / aw.jar and point the
    config at the local file. Extension comes from the spider URL.
    """
    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)
    spider = data.get("spider", "")
    parts = spider.split(";")
    url = parts[0].strip()
    if not url or url.startswith("aw."):
        print(f"spider already local: {spider}")
        return data
    expected_md5 = parts[2].strip() if len(parts) > 2 else ""
    workdir = os.path.dirname(os.path.abspath(config_path)) or "."

    req = urllib.request.Request(
        url, headers={"User-Agent": "okhttp/3.12.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        content = resp.read()
        content_type = resp.headers.get_content_type()
    ext = os.path.splitext(urlparse(url).path)[1].lower()
    if ext not in (".png", ".jar", ".zip"):
        ext = {".png": ".png", "image/png": ".png",
               "image/jpeg": ".jpg",
               "application/java-archive": ".jar",
               "application/zip": ".zip"}.get(content_type, ".jar")
    local_name = f"aw{ext}"
    local_path = os.path.join(workdir, local_name)
    with open(local_path, "wb") as f:
        f.write(content)
    md5 = hashlib.md5(content).hexdigest()
    if expected_md5 and md5 != expected_md5:
        print(f"warning: spider md5 mismatch, config says "
              f"{expected_md5}, downloaded file is {md5}",
              file=sys.stderr)
    else:
        print(f"spider md5 matches: {md5}")
    # Remove a stale aw.* with a different extension.
    for old in glob.glob(os.path.join(workdir, "aw.*")):
        if os.path.abspath(old) != os.path.abspath(local_path):
            os.remove(old)
            print(f"removed stale {os.path.basename(old)}")
    data["spider"] = f"{local_name};md5;{md5}"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"spider: {url} -> {local_name} ({len(content)} bytes)")
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
    localize_spider(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
