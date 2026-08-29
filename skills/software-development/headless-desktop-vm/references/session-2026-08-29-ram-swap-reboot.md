# Session 2026-08-29 — Omarchy VM 4G + 8G Swap + Reboot

## Context
Host: 5.8G RAM, 4G swap (/swap.img), 48G disk (42G used, 6G free). Guest: Omarchy Hyprland QEMU `qemu-system-x86_64 -enable-kvm -cpu host -smp 2 -m 2560 ... -drive file=/root/omarchy/omarchy.qcow2`. User requested 4G guest, mouse latency fix, swap increase, autoclipping cleanup, reboot.

## Actions
1. **RAM 2.5G → 4G**: patched `/root/omarchy/run-vm.sh` (`-m 2560` → `-m 4096`), killed with `kill -9 $(pgrep -f "qemu.*omarchy.qcow2")` (pkill fails — 15-char limit), restarted. Verified `pgrep -a qemu | grep -o "-m [0-9]*"` → `-m 4096`. RSS just-booted 103M, later 175M (grows lazily).
2. **Swap 4G → 8G**: `swapon --show` showed /swap.img 3.7G/4G used. Added `/swap2.img` 4G via `fallocate/mkswap/swapon` + fstab. Did NOT resize primary (would require swapoff while 92% full → OOM risk). `free -h` → Swap 8.0G. `df -h /` → 46G/48G 96% (2.0G free) — tight.
3. **Disk cleanup**: autoclipping path is `/root/projects/autoclipping` (not /root/autoclipping). Removed `Outputs/*.mp4` (14 files, 165M including .raw.mp4) + `assets/clip_*.mp4` (5) + `data/endcard_tmp_*.mp4` + `~/.cache/*` (1.4G) + `apt clean`. Result: 43G/48G 91% (4.7G free), freed ~2.7G.
4. **Reboot**: `kill -9 3821195` → `bash /root/omarchy/run-vm.sh` → new PID 3831871, `-m 4096` confirmed, ports 2222/3389/5901 listening.

## Pitfalls hit
- `pkill -9 qemu-system-x86_64` → `pattern that searches for process name longer than 15 characters will result in zero matches`. Must use `pkill -f` or `pgrep -f ... | xargs kill -9`.
- `Failed to get "write" lock` on qcow2 means old QEMU still holds lock — kill harder + sleep 2s.
- `fallocate` for swap on nearly-full disk pushes to 96% — always check `df -h` before/after.
- User asked about tile layout/close: Hyprland `SUPER+J` toggles split, `SUPER+Q` closes tile, `SUPER+/` shows cheatsheet.

## Follow-ups
- Still missing `-device usb-tablet` for mouse latency — recommended but not yet patched (user didn't confirm "patch it").
- RDP (3389) available but user still on VNC; RDP would reduce latency 3-5x.
- Hyprland animations still enabled — `hyprctl keyword animations:enabled 0` would save CPU on llvmpipe.
