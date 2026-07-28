---
name: yt-dlp-downloader
description: "Download videos from X/Twitter, YouTube, and other sites using yt-dlp. Auto-installs yt-dlp and ffmpeg if missing, handles filename errors by retrying with simpler names, and merges video and audio streams."
version: 1.0.0
---
# yt-dlp Downloader Skill

Use `yt-dlp` to download high-quality videos from X/Twitter, YouTube, and other platforms, ensuring video and audio are properly merged.

## When to Use
- User provides a video link (X/Twitter, YouTube, etc.) and asks to download it.
- Existing download tools fail due to missing audio or complex filenames.

## Workflow

1. **Check Dependencies**:
   Ensure `yt-dlp` and `ffmpeg` are installed.
   ```bash
   which yt-dlp || apk add yt-dlp
   which ffmpeg || apk add ffmpeg
   ```

2. **Download Video**:
   Run `yt-dlp` and output to `/var/minis/attachments/`. Default to using the title for the filename.
   ```bash
   yt-dlp "URL" -o "/var/minis/attachments/%(title)s.%(ext)s"
   ```

3. **Handle Filename Errors (Fallback)**:
   If the download fails due to OS filename limits (e.g., "File name too long" or strange SSL EOF errors caused by path length), automatically retry with a simpler filename, such as the video ID.
   ```bash
   yt-dlp "URL" -o "/var/minis/attachments/%(id)s.%(ext)s"
   ```

4. **Verify Output**:
   `yt-dlp` will automatically call `ffmpeg` to merge the downloaded video and audio streams. Verify the final file:
   ```bash
   ls -lh /var/minis/attachments/
   ```

5. **Deliver to User**:
   Return the downloaded video in the chat using Markdown inline media syntax. Remember to URL-encode the filename in the Markdown link if it contains spaces or special characters.
   `![video](minis://attachments/filename.mp4)`