#!/bin/sh
# netlify_deploy.sh - 部署静态网页目录到 Netlify 的可靠脚本
# 用法: netlify_deploy.sh <部署目录> [站点名] [团队slug]
# 依赖: curl, NETLIFY_AUTH_TOKEN 环境变量
# 参考: Netlify API 手动部署 (POST deploys digest + PUT zip)

set -e

DEPLOY_DIR="${1:?用法: netlify_deploy.sh <部署目录> [站点名] [团队slug]}"
SITE_NAME="${2:-$(basename "$DEPLOY_DIR" | tr '._ ' '---' | tr '[:upper:]' '[:lower:]')}"
TEAM_SLUG="${3:-softwarepianist}"

# ---- 安全：token 只从环境变量读取，绝不明文落盘 ----
if [ -z "$NETLIFY_AUTH_TOKEN" ]; then
  echo "❌ 未设置 NETLIFY_AUTH_TOKEN 环境变量" >&2
  echo "   请先设置: 见 minis://settings/environments?create_key=NETLIFY_AUTH_TOKEN&create_value=" >&2
  exit 1
fi
TOKEN="$NETLIFY_AUTH_TOKEN"
API="https://api.netlify.com/api/v1"

# ---- 校验目录 ----
if [ ! -d "$DEPLOY_DIR" ]; then
  echo "❌ 目录不存在: $DEPLOY_DIR" >&2; exit 1
fi
[ -f "$DEPLOY_DIR/index.html" ] || { echo "❌ 目录缺少 index.html" >&2; exit 1; }

# ---- 1. 计算所有文件 digest ----
echo "📦 计算文件 digest ..."
FILES_JSON=""
ZIPLIST=""
cd "$DEPLOY_DIR"
for f in $(find . -type f | sed 's|^\./||'); do
  [ -e "$f" ] || continue
  sha=$(sha256sum "$f" | awk '{print $1}')
  FILES_JSON="$FILES_JSON\"$f\":\"$sha\","
  ZIPLIST="$ZIPLIST $f"
done
FILES_JSON="{$(echo "$FILES_JSON" | sed 's/,$//')}"

# ---- 2. 查找或创建站点 ----
echo "🔍 查找站点 $SITE_NAME ..."
SITE_ID=$(curl -s "$API/sites?name=$SITE_NAME" -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(d[0]['id'] if d else '')" 2>/dev/null)

if [ -z "$SITE_ID" ]; then
  echo "🆕 站点不存在，创建 $SITE_NAME ..."
  SITE_ID=$(curl -s -X POST "$API/sites" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"name\":\"$SITE_NAME\",\"team_slug\":\"$TEAM_SLUG\"}" \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
  echo "   站点创建成功: id=$SITE_ID"
else
  echo "   站点已存在: id=$SITE_ID"
fi

# ---- 3. 创建部署 (digest) ----
echo "🚀 创建部署请求 ..."
DEPLOY_JSON=$(curl -s -X POST "$API/sites/$SITE_ID/deploys" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"files\":$FILES_JSON}")
DEPLOY_ID=$(echo "$DEPLOY_JSON" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
STATE=$(echo "$DEPLOY_JSON" | python3 -c "import sys,json;print(json.load(sys.stdin).get('state'))")
echo "   deploy_id=$DEPLOY_ID state=$STATE"

# ---- 4. 打包 zip 并上传 (注意端点是 sites/{id}/deploys/{id}) ----
echo "🗜️ 打包并上传 ..."
ZIP=/tmp/netlify_deploy_$$.zip
rm -f "$ZIP"
which zip >/dev/null 2>&1 || apk add zip >/dev/null 2>&1
zip -q -r "$ZIP" . -x '*.git*' 2>/dev/null || zip -q -r "$ZIP" *
UP=$(curl -s -X PUT "$API/sites/$SITE_ID/deploys/$DEPLOY_ID" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/zip" \
  --data-binary @"$ZIP")
rm -f "$ZIP"
NEWSTATE=$(echo "$UP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('state'))")
echo "   上传后 state=$NEWSTATE"

# ---- 5. 轮询直到 ready ----
echo "⏳ 等待发布 ..."
for i in 1 2 3 4 5 6 7 8; do
  sleep 3
  S=$(curl -s "$API/sites/$SITE_ID/deploys/$DEPLOY_ID" -H "Authorization: Bearer $TOKEN" \
    | python3 -c "import sys,json;print(json.load(sys.stdin).get('state'))")
  echo "   [$i] $S"
  [ "$S" = "ready" ] && break
done

# ---- 6. 输出结果 ----
URL="https://$SITE_NAME.netlify.app"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL/")
echo ""
echo "✅ 部署完成！"
echo "   公网地址: $URL"
echo "   HTTP状态: $CODE"
if [ "$CODE" = "200" ]; then
  echo "   站点可公开访问 ✓"
else
  echo "   ⚠️ 非200，可能触发了 Team Protection，需账号所有者登录 app.netlify.com 确认一次"
fi
