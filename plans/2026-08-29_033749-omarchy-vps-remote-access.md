# Run Omarchy (Arch + Hyprland) on this VPS with Remote Access from Your PC

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Run Omarchy desktop on the current Ubuntu 24.04 KVM VPS (3 vCPU / 5.8 GiB RAM / no GPU) and access it interactively from a Windows PC as if it were local.

**Architecture:** Omarchy is Arch Linux + Hyprland (Wayland compositor). It cannot install directly onto Ubuntu — you nest it inside a KVM/QEMU VM that boots the Omarchy ISO. The VM's Wayland session is streamed to your PC via a remote-desktop gateway. Four gateway options are ranked; the plan implements the best-fit for this VPS.

**Tech Stack:** QEMU/KVM (qemu-system-x86_64, libvirt/virt-manager optional), Arch/Omarchy ISO, Hyprland + wayvnc or RDP (xrdp/wlroots), noVNC / KasmVNC, Sunshine+Moonlight, Tailscale/WireGuard + UFW, TigerVNC/XRDP, NGINX reverse proxy + TLS.

---

## 1. Current Context & Assumptions

| Fact | Value |
|------|-------|
| Host OS | Ubuntu 24.04 Noble, kernel 6.8.0-106, `systemd-detect-virt: kvm` (guest VM itself) |
| vCPU/RAM | 3 vCPU (Xeon Gold 6262) with VT-x flag, 5.8 GiB RAM (3.0 GiB avail), 4 GiB swap |
| GPU | QEMU `1234:1111` VGA (bochs/cirrus) — no NVIDIA, no 3D accel |
| Nested virt | `vmx` flag present — KVM-inside-KVM works but is slower; viable for this workload |
| Already running | Hermes, gbrain, autoclipping pipeline — don't break ports 27183/tunnel |
| Omarchy reqs | Arch + Hyprland, installer wants full disk (LUKS) — inside a VM virtual disk is perfect |
| Network | Public IP with UFW default; ports 22 + 53317 (LocalSend) allowed by Omarchy defaults |

**Key constraint:** No GPU → Hyprland must run headless/software-rendered (WLR `WLR_RENDERER_ALLOW_SOFTWARE=1`) or via XWayland fallback. Performance will be "usable for dev" not gaming.

---

## 2. Is It Possible? — Yes, 4 Ways Ranked

### Method A — QEMU/KVM VM + RDP/wayvnc via Tailscale (RECOMMENDED for this VPS)
- **What:** Create a 40–60 GiB qcow2 disk, boot `omarchy.iso` (or Arch + `omarchy install` script) as a KVM guest. Inside guest: Omarchy/Hyprland. Expose via `wayvnc` (native Wayland VNC) or `xrdp`/`uwsm`, tunneled over Tailscale/WireGuard SSH. Access with any VNC/RDP client on Windows.
- **Pros:** True Omarchy (not container fake), isolated, snapshots, LUKS inside guest fine, minimal host pollution, firewall friendly over Tailscale.
- **Cons:** Nested KVM overhead, RAM tight (give guest 3 GiB, host needs ~2 GiB), software rendering only.
- **Best for:** Your case — wants the real Omarchy on an existing Ubuntu VPS.

### Method B — QEMU/KVM VM + noVNC / KasmVNC (Browser Access, No Client Install)
- **What:** Same VM as A but expose via `novnc` websockify or KasmVNC on top of TigerVNC/wayvnc. NGINX + TLS (Let's Encrypt) → `https://vps-ip:6080/vnc.html`.
- **Pros:** Access from any browser on any PC, no RDP client, easy to share, works behind restrictive firewalls.
- **Cons:** Extra hop (websockify), slightly laggier, TLS/cert setup.
- **Best for:** "I want to click a URL and have a desktop" without installing anything on PC.

### Method C — Docker/Podman Container with KasmVNC (Lightest, but NOT Real Omarchy)
- **What:** `kasroid` / `linuxserver/webtop` or custom `archlinux:base` + Omarchy dotfiles + Hyprland inside Docker, streamed via KasmVNC on `:3000`/`3001`.
- **Pros:** Lightest RAM/CPU, instant start, no nested KVM tax, one `docker run`.
- **Cons:** Not a real Omarchy install (theme/scripts must be manually replicated), Hyprland-in-Docker is brittle, systemd inside container hacks, no LUKS/full-disk, Wayland nesting issues.
- **Best for:** Quick demo/trial when you don't need installer fidelity.

### Method D — Sunshine (Host) + Moonlight (PC) — Best Performance, Needs Setup
- **What:** VM method A + Sunshine streaming server inside guest (or host if you `arch-chroot` Omarchy onto host — destructive, not recommended). Moonlight client on Windows gives near-native latency via H.264/AV1.
- **Pros:** Lowest latency, hardware-encoded if available, game-grade smoothness, clipboard/audio forwarding.
- **Cons:** Overkill for dev desktop, needs UDP ports 47984-48010, software encode only (no GPU) so CPU cost high.
- **Best for:** When you want buttery smoothness and can open UDP ports.

**Verdict:** **Do A, optionally add B as a second gateway.** D is a nice add-on later. Avoid C unless you only want a toy.

---

## 3. Proposed Approach (Method A + B)

1. Prepare host: `qemu-kvm`, `ovmf` (UEFI), `virtio` drivers, create qcow2 disk + bridge/NAT.
2. Download `omarchy.iso` (from omarchy.org) to `~/omarchy/`.
3. Create VM with `virt-install` / `qemu-system-x86_64` with VNC listen + QMP.
4. Install Omarchy inside VM (follow installer prompts, LUKS on virtual disk).
5. First boot: enable `wayvnc` (or `gnome-remote-desktop` RDP backend for Hyprland) + `wlroots` headless output. Alternative fallback: `xrdp`+`xorg` if wayvnc unstable.
6. Wire secure access: Tailscale (preferred) or SSH `-L 5900:localhost:5900` tunnel + UFW rule. Optionally add `websockify`→noVNC for browser access behind NGINX+TLS.
7. Validate from Windows: TigerVNC / Windows RDP / browser.
8. Harden: UFW, fail2ban, snapshots, backup.

---

## 4. Step-by-Step Plan (TDD where applicable — verification commands included)

### Phase 0 — Discovery & Sizing

#### Task 0.1: Confirm nested KVM and disk space
**Files:** none (read-only)

**Step 1:** Run
```bash
egrep -c 'vmx|svm' /proc/cpuinfo; ls -l /dev/kvm; qemu-system-x86_64 --version 2>&1 | head -1; df -h /; free -h
```
**Expected:** `vmx >0`, `/dev/kvm` exists, `qemu 8.x`, `>50 GiB free` needed. If <30 GiB free → abort or attach block volume first.

**Step 2:** If `/dev/kvm` missing:
```bash
sudo modprobe kvm_intel 2>&1; ls -l /dev/kvm
```
If still missing, nested virt disabled by provider → fall back to Method C (Docker) or QEMU TCG (slow, not recommended).

---

### Phase 1 — Host Prep

#### Task 1.1: Install QEMU/KVM/OVMF/virtio stack on host
**Files:** apt packages

```bash
sudo apt update
sudo apt install -y qemu-system-x86 qemu-utils ovmf virtinst bridge-utils cpu-checker websockify novnc tigervnc-standalone-server
kvm-ok  # expect: INFO: /dev/kvm exists, KVM acceleration can be used
virsh --version  # optional if libvirt used
```

**Verify:** `kvm-ok` says usable, `ls /usr/share/OVMF/OVMF.fd` exists.

#### Task 1.2: Create VM storage and ISO dir
**Files:** Create `~/omarchy/omarchy.qcow2`, `~/omarchy/iso/`

```bash
mkdir -p ~/omarchy/iso
qemu-img create -f qcow2 ~/omarchy/omarchy.qcow2 50G
qemu-img info ~/omarchy/omarchy.qcow2  # expect: 50G virtual, ~200K actual
# Download ISO (check omarchy.org for current link — example):
wget -O ~/omarchy/iso/omarchy.iso https://omarchy.org/download/latest.iso
# or: curl -L https://github.com/basecamp/omarchy/releases/latest/download/omarchy.iso -o ~/omarchy/iso/omarchy.iso
ls -lh ~/omarchy/iso/omarchy.iso
```

#### Task 1.3: UFW / firewall plan
**Files:** `/etc/ufw/*` (via `ufw` CLI)

```bash
sudo ufw status
# Plan: allow 22 (ssh) keep, add for VNC/RDP only via Tailscale or localhost-bound + SSH tunnel.
# For noVNC browser method, open 6080/tcp behind TLS, or better: keep closed and use SSH -L 6080:localhost:6080
sudo ufw allow 22/tcp
# Do NOT open 5900 publicly; bind VNC to 127.0.0.1 and tunnel.
```

---

### Phase 2 — Create & Install VM

#### Task 2.1: Create VM definition (virt-install one-liner)
**Files:** Create `~/omarchy/run-vm.sh`

```bash
cat > ~/omarchy/run-vm.sh <<'EOS'
#!/bin/bash
set -e
ISO="$HOME/omarchy/iso/omarchy.iso"
DISK="$HOME/omarchy/omarchy.qcow2"
# BIOS boot with Q35; switch to OVMF for UEFI if ISO requires it: -bios /usr/share/OVMF/OVMF.fd
qemu-system-x86_64 \
  -enable-kvm -cpu host -smp 2 -m 3072 \
  -machine q35 \
  -drive file="$DISK",if=virtio,format=qcow2 \
  -cdrom "$ISO" -boot order=d \
  -net nic,model=virtio -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::5900-:5900,hostfwd=tcp::6080-:6080 \
  -vnc :0,password=off \
  -daemonize -display none \
  -vga virtio
# For UEFI: add: -bios /usr/share/OVMF/OVMF_CODE.fd -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE.fd
EOS
chmod +x ~/omarchy/run-vm.sh
```

**Alternative (libvirt):**
```bash
sudo virt-install --name omarchy --ram 3072 --vcpus 2 \
  --disk path=$HOME/omarchy/omarchy.qcow2,format=qcow2,bus=virtio \
  --cdrom $HOME/omarchy/iso/omarchy.iso --os-variant archlinux \
  --network user --graphics vnc,listen=127.0.0.1 --noautoconsole --boot uefi
```

**Verify:** `ps aux | grep qemu`, `ss -tlnp | grep 5900`, `vncviewer localhost:5900` or `virsh list`.

#### Task 2.2: Install Omarchy inside VM via VNC
**Files:** inside VM only

1. From your PC: `ssh -L 5900:localhost:5900 root@<VPS_IP> -N` then open TigerVNC Viewer → `localhost:5900`. Or use `browser_exec` to drive the VNC canvas.
2. Follow Omarchy installer: select virtual disk (`vda`), set user/pass, LUKS passphrase (remember it), install.
3. On finish, shutdown VM (`poweroff`), then edit `run-vm.sh` to boot from disk (`-boot order=c` and remove `-cdrom`).

**Verify:** VM reboots to Omarchy login (Hyprland greets).

---

### Phase 3 — Remote Desktop Gateway Inside Guest

#### Task 3.1: Enable wayvnc (Wayland-native VNC) in guest — primary path
**Files (inside guest):** `~/.config/hypr/hyprland.conf`, `/etc/wayvnc/config`

```bash
# Inside Omarchy guest (arch):
sudo pacman -S --needed wayvnc wl-clipboard
# Create headless output if no monitor detected:
# Add to hyprland.conf: monitor=,preferred,auto,1  and: exec-once = wayvnc 0.0.0.0 5900
wayvnc --help
# Test headless:
WLR_BACKENDS=headless WLR_RENDERER_ALLOW_SOFTWARE=1 wayvnc 0.0.0.0 5900 &
ss -tlnp | grep 5900
```

**Verify from host:** `vncviewer localhost:5900` shows Hyprland desktop.

#### Task 3.2: Fallback — xrdp if wayvnc unstable
**Files (guest):** `/etc/xrdp/*`

```bash
sudo pacman -S --needed xrdp xorg-server xorg-xinit
sudo systemctl enable --now xrdp
sudo ufw allow 3389/tcp  # guest UFW only
# Connect via Windows Remote Desktop to VPS:2222 or tunneled 3389
```

#### Task 3.3: noVNC browser gateway (optional, Method B)
**Files (host or guest):** systemd unit `novnc.service`

```bash
# On host, proxy guest VNC to browser:
websockify --web /usr/share/novnc 6080 localhost:5900 &
# Or: novnc_proxy --vnc localhost:5900 --listen 6080
# NGINX TLS:
sudo apt install -y nginx certbot python3-certbot-nginx
# /etc/nginx/sites-available/novnc -> proxy_pass http://127.0.0.1:6080; + certbot --nginx -d vnc.yourdomain.com
```

**Verify:** `https://<VPS_IP>:6080/vnc.html` (or tunneled `http://localhost:6080/vnc.html`) shows desktop in browser.

#### Task 3.4: Sunshine+Moonlight (optional high-perf)
**Files (guest):** Sunshine config

```bash
# Inside guest:
yay -S sunshine  # or pacman if packaged
sunshine &
# Open UDP 47984-48010 on host forwarding, pair Moonlight client on Windows
```

---

### Phase 4 — Secure Access from Windows PC

#### Task 4.1: Tailscale (recommended — no public VNC ports)
**Files:** host + guest

```bash
# Host + guest:
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up  # auth URL -> add to tailnet
tailscale ip -4  # use this IP for VNC/RDP
# Now VNC/RDP binds to tailscale0, not public internet
```

**Verify:** From Windows (Tailscale installed + same tailnet): `ping <tailscale-ip>`, then VNC/RDP to `<tailscale-ip>:5900`.

#### Task 4.2: SSH tunnel alternative (no Tailscale)
**Files:** Windows side

```powershell
# PowerShell on Windows:
ssh -L 5900:localhost:5900 -L 6080:localhost:6080 root@<VPS_IP> -N
# Then open: vncviewer localhost:5900  or  browser http://localhost:6080/vnc.html
# For RDP: ssh -L 3389:localhost:3389 root@<VPS_IP> -N ; mstsc /v:localhost
```

Add to `~/.ssh/config` for persistence.

---

### Phase 5 — Hardening & Ops

#### Task 5.1: Autostart + watchdog
**Files:** `/etc/systemd/system/omarchy-vm.service` (host)

```ini
[Unit]
Description=Omarchy QEMU VM
After=network.target

[Service]
Type=forking
User=root
ExecStart=/root/omarchy/run-vm.sh
ExecStop=/bin/sh -c 'virsh shutdown omarchy || pkill qemu'
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload; sudo systemctl enable --now omarchy-vm
sudo systemctl status omarchy-vm
```

#### Task 5.2: Snapshots & backup
```bash
qemu-img snapshot -c pre-omarchy ~/omarchy/omarchy.qcow2
qemu-img snapshot -l ~/omarchy/omarchy.qcow2
# Or virsh: virsh snapshot-create-as omarchy clean-install
```

#### Task 5.3: Resource guardrails
- Give guest 2 vCPU / 3 GiB (leaves 1 vCPU / 2.8 GiB for host Hermes/autoclipping).
- Enable `zram` or keep 4 GiB swap; set `vm.swappiness=10` on host.
- Monitor: `htop`, `virsh domstats`, `systemd-cgtop`.
- If RAM pressure high → reduce guest to 2 GiB or move to Method C.

---

## 5. Files Likely to Change

| Path | Action |
|------|--------|
| `~/omarchy/run-vm.sh` | Create — QEMU launch script |
| `~/omarchy/omarchy.qcow2` | Create — 50 GiB virtual disk |
| `~/omarchy/iso/omarchy.iso` | Download |
| `/etc/systemd/system/omarchy-vm.service` | Create — autostart |
| `/etc/nginx/sites-available/novnc` | Create — if browser access |
| Guest `~/.config/hypr/hyprland.conf` | Modify — headless output + wayvnc autostart |
| Guest `/etc/wayvnc/config` | Create |
| `/etc/ufw/*` | Modify via `ufw` — port policy |

---

## 6. Tests / Validation

| Check | Command | Expected |
|-------|---------|----------|
| Nested KVM | `kvm-ok && ls -l /dev/kvm` | `KVM acceleration can be used` |
| QEMU running | `ps aux | grep qemu; ss -tlnp | grep 5900` | process + LISTEN |
| Guest boots | VNC to `:5900` | Omarchy login / Hyprland |
| wayvnc | `ss -tlnp | grep 5900` inside guest | LISTEN 0.0.0.0:5900 |
| Tailscale | `tailscale status` + `ping <100.x>` from Windows | OK |
| SSH tunnel | `ssh -L 5900:localhost:5900 ...` then `vncviewer localhost:5900` | Desktop appears |
| noVNC | `curl -I http://localhost:6080/vnc.html` | 200 |
| Load | `free -h; htop` during desktop use | host avail >500 MiB, guest responsive |

---

## 7. Risks, Tradeoffs & Open Questions

| Risk | Impact | Mitigation |
|------|--------|------------|
| **RAM starvation** (5.8 GiB total) | Host OOM kills Hermes/autoclipping | Cap guest at 3 GiB, enable zram, monitor `free -h`, snapshot before install |
| **No GPU / software render** | Hyprland animations janky, high CPU | Set `WLR_RENDERER_ALLOW_SOFTWARE=1`, disable blur/animations in hyprland.conf, use RDP fallback if needed |
| **Nested KVM disabled by provider** | VM runs in slow TCG emulation | Test `kvm-ok` first; if fails, pivot to Docker Method C |
| **Omarchy ISO needs UEFI/SecureBoot off** | Boot fail | Use OVMF_CODE.fd, disable Secure Boot in VM firmware (F2 on boot) |
| **Public VNC exposed** | Brute force | Bind to `127.0.0.1` or `tailscale0` only, never `0.0.0.0` public; use SSH tunnel or Tailscale ACLs |
| **Disk space** | 50 GiB qcow2 fills host | Check `df -h` first; thin-provisioned qcow2 starts ~200 KiB, grows on use; add block volume if needed |
| **Host reboot loses VM** | Manual restart | systemd unit + `Restart=on-failure` |
| **Wayland VNC clipboard** | Copy/paste broken | Install `wl-clipboard` + `wayvnc` 0.8+, test Super+C/V |

**Open questions for you:**
1. Do you want **browser-only** (noVNC) or **native VNC/RDP client** on Windows — or both?
2. Do you have a **domain** for TLS (e.g. `vnc.yourdomain.com`) or prefer pure SSH tunnel/Tailscale (no public ports)?
3. Is **50 GiB** disk OK, or do you need smaller (30 GiB works for minimal Omarchy)?
4. Should the VM **autostart on VPS boot**, or manual start only?

---

## 8. Cost & Performance Notes

- No extra VPS cost if `df -h` has 50 GiB free; otherwise attach a 50 GiB volume (~$5/mo typical).
- Tailscale free tier covers this use.
- Expected latency: RDP/wayvnc ~80–150 ms usable for coding; Sunshine/Moonlight ~30–60 ms if you add it.
- Hyprland software rendering: ~0.5–1 vCPU constant; keep animations off for headroom.

---

## 9. Next Step

Pick **Method A (+ optional B)** and run Tasks 0.1 → 5.3 in order. If you want me to execute, say **"execute Method A"** and I'll start with host prep (`qemu` install + ISO download + VM create) and drive the installer over VNC.
