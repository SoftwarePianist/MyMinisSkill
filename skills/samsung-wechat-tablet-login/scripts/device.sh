#!/bin/sh
# Device/Intent helpers. Shizuku is preferred but never required.

SWTL_WECHAT_PKG=${SWTL_WECHAT_PKG:-com.tencent.mm}
SWTL_SHIZUKU_STATE=${SWTL_SHIZUKU_STATE:-unknown}

shizuku_detect() {
  out=$(android-shizuku-cli service ping 2>&1); rc=$?
  if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -qi 'service is READY\|Shizuku service is running\|"ok":true'; then
    SWTL_SHIZUKU_STATE=ready
  elif printf '%s' "$out" | grep -qi 'permission.denied\|not allowed\|未授权'; then
    SWTL_SHIZUKU_STATE=permission_denied
  elif printf '%s' "$out" | grep -qi 'NOT_RUNNING\|not READY\|service is not running'; then
    SWTL_SHIZUKU_STATE=not_running
  else
    SWTL_SHIZUKU_STATE=error
  fi
  export SWTL_SHIZUKU_STATE
  if command -v state_set >/dev/null 2>&1; then state_set shizukuState "$SWTL_SHIZUKU_STATE"; fi
  [ "$SWTL_SHIZUKU_STATE" = ready ]
}

shizuku_state() {
  if [ "$SWTL_SHIZUKU_STATE" = unknown ] && command -v state_get >/dev/null 2>&1; then
    cached=$(state_get shizukuState 2>/dev/null || true)
    case "$cached" in ready|not_running|permission_denied) SWTL_SHIZUKU_STATE=$cached;; esac
  fi
  # Transient error is never trusted for the whole flow; probe again next use.
  case "$SWTL_SHIZUKU_STATE" in unknown|error) shizuku_detect >/dev/null 2>&1 || true;; esac
  printf '%s\n' "$SWTL_SHIZUKU_STATE"
}

shizuku_ready() {
  shizuku_state >/dev/null
  [ "$SWTL_SHIZUKU_STATE" = ready ]
}

shizuku_invalidate() {
  SWTL_SHIZUKU_STATE=unknown; export SWTL_SHIZUKU_STATE
  if command -v state_set >/dev/null 2>&1; then state_set shizukuState unknown; fi
}

wechat_pid() {
  shizuku_ready || return 2
  out=$(android-shizuku-cli exec pidof "$SWTL_WECHAT_PKG" 2>/dev/null) || return 1
  printf '%s' "$out" | grep -o '[0-9][0-9]*' | head -1
}

# Returns 0=running, 1=confirmed stopped, 2=unknown without Shizuku.
wechat_running_state() {
  if shizuku_ready; then
    pid=$(wechat_pid 2>/dev/null || true)
    [ -n "$pid" ] && return 0 || return 1
  fi
  info=$(android-a11y-cli ui info --quiet 2>/dev/null || true)
  printf '%s' "$info" | grep -q "$SWTL_WECHAT_PKG" && return 0
  return 2
}

open_wechat_details() {
  android-open "intent:package:${SWTL_WECHAT_PKG}#Intent;action=android.settings.APPLICATION_DETAILS_SETTINGS;end" >/dev/null 2>&1
}

open_manage_apps() {
  android-open 'intent:#Intent;action=android.settings.MANAGE_APPLICATIONS_SETTINGS;end' >/dev/null 2>&1
}

open_application_settings() {
  android-open 'intent:#Intent;action=android.settings.APPLICATION_SETTINGS;end' >/dev/null 2>&1
}

open_display_settings() {
  android-open 'intent:#Intent;action=android.settings.DISPLAY_SETTINGS;end' >/dev/null 2>&1
}

launch_wechat_once() {
  if shizuku_ready; then
    if android-shizuku-cli exec monkey -p "$SWTL_WECHAT_PKG" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; then return 0; fi
    shizuku_invalidate
  fi
  android-open "intent:#Intent;package=${SWTL_WECHAT_PKG};action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;end" >/dev/null 2>&1
}

# Resolution changes can make WeChat crash on the first cold start. Launch twice:
# the first launch is a warm-up and is never treated as final success; only the
# second launch is followed by foreground verification in workflow.sh.
launch_wechat_twice() {
  launch_wechat_once >/dev/null 2>&1 || true
  sleep 0.65
  launch_wechat_once >/dev/null 2>&1 || true
}

launch_wechat() { launch_wechat_once; }

stop_wechat_fast() {
  if shizuku_ready; then
    if ! android-shizuku-cli exec am force-stop "$SWTL_WECHAT_PKG" >/dev/null 2>&1; then shizuku_invalidate; return 2; fi
    sleep 0.3
    wechat_running_state; rc=$?
    [ "$rc" -eq 1 ]
    return
  fi
  wechat_running_state; rc=$?
  [ "$rc" -eq 1 ] && return 0       # confirmed stopped
  return 2                            # UI fallback required
}

wait_package() {
  android-a11y-cli wait activity "$1" --timeout "${2:-5}" --compact 2>/dev/null | grep -q "\"packageName\":\"$1\""
}
