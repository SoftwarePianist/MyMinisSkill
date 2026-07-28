---
name: video-to-markdown-summary
description: 将本地视频、聊天附件或视频分享链接整理成结构化 Markdown 总结文档。用户说“总结这个视频”“根据视频生成 Markdown/笔记/教程/操作指南”“提取视频要点并保存成文档”时使用。结合字幕或语音转写、定时取帧、画面 OCR、项目/网页资料交叉核验；在无法完整转写时明确证据边界，不把画面推断冒充逐字内容。
version: 1.0.0
---
# Video to Markdown Summary

把视频内容整理成准确、可下载的 Markdown 文档，并保存到 `/var/minis/workspace/`。

## Workflow

### 1. 获取视频

- 本地附件：在 `/var/minis/attachments/` 查找对应视频，不扫描整个文件系统。
- 分享链接：先使用匹配的下载 skill（如 Toutiao、Douyin、yt-dlp），下载到 attachments。
- 用户同时提供标题或来源链接时保留，便于核验背景资料。

### 2. 按可靠性收集内容

优先级从高到低：

1. 视频自带字幕、字幕文件或用户提供的文字稿。
2. 可用 ASR 生成的语音转写。
3. 定时取帧、画面 OCR、界面操作顺序和可见字幕。
4. 视频标题、简介、来源页面及官方文档，用于补充和核验，不能代替视频内容。

先检查媒体：

```sh
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height -of default=nw=1 'VIDEO'
```

如需提取证据，运行 bundled script：

```sh
python3 /var/minis/skills/video-to-markdown-summary/scripts/extract_evidence.py 'VIDEO' --output /var/minis/workspace/video_evidence
```

脚本会生成：

- `metadata.txt`：时长、编码和分辨率
- `frames/`：按时间间隔提取的画面
- `ocr.txt`：画面文字（已安装 Tesseract 时）
- `contact-sheet.jpg`：关键帧总览

用 `read_image` 查看总览，再查看包含关键设置、步骤或结论的单帧。OCR 只能作为线索，界面小字必须通过原图复核。

### 3. 语音转写

- 优先使用环境中已有且已配置的 ASR 工具。
- 若使用 Volcano ASR，先只检查 `VOLC_APP_KEY` 和 `VOLC_ACCESS_KEY` 是否为 set，绝不输出值；可调用 Douyin downloader skill 中的 `transcribe_audio.py`。
- 无 ASR 凭据时，不要求用户必须配置；继续使用画面、OCR、字幕和可信资料完成“基于可见内容”的总结。
- 没有完整转写时，文末注明“本文并非逐字转录”。

### 4. 必要时交叉核验

当视频讲解软件、项目、产品或系统设置时，可读取其官方网站、GitHub README 或厂商文档，核对：

- 功能名称和版本要求
- 权限与菜单路径
- 已知兼容性问题
- 下载地址及安全注意事项

区分“视频中展示”和“外部资料补充”，不要把外部信息写成视频原话。

### 5. 编写 Markdown

根据视频类型调整结构，不机械套模板。

教程/设置类建议结构：

```markdown
# 标题

> 视频来源、主题、适用设备/版本

## 核心结论
## 使用前提
## 操作步骤
## 主要功能或设置说明
## 推荐配置
## 注意事项与排错
## 一句话总结
## 相关链接

---
*证据与转写范围说明*
```

知识讲解类可改为：背景、核心观点、论据、案例、结论、行动建议。测评类可改为：产品定位、优点、缺点、适用人群、购买建议。

写作要求：

- 提炼内容，不堆砌 OCR 碎片。
- 操作步骤使用有序列表；选项和路径加粗或使用代码格式。
- 保留重要版本、权限、兼容性和风险信息。
- 不确定内容使用“视频显示”“可能”“建议核实”等表述。
- 不编造讲者未表达的观点，也不声称是逐字稿。
- 默认使用与用户相同的语言。

### 6. 保存并交付

- 文件名采用简洁、可识别的中文或英文标题，扩展名 `.md`。
- 使用 `file_write` 创建 `/var/minis/workspace/<标题>.md`。
- 最终回复简短列出文档涵盖内容，并提供可点击的 `minis://workspace/...` Markdown 链接。
- 用户未要求时，不附带全部正文；让用户点击预览或下载。

## Accuracy rules

- 画面 OCR 错误率可能很高，必须结合截图人工确认。
- 只有画面证据时，不能声称完整覆盖旁白。
- 外部文档只能用于核验和补充，并在文中说明。
- 涉及系统菜单时提醒：名称可能随设备地区、系统版本变化。
- 涉及第三方 APK、通知读取、无障碍或设备管理权限时，明确隐私与安全风险。

## Tool fallback

如缺少基础工具：

```sh
command -v ffmpeg >/dev/null 2>&1 || apk add ffmpeg
command -v tesseract >/dev/null 2>&1 || apk add tesseract-ocr tesseract-ocr-data-chi_sim tesseract-ocr-data-eng
```

如果无法安装 OCR，也可仅取帧后用 `read_image` 人工分析关键画面。
