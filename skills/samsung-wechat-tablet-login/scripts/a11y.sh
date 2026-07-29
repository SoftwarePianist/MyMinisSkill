#!/bin/sh
# Robust Accessibility helpers for Samsung One UI.
# POSIX sh; JSON parsing is delegated to ui_nodes.py.

SKILL_DIR=${SWTL_SKILL_DIR:-/var/minis/skills/samsung-wechat-tablet-login}
UI_PARSER="$SKILL_DIR/scripts/ui_nodes.py"
UI_DUMP=${SWTL_UI_DUMP:-/tmp/swtl_ui.json}
UI_SNAPSHOT_VALID=false
UI_SNAPSHOT_NAME=""

_a11y_json_ok() { python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$1" >/dev/null 2>&1; }

a11y_ping() { android-a11y-cli service ping 2>&1 | grep -qi 'running\|"ok":true'; }
a11y_home() { android-a11y-cli input key HOME >/dev/null 2>&1; }
a11y_back() { android-a11y-cli input key BACK >/dev/null 2>&1; }
a11y_foreground() { android-a11y-cli ui info --quiet 2>/dev/null; }

# Dump retries because One UI can transiently return a minimal tree.
a11y_dump() {
  out=${1:-$UI_DUMP}; tries=${2:-3}; best=""; best_size=0; i=1
  while [ "$i" -le "$tries" ]; do
    tmp="${out}.try.$i"
    android-a11y-cli ui dump --compact 2>/dev/null > "$tmp" || true
    if _a11y_json_ok "$tmp"; then
      size=$(wc -c < "$tmp")
      [ "$size" -gt "$best_size" ] && best="$tmp" && best_size=$size
      # A rich enough tree generally has text/contentDesc and multiple nodes.
      if grep -q '"text"\|"contentDesc"' "$tmp" && [ "$size" -ge 1800 ]; then best="$tmp"; break; fi
    fi
    i=$((i+1)); [ "$i" -le "$tries" ] && sleep 0.35
  done
  [ -n "$best" ] || return 1
  cp "$best" "$out"; rm -f "${out}.try."*; return 0
}

a11y_snapshot() {
  UI_SNAPSHOT_NAME=${1:-page}
  a11y_dump "$UI_DUMP" "${2:-3}" || { UI_SNAPSHOT_VALID=false; return 1; }
  UI_SNAPSHOT_VALID=true
}

a11y_invalidate() { UI_SNAPSHOT_VALID=false; UI_SNAPSHOT_NAME=""; }

a11y_ensure_snapshot() {
  [ "$UI_SNAPSHOT_VALID" = true ] && [ -s "$UI_DUMP" ] && return 0
  a11y_snapshot "${1:-page}" "${2:-3}"
}

a11y_find_cached() {
  q=$1; field=${2:-any}; exact=${3:-false}
  a11y_ensure_snapshot || return 1
  if [ "$exact" = true ]; then python3 "$UI_PARSER" "$UI_DUMP" find "$q" --field "$field" --exact
  else python3 "$UI_PARSER" "$UI_DUMP" find "$q" --field "$field"; fi
}

a11y_plan_cached() {
  q=$1; field=${2:-any}; exact=${3:-false}
  a11y_ensure_snapshot || return 1
  if [ "$exact" = true ]; then python3 "$UI_PARSER" "$UI_DUMP" tap-plan "$q" --field "$field" --exact
  else python3 "$UI_PARSER" "$UI_DUMP" tap-plan "$q" --field "$field"; fi
}

a11y_tap_cached() {
  q=$1; field=${2:-any}; exact=${3:-false}
  plan=$(a11y_plan_cached "$q" "$field" "$exact") || return 1
  node=$(printf '%s' "$plan" | python3 -c 'import json,sys; print(json.load(sys.stdin)["tap"].get("nodeId", ""))')
  x=$(printf '%s' "$plan" | python3 -c 'import json,sys; print(json.load(sys.stdin)["tap"].get("x", -1))')
  y=$(printf '%s' "$plan" | python3 -c 'import json,sys; print(json.load(sys.stdin)["tap"].get("y", -1))')
  if [ -n "$node" ]; then android-a11y-cli tap node "$node" >/dev/null 2>&1 && return 0; fi
  [ "$x" -ge 0 ] && [ "$y" -ge 0 ] || return 1
  android-a11y-cli tap xy "$x" "$y" >/dev/null 2>&1
}

a11y_viewport() { a11y_snapshot viewport 2 || return 1; python3 "$UI_PARSER" "$UI_DUMP" viewport; }
a11y_labels() { a11y_snapshot labels 2 || return 1; python3 "$UI_PARSER" "$UI_DUMP" labels; }
a11y_signature() { a11y_snapshot signature 2 || return 1; python3 "$UI_PARSER" "$UI_DUMP" signature; }

a11y_plan() {
  q=$1; field=${2:-any}; exact=${3:-false}
  a11y_dump "$UI_DUMP" 3 || return 1
  if [ "$exact" = true ]; then python3 "$UI_PARSER" "$UI_DUMP" tap-plan "$q" --field "$field" --exact
  else python3 "$UI_PARSER" "$UI_DUMP" tap-plan "$q" --field "$field"; fi
}

a11y_tap() {
  q=$1; field=${2:-any}; exact=${3:-false}
  plan=$(a11y_plan "$q" "$field" "$exact") || { echo "TAP_FAIL:$q" >&2; return 1; }
  node=$(printf '%s' "$plan" | python3 -c 'import json,sys; print(json.load(sys.stdin)["tap"].get("nodeId", ""))')
  x=$(printf '%s' "$plan" | python3 -c 'import json,sys; print(json.load(sys.stdin)["tap"].get("x", -1))')
  y=$(printf '%s' "$plan" | python3 -c 'import json,sys; print(json.load(sys.stdin)["tap"].get("y", -1))')
  if [ -n "$node" ]; then
    android-a11y-cli tap node "$node" >/dev/null 2>&1 && { a11y_invalidate; return 0; }
  fi
  [ "$x" -ge 0 ] && [ "$y" -ge 0 ] || return 1
  android-a11y-cli tap xy "$x" "$y" >/dev/null 2>&1 && a11y_invalidate
}

a11y_tap_desc() { a11y_tap "$1" desc true; }
a11y_tap_text() { a11y_tap "$1" text true; }
a11y_wait() { android-a11y-cli wait appear "$1" --timeout "${2:-10}" --compact 2>/dev/null | grep -q '"found":true'; }

a11y_has() {
  q=$1; field=${2:-any}
  a11y_dump "$UI_DUMP" 2 || return 1
  python3 "$UI_PARSER" "$UI_DUMP" find "$q" --field "$field" 2>/dev/null | grep -q 'nodeId'
}

# One controlled scroll. Prefer the actual scrollable node; use a proportional
# gesture only when One UI emits a minimal tree without scrollable metadata.
a11y_scroll_percent() {
  direction=$1; percent=${2:-30}
  a11y_dump "$UI_DUMP" 3 || return 1
  scroll=$(python3 "$UI_PARSER" "$UI_DUMP" scrollable 2>/dev/null || true)
  node=$(printf '%s' "$scroll" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("nodeId",""))' 2>/dev/null || true)
  if [ -n "$node" ]; then
    android-a11y-cli scroll node "$node" --direction "$direction" --times 1 >/dev/null 2>&1 && { a11y_invalidate; return 0; }
  fi
  dims=$(python3 "$UI_PARSER" "$UI_DUMP" viewport)
  w=$(printf '%s' "$dims" | python3 -c 'import json,sys; print(json.load(sys.stdin)["width"])')
  h=$(printf '%s' "$dims" | python3 -c 'import json,sys; print(json.load(sys.stdin)["height"])')
  [ "$w" -gt 0 ] && [ "$h" -gt 0 ] || return 1
  x=$((w/2)); delta=$((h*percent/100)); mid=$((h/2))
  if [ "$direction" = down ]; then start=$((mid+delta/2)); end=$((mid-delta/2));
  else start=$((mid-delta/2)); end=$((mid+delta/2)); fi
  android-a11y-cli gesture swipe "$x" "$start" "$x" "$end" >/dev/null 2>&1 && a11y_invalidate
}

# Classify a visible target: safe / above / below / absent.
a11y_target_zone() {
  q=$1
  a11y_ensure_snapshot zone 2 || return 1
  python3 "$UI_PARSER" "$UI_DUMP" zone "$q" --field text --exact
}

# Locate the Display target zone without jumping straight to the bottom.
# Default increments are 28%; edge correction is 12–22%; one 55% retry is
# allowed only after two proven no-op scrolls.
a11y_find_display_controls() {
  attempts=${1:-7}; i=1; last_sig=""; no_move=0
  while [ "$i" -le "$attempts" ]; do
    a11y_snapshot display_seek 3 || return 1
    zone=absent
    for target in 屏幕分辨率 屏幕缩放 字体大小和样式; do
      z=$(a11y_target_zone "$target" 2>/dev/null || echo absent)
      [ "$z" != absent ] && zone=$z && break
    done
    [ "$zone" = safe ] && return 0
    sig=$(python3 "$UI_PARSER" "$UI_DUMP" signature)
    [ "$sig" = "$last_sig" ] && no_move=$((no_move+1)) || no_move=0
    last_sig=$sig
    if [ "$zone" = below ]; then
      a11y_scroll_percent down 12
    elif [ "$zone" = above ]; then
      a11y_scroll_percent up 12
    elif printf '%s' "$sig" | grep -q '简易模式\|导航条\|屏幕保护\|触摸灵敏度\|防误触保护'; then
      a11y_scroll_percent up 22
    elif [ "$no_move" -ge 2 ]; then
      a11y_scroll_percent down 55; no_move=0
    else
      a11y_scroll_percent down 28
    fi
    sleep 0.8; i=$((i+1))
  done
  return 1
}

# Press a contentDesc button to its limit, with a hard cap. Samsung's zoom
# preview changes visually but the exposed labels/signature stay constant, so
# signature equality is NOT a valid stop condition. Stop only on disabled state;
# when enabled/progress is unavailable, use the bounded cap.
a11y_press_until_stable() {
  desc=$1; cap=${2:-12}; i=0
  while [ "$i" -lt "$cap" ]; do
    a11y_dump "$UI_DUMP" 2 || return 1
    node=$(python3 "$UI_PARSER" "$UI_DUMP" find "$desc" --field desc --exact 2>/dev/null) || return 1
    printf '%s' "$node" | grep -q '"nodeId"' || break
    printf '%s' "$node" | grep -q '"enabled": false' && break
    a11y_tap_desc "$desc" || return 1
    i=$((i+1)); sleep 0.18
  done
  printf '%s\n' "$i"
}
