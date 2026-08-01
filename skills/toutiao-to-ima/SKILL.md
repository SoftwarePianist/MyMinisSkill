---
name: toutiao-to-ima
description: "把今日头条图文链接以完整全文形式收藏到 ima 知识库。当用户发送 m.toutiao.com / toutiao.com 的头条链接，或包含头条链接的分享文本，并表达收藏/保存/存到知识库/记一下等意图时触发。先判断链接类型：图文(/article/、/group/、item_id)才处理；视频(/video/)一律跳过并改用 toutiao-downloader 技能下载。本地提取完整正文与图片 → 通过 ima-skill 建成 Markdown 笔记 → 关联进知识库对应文件夹，实现真正的全文收藏与自动分类。"
version: 1.8.0
---

# Toutiao → ima 全文收藏

只处理**图文**。视频链接不处理，交给 `toutiao-downloader`。

## 前置依赖

- 凭证：`$IMA_OPENAPI_CLIENTID` / `$IMA_OPENAPI_APIKEY` 环境变量（或 `~/.config/ima/`）。缺失时引导用户按 `ima-skill/SKILL.md` 配置。
- 运行时：Node ≥ 18（调用 `ima-skill/ima_api.cjs`）；Python 3 + `markdownify`（`pip install markdownify`，会装 beautifulsoup4）。降级链：无 markdownify → 用 `py3-html2text`（`apk add py3-html2text`），但代码块会退化为缩进式、不保留 ``` 围栏。
- API 封装：`/var/minis/skills/ima-skill/ima_api.cjs <apiPath> <bodyJson> <optsJson>`，`optsJson` 固定为 `{"clientId":"$IMA_OPENAPI_CLIENTID","apiKey":"$IMA_OPENAPI_APIKEY"}`。

## 默认目标知识库

「Cs、的知识库」kb_id: `qKu4Gf3eS2EKv4LWnMKZ_Zyk0SfhRkFtAkCBnzbZHK4=`。用户指定别的库时用 `search_knowledge_base` 解析。

## 为什么不能直接 import_urls

`import_urls` 把头条链接丢给 ima 服务端解析，但头条 `www.toutiao.com` 返回的是加密空壳页，ima 抓到的只是"打开APP查看"的占位内容，**不是完整图文**。因此必须**本地先解析出全文，再以笔记形式入库**。

## 工作流

### 1. 提取并规范 URL

从消息中抓首个头条 URL（可能被分享文案包裹），去掉末尾标点与分享参数；短链先跟随重定向拿最终落地 URL。

### 2. 判断类型（只收图文）

- `/video/<id>/` → 视频，停止并提示改用 toutiao-downloader。
- `/article/<id>/`、`/group/<id>/` → 图文，继续。
- 其他形态 → 用 `scripts/extract.py <url>` 的输出判断：`type=video` 停止，`type=article` 继续。

### 3. 本地提取完整图文

```bash
python3 /var/minis/skills/toutiao-to-ima/scripts/extract.py '<url>' > /tmp/art.json
```

返回字段：`type / title / author / publish_time / summary / markdown`。`markdown` 是完整正文（段落 + 远程图片 URL），可直接作为笔记内容。

若 `markdown` 为空或 `type=unknown`，降级：退回 `import_urls` 直接收藏链接（ima 至少能存个书签），并在回复里告诉用户"未拿到全文，已按链接收藏"。

### 4. 选择分类文件夹

1. `get_knowledge_list` 拉根目录 `media_type=99` 的文件夹列表。
2. 根据标题/摘要语义匹配最相近的；都不贴切就起一个新文件夹名（2-6 字）。
3. 新建：`openapi/wiki/v1/create_folder`，body `{"knowledge_base_id":"<kb_id>","name":"<名>"}`，返回 `data.media_id`（`folder_xxx`）作为 folder_id。

### 5. 建成 ima 笔记

用 Python 拼好 body（标题 + 来源 + 原文链接 + 正文 Markdown），再调 `import_doc`：

```python
import json
d = json.load(open('/tmp/art.json'))
content = (f"# {d['title']}\n\n"
           f"> 来源：今日头条 · {d['author']}\n"
           f"> 原文：<url>\n\n---\n\n"
           f"{d['markdown']}")
json.dump({"content_format": 1, "content": content},
          open('/tmp/doc_body.json', 'w'), ensure_ascii=False)
```

```bash
node ima_api.cjs 'openapi/note/v1/import_doc' "$(cat /tmp/doc_body.json)" "$OPTS"
# 返回 data.note_id
```

> ⛔ 必须确保 `content` 是合法 UTF-8；`extract.py` 已输出 UTF-8 JSON，直接读文件即可，不要经过 GBK 转换。

### 6. 关联笔记进知识库文件夹

```bash
node ima_api.cjs 'openapi/wiki/v1/add_knowledge' "{
  \"media_type\": 11,
  \"note_info\": {\"content_id\": \"<note_id>\"},
  \"title\": \"<标题>\",
  \"knowledge_base_id\": \"<kb_id>\",
  \"folder_id\": \"<folder_id>\"
}" "$OPTS"
```

### 7. 回复用户

```
已收藏到 ima「Cs、的知识库 / 生活」✓
《标题》
全文（含图片）已保存为笔记并入库。
```

视频：

```
这是视频链接，图文收藏不适用。要我直接用 toutiao-downloader 下载吗？
```

失败：把后端 `msg` 原样告知。

## 能力边界（用户已确认接受）

Markdown 转换的固有限制：
- ✅ 保留：标题层级（大号加粗）、正文、图片、链接、代码块（含语言标签、对齐、缩进）
- ❌ 丢失：**颜色**（如头条的红色标题）、字体、背景色——Markdown 不支持，非 bug
- 若用户坚持要颜色/完整排版：走 HTML 附件（`create_media` + COS 上传 + `add_knowledge` media_type=20），100% 还原但变成"死"文件，不可搜索、AI 问答读不到

## 注意

- **不要**把正文整段贴回聊天，只回标题 + 落点。
- **不要**暴露 kb_id / folder_id / media_id / note_id。
- 图片是头条 CDN 的远程 URL，符合 ima 笔记"仅支持网络图片"的限制；**不要**下载到本地再传。
- ima OpenAPI **无删除接口**，误操作产生的笔记/文件夹需用户在 App 手动删。
- 标签仍由 ima App 入库后 AI 自动生成，API 无法预设。
- 用户纠正过分类偏好时写入 daily memory，下次沿用。
