#!/usr/bin/env python3
import argparse, json, subprocess, sys
from pathlib import Path

REF_W, REF_H = 720, 1280
BOXES = {
    "top_left": (1, 1, 310, 145),
    "bottom_right": (500, 1170, 215, 100),
}

def probe(path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height", "-of", "json", path]
    data = json.loads(subprocess.check_output(cmd))
    s = data["streams"][0]
    return int(s["width"]), int(s["height"])

def intervals(value):
    if not value:
        return []
    out = []
    for part in value.split(","):
        a, b = map(float, part.strip().split("-", 1))
        if a < 0 or b <= a:
            raise ValueError(f"无效区间: {part}")
        out.append((a, b))
    return out

def enable_expr(items):
    return "+".join(f"between(t,{a:g},{b:g})" for a, b in items)

def scaled_box(box, width, height):
    x, y, w, h = box
    sx, sy = width / REF_W, height / REF_H
    x = max(1, round(x * sx)); y = max(1, round(y * sy))
    w = min(width - x - 1, max(2, round(w * sx)))
    h = min(height - y - 1, max(2, round(h * sy)))
    return x, y, w, h

def main():
    p = argparse.ArgumentParser(description="按出现时段去除豆包视频角落水印")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--top-left", default="", help="如 3.8-8.15")
    p.add_argument("--bottom-right", default="", help="如 0.8-4.15,7.8-10.1")
    p.add_argument("--crf", type=int, default=18)
    args = p.parse_args()
    if not Path(args.input).is_file():
        p.error("输入视频不存在")
    width, height = probe(args.input)
    filters = []
    for name, raw in (("top_left", args.top_left), ("bottom_right", args.bottom_right)):
        spans = intervals(raw)
        if spans:
            x, y, w, h = scaled_box(BOXES[name], width, height)
            filters.append(f"delogo=x={x}:y={y}:w={w}:h={h}:enable='{enable_expr(spans)}'")
    if not filters:
        p.error("至少指定一个水印时段")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", args.input, "-vf", ",".join(filters),
           "-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf),
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", args.output]
    subprocess.run(cmd, check=True)
    print(args.output)

if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
