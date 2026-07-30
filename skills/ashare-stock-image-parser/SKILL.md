---
name: ashare-stock-image-parser
description: "识别股票持仓图片、交易界面截图或行情列表中包含的A股股票，提取股票名称和代码并查询今日最新收盘/实时价格。当用户发送股票持仓截图、行情图片并要求“查一下股票价格”、“查看这些股票最新价格”、“分析图片里的股票价格/持仓”时使用。"
version: 1.0.0
---

# A股股票截图查价技能

本技能通过 OCR 自动识别图片（持仓界面、行情列表、自选股截图等）中的 A 股股票名称或代码，并通过实时行情 API 查询最新收盘价、涨跌幅、开盘/最高/最低价。

## 适用场景

- 用户上传带有 A 股股票列表的截图（如同花顺、腾讯证券、东方财富等券商或行情软件截图）。
- 用户询问：“帮我查一下这几只股票今天的收盘价”、“看看图片里的股票现在多少钱”。

## 依赖工具

- 系统依赖：`tesseract-ocr` + `tesseract-ocr-data-chi_sim`（默认已安装，如缺少可用 `apk add tesseract-ocr tesseract-ocr-data-chi_sim`）。
- 脚本位置：`/var/minis/skills/ashare-stock-image-parser/scripts/parse_and_fetch.py`

## 执行工作流

1. **确定图片路径**
   从用户输入或附件信息中获取图片绝对路径（如 `/var/minis/attachments/uploads/xxx.jpg`）。

2. **运行解析脚本**
   使用 `shell_execute` 执行解析脚本：
   ```bash
   python3 /var/minis/skills/ashare-stock-image-parser/scripts/parse_and_fetch.py <图片绝对路径>
   ```

3. **处理与输出结果**
   - 脚本返回 JSON 格式数据，其中包含 `count`（股票数量）、`stocks`（股票报价列表）及 `markdown_table`（预格式化的 Markdown 表格）。
   - 将行情数据以清晰直观的表格形式展现给用户，并附上简单的行情汇总分析（如大盘环境、多空占比或主要涨跌股）。

## 脚本参数说明

`parse_and_fetch.py` 自动完成以下步骤：
1. 调用 `tesseract` OCR 识别图片文本，逐行清理拼音/空格/干扰字词。
2. 匹配 6 位 A 股股票代码或 2~6 字中文股票名称。
3. 通过 Sina API 将名称映射为标准交易所代码（如 `sz300058`、`sh688008`）。
4. 通过 腾讯行情 API 批量获取实时/收盘数据。
