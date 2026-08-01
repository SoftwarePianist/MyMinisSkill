#!/usr/bin/env python3
"""Extract Toutiao article from RENDER_DATA and emit full Markdown.

Usage: extract.py <url>
Prints a single-line JSON:
  {"type": "article", "title": str, "summary": str, "markdown": str, "author": str, "publish_time": str}
or for videos / failures:
  {"type": "video"|"unknown", "title": str, "summary": str, "markdown": ""}

Conversion pipeline:
  articleInfo.content (HTML) → markdownify → fenced code blocks preserved.
  Toutiao's editor often stuffs multiple shell commands into one <code> with no
  newlines; a conservative heuristic re-splits them onto separate lines.

Images stay as remote http(s) URLs, which satisfies ima notes' "network images
only" rule.
"""
import gzip
import json
import re
import sys
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36")

# --- code-block re-splitting heuristics ------------------------------------
# Newline before an env-var assignment like MINIMAX_API_KEY=... (but not in the
# middle of a longer identifier).
_ENV_PAT = re.compile(r'(?<![A-Za-z_])([A-Z][A-Z_]{2,}=)')
# Newline before a common shell command keyword.
_CMD_PAT = re.compile(
    r'(?<=\S)((?:git|pip|pip3|python|python3|cd|npm|npx|conda|source|export|sudo'
    r'|curl|wget|docker|mkdir|touch|chmod|brew|apt|apt-get)\s)'
)
# Newline before a "# comment" that follows non-space text.
_COMMENT_PAT = re.compile(r'(?<=\S)(#\s)')
# Flow-diagram arrows: "Firecrawl        ↓Crawl4AI" → newline after the arrow.
_ARROW_PAT = re.compile(r'(↓|→|←|↑|⬇|▶|➜|➡️)\s*')


def _split_code(code: str) -> str:
    """Re-insert newlines into a single-line <code> blob (best effort)."""
    if '\n' in code:
        return code
    # Flow-diagram style: split after each arrow so every step gets its own line.
    if _ARROW_PAT.search(code):
        code = _ARROW_PAT.sub(lambda m: m.group(1) + '\n', code)
        return code.strip()
    # Directory-tree / aligned style: toutiao uses runs of 2+ spaces instead of
    # newlines (HTML collapses them when rendered). Split on those runs, keeping
    # the leading spaces of each line as indentation.
    if re.search(r'  +', code):
        code = re.sub(r'(\S)(  +)(\S)', lambda m: m.group(1) + '\n' + m.group(2) + m.group(3), code)
        return code.strip()
    code = _ENV_PAT.sub(r'\n\1', code)
    code = _CMD_PAT.sub(r'\n\1', code)
    code = _COMMENT_PAT.sub(r'\n\1', code)
    return code.strip()


def _looks_like_code(code: str) -> bool:
    """Whether a <code> blob is actual code (vs. plain text / flow diagram)."""
    return bool(_guess_lang(code))


def _guess_lang(code: str) -> str:
    """Heuristic language detection for a code block. Returns '' when unsure."""
    c = code.strip()
    if re.search(r'^\s*(def |import |from |print\(|if __name__|elif )', c, re.M):
        return 'python'
    if re.search(r'\b(public|private|protected)\s+(static\s+)?(class|void|int|String|boolean)\b', c) \
            or 'System.out.println' in c:
        return 'java'
    if re.search(r'\b(const|let|var)\s+\w+\s*=\s*(\(|async|function|require)', c) \
            or re.search(r'=>|console\.log|module\.exports', c):
        return 'javascript'
    if re.search(r'#include\s*<', c) or re.search(r'\bint\s+main\s*\(', c):
        return 'cpp'
    if re.search(r'\bfunc\s+\w+\s*\(.*\)\s*\{', c) and 'package ' in c:
        return 'go'
    if re.search(r'\b(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE)\b', c, re.I):
        return 'sql'
    # Shell: command keyword, env-var assignment, or comment line
    if re.search(r'^\s*(git |pip |cd |npm |curl |wget |sudo |apt |export |python -m'
                 r'|echo |\$ |[A-Z_]{3,}=|#\s)', c, re.M):
        return 'shell'
    if c.startswith('{') and c.endswith('}'):
        try:
            json.loads(c)
            return 'json'
        except Exception:  # noqa: BLE001
            pass
    return ''


def _fix_code_blocks(md: str) -> str:
    """Split code blobs and attach a language tag ('plaintext' when undetectable)."""
    def repl(m: re.Match) -> str:
        body = _split_code(m.group(1))
        lang = _guess_lang(body) or 'plaintext'
        return f'```{lang}\n{body}\n```'
    # ``` ... ``` blocks (markdownify emits no language tag)
    return re.sub(r'```\n(.*?)\n```', repl, md, flags=re.S)


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw.decode("utf-8", "replace")


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


def html_to_markdown(html: str) -> str:
    """Convert Toutiao's content HTML to clean Markdown with fenced code blocks."""
    try:
        from markdownify import markdownify as _md
        md = _md(
            html,
            heading_style='ATX',
            code_language='',
            strip=['script', 'style'],
        )
    except ImportError:
        # Fallback: html2text (older, merges code into indented blocks)
        try:
            import html2text
            conv = html2text.HTML2Text()
            conv.body_width = 0
            conv.ignore_links = False
            conv.ignore_images = False
            conv.unicode_snob = True
            md = conv.handle(html)
        except ImportError:
            html = re.sub(r"<img[^>]*src=[\"']([^\"']+)[\"'][^>]*>", r"![](\1)", html)
            md = strip_html(html)

    md = _fix_code_blocks(md)
    # Remove Toutiao's "open app to view image" captions and empty image links
    md = re.sub(r"打开今日头条查看图片详情", "", md)
    md = re.sub(r"!\[\]\(\s*\)", "", md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md


def main() -> None:
    url = sys.argv[1]
    out = {"type": "unknown", "title": "", "summary": "",
           "markdown": "", "author": "", "publish_time": ""}
    try:
        html = fetch(url)
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(out, ensure_ascii=False))
        sys.exit(1)

    if "/video/" in url or re.search(r"<video[\s>]", html):
        out["type"] = "video"

    title = summary = markdown = author = publish_time = ""
    m = re.search(
        r'<script id="RENDER_DATA" type="application/json">(.*?)</script>', html, re.S
    )
    if m:
        try:
            data = json.loads(urllib.parse.unquote(m.group(1)))
            for node in _walk(data):
                info = node.get("articleInfo") if isinstance(node, dict) else None
                if isinstance(info, dict):
                    title = info.get("title") or title
                    author = info.get("source") or info.get("mediaName") or author
                    publish_time = info.get("publishTime") or info.get("publish_time") or publish_time
                    content = info.get("content") or ""
                    if content:
                        summary = strip_html(content)[:300]
                        markdown = html_to_markdown(content)
                    if title or markdown:
                        break
        except Exception:  # noqa: BLE001
            pass

    if not title:
        tm = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        if tm:
            title = re.sub(r"\s+", " ", tm.group(1)).strip()
            title = re.sub(r"\s*[-_]\s*今日头条\s*$", "", title)

    if out["type"] == "unknown":
        out["type"] = "article" if markdown else out["type"]

    out.update(title=title, summary=summary, markdown=markdown,
               author=author, publish_time=publish_time)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
