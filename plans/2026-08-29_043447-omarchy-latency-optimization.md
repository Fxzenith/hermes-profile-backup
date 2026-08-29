# Omarchy Remote Desktop Latency Optimization Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Reduce remote desktop latency, input lag, and stuttering for the Omarchy (Arch Linux + Hyprland) VM running on the VPS when accessed from a Windows PC.

**Architecture:** Transition from the current uncompressed raw QEMU framebuffer scraping over a TCP SSH tunnel to an optimized pipeline: disable Hyprland software-render blur/animations, tune client compression, install Omarchy directly to local disk, and deploy a low-bandwidth/low-latency remote protocol (XRDP with audio/clipboard support or Sunshine/Moonlight over UDP).

**Tech Stack:** QEMU/KVM, Hyprland (`hyprland.conf`), TigerVNC (Tight/JPEG compression), XRDP / FreeRDP, Sunshine (x264 software encoder), Tailscale/WireGuard (UDP tunnel).

---

## 1. Root Cause Analysis of High Latency

Currently, 4 distinct bottlenecks compound to make the connection feel slow:

1. **Uncompressed Framebuffer Scraping:** QEMU's built-in `-vnc` engine captures the virtual display as raw pixel matrices. Without server-side lossy video compression (H.264/JPEG), large screen updates consume 20–50 Mbps of bandwidth.
2. **Hyprland Software Rendering & Continuous Redraws:** Hyprland's default config enables active window animations, background blurs, drop shadows, and high-frequency repaints. Without a dedicated GPU, CPU software rendering (`llvmpipe`) pegs the host CPU and forces continuous multi-megabyte VNC screen diffs.
3. **TCP Tunnel Overhead (SSH Port Forwarding):** Tunneling interactive VNC traffic through `ssh -L` over high-latency WAN creates TCP-in-TCP head-of-line blocking whenever a packet drops.
4. **Live ISO Stream Overhead:** Running the live installer while streaming data on-demand from `https://iso.omarchy.org/` adds disk I/O latency to every application launch inside the guest.

---

## 2. Optimization Strategy (Phased Approach)

| Phase | Strategy | Latency Impact | Effort |
|-------|----------|----------------|--------|
| **Phase 1** | Immediate TigerVNC & SSH compression tweaks on client | ~30% improvement | 1 minute |
| **Phase 2** | Complete local disk install & remove HTTP ISO streaming | 2x responsiveness | 5 minutes |
| **Phase 3** | Disable Hyprland animations, blurs, and shadows (LLVMpipe profile) | 3x CPU & render speedup | 3 minutes |
| **Phase 4** | Deploy Native High-Performance Streaming (XRDP / Sunshine over UDP) | Sub-100ms fluid experience | 10 minutes |

---

## 3. Step-by-Step Implementation Tasks

### Phase 1: Immediate Client & VNC Protocol Tweaks

#### Task 1: Tune TigerVNC Viewer Client Compression
**Objective:** Reduce bandwidth and frame transmission delay in TigerVNC without touching the server.

**Files:** TigerVNC Options Dialog on Windows

**Step 1: Open TigerVNC Settings**
1. In TigerVNC Viewer, click **Options...** (before or during session via F8 key -> Options).
2. Go to **Compression** tab:
   - Select **Preferred encoding**: `Tight`
   - Check **Allow JPEG compression**: Set Quality level to `6` or `7` (reduces frame size by 80%).
   - Set **Compression level**: `6`.
3. Go to **Color & Screen** tab:
   - Select **Color level**: `Medium (256 colors)` or `Low (64 colors)` for maximum speed, or `Medium (16-bit)` for balance.

**Step 2: Enable SSH Compression on Windows Tunnel**
Run the SSH tunnel with the `-C` flag (enables gzip stream compression):
```powershell
ssh -C -L 5901:localhost:5901 root@102.208.217.192 -N
```

**Verification:** Connect TigerVNC to `localhost:5901` and verify typing responsiveness is noticeably sharper.

---

### Phase 2: Complete Local Disk Install

#### Task 2: Install Omarchy to Virtual Disk & Switch to Disk Boot
**Objective:** Stop streaming the 6GB ISO over HTTPS and run entirely from local SSD virtual disk (`omarchy.qcow2`).

**Files:**
- Host: `/root/omarchy/run-vm.sh`
- Host: `/root/omarchy/omarchy.qcow2`

**Step 1: Finish installation in the VNC window**
In the installer GUI:
1. Select target disk (`/dev/vda` - 20 GiB virtio disk).
2. Set your username, password, and encryption passphrase.
3. Allow the installer to partition and copy packages to local disk.
4. When prompted, select **Reboot** or **Power Off**.

**Step 2: Update `run-vm.sh` on host to remove ISO boot**
Edit `/root/omarchy/run-vm.sh` to boot from disk only:

```bash
cat > /root/omarchy/run-vm.sh <<'EOS'
#!/bin/bash
set -e
DISK="$HOME/omarchy/omarchy.qcow2"
OVMF_CODE="/usr/share/OVMF/OVMF_CODE_4M.fd"
OVMF_VARS="$HOME/omarchy/OVMF_VARS.fd"

pkill -9 qemu-system-x86_64 2>/dev/null || true
sleep 1

exec qemu-system-x86_64 \
  -enable-kvm -cpu host -smp 2 -m 2560 \
  -machine q35 \
  -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" \
  -drive if=pflash,format=raw,file="$OVMF_VARS" \
  -drive file="$DISK",if=virtio,format=qcow2 \
  -boot order=c \
  -net nic,model=virtio -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::3389-:3389 \
  -vnc 127.0.0.1:1 \
  -daemonize -display none \
  -vga virtio
EOS
chmod +x /root/omarchy/run-vm.sh
/root/omarchy/run-vm.sh
```

**Verification:** Run `ps aux | grep qemu` and confirm QEMU is running with `-boot order=c` without network ISO overhead.

---

### Phase 3: Optimize Hyprland for Headless / Software Rendering

#### Task 3: Disable Hyprland Animations, Shadows, and Blurs
**Objective:** Eliminate 90% of unnecessary frame repaints in Hyprland so LLVMpipe software rendering runs at high speed.

**Files:**
- Guest: `~/.config/hypr/hyprland.conf`

**Step 1: SSH into Omarchy guest system**
```bash
ssh -p 2222 your_user@localhost
```

**Step 2: Apply software-rendering optimizations to `hyprland.conf`**
Add/update the following blocks in `~/.config/hypr/hyprland.conf`:

```ini
# Disable expensive rendering effects
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
    vfr = true                  # Variable Frame Rate: only render when screen changes!
    vrr = 0
}

# Cap refresh rate to save CPU and network bandwidth
monitor=,1920x1080@30,auto,1
```

**Step 3: Reload Hyprland**
Press `Super + M` or run `hyprctl reload` inside the guest.

**Verification:** Open a terminal and move windows around. CPU usage on host (`htop`) should drop from 90% to <15%.

---

### Phase 4: Upgrade Remote Protocol from Raw VNC to XRDP / RDP

#### Task 4: Configure XRDP inside Omarchy Guest for Native Windows Remote Desktop
**Objective:** Replace VNC with Microsoft RDP protocol (`mstsc.exe`), which utilizes tile caching, motion vectors, and local pointer rendering to feel near-native.

**Files:**
- Guest: `/etc/xrdp/xrdp.ini`
- Guest: `~/.xinitrc`

**Step 1: Install XRDP and Xorg inside Omarchy guest**
```bash
sudo pacman -S --noconfirm xrdp xorg-server xorg-xinit xorg-xwayland
```

**Step 2: Enable and start XRDP service**
```bash
sudo systemctl enable --now xrdp
sudo systemctl enable --now xrdp-sesman
```

**Step 3: Tunnel RDP port to Windows PC**
Run on Windows PowerShell:
```powershell
ssh -L 3389:localhost:3389 root@102.208.217.192 -N
```

**Step 4: Connect with Windows Remote Desktop Client**
1. Press `Win + R` -> type `mstsc` -> Press Enter.
2. Computer: `localhost:3389`
3. In **Experience** tab: Select `Low-speed broadband (256 Kbps - 2 Mbps)` -> check **Persistent bitmap caching**.
4. Connect.

**Verification:** Connect via Remote Desktop. Keystroke and mouse input lag will be drastically reduced compared to raw VNC.

---

### Phase 5: Switch from TCP Tunnel to UDP Tunnel (Tailscale)

#### Task 5: Eliminate TCP Head-of-Line Blocking with Tailscale
**Objective:** Use direct UDP WireGuard routing instead of SSH TCP tunneling for zero-packet-queueing network latency.

**Step 1: Install Tailscale on host**
```bash
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up
```

**Step 2: Connect Windows client directly via Tailscale IP**
Connect RDP or TigerVNC directly to `100.x.y.z:3389` without needing an SSH tunnel window running.

---

## 4. Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Screen tearing on RDP | Ensure `Persistent bitmap caching` is enabled in `mstsc`. |
| Software render crash | Keep `WLR_RENDERER_ALLOW_SOFTWARE=1` in environment. |
| Port 3389 collision on Windows | Map host port `3390` in SSH tunnel: `ssh -L 3390:localhost:3389` -> connect to `localhost:3390`. |

---

## 5. Next Steps

1. **Immediate fix right now:** In your open TigerVNC Viewer, press `F8` -> `Options` -> `Compression` -> Enable **JPEG (Quality 6)** and **Tight** encoding.
2. **Execute plan:** Finish the Omarchy installation to disk so we can execute Phases 2, 3, and 4.
