---
name: tvbox-spider-creator
description: "根据用户提供的静态/动态影视、吃瓜、短剧等网站，生成适用于 TVBox、CatVod、影视仓等 APP 的 Python 爬虫插件脚本。当用户要求“写一个 TVBox 爬虫”、“生成影视仓 Python 脚本”或提供一个视频网站要求转为 TVBox 接口时触发。"
version: 1.0.0
---
# TVBox Spider Creator

This skill provides a structured workflow for analyzing a target video website (like MacCMS variations, gossip sites, or short-drama sites) and generating a robust, fully-featured Python spider script for the TVBox / CatVod ecosystem.

## Core Workflow

1. **Probe the Website**: 
   - Fetch the homepage of the provided URL to understand its structure, CMS type (e.g., MacCMS), and encoding.
   - Check if there are redirects (e.g., 301 to a new domain) or DNS pollution.
2. **Identify Directory Structure**:
   - Parse the top-level menus and secondary menus (dropdowns).
   - Map them to the TVBox `class` and `filters` dictionary format.
3. **Analyze Pagination and Detail URLs**:
   - Determine how the list pages are paginated (e.g., `/category/{id}/{page}/`).
   - Understand the detail page URL structure (e.g., `/archives/{vid}/`).
4. **Extract Video Data**:
   - Check the detail page HTML to find where the actual video stream (M3U8/MP4) is located. It might be in a `<video>` tag, embedded JSON (`data-config`), or requires an API call.
   - Identify if there are multiple videos per page and implement `#` separated `play_url` logic (`视频1$url1#视频2$url2`).
5. **Handle Image Encryption (If Applicable)**:
   - Check if images return binary data instead of valid JPEG/PNG headers (e.g., AES encrypted).
   - If so, implement a local HTTP proxy server inside the spider (e.g., `127.0.0.1:9980/img?url=...`) to decrypt images on the fly.
6. **Generate the Spider Script**:
   - Use the template at `/var/minis/skills/tvbox-spider-creator/templates/spider_template.py` as a baseline.
   - Inject dummy data (`vod_year="2026"`, `vod_director="管理员"`, `vod_actor="网友"`) in `detailContent` and `_parse_list` to trick TVBox into activating the advanced Carousel (轮播图) UI for themes with filters.
   - Use fake pagination totals (`total: 9999`, `pagecount: 999`) to forcefully enable TVBox's infinite scroll feature without needing to parse the exact total page count.
   - Output the finalized Python script.

## Important TVBox Spider Concepts

- **Filters vs Carousel**: If `result["filters"]` is populated in `homeContent`, TVBox switches to an advanced UI engine. In this mode, items in `result["list"]` MUST contain `vod_year`, `vod_actor`, and `vod_director` metadata, otherwise the top carousel (轮播图) will degrade into a normal grid.
- **Pagination Trick**: TVBox checks `result["pagecount"]` against the requested `page` to decide whether to trigger "load more". Returning `pagecount: 999` and `total: 9999` ensures endless scrolling until the crawler actually returns an empty list.
- **BaseSpider**: All scripts must define a `Spider` class inheriting from `base.spider.Spider` (or a mock `BaseSpider` if imported manually).
- **Anti-Ban/Dynamic Domains**: If a site uses JS-based dictionary random domain generation (e.g., `abandon.xxx.com`), replicate that logic in Python using `random.choice(words)` to make the spider resilient to DNS pollution.

## Execution

When triggered, proactively run `curl` or `python3` scripts in the shell to analyze the target URL provided by the user. Do not ask for permission to probe; act first, gather the HTML, parse the structure, build the logic, and write the `.py` file to `/var/minis/workspace/`. Finally, share the Markdown link to the generated script with the user.