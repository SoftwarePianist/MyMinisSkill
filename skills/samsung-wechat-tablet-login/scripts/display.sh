#!/bin/sh
# High-level Display workflow. Source after a11y.sh and device.sh.

SWTL_SKILL_DIR=${SWTL_SKILL_DIR:-/var/minis/skills/samsung-wechat-tablet-login}
. "$SWTL_SKILL_DIR/scripts/a11y.sh"
. "$SWTL_SKILL_DIR/scripts/device.sh"

SWTL_DEVICE_MODEL=${SWTL_DEVICE_MODEL:-SM-S9180}

is_display_page_cached() {
  a11y_ensure_snapshot display 2 || return 1
  python3 "$UI_PARSER" "$UI_DUMP" find "亮度" --field text 2>/dev/null | grep -q nodeId && \
  python3 "$UI_PARSER" "$UI_DUMP" find "屏幕模式" --field text 2>/dev/null | grep -q nodeId
}

is_display_page() {
  a11y_snapshot display 3 || return 1
  is_display_page_cached
}

is_zoom_subpage_cached() {
  a11y_ensure_snapshot page_kind 2 || return 1
  a11y_find_cached 减小大小 desc true 2>/dev/null | grep -q nodeId && \
  a11y_find_cached 增加大小 desc true 2>/dev/null | grep -q nodeId
}

is_resolution_subpage_cached() {
  a11y_ensure_snapshot page_kind 2 || return 1
  for q in HD+ FHD+ QHD+ 应用; do
    a11y_find_cached "$q" text true 2>/dev/null | grep -q nodeId || return 1
  done
}

# Normalize the Settings task stack to the Display list. DISPLAY_SETTINGS may
# resume the last child fragment instead of the list itself.
normalize_to_display_list() {
  tries=${1:-3}; i=1
  while [ "$i" -le "$tries" ]; do
    a11y_snapshot page_kind 3 || return 1
    is_display_page_cached && return 0
    if is_zoom_subpage_cached || is_resolution_subpage_cached; then
      a11y_back; a11y_invalidate; sleep 0.55; i=$((i+1)); continue
    fi
    return 1
  done
  a11y_snapshot display 3 || return 1
  is_display_page_cached
}

# SM-S9180 calibrated fast path: one moderate Settings scroll at the current
# resolution, then one verification snapshot. It never scrolls to the bottom.
display_fast_seek() {
  a11y_ensure_snapshot display_controls 2 || return 1
  for q in 屏幕分辨率 屏幕缩放; do
    [ "$(python3 "$UI_PARSER" "$UI_DUMP" zone "$q" --field text --exact)" = safe ] && return 0
  done
  [ "$SWTL_DEVICE_MODEL" = SM-S9180 ] || return 1
  dims=$(python3 "$UI_PARSER" "$UI_DUMP" viewport)
  w=$(printf '%s' "$dims" | python3 -c 'import json,sys; print(json.load(sys.stdin)["width"])')
  h=$(printf '%s' "$dims" | python3 -c 'import json,sys; print(json.load(sys.stdin)["height"])')
  [ "$w" -gt 0 ] && [ "$h" -gt 0 ] || return 1
  android-a11y-cli scroll xy "$((w/2))" "$((h*486/1000))" >/dev/null 2>&1 || return 1
  a11y_invalidate; sleep 0.45
  a11y_snapshot display_controls 2 || return 1
  for q in 屏幕分辨率 屏幕缩放; do
    [ "$(python3 "$UI_PARSER" "$UI_DUMP" zone "$q" --field text --exact)" = safe ] && return 0
  done
  return 1
}

wait_for_text_snapshot() {
  q=$1; field=${2:-text}; tries=${3:-5}; delay=${4:-0.35}; i=1
  while [ "$i" -le "$tries" ]; do
    a11y_invalidate
    if a11y_snapshot wait_page 2 && a11y_find_cached "$q" "$field" true 2>/dev/null | grep -q nodeId; then return 0; fi
    sleep "$delay"; i=$((i+1))
  done
  return 1
}

open_display_page() {
  # Terminal/offline mode can regain focus while an Intent is launching. Issue
  # the Intent in a short command and verify by page features, retrying once.
  for attempt in 1 2; do
    open_display_settings >/dev/null 2>&1 || true
    sleep 0.65; a11y_invalidate
    if wait_package com.android.settings 2; then
      a11y_invalidate
      normalize_to_display_list 3 && return 0
    fi
  done
  # UI fallback: wait for the launcher and the Settings icon, never tap early.
  a11y_home; a11y_invalidate
  wait_package com.sec.android.app.launcher 3 || true
  wait_for_text_snapshot 设置 text 8 0.35 || return 1
  a11y_tap_cached 设置 text true || return 1
  a11y_invalidate
  wait_package com.android.settings 5 || return 1
  android-a11y-cli scroll to-text 显示 >/dev/null 2>&1 || true
  sleep 0.65; a11y_invalidate
  if ! wait_for_text_snapshot 显示 text 5 0.3; then return 1; fi
  a11y_tap_cached 显示 text true || return 1
  a11y_invalidate; sleep 0.7
  wait_for_text_snapshot 亮度 text 5 0.3 || return 1
  a11y_find_cached 屏幕模式 text false 2>/dev/null | grep -q nodeId
}

ensure_display_controls() {
  if ! is_display_page_cached; then open_display_page || return 1; fi
  display_fast_seek && return 0
  a11y_find_display_controls 7
}

open_display_control() {
  label=$1
  ensure_display_controls || return 1
  a11y_tap_text "$label" || return 1
  sleep 0.6
}

is_resolution_page_cached() {
  a11y_ensure_snapshot resolution 2 || return 1
  for q in HD+ FHD+ QHD+ 应用; do
    python3 "$UI_PARSER" "$UI_DUMP" find "$q" --field text --exact 2>/dev/null | grep -q nodeId || return 1
  done
}

is_resolution_page() { a11y_snapshot resolution 3 && is_resolution_page_cached; }

resolution_description_ok_cached() {
  target=$1; a11y_ensure_snapshot resolution_selected 2 || return 1
  case "$target" in
    HD+) grep -q '基本视觉效果、最低电池使用量' "$UI_DUMP" ;;
    FHD+) grep -q '改进的视觉效果、中等电池使用量' "$UI_DUMP" ;;
    QHD+) grep -q '最清晰的视觉效果、最多电池使用量' "$UI_DUMP" ;;
    *) return 1 ;;
  esac
}

resolution_value_visible_cached() {
  target=$1; a11y_ensure_snapshot display_value 2 || return 1
  case "$target" in
    HD+) grep -q 'HD+ (1544 x 720)' "$UI_DUMP" ;;
    FHD+) grep -q 'FHD+ (2316 x 1080)' "$UI_DUMP" ;;
    QHD+) grep -q 'QHD+ (3088 x 1440)' "$UI_DUMP" ;;
    *) return 1 ;;
  esac
}

set_resolution() {
  target=$1
  case "$target" in HD+|FHD+|QHD+) ;; *) return 2;; esac
  open_display_page || return 1
  ensure_display_controls || return 1
  # Reuse the existing Display snapshot from fast seek.
  resolution_value_visible_cached "$target" && return 0
  a11y_tap_cached "屏幕分辨率" text true || return 1
  a11y_invalidate; sleep 0.45
  is_resolution_page || return 1
  # Reuse one resolution-page snapshot to locate all options.
  a11y_tap_cached "$target" text true || return 1
  a11y_invalidate; sleep 0.25
  a11y_snapshot resolution_selected 2 || return 1
  resolution_description_ok_cached "$target" || return 1
  # Selection may redraw the page; take one fresh snapshot for Apply.
  a11y_tap_cached "应用" text true || return 1
  a11y_invalidate; sleep 0.9
  # All old node IDs and coordinates are invalid after Apply.
  a11y_snapshot display_value 4 || return 1
  resolution_value_visible_cached "$target"
}

is_zoom_page_cached() {
  a11y_ensure_snapshot zoom 2 || return 1
  python3 "$UI_PARSER" "$UI_DUMP" find "减小大小" --field desc --exact 2>/dev/null | grep -q nodeId && \
  python3 "$UI_PARSER" "$UI_DUMP" find "增加大小" --field desc --exact 2>/dev/null | grep -q nodeId
}

open_zoom_page() {
  open_display_page || return 1
  ensure_display_controls || return 1
  a11y_tap_cached "屏幕缩放" text true || return 1
  a11y_invalidate; sleep 0.4
  a11y_snapshot zoom 3 || return 1
  is_zoom_page_cached
}

minimize_zoom() {
  cap=${1:-12}
  open_zoom_page || return 1
  # One snapshot, one NodeID, bounded rapid taps on the same stable page.
  plan=$(a11y_plan_cached "减小大小" desc true) || return 1
  node=$(printf '%s' "$plan" | python3 -c 'import json,sys; print(json.load(sys.stdin)["tap"].get("nodeId",""))')
  [ -n "$node" ] || return 1
  i=0
  while [ "$i" -lt "$cap" ]; do
    android-a11y-cli tap node "$node" >/dev/null 2>&1 || break
    i=$((i+1))
  done
  # Leave Settings on the Display list, not inside the Screen zoom fragment.
  a11y_invalidate
  a11y_back; sleep 0.55; a11y_invalidate
  if ! normalize_to_display_list 2; then
    # The zoom action itself succeeded; later open_display_page can still repair
    # the stack. Do not lose the press count because of a transient dump failure.
    a11y_invalidate
  fi
  printf '%s\n' "$i"
}

increase_zoom_once() {
  open_zoom_page || return 1
  a11y_tap_cached "增加大小" desc true
  a11y_invalidate
}
