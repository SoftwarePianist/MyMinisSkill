---
name: firecrawl
description: "使用 Firecrawl API 抓取单个网页或爬取整个网站，并提取干净的 Markdown 或结构化数据。当用户要求抓取网页、清理网页内容、使用 Firecrawl 或从网页提取特定字段时触发。"
version: 1.0.0
---
# Firecrawl 网页抓取与数据提取技能

此技能通过 Firecrawl 官方 API 将复杂的网页或整个网站转换为大语言模型（LLM）可以直接处理的纯净 Markdown 或结构化 JSON 数据。

## 环境变量要求

执行任务前，务必检查是否已配置 `FIRECRAWL_API_KEY` 环境变量：
```bash
[ -n "$FIRECRAWL_API_KEY" ] && echo "set" || echo "not set"
```
如果尚未设置，请提示用户前往 [设置 FIRECRAWL_API_KEY](minis://settings/environments?create_key=FIRECRAWL_API_KEY) 配置。

## 核心工具

本技能内置了开箱即用的 Python 脚本，无需安装额外依赖：
`/var/minis/skills/firecrawl/scripts/firecrawl_helper.py`

### 1. 抓取单页 (Scrape)
获取页面的纯净 Markdown：
```bash
python3 /var/minis/skills/firecrawl/scripts/firecrawl_helper.py scrape "https://example.com" > /var/minis/workspace/result.json
```
使用大模型根据 Prompt 提取结构化数据：
```bash
python3 /var/minis/skills/firecrawl/scripts/firecrawl_helper.py scrape "https://example.com" --extract "提取页面上所有的商品名称和价格" > /var/minis/workspace/extracted.json
```

### 2. 全站爬取 (Crawl)
自动解析 Sitemap 和子链接，批量爬取特定域名下的页面（默认上限10页），并等待任务完成：
```bash
python3 /var/minis/skills/firecrawl/scripts/firecrawl_helper.py crawl "https://example.com" --limit 5 --wait > /var/minis/workspace/crawl_result.json
```

## 最佳实践与注意事项

1. **重定向输出**：由于网页内容通常很长，**绝对不要**把结果直接输出到终端控制台，务必使用 `>` 重定向到 `/var/minis/workspace/` 下的 JSON 文件中，然后用 `file_read` 提取所需部分。
2. **提取 Markdown**：`scrape` 成功的返回值是一个 JSON。页面纯净内容存放在 `.data.markdown` 字段中。
3. **按需选择模式**：一般用户只是想分析单条链接的内容时，使用 `scrape` 即可。只有当明确需要深挖整个网站、抓取子链接的内容时才使用 `crawl`。
