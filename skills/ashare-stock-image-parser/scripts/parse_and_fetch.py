#!/usr/bin/env python3
import sys
import os
import re
import json
import urllib.request
import urllib.parse
import subprocess

def run_ocr(image_path):
    """Run tesseract OCR on image and return output text."""
    try:
        res = subprocess.run(
            ["tesseract", image_path, "stdout", "-l", "chi_sim+eng"],
            capture_output=True, text=True, check=True
        )
        return res.stdout
    except Exception as e:
        try:
            res = subprocess.run(
                ["tesseract", image_path, "stdout"],
                capture_output=True, text=True, check=True
            )
            return res.stdout
        except Exception as e2:
            sys.stderr.write(f"OCR Error: {e2}\n")
            return ""

def search_stock_code(query):
    """Query Sina suggest API for stock code by name or code."""
    query = query.strip()
    if not query:
        return None
    encoded = urllib.parse.quote(query)
    url = f"http://suggest3.sinajs.cn/suggest/key={encoded}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read().decode("gbk", errors="ignore")
            items = content.split(";")
            for item in items:
                parts = item.split(",")
                if len(parts) >= 4 and parts[1] == "11":  # type 11 = A-share stock
                    name = parts[0].replace('var suggestvalue="', '').strip()
                    code_num = parts[2]
                    full_code = parts[3]
                    if full_code.startswith(("sz", "sh", "bj")):
                        return full_code, name, code_num
    except Exception as e:
        sys.stderr.write(f"Suggest API Error for {query}: {e}\n")
    return None

def fetch_quotes(full_codes):
    """Fetch quotes for full stock codes from Tencent finance API."""
    if not full_codes:
        return {}
    url = f"http://qt.gtimg.cn/q={','.join(full_codes)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    results = {}
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read().decode("gbk", errors="ignore")
            lines = content.strip().split(";\n")
            for line in lines:
                if not line.strip() or "=" not in line:
                    continue
                parts = line.split("=")
                full_code = parts[0].split("_")[-1]
                fields = parts[1].strip('"').split("~")
                if len(fields) > 34:
                    results[full_code] = {
                        "full_code": full_code,
                        "name": fields[1],
                        "code": fields[2],
                        "price": float(fields[3]),
                        "yesterday_close": float(fields[4]),
                        "open": float(fields[5]),
                        "high": float(fields[33]),
                        "low": float(fields[34]),
                        "change_amount": float(fields[31]),
                        "change_percent": float(fields[32]),
                        "datetime": fields[30]
                    }
    except Exception as e:
        sys.stderr.write(f"Quote API Error: {e}\n")
    return results

def extract_stock_names(ocr_text):
    """Clean OCR text line-by-line and extract potential stock name tokens."""
    ignore_words = {"市值", "盈亏", "成本", "现价", "持仓", "可用", "参考", "卖出", "买入", "成交", "账号", "总资产", "资金", "冻结", "收益", "比例", "数量", "人民币", "当日", "浮动", "后", "令"}
    
    candidates = []
    
    # Also look for explicit 6-digit stock codes
    code_matches = re.findall(r'\b(60\d{4}|688\d{3}|00\d{4}|30\d{4}|8\d{5})\b', ocr_text)
    for code in code_matches:
        candidates.append(code)

    for line in ocr_text.splitlines():
        if not line.strip():
            continue
        cleaned_line = line
        for _ in range(3):
            cleaned_line = re.sub(r'([\u4e00-\u9fa5])\s+([\u4e00-\u9fa5])', r'\1\2', cleaned_line)
        cleaned_line = re.sub(r'([\u4e00-\u9fa5])\s+([A-Za-z|Ａ-Ｚａ-ｚ])', r'\1\2', cleaned_line)
        cleaned_line = re.sub(r'\b(XD|ST|\*ST|N|C)\s*', '', cleaned_line)
        
        matches = re.findall(r'[\u4e00-\u9fa5]{2,6}(?:[A-Za-z|Ａ-Ｚａ-ｚ])?', cleaned_line)
        for m in matches:
            m_str = m.strip()
            if any(w in m_str for w in ignore_words):
                continue
            if len(m_str) >= 2:
                candidates.append(m_str)

    # Deduplicate preserving order
    seen = set()
    deduped = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped

def format_markdown_table(stocks):
    """Generate Markdown report table from stock quotes list."""
    if not stocks:
        return "未查询到股票行情数据。"
    
    lines = [
        "| 股票名称 | 代码 | 今日最新价 | 涨跌幅 | 涨跌额 | 今开 | 最高 | 最低 | 昨收 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    for s in stocks:
        pct_str = f"+{s['change_percent']:.2f}%" if s['change_percent'] > 0 else f"{s['change_percent']:.2f}%"
        amt_str = f"+{s['change_amount']:.2f}" if s['change_amount'] > 0 else f"{s['change_amount']:.2f}"
        line = f"| **{s['name']}** | {s['code']} | **{s['price']:.2f} 元** | {pct_str} | {amt_str} 元 | {s['open']:.2f} | {s['high']:.2f} | {s['low']:.2f} | {s['yesterday_close']:.2f} 元 |"
        lines.append(line)
    return "\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: parse_and_fetch.py <image_path>"}))
        sys.exit(1)
        
    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(json.dumps({"error": f"File not found: {image_path}"}))
        sys.exit(1)

    ocr_text = run_ocr(image_path)
    stock_candidates = extract_stock_names(ocr_text)

    found_stocks = {}
    for candidate in stock_candidates:
        res = search_stock_code(candidate)
        if res:
            full_code, name, code_num = res
            if full_code not in found_stocks:
                found_stocks[full_code] = name

    if not found_stocks:
        print(json.dumps({
            "ocr_text": ocr_text,
            "stocks": [],
            "markdown_table": "",
            "message": "未能在图片中识别出有效A股股票名称或代码。"
        }, ensure_ascii=False))
        return

    quotes = fetch_quotes(list(found_stocks.keys()))
    stock_list = list(quotes.values())
    markdown_table = format_markdown_table(stock_list)

    output_data = {
        "count": len(stock_list),
        "stocks": stock_list,
        "markdown_table": markdown_table,
        "raw_ocr": ocr_text
    }
    
    print(json.dumps(output_data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
