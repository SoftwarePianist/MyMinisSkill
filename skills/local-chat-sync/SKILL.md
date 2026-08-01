---
name: local-chat-sync
description: 在局域网内两台手机之间同步和导出 Minis 对话记录。用户说“启动对话同步端”、“发送对话到另一台手机”时触发发送端模式；用户说“接收对话”、“从另一台手机同步对话 IP是...”时触发接收端模式。
version: 1.0.0
---
# 局域网对话同步 (Local Chat Sync)

本技能用于在局域网内的两台设备之间同步 Minis 对话记录。
由于当前环境系统限制直接写入会话库，本技能会将对话导出为便于阅读的 Markdown 格式，并在接收端保存到共享文件夹中供原生预览。

## 工作模式

本技能分为**发送端 (Host)** 和 **接收端 (Client)** 两种模式。

### 1. 发送端 (Host) 模式
当用户想要把这台手机的对话发送给另一台手机时：
1. 运行导出脚本：`python3 /var/minis/skills/local-chat-sync/scripts/sync_tool.py export /tmp/chat_sync`
2. 使用后台命令启动文件服务：`cd /tmp/chat_sync && python3 -m http.server 8765 > /dev/null 2>&1 &`
3. 获取本机的局域网 IP (`hostname -I` 提取第一个IP 或 `ip -4 addr`)。
4. 告诉用户：“同步服务已启动，请在另一台手机上对 Minis 说：`接收对话，IP是 [你的IP]`”。

### 2. 接收端 (Client) 模式
当用户提供了一个 IP 地址并要求接收对话时：
1. 确认目标 IP 地址。
2. 运行导入脚本：`python3 /var/minis/skills/local-chat-sync/scripts/sync_tool.py import http://<IP>:8765/chats_export.json /var/minis/shared/synced_chats`
3. 使用 `ls /var/minis/shared/synced_chats` 列出生成的 Markdown 文件。
4. 告诉用户同步完成，并提供文件链接列表（使用 `[会话标题](minis://shared/synced_chats/文件名.md)` 格式，确保文件名进行了 URL 编码以防中文导致链接失效）供用户点击原生预览。