#!/usr/bin/env python3
import argparse
import math
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd, stdout=subprocess.PIPE):
    return subprocess.run(cmd, check=True, text=True, stdout=stdout, stderr=subprocess.PIPE)


def main():
    p = argparse.ArgumentParser(description="Extract metadata, frames, OCR, and contact sheet from a video")
    p.add_argument("video")
    p.add_argument("--output", required=True)
    p.add_argument("--interval", type=float, default=0, help="frame interval seconds; auto when omitted")
    p.add_argument("--max-frames", type=int, default=30)
    p.add_argument("--lang", default="chi_sim+eng")
    args = p.parse_args()

    video = Path(args.video).expanduser().resolve()
    out = Path(args.output).expanduser().resolve()
    frames = out / "frames"
    if not video.is_file():
        sys.exit(f"Video not found: {video}")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        sys.exit("ffmpeg/ffprobe required")

    frames.mkdir(parents=True, exist_ok=True)
    for old in frames.glob("frame-*.jpg"):
        old.unlink()

    meta_cmd = ["ffprobe", "-v", "error", "-show_entries",
                "format=duration,size,format_name:stream=index,codec_type,codec_name,width,height",
                "-of", "default=nw=1", str(video)]
    meta = run(meta_cmd).stdout
    (out / "metadata.txt").write_text(meta, encoding="utf-8")

    duration = 0.0
    for line in meta.splitlines():
        if line.startswith("duration="):
            try:
                duration = float(line.split("=", 1)[1])
            except ValueError:
                pass
    interval = args.interval or max(3.0, duration / max(1, args.max_frames))
    vf = f"fps=1/{interval:.3f},scale=540:-2"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf", vf,
         "-frames:v", str(args.max_frames), str(frames / "frame-%03d.jpg")])

    images = sorted(frames.glob("frame-*.jpg"))
    ocr_path = out / "ocr.txt"
    with ocr_path.open("w", encoding="utf-8") as ocr:
        if shutil.which("tesseract"):
            for i, image in enumerate(images):
                seconds = i * interval
                ocr.write(f"\n=== {image.name} @ {seconds:.1f}s ===\n")
                result = subprocess.run(["tesseract", str(image), "stdout", "-l", args.lang],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                ocr.write(result.stdout)
        else:
            ocr.write("Tesseract unavailable; inspect frames manually.\n")

    if images:
        cols = 5
        rows = min(6, math.ceil(len(images) / cols))
        run(["ffmpeg", "-y", "-v", "error", "-pattern_type", "glob", "-i",
             str(frames / "frame-*.jpg"), "-vf", f"scale=180:-2,tile={cols}x{rows}",
             "-frames:v", "1", str(out / "contact-sheet.jpg")])

    print(f"VIDEO={video}")
    print(f"OUTPUT={out}")
    print(f"DURATION={duration:.3f}")
    print(f"INTERVAL={interval:.3f}")
    print(f"FRAMES={len(images)}")
    print(f"OCR={ocr_path}")
    if (out / "contact-sheet.jpg").exists():
        print(f"CONTACT_SHEET={out / 'contact-sheet.jpg'}")


if __name__ == "__main__":
    main()
