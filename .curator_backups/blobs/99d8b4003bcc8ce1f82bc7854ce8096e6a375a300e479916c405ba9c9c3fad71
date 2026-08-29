# Session 2026-08-29 — SPICE + Open-to-0.0.0.0 + Display Matrix

## Host probes (read-only, before write)
- QEMU 8.2.2 (`qemu-system-x86_64 -display help` → none/gtk/sdl/egl-headless/curses/spice-app/dbus; `-vga help` → qxl+virtio; `-device ?` → virtio-gpu-gl, virtio-vga-gl, qxl, usb-tablet present)
- `dpkg -l` → qemu-system-modules-opengl/spice/gui 8.2.2, libvirglrenderer 1.0.0, libspice-server 0.15.1, .so for egl-headless/opengl/qxl/spice-core/app present
- `ss -tlnp` → 2222/3389 0.0.0.0 (QEMU hostfwd), 5901 127.0.0.1 (VNC), after patch 5930 127.0.0.1 then 0.0.0.0 (SPICE), then 5901/5930 0.0.0.0 after explicit user request
- `free/df/swapon` → 5.8G RAM 136M free/278M avail critical, 8G swap 3.9G used, 48G disk 94% (3.2G avail) — worse than morning 91% after cleanup; load 2.59, QEMU 100% CPU / 3.1G RSS
- `/dev/dri/card0` exists, no `renderD128` → VirGL would be llvmpipe CPU fallback only
- Guest `ssh -p 2222` banner timeout (120s, 3 attempts inc. ssh -vvv) but `nc -vz 127.0.0.1 2222` open — hostfwd TCP OK, guest getty slow. Spice-vdagent/qemu-guest-agent not installed on guest for this reason.

## Decision matrix (scored A-F, 1-5)
Created `.hermes/plans/omarchy-display-matrix.md` + `.hermes/plans/baseline.md`:
- A SPICE+QXL+usb-tablet ✅ Wayland-compatible, 40-80ms, Low friction, 5-10 Mbps, TLS optional, VPS-friendly Yes — **Ranked #1**
- B RDP/xrdp ⚠️ partial Wayland (needs XWayland or gnome-remote-desktop WLR RDP backend, package missing) — pivot to Waypipe if probe fails
- C Waypipe ✅ Wayland-native 20-50ms SSH — second choice if RDP fails
- D Sunshine/Moonlight 15-35ms UDP, High friction (build + CPU encode), 10-30 Mbps — only if user wants gaming latency
- E VirGL+SPICE ⚠️ partial (libvirgl present, egl-headless valid, but no render node → llvmpipe)
- F NoMachine/RustDesk no (extra deps)
VNC kept as fallback on 5901.

## SPICE implementation (host-side complete)
- Backup: `/root/omarchy/run-vm.sh.bak`
- Patch to `run-vm.sh`:
  ```
  -vnc 127.0.0.1:1  (kept)
  -spice port=5930,addr=127.0.0.1,disable-ticketing=on
  -device virtio-serial-pci
  -chardev spicevmc,id=vdagent,name=vdagent
  -device virtserialport,chardev=vdagent,name=com.redhat.spice.0
  -device qemu-xhci
  -device usb-tablet
  -device virtio-keyboard-pci
  -vga qxl
  ```
- Restart: killed 3831871 → 3834233, verified `ss` 127.0.0.1:5901+5930 + `ps aux | grep spice` shows qxl.
- Guest vdagent install skipped due SSH timeout — documented manual step: `sudo pacman -S --noconfirm spice-vdagent qemu-guest-agent && sudo systemctl enable --now spice-vdagentd`

## Open to 0.0.0.0 (explicit user request)
- User asked to use Omarchy without tunnel; confirmed yes to opening.
- Patched `-vnc 0.0.0.0:1` and `-spice addr=0.0.0.0`, killed 3834233 → 3834674, verified `ss` 0.0.0.0:5901 + 0.0.0.0:5930 + 0.0.0.0:3389. VPS IP 102.208.217.192 → direct `spice://102.208.217.192:5930` / `102.208.217.192:5901` / `102.208.217.192:3389` reachable. Warned: disable-ticketing with no password on 0.0.0.0 is insecure — use 127.0.0.1 + tunnel or add password/TLS for production.

## Client runbook (given)
- SPICE: `ssh -L 5930:localhost:5930` + `remote-viewer spice://localhost:5930` or direct `spice://VPS_IP:5930` after open
- VNC: `ssh -L 5901:localhost:5901` + `vncviewer localhost:1` or `VPS_IP:5901`
- RDP: `xfreerdp /v:VPS_IP:3389 ...` / `mstsc -> VPS_IP:3389` (direct when hostfwd 0.0.0.0)

## Follow-ups for next session
- When guest SSH banner succeeds, install spice-vdagent/qemu-guest-agent and optionally xrdp or waypipe or sunshine depending on matrix winner (RDP → Waypipe fallback).
- Consider VirGL `virtio-vga-gl` + `egl-headless,gl=on` test (expect llvmpipe, not HW).
- Re-lock VNC/SPICE to 127.0.0.1 + tunnel after user finishes direct test, or add SPICE password.
