---
name: netlify-web-deploy
description: "把网络搜索/整理的信息制作成美观的网页，并部署到用户的 Netlify 账号使其公开可访问。触发场景：用户说'把XX做成网页并部署到Netlify/公网/网上'、'把这个信息做成网页分享'、'部署网站到我的Netlify'。包含完整的网页制作规范、GitHub仓库准备、以及 Netlify API 手动部署流程（无需本地登录，用 NETLIFY_AUTH_TOKEN）。"
version: 1.0.0
---

# Netlify 网页制作与部署

把整理好的信息做成一个**美观、移动端适配**的网页，推送到 GitHub 公开仓库，并部署到用户的 Netlify 账号，最终得到一个可分享的公网链接。

## 触发条件

- 用户想把信息/新闻/内容做成网页发布
- 用户想部署网站到 Netlify 或任何公网
- 用户提到"分享链接"、"做成网页"

## 核心原则

1. **优先本地做网页，再部署**——不要在浏览器里做，用 `file_write` 生成 `index.html` + `style.css`
2. **部署用 Netlify API**（`NETLIFY_AUTH_TOKEN`），比 `netlify deploy` CLI 更可靠——CLI 常报 "No teams available"，API 手动部署不会
3. **注意 Team Protection**——新免费账号默认开启，返回 401，需用户在 `app.netlify.com` 登录一次解除
4. **token 只存环境变量，绝不明文**写入记忆/聊天/文件

## 工作流

### Step 1: 搜索并整理信息
用浏览器搜索全网信息，交叉验证多个来源（官方文档优先），整理成结构化内容。保存到 `/var/minis/workspace/`。

### Step 2: 制作网页
在 `/var/minis/workspace/<项目名>/` 创建两个文件：

- `index.html` — 语义化结构、深色科技风、含元描述、移动端优先
- `style.css` — 暗色渐变背景、卡片式布局、响应式媒体查询

参考已有可复用模板：`/var/minis/workspace/dsv4flash/`（DeepSeek V4 Flash 新闻页，包含完整的暗色科技风样式：hero、卡片、表格、时间线、要点网格、号召块）。

设计要点：
- `:root` CSS 变量统一配色（--bg、--accent、--up、--price 等）
- `.container` 最大宽度 ~900px 居中
- 表格用 `.bench-table` 包 `overflow-x:auto` 适配小屏
- 卡片 `animation: fadeUp` 渐入，`backdrop-filter: blur`
- 手机端 `<640px` 缩小 padding 和字号

完成后用浏览器 `navigate` 到 `minis://workspace/<项目名>/index.html` 截图验证视觉效果。

### Step 3: 推送到 GitHub
用 `gh` CLI（用户账号已登录，如 `SoftwarePianist`）：
```sh
cd /var/minis/workspace/<项目名>
git init -q && git add -A
git -c user.email="<账号>@users.noreply.github.com" -c user.name="<账号>" commit -q -m "<提交信息>"
gh repo create <仓库名> --public --source=. --remote=origin --description "<描述>" --push
```
> 仓库名全小写连字符（如 `deepseek-v4-flash-news`）。改名用 `gh repo rename <新名> --repo <账号>/<旧名>`，之后记得 `git remote set-url origin`。

### Step 4: 部署到 Netlify（核心）
先确认环境变量：
```sh
[ -n "$NETLIFY_AUTH_TOKEN" ] && echo set || echo "not set"
```
如果未设置，给用户链接 [Set NETLIFY_AUTH_TOKEN](minis://settings/environments?create_key=NETLIFY_AUTH_TOKEN&create_value=)，让用户粘贴 token。

**推荐：直接运行技能自带脚本**（封装了完整 API 部署流程）：
```sh
source /var/minis/skills/netlify-web-deploy/scripts/netlify_deploy.sh 2>/dev/null
chmod +x /var/minis/skills/netlify-web-deploy/scripts/netlify_deploy.sh
/var/minis/skills/netlify-web-deploy/scripts/netlify_deploy.sh /var/minis/workspace/<项目名> <站点名> <team-slug>
```
脚本自动：计算 digest → 查找/创建站点 → POST 创建部署 → zip 打包 → PUT 上传 → 轮询到 ready → 输出公网 URL。

如果脚本不可用，手动 API 流程如下：

```sh
# 环境变量需在 shell 内 source 或用 $$NETLIFY_AUTH_TOKEN 引用
TOKEN="$NETLIFY_AUTH_TOKEN"
API="https://api.netlify.com/api/v1"
TEAM_SLUG="<用户team slug，如 softwarepianist>"

# 1) 计算文件 digest
cd /var/minis/workspace/<项目名>
FILES='{"index.html":"<sha256>","style.css":"<sha256>"}'

# 2) 创建站点（如不存在）
SITE_ID=$(curl -s -X POST "$API/sites" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"<站点名>\",\"team_slug\":\"$TEAM_SLUG\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

# 3) 创建部署
DEPLOY_ID=$(curl -s -X POST "$API/sites/$SITE_ID/deploys" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"files\":$FILES}" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

# 4) 打包上传（关键：端点是 sites/{id}/deploys/{id}，不是 deploys/{id}）
zip -r /tmp/deploy.zip index.html style.css
curl -s -X PUT "$API/sites/$SITE_ID/deploys/$DEPLOY_ID" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/zip" \
  --data-binary @/tmp/deploy.zip

# 5) 轮询到 ready
curl -s "$API/sites/$SITE_ID/deploys/$DEPLOY_ID" -H "Authorization: Bearer $TOKEN"
```

### Step 5: 验证公网访问
```sh
curl -s -o /dev/null -w "%{http_code}" "https://<站点名>.netlify.app/"
```
- **200** → 部署成功，公开可访问
- **401 / 跳转 edge-access** → **Team Protection 未解除**，需用户登录 `app.netlify.com` 确认一次（新免费账号默认开启）

## 已知坑与排查

| 问题 | 原因 | 解决 |
|---|---|---|
| 访问 401 / `app.netlify.com/edge-access` | 新免费账号默认 Team Protection | 用户登录 app.netlify.com 一次，自动解除 |
| `netlify deploy` 报 "No teams available" | CLI 的 team 探测 bug | 用 API 手动部署（本技能方法） |
| PUT 上传返回 404 | 端点写错 | 用 `sites/{site_id}/deploys/{deploy_id}` 而非 `deploys/{id}` |
| 两个文件共用同一 digest | 错误地把不同文件填成同一 SHA | 每个文件单独 `sha256sum` |
| 部署卡在 uploading | zip 未真正上传 | 确认 PUT 请求带 `Content-Type: application/zip` |

## 安全须知

- `NETLIFY_AUTH_TOKEN` 是敏感凭据：**只存环境变量，绝不写进记忆、聊天、文件名或脚本明文**
- 用户把 token 发给聊天时，用完后立即删除临时文件，不要残留
- 部署完成后可主动清理 `/tmp` 下的 zip 和 token 相关临时文件
- 向用户索要 token 时，提供 [Set NETLIFY_AUTH_TOKEN](minis://settings/environments?create_key=NETLIFY_AUTH_TOKEN&create_value=) 深链让用户自己粘贴更安全

## 参考

- 已部署范例：DeepSeek V4 Flash 新闻页 → https://deepseek-v4-flash-news.netlify.app（本地 `/var/minis/workspace/dsv4flash/`，GitHub `SoftwarePianist/newsShare`）
- Netlify 手动部署 API 文档：POST `/api/v1/sites/{site_id}/deploys`（body: files digest）+ PUT `/api/v1/sites/{site_id}/deploys/{deploy_id}`（zip）
