---
name: samsung-wechat-tablet-login
description: >-
  在三星手机（One UI）上自动完成平板微信登录准备：停止微信，将屏幕分辨率降至 HD+、屏幕缩放降至最小，打开微信等待用户扫码；用户确认“已登录”后，将分辨率恢复到 QHD+ 并把屏幕缩放加号点击一次。适用于“登录平板微信”“用手机登录平板微信”“缩小屏幕显示微信二维码”等请求。
version: 2.3.2
---

# 三星手机登录平板微信

## 固定流程

1. 停止微信。
2. 设置 → 显示 → 屏幕分辨率：选择 **HD+ (1544×720)** 并应用。
3. 设置 → 显示 → 屏幕缩放：点击真实红色减号 `contentDesc="减小大小"`，直到最小。
4. 打开微信，确认 `com.tencent.mm` 在前台；停止自动化并等待用户扫码。微信登录页对无障碍不可见，截图也可能被系统禁止。
5. 用户明确回复“已登录/登录完成”后：分辨率恢复为 **QHD+ (3088×1440)** 并应用；屏幕缩放的 `contentDesc="增加大小"` **只点击一次**。

恢复目标由用户明确指定，不要解释成“恢复原始缩放档位”。Step 5 必须验证 QHD+ 已真正应用；只选中 QHD+ 不算完成。

## SM-S9180 快速模式（2.1）

本机已校准以下快速路径，失败一次立即回退通用识别：

1. **页面快照缓存**：同一稳定页面调用 `a11y_snapshot` 一次，后续使用 `a11y_find_cached / a11y_plan_cached / a11y_tap_cached`；页面跳转、滚动、弹窗或分辨率切换后必须 `a11y_invalidate`。
2. **缩放减号 NodeID 复用**：进入缩放页只 Dump 一次，取得 `contentDesc="减小大小"` 的 NodeID 后在同页连续点击最多 12 次，不逐次 Dump。
3. **本轮 Shizuku 缓存**：新流程只探测一次并写入 `shizukuState`。`not_running/permission_denied` 在本轮不重复 ping；新流程、用户明确启动 Shizuku、或实际 Shizuku 调用断开时才失效重测。
4. **显示页一次校准短滚**：Display Intent 后先快照；目标未出现时，SM-S9180 按当前视口执行一次中等短滚：`x=width×0.5, y=height×0.486`（QHD 约 720,1500；HD 约 360,750），再快照验证。失败才进入分段滚动，绝不默认滚到底。

## 无 Agent 离线运行（2.3）

即使 Agent 无法连接，也可打开 Minis 终端直接执行：

```sh
tablet-wechat run
```

该命令交互式完成：准备显示 → 连续打开微信两次 → 等待用户扫码 → 用户回终端按回车 → 自动恢复。

也可以分开执行：

```sh
tablet-wechat prepare            # 做到微信等待扫码
tablet-wechat restore            # 登录后恢复
tablet-wechat emergency-restore  # 中断/取消时强制恢复显示
tablet-wechat resume             # 根据状态续跑
tablet-wechat status             # 查看状态
tablet-wechat doctor             # 环境诊断
tablet-wechat log                # 查看日志
```

短紧急命令：`tablet-wechat-restore`。CLI 带单实例锁，状态和日志保存在 workspace；重复恢复由状态机防止再次点击加号。

离线说明页：`/var/minis/workspace/tablet-wechat-offline.html`。

## 脚本

```sh
SKILL=/var/minis/skills/samsung-wechat-tablet-login
. "$SKILL/scripts/workflow.sh"
```

- `scripts/ui_nodes.py`：解析 rich/minimal UI Dump，查 text/contentDesc、点击节点/父容器、视口和安全区。
- `scripts/a11y.sh`：Dump 重试、NodeID 优先点击、短距离分段滚动、目标区定位。
- `scripts/device.sh`：Shizuku、Intent、微信运行状态、停止/启动微信。
- `scripts/display.sh`：显示页、HD+/QHD+、红色减号和加号。
- `scripts/workflow.sh`：状态文件与幂等流程。

默认状态文件：

```text
/var/minis/workspace/samsung-wechat-tablet-login-state.json
```

开始新流程时执行 `state_reset`。用户回复“已登录”时执行 `workflow_login_confirmed`，然后 `workflow_restore_display`。若状态已标记 `zoomRestored=true`，不得再次点击加号。

## Step 0：预检

1. `a11y_ping` 必须成功；否则引导用户启用 Minis 无障碍服务。
2. 检查设备是否解锁；锁屏时不要坐标点击。
3. 只探测一次 Shizuku：`shizuku_ready`。
4. 进入新流程前 `state_reset`；续跑时先 `state_show`，不要重复已完成步骤。

## Step 1：停止微信

按以下优先级：

### A. Shizuku 可用

`workflow_stop_wechat` 直接执行：

```sh
android-shizuku-cli exec am force-stop com.tencent.mm
```

并通过 `pidof` 验证。最快、最确定。

### B. Shizuku 不可用且能确认微信未运行

直接跳过。不要进入应用列表或应用详情。

### C. 状态未知

按以下 Intent 链路降级：

1. 直达微信应用详情：`APPLICATION_DETAILS_SETTINGS + package:com.tencent.mm`。
2. 若未出现 `contentDesc="强制停止"`，直接打开应用程序菜单：`MANAGE_APPLICATIONS_SETTINGS`。
3. 若 OEM 不响应，再尝试 `APPLICATION_SETTINGS`。
4. 在应用程序页点击 `contentDesc="搜索应用程序"`，搜索微信并进入详情。
5. 只有上述 Intent 都失败时，才走“设置主列表 → 应用程序”。

进入详情后查找 `contentDesc="强制停止"`，优先 `tap node`，必要时处理确认弹窗。不能只根据 `android-open` 的退出码判断 Intent 失败，必须检查页面特征。

## Step 2/3：进入显示设置

优先用 Intent：

```text
android.settings.DISPLAY_SETTINGS
```

Intent 失败才走 HOME → 设置 → 显示。文字节点常 `clickable:false`，点击器必须尝试包含它的 clickable 父容器/同一行节点；不要猜固定坐标。

## 显示页滚动算法

“屏幕缩放/屏幕分辨率”位于显示页中部。**禁止把单次大距离滚动作为默认操作**，否则会越过目标到“简易模式、导航条、屏幕保护”等底部区域。

调用：

```sh
a11y_find_display_controls 7
```

规则：

1. 进入显示页先 Dump，不滚动。
2. 同时搜索锚点：`字体大小和样式`、`屏幕缩放`、`屏幕分辨率`。
3. 目标位于视口 15%～85% 安全区时立即停止。
4. 目标在底边：向下微调约 12%；在顶边：向上微调约 12%。
5. 无目标时默认一次滚动约 28%，每次滚动后重新 Dump；不能连续滚动后才检查。
6. 看到底部锚点（简易模式/导航条/屏幕保护/触摸灵敏度/防误触保护）而无目标时，向上回滚约 22%。
7. 连续两次标签集合不变，才允许一次约 55% 的降级滚动；执行后立即检查，不得连续大滚。
8. `scroll to-text found:true` 只算候选提示；必须重新 Dump 并检查目标 y 在安全区。

滚动优先 `scroll node <scrollableId> --direction ... --times 1`；minimal dump 找不到滚动容器时才用按视口比例计算的 `gesture swipe`。不使用跨分辨率固定像素坐标。

## Step 2：分辨率降为 HD+

```sh
set_resolution HD+
```

要求：

- 选择 HD+ 后验证说明文案：`基本视觉效果、最低电池使用量`。
- FHD+ 文案为“改进…中等…”，QHD+ 为“最清晰…最多…”，出现它们说明点错。
- 从最新 Dump 读取“应用” NodeID并立即点击。
- 应用后坐标系变化：立即废弃旧 NodeID 和坐标，重新 Dump。
- 最终必须读到 `HD+ (1544 x 720)`。

## Step 3：缩放降至最小

```sh
presses=$(minimize_zoom 12)
```

真正按钮：

```text
红色减号：contentDesc="减小大小"
加号：    contentDesc="增加大小"
```

“缩小/放大”只是标签，不能点击。若无滑块 progress/disabled 状态，使用有上限的 12 次点击兜底；不要无限循环，也不要把“必须点击 20 次”写死。

完成减号点击后必须按 BACK 返回一次，并通过 `normalize_to_display_list` 确认 Settings 停留在“显示”列表，而不是“屏幕缩放”子页面。这样 Step 5 会先看到“屏幕分辨率”。即使中断时仍停在子页，Step 5 也会自动识别缩放页/分辨率页并最多 BACK 两次归一化。

完成 Step 2/3 后更新状态：

```sh
workflow_lower_display
```

## Step 4：启动微信并等待用户

```sh
workflow_launch_wechat
```

- 分辨率变化后微信第一次冷启动可能闪退，因此 **固定启动两次**：第一次只预热，不作为成功依据；间隔约 0.65 秒后再次启动。
- Shizuku 可用时两次均用 monkey/launcher；不可用时两次均优先系统 Intent。
- 第二次启动后才检查前台；若仍失败，桌面微信图标降级也点击两次，然后用 `wait_package com.tencent.mm 5` 最终确认。
- 状态文件记录 `wechatLaunchAttempts=2`。
- 不尝试 OCR、截图或通过微信 UI 判断登录完成。
- 明确告诉用户：扫码后回来回复“已登录”。此时结束当前自动操作。

## Step 5：用户确认后恢复

只有用户明确确认登录后：

```sh
workflow_login_confirmed
workflow_restore_display
```

`workflow_restore_display` 是幂等的：

1. 若尚未恢复，`set_resolution QHD+`。
2. 选择后验证 `最清晰的视觉效果、最多电池使用量`。
3. 点击最新“应用”节点，最终必须读到 `QHD+ (3088 x 1440)`。
4. 若 `zoomRestored` 尚未为 true，打开屏幕缩放并把 `增加大小` 点击一次。
5. 状态置为 completed。重复收到“已登录”时不得再次点击加号。

## 错误处理

- 页面特征不匹配时禁止点击固定坐标；HOME/Intent 重新打开目标页后再 Dump。
- minimal Dump：最多重试并选取信息量最大的有效树；NodeID 只在最新 Dump 后立即使用。
- 分辨率切换后旧 NodeID/坐标全部失效。
- Step 5 部分失败要报告具体剩余项，并从状态文件续跑。
- 用户取消时说明当前显示状态，询问是否立即恢复；不要擅自恢复后继续登录。
