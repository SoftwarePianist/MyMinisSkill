#!/usr/bin/env python3
"""Standalone Toutiao video downloader. Python standard library only."""

import argparse
import base64
import html
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/118.0 Mobile Safari/537.36"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request(url, referer=None, timeout=30):
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    return OPENER.open(urllib.request.Request(url, headers=headers), timeout=timeout)


def fetch_page(url):
    with request(url) as r:
        return r.geturl(), r.read().decode("utf-8", "replace")


def render_data(page):
    match = re.search(r'<script[^>]+id=["\']RENDER_DATA["\'][^>]*>(.*?)</script>', page, re.S | re.I)
    if not match:
        raise RuntimeError("页面中没有 RENDER_DATA，链接可能不是头条视频或页面结构已变化")
    try:
        return json.loads(urllib.parse.unquote(html.unescape(match.group(1))))
    except Exception as exc:
        raise RuntimeError(f"无法解析头条页面数据：{exc}") from exc


def play_info(data):
    article = data.get("articleInfo") or {}
    token = article.get("playAuthTokenV2")
    if not token:
        raise RuntimeError("页面没有视频播放授权信息")
    try:
        decoded = json.loads(base64.b64decode(token).decode("utf-8"))
        query = decoded["GetPlayInfoToken"]
    except Exception as exc:
        raise RuntimeError(f"无法解析视频播放授权：{exc}") from exc
    api = "https://vod.bytedanceapi.com/?" + query
    with request(api) as r:
        payload = json.load(r)
    try:
        items = payload["Result"]["Data"]["PlayInfoList"]
    except Exception as exc:
        message = payload.get("ResponseMetadata", {}).get("Error", {}).get("Message", "播放接口未返回视频地址")
        raise RuntimeError(message) from exc
    if not items:
        raise RuntimeError("播放接口返回的视频清晰度列表为空")
    return article, sorted(items, key=lambda x: (int(x.get("Bitrate") or 0), int(x.get("Height") or 0)), reverse=True)


def safe_title(title, max_bytes=180):
    """Build a readable, filesystem-safe UTF-8 filename stem from the title."""
    value = html.unescape(str(title or "")).replace("\u3000", " ")
    value = re.sub(r"[\\/:*?\"<>|\x00-\x1f\x7f]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    if not value:
        value = "头条视频"
    while len(value.encode("utf-8")) > max_bytes:
        value = value[:-1]
    return value.rstrip(" .") or "头条视频"


def unique_target(path):
    """Avoid overwriting an existing title-named video."""
    if not path.exists():
        return path
    for number in range(2, 10000):
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("同名文件过多，无法生成唯一文件名")


def minis_url(path):
    """Return a percent-encoded minis:// URL for files under /var/minis."""
    resolved = path.resolve()
    root = Path("/var/minis")
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        return None
    encoded = "/".join(urllib.parse.quote(part, safe="") for part in relative.parts)
    return f"minis://{encoded}"


def looks_like_mp4(path):
    if path.stat().st_size < 1024:
        return False
    with path.open("rb") as f:
        head = f.read(32)
    return len(head) >= 12 and head[4:8] == b"ftyp"


def download(url, target, referer):
    temp = Path(str(target) + ".part")
    temp.unlink(missing_ok=True)
    try:
        with request(url, referer=referer, timeout=45) as src, temp.open("wb") as dst:
            total = int(src.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = src.read(256 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
                done += len(chunk)
                if sys.stderr.isatty() and total:
                    print(f"\r下载 {done * 100 / total:5.1f}%", end="", file=sys.stderr)
        if sys.stderr.isatty():
            print(file=sys.stderr)
        if not looks_like_mp4(temp):
            raise RuntimeError("下载内容不是有效 MP4")
        os.replace(temp, target)
        return target.stat().st_size
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description="独立下载今日头条视频（无需 Agent 或浏览器）")
    parser.add_argument("url", help="头条视频或分享短链接")
    parser.add_argument("-o", "--output", help="输出 MP4 文件或目录；默认保存到当前目录")
    parser.add_argument("--list", action="store_true", help="只列出可用清晰度，不下载")
    args = parser.parse_args()

    final_url, page = fetch_page(args.url)
    data = render_data(page)
    article, items = play_info(data)
    title = article.get("title") or "Toutiao video"
    print(f"标题：{title}")
    print(f"视频ID：{article.get('gid') or article.get('videoId') or '-'}")
    for i, item in enumerate(items, 1):
        print(f"[{i}] {item.get('Definition', '?')} {item.get('Width', '?')}x{item.get('Height', '?')} {int(item.get('Bitrate') or 0) // 1000} kbps")
    if args.list:
        return 0

    default_name = f"{safe_title(title)}.mp4"
    if args.output:
        output = Path(args.output).expanduser()
        is_directory = output.is_dir() or str(args.output).endswith(os.sep)
        target = unique_target(output / default_name) if is_directory else output
    else:
        target = unique_target(Path.cwd() / default_name)
    target.parent.mkdir(parents=True, exist_ok=True)

    errors = []
    for item in items:
        for key in ("MainPlayUrl", "BackupPlayUrl"):
            url = item.get(key)
            if not url:
                continue
            try:
                size = download(url, target, final_url)
                print(f"已保存：{target.resolve()}")
                print(f"清晰度：{item.get('Definition', '?')}，大小：{size / 1024 / 1024:.1f} MB")
                preview = minis_url(target)
                if preview:
                    print(f"MINIS_URL={preview}")
                    print(f"MARKDOWN=![{title}]({preview})")
                return 0
            except Exception as exc:
                errors.append(f"{item.get('Definition', '?')} {key}: {exc}")
                target.unlink(missing_ok=True)
    raise RuntimeError("所有视频源均下载失败：\n" + "\n".join(errors))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("已取消", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1)
