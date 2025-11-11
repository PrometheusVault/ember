#!/bin/sh
# Lightweight battery/AC indicator for the tmux HUD.

set -e

# Choose palette similar to the rest of the HUD.
good_color="colour82"
warn_color="colour214"
crit_color="colour196"
ac_color="colour39"

print_segment() {
  color="$1"
  label="$2"
  value="$3"
  printf '#[fg=%s,bold]%s #[fg=%s]%s#[default]' "$color" "$label" "$color" "$value"
}

percent=""
state=""

# macOS support (developer laptops)
if command -v pmset >/dev/null 2>&1; then
  # Example: "Now drawing from 'Battery Power'\n -InternalBattery-0 (id=1234567)   87%; discharging; ... "
  info="$(pmset -g batt 2>/dev/null | awk 'NR==2')"
  percent="$(printf '%s' "$info" | grep -Eo '[0-9]+%' | head -n1)"
  if printf '%s' "$info" | grep -q 'charging'; then
    state="Charging"
  elif printf '%s' "$info" | grep -q 'discharging'; then
    state="Discharging"
  elif printf '%s' "$info" | grep -q 'charged'; then
    state="Full"
  fi
else
  for battery in /sys/class/power_supply/BAT*; do
    [ -d "$battery" ] || continue
    if [ -z "$percent" ] && [ -f "$battery/capacity" ]; then
      percent="$(cat "$battery/capacity" 2>/dev/null)%"
    fi
    if [ -z "$state" ] && [ -f "$battery/status" ]; then
      state="$(cat "$battery/status" 2>/dev/null)"
    fi
    [ -n "$percent" ] && break
  done

  if [ -z "$state" ] && [ -f /sys/class/power_supply/AC/online ]; then
    if [ "$(cat /sys/class/power_supply/AC/online 2>/dev/null)" = "1" ]; then
      state="AC"
    fi
  fi
fi

if [ -z "$percent" ]; then
  # Headless boards (e.g., Raspberry Pi) usually have no battery. Treat as AC.
  print_segment "$ac_color" "AC" "Powered"
  exit 0
fi

percent_value="${percent%%%%}"
color="$good_color"
case "$percent_value" in
  ''|*[!0-9]*)
    color="$ac_color"
    ;;
  *)
    if [ "$percent_value" -le 20 ]; then
      color="$crit_color"
    elif [ "$percent_value" -le 40 ]; then
      color="$warn_color"
    fi
    ;;
esac

status_label="BAT"
if [ -n "$state" ]; then
  status_label="$state"
fi

print_segment "$color" "$status_label" "$percent"
