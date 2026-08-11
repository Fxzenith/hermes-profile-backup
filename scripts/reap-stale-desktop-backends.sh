#!/usr/bin/env bash
# reap-stale-desktop-backends.sh
# Server-side watchdog for Hermes Desktop SSH backends.
#
# WHY: The Hermes Desktop app (Windows client) spawns a detached `hermes serve
# --isolated --host 127.0.0.1 --port 0 --ssh-session-token-file ...` backend on
# the VPS and REUSES it across boots. Client bug: if the backend PID is alive
# but no longer answering (stale), the reuse probe throws and the app shows
# "Desktop boot failed - Could not verify the existing SSH backend" instead of
# respawning. The client cannot be patched server-side, so we reap stale
# backends here before the app ever tries to reuse them.
#
# Staleness rule (mirrors the client's own reuse probe):
#   - lockfile port > 0 AND HTTP probe on 127.0.0.1:port fails  -> STALE, reap
#   - lockfile port == 0 AND process older than GRACE            -> STALE, reap
#   - process answers HTTP (even 404/401)                        -> healthy, keep
#   - lockfile references a PID that no longer exists            -> remove record
#
# Safe: only touches processes whose cmdline contains --ssh-session-token-file.
# Never touches the Telegram/CLI gateway or any other hermes serve instance.
# Idempotent. Logs every action to LOG_FILE. Silent on healthy runs.

set -u

DESKTOP_SSH_DIR="${HOME}/.hermes/desktop-ssh"
LOG_FILE="${DESKTOP_SSH_DIR}/watchdog.log"
GRACE_SECONDS=180          # time a brand-new backend may take to announce its port
CURL_TIMEOUT_SECONDS=3

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "${LOG_FILE}"
}

# --- 1. Reap processes that are alive but not serving -------------------------
for tok in $(pgrep -f -- '--ssh-session-token-file' 2>/dev/null); do
  # Skip our own pgrep wrapper by verifying cmdline really is a hermes serve.
  cmdline=$(tr '\0' ' ' < /proc/${tok}/cmdline 2>/dev/null || true)
  case "${cmdline}" in
    *"serve --isolated"*) ;;
    *) continue ;;
  esac

  lstart=$(stat -c %Y /proc/${tok} 2>/dev/null || date +%s)
  now=$(date +%s)
  age=$(( now - lstart ))

  # Locate the ownership record for this PID.
  lockfile=""
  for f in ${DESKTOP_SSH_DIR}/*/backend.lock.json; do
    [ -f "${f}" ] || continue
    if grep -q "\"pid\":${tok}\b" "${f}" 2>/dev/null || grep -q "\"pid\": ${tok}" "${f}" 2>/dev/null; then
      lockfile="${f}"
      break
    fi
  done

  if [ -z "${lockfile}" ]; then
    # No ownership record: an orphaned spawn. Only reap if it is older than the
    # grace period so a mid-boot spawn is not killed.
    if [ "${age}" -ge "${GRACE_SECONDS}" ]; then
      log "reap orphan backend pid=${tok} age=${age}s (no lockfile)"
      kill "${tok}" 2>/dev/null || true
      sleep 0.5
      kill -9 "${tok}" 2>/dev/null || true
    fi
    continue
  fi

  port=$(grep -o '"port":[ ]*[0-9]*' "${lockfile}" 2>/dev/null | grep -o '[0-9]*$' || true)

  if [ -n "${port}" ] && [ "${port}" -gt 0 ] 2>/dev/null; then
    # Probe exactly like the desktop would.
    if curl -sS --max-time "${CURL_TIMEOUT_SECONDS}" -o /dev/null \
         "http://127.0.0.1:${port}/" >/dev/null 2>&1; then
      log "keep backend pid=${tok} port=${port} (answering)"
      continue
    fi
    log "reap stale backend pid=${tok} port=${port} age=${age}s (no HTTP answer)"
  else
    if [ "${age}" -lt "${GRACE_SECONDS}" ]; then
      continue # still within spawn grace window
    fi
    log "reap wedged backend pid=${tok} port=${port:-0} age=${age}s (never announced)"
  fi

  kill "${tok}" 2>/dev/null || true
  sleep 0.5
  kill -9 "${tok}" 2>/dev/null || true

  # Remove the stale ownership record so the client spawns fresh next boot.
  owner_dir=$(dirname "${lockfile}")
  if [ -d "${owner_dir}" ]; then
    rm -rf "${owner_dir}"
    log "removed ownership record ${owner_dir}"
  fi
done

# --- 2. Clean lockfiles whose PID is gone (dead backend) ----------------------
for f in ${DESKTOP_SSH_DIR}/*/backend.lock.json; do
  [ -f "${f}" ] || continue
  pid=$(grep -o '"pid":[ ]*[0-9]*' "${f}" 2>/dev/null | grep -o '[0-9]*$' || true)
  if [ -n "${pid}" ] && ! kill -0 "${pid}" 2>/dev/null; then
    owner_dir=$(dirname "${f}")
    log "clean dead-backend record pid=${pid} ${owner_dir}"
    rm -rf "${owner_dir}"
  fi
done

exit 0