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

Local pack (same idea as the bjq.catvod.site editor's "下载本地包"):
  After decrypting, every downloadable remote file in the config
  is downloaded and sorted into folders, and the config is
  rewritten to relative paths:
    spider            -> jar/aw.png (or aw.jar - extension comes
                       from the spider URL, name is always aw.*)
                       spider field becomes:
                       "./jar/aw.png;md5;f33fe0621341289e1491f2ae55b4423b"
    images (logo etc) -> img/<original filename>
    other http files  -> ext/<original filename>
                       (sites' api/ext, e.g. .aowu / .gz files)
    live lists (.m3u) -> lib/<original filename>
                       (lives[].url, e.g. huyayqk.m3u, iptv.m3u;
                       lives without a .m3u URL stay remote)
  Skipped, left as remote URLs: localhost / 127.0.0.1 addresses,
  URLs with {placeholders}, and URLs with no filename (parse /
  DoH endpoints, the 综合直播 iptv.php). A failed download only
  warns and keeps the remote URL, except for the spider, which
  fails the sync. Stale files in jar/ / img/ / ext/ / lib/ that
  the current config no longer references are deleted, and a
  stale aw.* at the repo root (from the earlier layout) is
  removed too.

Usage: python3 scripts/sync_aowu.py [output.json]
Exit code is non-zero if neither method produced a valid config,
so the GitHub Action fails visibly instead of committing a bad file.
"""
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from urllib.parse import unquote, urlparse

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


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp"}
LOCALHOSTS = {"localhost", "127.0.0.1", "0.0.0.0"}
URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def _download(url):
    """Download a URL. TVBox hosts usually accept okhttp; some
    (e.g. cdn.waimaimingtang.com) close the connection for it,
    so fall back to a browser UA before giving up. Some mirrors
    (e.g. down.nigx.cn/raw.githubusercontent.com/...) may 403,
    so fall back to the direct raw.githubusercontent.com URL."""
    candidates = [url]
    if "/raw.githubusercontent.com/" in url:
        direct = "https://raw.githubusercontent.com/" + \
            url.split("/raw.githubusercontent.com/", 1)[1]
        if direct != url:
            candidates.append(direct)
    last_err = None
    for candidate in candidates:
        for ua in ("okhttp/3.12.0",
                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"):
            try:
                req = urllib.request.Request(
                    candidate, headers={"User-Agent": ua})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return resp.read(), resp.headers.get_content_type()
            except Exception as e:
                last_err = e
    raise last_err


def _basename(url):
    name = unquote(urlparse(url).path).rstrip("/").rsplit("/", 1)[-1]
    return name


def localize_resources(config_path):
    """Download the config's remote files into jar/ img/ ext/ and
    rewrite the config to relative paths. See module docstring.
    """
    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)
    workdir = os.path.dirname(os.path.abspath(config_path)) or "."
    kept = set()  # absolute paths of local files still referenced

    # --- spider -> jar/aw.png (or aw.jar) ---
    spider = data.get("spider", "")
    parts = spider.split(";")
    url = parts[0].strip()
    if url.startswith("http"):
        expected_md5 = parts[2].strip() if len(parts) > 2 else ""
        content, content_type = _download(url)
        ext = os.path.splitext(urlparse(url).path)[1].lower()
        if ext not in (".png", ".jar", ".zip"):
            ext = {"image/png": ".png", "image/jpeg": ".jpg",
                   "application/java-archive": ".jar",
                   "application/zip": ".zip"}.get(content_type, ".jar")
        local_name = f"aw{ext}"
        dest = os.path.join(workdir, "jar", local_name)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(content)
        md5 = hashlib.md5(content).hexdigest()
        if expected_md5 and md5 != expected_md5:
            print(f"warning: spider md5 mismatch, config says "
                  f"{expected_md5}, downloaded file is {md5}",
                  file=sys.stderr)
        data["spider"] = f"./jar/{local_name};md5;{md5}"
        kept.add(os.path.abspath(dest))
        print(f"spider: {url} -> jar/{local_name} ({len(content)} bytes)")

    # --- everything else: walk the config, download http URLs ---
    # (parent, key) pairs so the string can be rewritten in place.
    def walk(obj, in_lives=False):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield from walk(v, in_lives or k == "lives")
        elif isinstance(obj, list):
            for v in obj:
                yield from walk(v, in_lives)
        elif isinstance(obj, str):
            yield obj, in_lives

    # Collect first, because rewriting while walking is unsafe.
    strings = []
    for value, in_lives in walk(data):
        if "http" in value and not in_lives:
            strings.append(value)

    seen_url = {}  # url -> local relative path
    for value in strings:
        for url in URL_RE.findall(value):
            if url in seen_url:
                rel = seen_url[url]
                data = _rewrite(data, value, url, rel)
                continue
            host = urlparse(url).hostname or ""
            if host in LOCALHOSTS or host.startswith(("192.168.", "10.")):
                continue
            if "{" in url or "}" in url:
                continue
            name = _basename(url)
            if not name or "." not in name:
                continue  # parse / DoH endpoints, no filename
            ext = os.path.splitext(name)[1].lower()
            folder = "img" if ext in IMAGE_EXTS else "ext"
            # Same filename from a different URL: keep both.
            rel = f"./{folder}/{name}"
            dest = os.path.join(workdir, folder, name)
            if os.path.exists(dest) and rel in seen_url.values():
                stem, suffix = os.path.splitext(name)
                tag = hashlib.md5(url.encode()).hexdigest()[:8]
                rel = f"./{folder}/{stem}-{tag}{suffix}"
                dest = os.path.join(workdir, folder,
                                    f"{stem}-{tag}{suffix}")
            try:
                content, _ct = _download(url)
            except Exception as e:
                print(f"warning: could not download {url}: {e}, "
                      f"keeping remote URL", file=sys.stderr)
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(content)
            seen_url[url] = rel
            kept.add(os.path.abspath(dest))
            data = _rewrite(data, value, url, rel)
            print(f"resource: {url} -> {rel} ({len(content)} bytes)")

    # --- lives .m3u files -> lib/ (like the editor's local pack) ---
    for live in data.get("lives", []) or []:
        if not isinstance(live, dict):
            continue
        url = (live.get("url") or "").strip()
        if not url.startswith("http"):
            continue
        name = _basename(url)
        if not name.lower().endswith(".m3u"):
            continue  # e.g. the 综合直播 iptv.php, no file to fetch
        rel = f"./lib/{name}"
        dest = os.path.join(workdir, "lib", name)
        try:
            content, _ct = _download(url)
        except Exception as e:
            print(f"warning: could not download live list {url}: "
                  f"{e}, keeping remote URL", file=sys.stderr)
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(content)
        live["url"] = rel
        kept.add(os.path.abspath(dest))
        print(f"live: {url} -> {rel} ({len(content)} bytes)")

    # --- clean stale files ---
    for folder in ("jar", "img", "ext", "lib"):
        for path in glob.glob(os.path.join(workdir, folder, "*")):
            if os.path.isfile(path) and os.path.abspath(path) not in kept:
                os.remove(path)
                print(f"removed stale {folder}/{os.path.basename(path)}")
    # Stale aw.* at the repo root, from the earlier layout.
    for old in glob.glob(os.path.join(workdir, "aw.*")):
        os.remove(old)
        print(f"removed stale root {os.path.basename(old)}")

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def _rewrite(obj, old_value, url, rel):
    """Replace one URL inside one config string value, in place."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if v is old_value or v == old_value:
                obj[k] = old_value.replace(url, rel, 1)
            else:
                _rewrite(v, old_value, url, rel)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if v is old_value or v == old_value:
                obj[i] = old_value.replace(url, rel, 1)
            else:
                _rewrite(v, old_value, url, rel)
    return obj


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
    localize_resources(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
