#!/bin/sh
# State and high-level helpers for samsung-wechat-tablet-login.

SKILL_DIR=${SWTL_SKILL_DIR:-/var/minis/skills/samsung-wechat-tablet-login}
STATE_FILE=${SWTL_STATE_FILE:-/var/minis/workspace/samsung-wechat-tablet-login-state.json}
. "$SKILL_DIR/scripts/a11y.sh"
. "$SKILL_DIR/scripts/device.sh"
. "$SKILL_DIR/scripts/display.sh"

state_init() {
  mkdir -p "$(dirname "$STATE_FILE")"
  [ -f "$STATE_FILE" ] || python3 -c 'import json,sys,time; json.dump({"version":2,"startedAt":int(time.time()),"shizukuState":"unknown","wechatStopped":False,"resolutionLowered":False,"zoomMinimized":False,"wechatLaunchAttempts":0,"waitingForLogin":False,"loginConfirmed":False,"resolutionRestored":False,"zoomRestored":False,"completed":False},open(sys.argv[1],"w"),ensure_ascii=False,indent=2)' "$STATE_FILE"
}

state_get() {
  state_init
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); v=d.get(sys.argv[2]); print("true" if v is True else "false" if v is False else "" if v is None else v)' "$STATE_FILE" "$1"
}

state_set() {
  state_init; key=$1; value=$2
  python3 -c 'import json,sys,time; p,k,v=sys.argv[1:4]; d=json.load(open(p)); d[k]= True if v=="true" else False if v=="false" else int(v) if v.isdigit() else v; d["updatedAt"]=int(time.time()); json.dump(d,open(p,"w"),ensure_ascii=False,indent=2)' "$STATE_FILE" "$key" "$value"
}

state_reset() {
  rm -f "$STATE_FILE"
  SWTL_SHIZUKU_STATE=unknown; export SWTL_SHIZUKU_STATE
  state_init
}
state_show() { state_init; cat "$STATE_FILE"; }

is_wechat_details_page() {
  a11y_snapshot wechat_details 3 || return 1
  a11y_find_cached "强制停止" desc true 2>/dev/null | grep -q nodeId && \
  a11y_find_cached "打开" desc true 2>/dev/null | grep -q nodeId
}

is_manage_apps_page() {
  a11y_snapshot manage_apps 3 || return 1
  a11y_find_cached "搜索应用程序" desc true 2>/dev/null | grep -q nodeId || \
  a11y_find_cached "应用程序" text true 2>/dev/null | grep -q nodeId
}

open_wechat_from_apps_page() {
  is_manage_apps_page || return 1
  # Search control is icon-only on One UI.
  a11y_tap_cached "搜索应用程序" desc true || return 1
  a11y_invalidate; sleep 0.25
  android-a11y-cli input text 微信 >/dev/null || return 1
  sleep 0.45; a11y_snapshot wechat_results 3 || return 1
  # Filter out Minis/chat duplicates: exact matches in the upper half belong to
  # the Settings search list on the calibrated device.
  xy=$(a11y_find_cached 微信 text true | python3 -c 'import json,sys; a=json.load(sys.stdin); a=[n for n in a if n.get("y",10**9)>0]; n=sorted(a,key=lambda n:n["y"])[0]; print(n["x"],n["y"])' 2>/dev/null) || return 1
  android-a11y-cli tap xy $xy >/dev/null 2>&1 || return 1
  a11y_invalidate; sleep 0.65
  is_wechat_details_page
}

open_wechat_details_via_intents() {
  # 1) Fastest route: direct application details.
  open_wechat_details >/dev/null 2>&1 || true
  sleep 0.45; a11y_invalidate
  is_wechat_details_page && return 0
  # 2) Enter Apps directly, then search WeChat. Try the standard manage action,
  # then its OEM-compatible alias before falling back to Settings main UI.
  open_manage_apps >/dev/null 2>&1 || true
  sleep 0.45; a11y_invalidate
  open_wechat_from_apps_page && return 0
  open_application_settings >/dev/null 2>&1 || true
  sleep 0.45; a11y_invalidate
  open_wechat_from_apps_page
}

# Stop WeChat: Shizuku -> confirmed stopped -> details Intent -> Apps Intent -> UI fallback.
workflow_stop_wechat() {
  stop_wechat_fast; rc=$?
  if [ "$rc" -eq 0 ]; then state_set wechatStopped true; return 0; fi
  if ! open_wechat_details_via_intents; then
    # Last fallback: Settings main -> Apps. Keep this path only for OEM failures.
    a11y_home; a11y_invalidate; sleep 0.65
    a11y_tap_text 设置 || return 1
    wait_package com.android.settings 4 || return 1
    android-a11y-cli scroll to-text 应用程序 >/dev/null 2>&1 || true
    a11y_invalidate; sleep 0.45
    a11y_tap_text 应用程序 || return 1
    a11y_invalidate; sleep 0.55
    open_wechat_from_apps_page || return 1
  fi
  a11y_tap_cached "强制停止" desc true || {
    a11y_find_cached "打开" desc true 2>/dev/null | grep -q nodeId || return 1
  }
  a11y_invalidate; sleep 0.3
  a11y_tap_text "确定" 2>/dev/null || true
  state_set wechatStopped true
}

workflow_launch_wechat() {
  state_set wechatLaunchAttempts 0
  # First launch may flash/crash after the resolution change; always launch a
  # second time before deciding whether WeChat is ready.
  launch_wechat_twice
  state_set wechatLaunchAttempts 2
  sleep 0.55
  if ! wait_package "$SWTL_WECHAT_PKG" 2; then
    # Intent/monkey may be unavailable. Desktop fallback waits for the launcher
    # and the WeChat icon before each of the two taps.
    for attempt in 1 2; do
      a11y_home; a11y_invalidate
      wait_package com.sec.android.app.launcher 3 || true
      wait_for_text_snapshot 微信 text 8 0.35 || return 1
      a11y_tap_cached 微信 text true || return 1
      a11y_invalidate
      [ "$attempt" -eq 1 ] && sleep 0.8 || sleep 0.45
    done
    wait_package "$SWTL_WECHAT_PKG" 6 || return 1
  fi
  state_set waitingForLogin true
}

workflow_lower_display() {
  if [ "$(state_get resolutionLowered)" != true ]; then
    set_resolution HD+ || return 1
    state_set resolutionLowered true
  fi
  if [ "$(state_get zoomMinimized)" != true ]; then
    presses=$(minimize_zoom 12) || return 1
    state_set zoomMinusPresses "$presses"
    state_set zoomMinimized true
  fi
}

workflow_login_confirmed() {
  state_set loginConfirmed true
  state_set waitingForLogin false
}

workflow_restore_display() {
  [ "$(state_get loginConfirmed)" = true ] || { echo 'LOGIN_NOT_CONFIRMED' >&2; return 2; }
  if [ "$(state_get resolutionRestored)" != true ]; then
    # Step 3 may have left Settings inside the zoom fragment. Normalize before
    # looking for the Screen resolution row.
    open_display_page || return 1
    normalize_to_display_list 3 || return 1
    set_resolution QHD+ || return 1
    state_set resolutionRestored true
  fi
  # User-defined restore target: plus exactly once, never repeat on rerun.
  if [ "$(state_get zoomRestored)" != true ]; then
    increase_zoom_once || return 1
    state_set zoomRestored true
  fi
  workflow_mark_complete
}

workflow_mark_complete() {
  [ "$(state_get resolutionRestored)" = true ] || return 1
  [ "$(state_get zoomRestored)" = true ] || return 1
  state_set completed true
}
