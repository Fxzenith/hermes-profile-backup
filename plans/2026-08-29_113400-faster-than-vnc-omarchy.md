# Faster-Than-VNC Omarchy Alternatives Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Replace VNC (`-vnc 127.0.0.1:1 -vga virtio -display none`) with a sub-50ms, hardware-accelerated remote display for the Omarchy (Hyprland/Wayland) VM on this VPS.

**Architecture:** Keep QEMU/KVM + `omarchy.qcow2` but swap the display/remote-access layer. Evaluate 6 alternatives in a decision matrix (latency, Wayland support, setup cost, bandwidth), pick top 2 for implementation, patch `run-vm.sh` and Omarchy guest packages, expose new hostfwd ports, and provide client connection runbook.

**Tech Stack:** QEMU/KVM (q35, virtio), Hyprland/Wayland, SPICE/virt-viewer, RDP (xrdp + gnome-remote-desktop or xrdp), Waypipe, Sunshine/Moonlight, VirGL (`-display sdl,gl=on` / `-vga virtio -display gtk,gl=on`), TigerVNC as baseline. Host: Ubuntu 24.04, 5.8GB RAM, 8GB swap, 3 vCPUs.

---

## Current Context / Assumptions

- Host: VPS `Linux 6.8.0-106`, 5.8Gi RAM, 3 vCPUs, `/dev/sda1 48G` (now 43G used / 4.7G free after cleanup). Swap 8GB (`/swap.img` + `/swap2.img`). No Docker daemon, no `virsh`.
- VM: `/root/omarchy/omarchy.qcow2` (6.9G), `OVMF_CODE_4M.fd` + `OVMF_VARS.fd`, ` -smp 2 -m 4096`, `-net user,hostfwd=tcp::2222-:22,hostfwd=tcp::3389-:3389`, `-vnc 127.0.0.1:1 (5901)`, `-vga virtio -display none -daemonize`, PID 3831871. Guest is Omarchy = Arch + Hyprland (Wayland compositor). VNC is framebuffer polling → high latency, no cursor tablet, no accel.
- User complaints: tiled window layout confusion + high mouse/cursor latency. Already fixed layout shortcuts (`SUPER+J/Q/V`), bumped RAM 2.5→4G, swapped 4→8G, rebooted VM.
- Network: VPS NAT, user connects over internet (not LAN) — needs TCP, ideally UDP for streaming. SSH reachable on 2222.
- No GPU passthrough; only VirGL (virtio-GPU) available if host has `virglrenderer`.
- Read-only insight needed: check `virglrenderer` installed? `qemu-system-x86_64 -display help`, guest `hyprland.conf`, `pacman -Q | grep -E "xrdp|sunshine|waypipe"`.

## Proposed Approach

1. **Benchmark baseline** — measure VNC latency/bandwidth (so wins are provable).
2. **Decision matrix** — score 6 alternatives on Wayland compatibility, latency, install friction, VPS suitability, security.
3. **Implement #1: SPICE + Virtio tablet** — lowest-risk QEMU-native fix for cursor latency (keeps TCP, minimal guest changes, fixes absolute pointer).
4. **Implement #2: RDP (xrdp) or Waypipe** — best throughput for Hyprland/Wayland over WAN; if RDP fails on Wayland, fall back to Sunshine/Moonlight (H.264/H.265 streaming).
5. **Optional VirGL accel** — add `-device virtio-vga-gl` + `-display egl-headless` if host supports it, to offload compositing.
6. **Runbook + rollback** — client commands for each method, and how to revert to VNC in 10s.

VNC stays as fallback on 5901 until new method is verified.

---

## Step-by-Step Plan

### Task 1: Capture Baseline & Host Capabilities

**Objective:** Quantify current VNC pain and what the host can do.

**Files:**
- Read: `/root/omarchy/run-vm.sh`
- Read: `/usr/share/OVMF/OVMF_CODE_4M.fd` (exists check)
- Create: `.hermes/plans/baseline.md` (temp notes, not committed)

**Step 1:** Run read-only probes
```bash
qemu-system-x86_64 -display help 2>&1 | head -20
qemu-system-x86_64 -device ? 2>&1 | grep -E "virtio-vga|usb-tablet|spice"
dpkg -l | grep -E "virgl|spice|virt-viewer"
ss -tlnp | grep -E "5901|2222|3389"
ssh -p 2222 localhost "cat ~/.config/hypr/hyprland.conf | head -60; pacman -Q | grep -E 'xrdp|sunshine|waypipe' || true"
ping -c 5 1.1.1.1 | tail -2
free -h; swapon --show; df -h /
```

**Step 2:** Record baseline: VNC latency (perceived ms), `free`, `df`, host `virgl` availability.

**Step 3:** Document in plan appendix.

**Validation:** `qemu-system-x86_64 -display help` returns; SSH to guest succeeds.

---

### Task 2: Build Decision Matrix (6 Alternatives)

**Objective:** Produce scored comparison so choice is data-driven, not guesswork.

**Files:**
- Create: `.hermes/plans/omarchy-display-matrix.md` (will be folded into final plan or standalone)

**Alternatives to score (1-5, 5=best):**

| # | Alternative | Wayland Hyprland Native? | Expected Latency (WAN) | Setup Friction | Bandwidth | Security | VPS 5.8GB Friendly? |
|---|-------------|--------------------------|------------------------|----------------|-----------|----------|---------------------|
| A | **SPICE + QXL + usb-tablet** | Yes (framebuffer) | 40-80ms | Low (QEMU flags only) | ~5-10 Mbps | TLS optional | Yes |
| B | **RDP via xrdp / gnome-remote-desktop** | Partial (needs XWayland or WLR RDP backend) | 30-60ms | Medium (guest package + service) | 3-8 Mbps | TLS/NLA | Yes |
| C | **Waypipe (SSH tunnel)** | **Yes, native Wayland** | 20-50ms | Medium (guest + host install) | 5-15 Mbps | SSH | Yes |
| D | **Sunshine (host) + Moonlight (client) — H.264/AV1 streaming** | Yes (captures Wayland via KMS) | 15-35ms (UDP) | High (build + GPU encode) | 10-30 Mbps | HTTPS | Needs encode (CPU) |
| E | **VirGL + SPICE (`virtio-vga-gl` + `egl-headless`)** | Yes (GPU accel) | Same as A but smoother | Medium (needs virglrenderer) | Same as A | Same as A | Yes if `virglrenderer` present |
| F | **NoMachine / RustDesk / Tailscale** | Varies | 30-70ms | Medium-High (3rd party) | 5-20 Mbps | Varies | No (extra deps) |

**Step 1:** Fill matrix with real host checks from Task 1 (e.g., if `virglrenderer` missing, E=1).

**Step 2:** Rank: Recommended = **A (SPICE+tablet) first**, **B or C second** (if B fails Wayland test, use C; if user prioritizes lowest latency over LAN-like, pick D).

**Step 3:** Include client requirements per alternative (virt-viewer, xfreerdp, waypipe, moonlight).

**Validation:** Matrix has 6 rows, all columns filled, 2 winners highlighted with rationale.

---

### Task 3: Implement Alternative A — SPICE + USB Tablet (Immediate Cursor Fix)

**Objective:** Fix mouse latency with <2 min change, keep VNC as fallback.

**Files:**
- Modify: `/root/omarchy/run-vm.sh:12-20` (QEMU flags)
- Create: `/root/omarchy/run-vm-spice.sh` (optional alt launcher)

**Step 1: Patch run-vm.sh**
```bash
# BEFORE
  -vnc 127.0.0.1:1 \
  -daemonize -display none \
  -vga virtio

# AFTER (keep VNC as fallback, add SPICE on 5930 + tablet)
/root/omarchy/run-vm.sh:
  -vnc 127.0.0.1:1 \
  -spice port=5930,disable-ticketing \
  -device virtio-serial-pci \
  -chardev spicevmc,id=vdagent,name=vdagent \
  -device virtserialport,chardev=vdagent,name=com.redhat.spice.0 \
  -device usb-tablet \
  -device virtio-keyboard-pci \
  -daemonize -display none \
  -vga qxl   # or -vga virtio if qxl not available
```

Also add hostfwd for SPICE: `-net user,hostfwd=tcp::2222-:22,hostfwd=tcp::3389-:3389,hostfwd=tcp::5930-:5930`

**Step 2: Validate inside**
```bash
bash /root/omarchy/run-vm.sh
ss -tlnp | grep 5930
ps aux | grep qemu | grep spice
# client: virt-viewer spice://VPS_IP:5930  or remote-viewer spice://...
```

**Step 3: Inside guest (via SSH 2222)**
```bash
sudo pacman -S --noconfirm spice-vdagent qemu-guest-agent
sudo systemctl enable --now spice-vdagentd qemu-guest-agent
```

**Step 4: Commit**
```bash
git -C /root add omarchy/run-vm.sh  # if tracked, else note in backup
```

**Validation:** `ss -tlnp` shows 5930 LISTEN, `spice-vdagent` running, cursor no longer lags/drifts in virt-viewer. VNC still works on 5901.

**Risks:** SPICE without TLS over internet — mitigate by noting SSH tunnel: `ssh -L 5930:localhost:5930 root@VPS` then connect to `spice://localhost:5930`.

---

### Task 4: Implement Alternative B — RDP (Primary WAN Recommendation) OR C — Waypipe (Wayland-Native)

**Objective:** Provide high-throughput, low-latency access that beats VNC by 2-3x.

**Files:**
- Modify: `/root/omarchy/run-vm.sh` (add `hostfwd=tcp::3390-:3389` if needed, keep)
- Guest (via SSH): `/etc/xrdp/xrdp.ini`, `~/.config/hypr/hyprland.conf` (exec-once)

**Branch B (RDP) — try first:**
```bash
# Guest
ssh -p 2222 user@localhost
sudo pacman -S --noconfirm xrdp xorgxrdp  # Arch
sudo systemctl enable --now xrdp
# For Hyprland/Wayland: use xrdp's Xorg fallback or gnome-remote-desktop
# Option: add to hyprland.conf:
# exec-once = /usr/bin/gnome-remote-desktop --rdp
# Test:
xfreerdp /v:VPS_IP:3389 /u:omarchy_user /p:xxx +clipboard /dynamic-resolution
```

If Hyprland RDP fails (Wayland compositor doesn't expose RDP), switch to Branch C.

**Branch C (Waypipe) — Wayland-native:**
```bash
# Host (VPS)
sudo apt install -y waypipe  # or build
# Guest (Arch)
sudo pacman -S --noconfirm waypipe

# Usage (user runs locally):
ssh -p 2222 -X user@VPS "waypipe ssh -p 2222 user@localhost waypipe show foot"
# Simpler: waypipe ssh -p 2222 user@VPS_IP -- waypipe ssh user@localhost weston-terminal
# For full desktop: waypipe ssh -p 2222 user@VPS "waypipe ssh user@localhost hyprctl"
# Benchmark: waypipe ssh ... -- hyprland -- wayland app
```

**Pick one winner** based on actual test: if `xrdp` works on Hyprland in <5 min, ship B; else ship C. Document both but mark primary.

**Validation:** Connect from external machine: RDP shows desktop in <3s, typing latency <60ms (vs VNC >120ms). Or `waypipe ssh` launches a Wayland app with no VNC lag.

---

### Task 5: Optional VirGL Acceleration (If Host Supports It)

**Objective:** Offload Hyprland compositing to host GPU (even llvmpipe) to smooth animations that worsen perceived latency.

**Files:**
- Modify: `/root/omarchy/run-vm.sh` (display line)

**Step 1: Check**
```bash
dpkg -l | grep virgl
ls /usr/lib/x86_64-linux-gnu/libvirgl* 2>&1 | head
```

**Step 2: If present, patch:**
```bash
# Replace
  -vga virtio -display none
# With
  -device virtio-vga-gl \
  -display egl-headless,gl=on \
  -daemonize
# Or: -display sdl,gl=on (if host has display)
```

**Step 3: Guest**
```bash
# Verify inside guest:
glxinfo | grep -i virgl
hyprctl keyword animations:enabled 1  # re-enable to test smoothness
```

**Validation:** `glxinfo` shows `virgl`, Hyprland animations 60fps vs 15fps before. If not present, skip task and note "host lacks virglrenderer — skip, not blocking".

---

### Task 6: Benchmark, Runbook & Rollback

**Objective:** Deliver measurable proof and one-page client guide.

**Files:**
- Create: `/root/omarchy/CONNECT.md` (or `.hermes/plans/` handoff doc)
- Create: `/root/omarchy/benchmark.md`

**Benchmark (simple, no tooling):**
```bash
# Latency: measure time from keypress to screen (use `xev` or `wev` in guest, or just subjective)
# Bandwidth: watch `nload` or `iftop` on host during drag
# CPU: `top` host + `htop` guest during 1080p move
# Table: VNC vs SPICE vs RDP/Waypipe (ms, Mbps, CPU%)
```

**Runbook (`CONNECT.md`):**
```markdown
# Omarchy Connect — Faster Than VNC

1. SPICE (quick fix, TCP):
   ssh -L 5930:localhost:5930 root@VPS_IP
   remote-viewer spice://localhost:5930

2. RDP (recommended WAN):
   xfreerdp /v:VPS_IP:3389 /u:USER /p:PASS +clipboard /dynamic-resolution
   # Windows: mstsc -> VPS_IP:3389

3. Waypipe (Wayland-native, SSH):
   waypipe ssh -p 2222 USER@VPS_IP -- foot

4. Fallback VNC:
   vncviewer VPS_IP:5901
```

**Rollback (10s):**
```bash
# Restore VNC-only
cp /root/omarchy/run-vm.sh.bak /root/omarchy/run-vm.sh
pkill -f qemu-system-x86_64; bash /root/omarchy/run-vm.sh
```

**Validation:** Each connect method tested from external client, results in benchmark.md. Rollback script works.

---

## Files Likely to Change

- `/root/omarchy/run-vm.sh` — primary (all display/net flags)
- `/root/omarchy/OVMF_VARS.fd` — untouched (but backed up before flags change)
- Guest: `~/.config/hypr/hyprland.conf` (exec-once for vdagent/xrdp, animations toggle)
- Guest: `/etc/xrdp/xrdp.ini` (if RDP chosen), `/etc/systemd/system/spice-vdagentd.service`
- Host: `/etc/fstab` — not changed (swap already 8GB); `/etc/ssh/sshd_config` only if Waypipe needs X11Forwarding (unlikely)
- Docs: `/root/omarchy/CONNECT.md`, `/root/omarchy/benchmark.md`, `.hermes/plans/*.md`

## Tests / Validation

- **SPICE:** `ss -tlnp | grep 5930`, `spice-vdagent` active, cursor absolute (no drift when moving fast), copy-paste guest↔host.
- **RDP:** `xfreerdp` connects, dynamic resolution works, 1080p YouTube in guest <60ms lag.
- **Waypipe:** `waypipe ssh ... -- foot` opens, no VNC polling artifacts.
- **VirGL (optional):** `glxinfo | grep virgl` passes.
- **Fallback:** VNC on 5901 still connects after changes.
- **Host health:** `free -h` >500M available, `df -h /` <92% (currently 91% after cleanup), `swapon --show` 8G.

## Risks, Tradeoffs, and Open Questions

- **Risk: Wayland + xrdp incompatibility.** Hyprland is Wayland-only; `xrdp` historically Xorg. Mitigation: test `gnome-remote-desktop` RDP backend (supports Wayland via `xdg-desktop-portal-wlr`) or pivot to Waypipe (Task 4 Branch C). Keep SPICE as guaranteed win.
- **Tradeoff: SPICE vs RDP.** SPICE = lowest guest changes, but TCP and less WAN-optimized (jitter). RDP = best WAN compression but needs guest service. Waypipe = most native for Wayland but SSH tunnel = TCP head-of-line blocking unless run over UDP (not trivial). Sunshine/Moonlight = lowest latency but highest CPU encode + UDP firewall complexity — recommended only if user wants LAN-like gaming latency and accepts 10-30 Mbps.
- **Risk: Disk 91% full.** Adding packages in guest (xrdp, spice-vdagent, waypipe) grows `omarchy.qcow2` (which lives on host `/`). Host has 4.7G free; guest installs are inside qcow2, not host, but qcow2 can grow. Monitor `qemu-img info /root/omarchy/omarchy.qcow2` and `df -h`.
- **Risk: Security (SPICE/RDP without TLS).** Mitigation: document SSH tunnel (`-L 5930:localhost:5930`, RDP over SSH `-L 3389:...`) and/or enable TLS in SPICE (`-spice tls-port=... x509`).
- **Tradeoff: VirGL.** Needs `virglrenderer` on host; if missing, skip. Benefit ~20% smoother compositing, not critical for latency.
- **Open Q1:** Does Omarchy guest already have an RDP daemon enabled on 3389? `ss -tlnp` inside guest will tell (currently host forwards 3389 but guest may not listen). Verify before Task 4.
- **Open Q2:** User's client OS? Windows → RDP/Moonlight easiest; Linux → SPICE/Waypipe easiest; macOS → RDP/Moonlight. Runbook should cover all three.
- **Open Q3:** Bandwidth cap? VPS egress may be metered — Sunshine at 30 Mbps could cost. Note in matrix.

## Next Step

Plan saved to `.hermes/plans/`. Ready to execute using subagent-driven-development — dispatch a fresh subagent per task with two-stage review (spec compliance then code quality). Shall I proceed?
