---
name: headless-desktop-vm
description: Run desktop OS in headless QEMU/KVM with low-latency remote.
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [qemu, kvm, virtualization, vnc, rdp, xrdp, hyprland, wayland, omarchy, novnc]
---

# Headless Desktop Virtualization (QEMU/KVM)

Run guest desktop operating systems on headless VPS instances and stream them to a remote client with minimal latency and resource overhead.

## 1. Fast Provisioning on Disk-Constrained VPS

### Stream ISO Directly via HTTPS (Zero Local ISO Storage)
If the host has tight disk space (<10 GB free), avoid downloading 4–8 GB ISO files. Stream the ISO directly into QEMU via its built-in HTTP/HTTPS block driver:

```bash
qemu-system-x86_64 \
  -enable-kvm -cpu host -smp 2 -m 2560 \
  -machine q35 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive if=pflash,format=raw,file=$HOME/vm/OVMF_VARS.fd \
  -drive file=$HOME/vm/disk.qcow2,if=virtio,format=qcow2 \
  -drive file=https://example.com/distro.iso,media=cdrom,readonly=on,format=raw \
  -boot order=d \
  -net nic,model=virtio -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::3389-:3389 \
  -vnc 127.0.0.1:1 \
  -daemonize -display none \
  -vga virtio
```

### UEFI / OVMF Writable Vars
UEFI requires a per-VM writable NVRAM variables file:
```bash
if [ ! -f "$HOME/vm/OVMF_VARS.fd" ]; then
  cp /usr/share/OVMF/OVMF_VARS_4M.fd "$HOME/vm/OVMF_VARS.fd"
fi
```

---

## 2. Switching from Installer to Disk Boot

Once OS installation finishes:
1. Terminate the installer QEMU instance cleanly: `pkill -f "qemu.*disk.qcow2"`.
2. Launch with `-boot order=c` and drop the ISO `-drive` line.

```bash
exec qemu-system-x86_64 \
  -enable-kvm -cpu host -smp 2 -m 2560 \
  -machine q35 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive if=pflash,format=raw,file=$HOME/vm/OVMF_VARS.fd \
  -drive file=$HOME/vm/disk.qcow2,if=virtio,format=qcow2 \
  -boot order=c \
  -net nic,model=virtio -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::3389-:3389 \
  -vnc 127.0.0.1:1 \
  -daemonize -display none \
  -vga virtio
```

---

## 3. Latency & Performance Optimization

### A. Client-Side VNC Tuning (TigerVNC)
When connecting over WAN or SSH tunnels:
- **Encoding**: Set to `Tight` (combines zlib + JPEG).
- **JPEG Compression**: Enable and set Quality to `6` or `7` (cuts frame payload by 80%).
- **Color Depth**: Set to `Medium (16-bit)` or `256 Colors`.
- **SSH Tunnel**: Always pass `-C` for stream compression:
  ```powershell
  ssh -C -L 5901:localhost:5901 user@vps_ip -N
  ```

### B. Wayland & Hyprland Software Rendering (No GPU)
On VPS without dedicated GPUs, compositor effects (blur, shadows, animations) peg CPU software rendering (`llvmpipe`) and cause massive continuous screen repaints.

Add to `~/.config/hypr/hyprland.conf`:
```ini
decoration {
    rounding = 0
    drop_shadow = false
    blur {
        enabled = false
    }
}

animations {
    enabled = false
}

misc {
    disable_hyprland_logo = true
    disable_splash_rendering = true
    vfr = true                  # Variable Frame Rate: only render on change
    vrr = 0
}

# Cap refresh rate to save CPU and bandwidth
monitor=,1920x1080@30,auto,1
```

### C. Upgrade to SPICE + QXL + Absolute Tablet (Immediate Cursor Fix)
SPICE beats VNC by 2× on latency and fixes cursor drift by using an absolute `usb-tablet` device (VNC without it is relative → lag/drift). QXL gives better framebuffer than `virtio` on SPICE.

Host patch (`/root/omarchy/run-vm.sh`) — keep VNC as fallback on 5901:
```bash
# keep:  -vnc 0.0.0.0:1  (or 127.0.0.1:1 + ssh -L 5901:localhost:5901)
# add:
  -spice port=5930,addr=0.0.0.0,disable-ticketing=on \
  -device virtio-serial-pci \
  -chardev spicevmc,id=vdagent,name=vdagent \
  -device virtserialport,chardev=vdagent,name=com.redhat.spice.0 \
  -device qemu-xhci \
  -device usb-tablet \
  -device virtio-keyboard-pci \
  -vga qxl   # falls back to -vga virtio if qxl missing
```
Guest (once `ssh -p 2222` banner succeeds — it can timeout while hostfwd is open; retry 2–3×):
```bash
sudo pacman -S --noconfirm spice-vdagent qemu-guest-agent
sudo systemctl enable --now spice-vdagentd qemu-guest-agent
```
Client:
```bash
# if addr=0.0.0.0 (direct, insecure — add password later):
remote-viewer spice://VPS_IP:5930
# if addr=127.0.0.1 (tunnel, recommended):
ssh -L 5930:localhost:5930 root@VPS_IP -N
remote-viewer spice://localhost:5930
```
Security: `disable-ticketing=on` + `addr=0.0.0.0` with no password is open to internet — bind to `127.0.0.1` + tunnel for production, or add `password=...` / TLS (`tls-port`, `x509-dir`). Verify: `ss -tlnp | grep 5930`, `ps aux | grep spice`.

### D. Upgrade to XRDP / RDP Protocol
RDP supports client-side tile caching and delta compression, making typing and scrolling significantly faster than raw VNC. Hyprland is Wayland-only — `xrdp` is Xorg; if it shows black screen, use Wayland-native `gnome-remote-desktop` RDP or Waypipe (see matrix in references/).

Inside the guest:
```bash
sudo pacman -S --noconfirm xrdp xorg-server xorg-xinit
sudo systemctl enable --now xrdp
# Wayland alternative:
# sudo pacman -S gnome-remote-desktop && systemctl enable --now gnome-remote-desktop
```

On host, map guest port 3389 (already in run-vm.sh: `hostfwd=tcp::3389-:3389` on 0.0.0.0):
```bash
xfreerdp /v:VPS_IP:3389 /u:USER /p:PASS +clipboard /dynamic-resolution
# Windows: mstsc.exe -> VPS_IP:3389 (direct, no tunnel needed when hostfwd is 0.0.0.0)
# Tunnel alternative: ssh -L 3389:localhost:3389 root@VPS_IP -N
```

---

## 4. Verification & Diagnostics

- **Check QEMU ports**: `ss -tlnp | grep -E "5901|5930|2222|3389"` (5901 VNC, 5930 SPICE, 2222 SSH, 3389 RDP — note VNC/SPICE may be 127.0.0.1 + tunnel vs 0.0.0.0 direct)
- **Monitor CPU & RAM**: `htop` / `free -h` — QEMU RSS grows lazily (100M just-booted → 3G under load); if `available` <500M expect swap thrashing
- **Verify KVM Acceleration**: `kvm-ok` (must report `/dev/kvm exists`) and `qemu -display help` (check `egl-headless`, `spice-app`, `gtk`, `sdl`) + `qemu -device ? | grep -E "virtio-vga-gl|qxl|usb-tablet"` + `dpkg -l | grep -E "virgl|spice"` (libvirglrenderer 1.0.0 on this box, but no host `/dev/dri/renderD128` → VirGL is llvmpipe CPU fallback, not HW)
- **Verify VM RAM**: `pgrep -a qemu | grep -o "\-m [0-9]*"` or `cat /proc/$(pgrep -f qemu.*disk.qcow2)/cmdline | tr '\0' ' ' | grep -o "\-m [0-9]*"`

---

## 5. Live Resource Tuning (RAM, Swap, Disk)

### A. Resize VM RAM
Edit the launch script (`run-vm.sh` or `$HOME/omarchy/run-vm.sh`):

```bash
# change -m 2560 → -m 4096
patch run-vm.sh -m flag, then restart
```

Restart — `pkill` truncates at 15 chars and will NOT match `qemu-system-x86_64`. Use `pgrep -f` + `kill`:

```bash
OLD_PID=$(pgrep -f "qemu.*disk.qcow2")
kill -9 $OLD_PID
sleep 2
bash ~/omarchy/run-vm.sh
sleep 2
pgrep -a qemu | grep -o "\-m [0-9]*"  # verify
```

If restart fails with `Failed to get "write" lock — Is another process using the image?`, the old QEMU is still alive — re-kill and wait 2s before relaunch.

Host sizing: giving a 4G guest on a 5.8G host leaves ~1.8G for host + swap. Monitor `free -h` — if `available` <500M, add swap (next section) and expect QEMU resident to grow lazily (just-booted RSS ~100M, climbs to full `-m` under load).

### B. Expand Swap Without Downtime
When swap is >80% used, do NOT `swapoff` the primary file to resize it (risks OOM). Add a second file:

```bash
fallocate -l 4G /swap2.img
chmod 600 /swap2.img
mkswap /swap2.img
swapon /swap2.img
echo "/swap2.img none swap sw 0 0" >> /etc/fstab
swapon --show && free -h && df -h /
```

Check `df -h /` first — swap files live on root. On a 48G disk with 6G free, adding 4G pushes usage to ~96% (2G free). Follow with cleanup if needed.

### C. Disk Cleanup After Swap Expansion
Common reclamation on this box:

```bash
# autoclipping renders (165M + assets)
rm -f ~/projects/autoclipping/Outputs/*.mp4 ~/projects/autoclipping/assets/*.mp4

# system caches
apt clean
rm -rf ~/.cache/* /tmp/*
journalctl --vacuum-size=50M  # if journald is large
```

Before: `46G/48G (96%, 2.0G free)` → After: `43G/48G (91%, 4.7G free)` in this session.

### D. Input Device Latency Fix
VNC without an absolute tablet causes cursor drift/lag. Preferred stack is **SPICE + QXL + usb-tablet** (section 3C) — RDP is next best for WAN. For VNC-only, use TigerVNC Tight encoding + JPEG quality 6–7 + SSH `-C` compression. Opening to `0.0.0.0` (`-vnc 0.0.0.0:1`, `-spice addr=0.0.0.0`) makes ports directly reachable at `VPS_IP:5901/5930` — convenient but insecure without password/TLS; keep `127.0.0.1` + `ssh -L` for production and only switch to `0.0.0.0` on explicit request. Always `cp run-vm.sh run-vm.sh.bak` before flags change.

Pitfalls: `nc -vz 127.0.0.1 2222` can show `open` while `ssh -p 2222` banner times out (guest still booting / getty slow) — retry 3× with 15s gap before concluding SSH is down. `qemu-img info` not needed for qxl validation; `ps aux | grep spice` + `ss` is sufficient.
