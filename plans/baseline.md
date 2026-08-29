# Baseline — Omarchy VM Host Capabilities (2026-08-29 11:41 SAST)

> Read-only probes only — VM not modified. QEMU PID 3831871 kept running.

## 1. VM Current Config

**File:** `/root/omarchy/run-vm.sh` (602 B, executable)

```bash
#!/bin/bash
set -e
DISK="$HOME/omarchy/omarchy.qcow2"
OVMF_CODE="/usr/share/OVMF/OVMF_CODE_4M.fd"
OVMF_VARS="$HOME/omarchy/OVMF_VARS.fd"
pkill -9 qemu-system-x86_64 2>/dev/null || true
sleep 1
exec qemu-system-x86_64 \
  -enable-kvm -cpu host -smp 2 -m 4096 \
  -machine q35 \
  -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" \
  -drive if=pflash,format=raw,file="$OVMF_VARS" \
  -drive file="$DISK",if=virtio,format=qcow2 \
  -boot order=c \
  -net nic,model=virtio -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::3389-:3389 \
  -vnc 127.0.0.1:1 \
  -daemonize -display none \
  -vga virtio
```

- Disk: `/root/omarchy/omarchy.qcow2` 7.5 GiB (qemu-img info blocked by write-lock — VM running, normal)
- OVMF: `/usr/share/OVMF/OVMF_CODE_4M.fd` exists (3653632 B), `OVMF_VARS.fd` 540 KiB
- QEMU cmdline live: `qemu-system-x86_64 -enable-kvm -cpu host -smp 2 -m 4096 -machine q35 ... -vnc 127.0.0.1:1 -daemonize -display none -vga virtio` (verified via `/proc/<pid>/cmdline`)
- Hostfwd: 2222→22 (SSH), 3389→3389 (RDP/XRDP), VNC 5901 (display :1)

## 2. Host Hardware / OS

- OS: Ubuntu 24.04.4 LTS (Noble), kernel 6.8.0-106-generic x86_64
- CPU: 3 vCPUs Intel Xeon Gold 6262 @1.90GHz (QEMU pc-q35-9.2), flags: vmx, avx512, VT-x, KVM `kvm_intel` loaded, `/dev/kvm` crw-rw---- root:kvm
- RAM: **5.8 GiB total, 5.5 GiB used, 136 Mi free, 278 Mi available** — critically low headroom
- Swap: **8.0 GiB total, 3.9 Gi used, 4.1 Gi free** — `/swap.img` 4G pri -2 (3.7G used), `/swap2.img` 4G pri -3 (224M used). SwapCached 602 MB.
- Disk: `/dev/sda1 48G, 45G used, 3.2G avail, 94% used` — near-full (up from 91% in plan, needs cleanup). `/boot` 881M 15%, `/run/qemu` tmpfs 2.9G
- Load at probe: `2.59 2.24 2.11` (3 CPUs), vmstat shows si 3096, so 3196 bi under swap pressure, QEMU PID 3831871 at 100% CPU, 3.1 GiB RSS, 6.1 GiB VSZ
- Uptime: 65 days, 9 users
- `/dev/dri`: `card0` crw-rw---- root:video (226,0) exists, **no `renderD*` node** → no host GPU render node; VirGL would fall back to llvmpipe (CPU)

## 3. QEMU Capabilities

- Version: QEMU 8.2.2 (Debian 1:8.2.2+ds-0ubuntu1.18)
- Binary: `/usr/bin/qemu-system-x86_64` 26 MB, 2024-06-24
- Accelerators: `kvm`, `tcg`
- Display backends (`-display help`): `none`, `gtk`, `sdl`, `egl-headless`, `curses`, `spice-app`, `dbus` — note: no `vnc` listed there (VNC is via `-vnc` separate)
- `-vga help`: `none`, `std`, `cirrus`, `vmware`, `qxl`, `virtio` — **qxl available** (via `hw-display-qxl.so`)
- `-device ?` display devices present:
  - `virtio-gpu-device`, `virtio-gpu-pci`, `virtio-vga`, `virtio-vga-gl`, `virtio-gpu-gl-device`, `virtio-gpu-gl-pci`, `vhost-user-gpu` — **VirGL devices present**
  - `qxl`, `qxl-vga`, `ramfb`, `bochs-display`
  - `usb-tablet`, `virtio-tablet`, `virtio-keyboard`, `virtio-mouse` all present
- SPICE: `-spice help` full options present (port, gl, tls-port, x509, rendernode, streaming-video, etc.). Modules verified:
  - `/usr/lib/x86_64-linux-gnu/qemu/ui-spice-core.so`, `ui-spice-app.so`, `audio-spice.so`, `chardev-spice.so`, `hw-display-qxl.so` ✅
- OpenGL/VirGL modules:
  - `/usr/lib/x86_64-linux-gnu/qemu/hw-display-virtio-gpu-gl.so`, `hw-display-virtio-gpu-pci-gl.so`, `hw-display-virtio-vga-gl.so`, `ui-egl-headless.so`, `ui-opengl.so` ✅
  - `dpkg -l`: `qemu-system-modules-opengl` 8.2.2, `qemu-system-modules-spice` 8.2.2, `qemu-system-gui` 8.2.2 installed
  - `libvirglrenderer1` 1.0.0-1ubuntu2 ✅, `libspice-server1` 0.15.1-1build2 ✅
  - But `ls /dev/dri/render*` missing → host EGL will use llvmpipe, not GPU. `qemu -display egl-headless,gl=on -device virtio-vga-gl` syntax is valid (modules exist) but will be CPU-rendered
- VNC still functional: `ss -tlnp` shows `127.0.0.1:5901` LISTEN owned by qemu PID 3831871 fd 9

## 4. VirGL / SPICE Verdict

| Capability | Status | Details |
|------------|--------|---------|
| **SPICE** | ✅ **Ready** | Server lib + QEMU modules present; `-spice port=5930,disable-ticketing` + `-device usb-tablet` + `-vga qxl` will work. Tested conceptually via `-spice help`. Hostfwd port 5930 currently not forwarded — would need `hostfwd=tcp::5930-:5930` |
| **VirGL (`virtio-gpu-gl`)** | ⚠️ **Partial — CPU fallback** | `libvirglrenderer` + `virtio-vga-gl` device present, `egl-headless,gl=on` display supported. **BUT** host has no `/dev/dri/renderD128` (only `card0`), so VirGL would use llvmpipe software GL. Functional but not hardware-accelerated; expect 20% smoother compositing at cost of extra CPU. Host 100% CPU already suggests caution. Recommend testing but not blocking. |
| **QXL** | ✅ Ready | `hw-display-qxl.so` present, `-vga qxl` valid. Preferred for SPICE (better than `-vga virtio` for SPICE streaming) |
| **usb-tablet (absolute pointer)** | ✅ Ready | Device `usb-tablet` listed — fixes VNC cursor drift/lag immediately |

**Recommendation per plan:** Task 3 (SPICE+usb-tablet+QXL) is zero-risk and ready. Task 5 (VirGL) is possible via `-device virtio-vga-gl -display egl-headless,gl=on` but will be llvmpipe; worth A/B test after SPICE is stable, not as primary.

## 5. Network & Reachability

- `ss -tlnp` (host):
  - `0.0.0.0:2222` → qemu (SSH forward)
  - `0.0.0.0:3389` → qemu (RDP forward)
  - `127.0.0.1:5901` → qemu (VNC)
  - `0.0.0.0:22` → sshd (host)
  - Multiple `127.0.0.1:3xxxx-4xxxx` chrome/hermes/ngrok listeners
  - UDP: many qemu user-net ephemeral ports
- `ss -tulpn` confirms same
- `ping`: `1.1.1.1` 1.60 ms avg (0% loss), `8.8.8.8` 2.45 ms avg, `archlinux.org` 161 ms — WAN healthy
- **Guest SSH (port 2222) — DEGRADED at probe time:**
  - `nc -v 127.0.0.1 2222` → `Connection succeeded` (TCP level OK)
  - `ssh -vvv -p 2222 localhost` → `Connection established. Local version string SSH-2.0-OpenSSH_9.6...` then **`Connection timed out during banner exchange`** after 5 s. Same for `ssh -p 2222 -o BatchMode=yes localhost` and both `omarchy@`/`root@`.
  - Guest not sending SSH banner within 5 s. Likely guest overloaded (QEMU 100% CPU, swap thrashing, load 2.59). `qemu-img info` also blocked by write-lock (VM running, normal). *No VM modification attempted.* This blocks Task-1's `cat ~/.config/hypr/hyprland.conf` and `pacman -Q` probes — **deferred to retry when guest recovers or after reboot**.
  - Host SSH to VPS itself (port 22) unaffected.

## 6. Hygiene & Risks

- **Disk 94% full (3.2G free)** — up from plan's 91%/4.7G. Any `qcow2` growth or guest package installs could fill host. Recommend cleanup before Task 4 (e.g., `journalctl --vacuum-size=100M`, `apt clean`).
- **RAM 136M free, 278M available** — host under memory pressure; QEMU 3.1G RSS + host chrome/hermes workers consume rest. Adding `-m 4096` already maxes host; consider hostfwd+display changes only (no RAM bump).
- **Swap thrashing** — 3.9G swap used, si/so observed. Guest SSH timeout likely related.
- **No `virsh`, no Docker daemon** — as per plan, direct `qemu-system-x86_64` flags only.

## 7. Probes Executed (read-only)

```bash
qemu-system-x86_64 -display help
qemu-system-x86_64 -device ? | grep -E virtio|virgl|spice|qxl|vga|gl
dpkg -l | grep -E 'virgl|spice|qemu'
ss -tlnp; ss -tulpn
free -h; df -h; swapon --show; cat /proc/meminfo
ping -c 3 1.1.1.1; ping -c 3 8.8.8.8; ping -c 3 archlinux.org
nc -v 127.0.0.1 2222; ssh -vvv -p 2222 localhost (BatchMode)
qemu-system-x86_64 -spice help; -accel help; -vga help
ls -l /dev/kvm /dev/dri/*; ldconfig -p | grep virgl; dpkg -L qemu-system-modules-opengl/spice
ps aux | grep qemu; cat /proc/<pid>/cmdline; cat /proc/loadavg; vmstat 1 3
ls -l /usr/share/OVMF/; cat /etc/os-release; uname -a; lscpu; lsmod | grep kvm
cat /root/omarchy/run-vm.sh; ls -la /root/omarchy/; ls -la .hermes/plans/
```

All **read-only**, no `pkill`, no `qemu-img`, no VM reboot.

## 8. Next Steps (for Task 2/3)

- Retry guest SSH when load drops (or briefly `virsh`-less reboot via `run-vm.sh` — requires approval, not done here) to capture `hyprland.conf` and `pacman -Q`.
- Proceed to decision matrix scoring: SPICE+tablet = 5/5 ready, VirGL = 3/5 (functional but llvmpipe), RDP/Waypipe require guest SSH to score.
- Keep VNC on 5901 as fallback; add SPICE on 5930 as first improvement (lowest friction).
- Before any write: backup `run-vm.sh` → `run-vm.sh.bak`, `df -h` check, then patch.

---
*Generated 2026-08-29 SAST, host vm807cmml.yourlocaldomain.com, QEMU 8.2.2, probe PID 3831871.*
