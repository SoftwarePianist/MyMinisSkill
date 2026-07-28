---
name: toutiao-downloader
description: "Download 今日头条/Toutiao videos from m.toutiao.com or toutiao.com share links. Trigger when a user sends a Toutiao video URL, share text containing one, asks to save/download it, or when yt-dlp cannot parse the page. Prefer the bundled standalone Python downloader; it resolves short links, selects the highest-bitrate MP4, saves with a sanitized Chinese title, verifies it, and does not require Agent browser extraction."
version: 1.3.1
---
# Toutiao Video Downloader

Prefer the bundled standard-library Python downloader. It parses `RENDER_DATA`, exchanges `playAuthTokenV2` with the Toutiao VOD API, ranks all MP4 streams by bitrate, retries backup URLs, and validates the MP4 `ftyp` signature. Browser DOM extraction is the fallback if Toutiao changes or omits the embedded data.

## Primary workflow: standalone script

1. Ensure Python is available without printing an avoidable command-not-found error:

```sh
command -v python3 >/dev/null 2>&1 || apk add python3 >/dev/null
```

2. Run the bundled script and save directly into attachments:

```sh
python3 /var/minis/skills/toutiao-downloader/scripts/download.py 'TOUTIAO_URL' -o /var/minis/attachments/
```

The script uses only Python's standard library, disables environment proxies for page/API/CDN requests, follows short-link redirects, selects the highest bitrate, retries main and backup CDN URLs, removes partial files, and verifies MP4 internally. By default it names the file from the Chinese video title, removes filesystem-invalid/control characters, collapses whitespace, limits the UTF-8 name length, and appends ` (2)`, ` (3)`, etc. instead of overwriting an existing same-title file. A successful run prints the absolute path, selected resolution, size, a percent-encoded `MINIS_URL`, and ready-to-use inline `MARKDOWN` whenever the output is under `/var/minis`. Use that output directly; do not run a second URL-encoding command.

Useful manual commands:

```sh
# List available qualities without downloading
python3 /var/minis/skills/toutiao-downloader/scripts/download.py 'TOUTIAO_URL' --list

# Choose an exact output path
python3 /var/minis/skills/toutiao-downloader/scripts/download.py 'TOUTIAO_URL' -o '/path/video.mp4'
```

This script can be run manually from a terminal when Agent/model connectivity is unavailable, provided the device still has network access. It does not require `browser_use`, `wget`, `file`, `ffprobe`, third-party Python packages, cookies, or login.

3. On success, copy the script's `MARKDOWN=` value into the final response (without the `MARKDOWN=` prefix). This already handles Chinese, spaces, emoji, `#`, and punctuation safely. Do not call another shell command merely to generate or encode the preview URL. If the script fails because `RENDER_DATA`, authorization fields, or the VOD response changed, use the browser fallback below.

## Browser fallback

1. Navigate to the supplied URL with `browser_use` using `mobile_chrome`; allow the share-link redirect.
2. If no video appears immediately, call `wait_for_dom_stable`, then extract again. Do not require playback or login.
3. Extract every candidate, not only the first `<video>`:

```javascript
const cleanTitle = (document.title || 'toutiao_video')
  .replace(/[\/\\:*?"<>|]/g, '').trim();
const raw = [...document.querySelectorAll('video, video source, source')]
  .flatMap(e => [e.currentSrc, e.src, e.getAttribute('src')])
  .filter(Boolean);
const candidates = [...new Set(raw)].map(url => {
  let bitrate = 0;
  try { bitrate = Number(new URL(url).searchParams.get('br')) || 0; } catch (_) {}
  return { url, bitrate };
}).sort((a, b) => b.bitrate - a.bitrate);
return { title: cleanTitle, candidates };
```

4. Select the candidate with the largest numeric `br`. The first/current source is often lower quality; prefer a later `<source>` when its bitrate is higher.
5. Name the file from the cleaned Chinese page title, matching the standalone script. Remove `/\\:*?"<>|` and control characters, collapse repeated whitespace, trim trailing spaces/dots, and limit the UTF-8 stem to about 180 bytes. If the same name exists, append ` (2)`, ` (3)`, etc. Do not overwrite existing files.
6. Download with `wget`. Disabling the proxy is essential because Toutiao CDN requests may otherwise return 502:

```sh
wget -Y off -U 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/118.0.0.0 Safari/537.36' 'VIDEO_URL' -O '/var/minis/attachments/CLEAN_CHINESE_TITLE.mp4'
```

If the highest-bitrate URL fails, retry candidates in descending bitrate order. Re-extract the page if URLs have expired. Add a `Referer` header matching the final Toutiao page only if the CDN returns 403.

7. Verify before delivery without assuming optional commands are installed.

First ensure the download succeeded and is non-empty:

```sh
VIDEO='/var/minis/attachments/CLEAN_CHINESE_TITLE.mp4'; [ -s "$VIDEO" ] || { echo 'download_failed_or_empty'; exit 1; }
```

Then choose an available validator. Prefer `ffprobe`, otherwise use `file`. Check availability with `command -v` before invocation so a missing utility never produces exit code 127:

```sh
VIDEO='/var/minis/attachments/CLEAN_CHINESE_TITLE.mp4'; if command -v ffprobe >/dev/null 2>&1; then ffprobe -v error -show_entries format=format_name,duration,size -of default=nw=1 "$VIDEO"; elif command -v file >/dev/null 2>&1; then file "$VIDEO"; else apk add file >/dev/null && file "$VIDEO"; fi; ls -lh "$VIDEO"
```

Accept only a successful result identifying MP4/MOV/ISO media. With `ffprobe`, `format_name` should contain `mp4`, `mov`, or `m4a`; with `file`, output should contain `ISO Media`, `MP4`, or `QuickTime`. Reject HTML, JSON, XML, text, zero-byte files, and validator errors.

If validation fails, delete the bad partial file and retry the next candidate. Do not show routine installer or validator output to the user unless all candidates fail.

8. Return inline media, not a plain link:

```markdown
![视频标题](minis://attachments/CLEAN_CHINESE_TITLE.mp4)
```

Keep the final response brief. Mention that the highest available bitrate was selected when useful.