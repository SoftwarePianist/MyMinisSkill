# MyMinisSkill

我在 OpenMinis 中创建和使用的技能集合。

## Skills

- `douyin-downloader`：下载抖音分享链接中的视频。
- `toutiao-downloader`：下载今日头条分享链接中的视频。
- `twitter-downloader`：下载 Twitter/X 推文中的文本与媒体。
- `video-to-markdown-summary`：将本地视频或视频链接整理成结构化 Markdown 总结。
- `yt-dlp-downloader`：使用 yt-dlp 下载 YouTube、Twitter/X 及其他受支持网站的视频。

## 目录结构

每个技能位于 `skills/<skill-name>/`，主要说明文件为 `SKILL.md`；如有辅助脚本，则放在对应技能的 `scripts/` 目录中。

## 使用方法

将需要的技能目录复制到 OpenMinis 的技能目录中，然后按其 `SKILL.md` 中的触发条件和说明使用。

## 注意

部分技能可能依赖外部命令、Python 包、网站接口或环境变量。具体依赖及限制请查看相应技能的 `SKILL.md`。
