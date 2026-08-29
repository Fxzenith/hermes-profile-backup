# Omarchy Display Decision Matrix — 6 Alternatives (2026-08-29)

> **Source of truth:** `.hermes/plans/baseline.md` (host probe 2026-08-29 11:41 SAST) + `.hermes/plans/2026-08-29_113400-faster-than-vnc-omarchy.md`
> **Host caps (Task 1):** `VirGL PARTIAL llvmpipe` · `QXL+usb-tablet YES` · `SPICE YES`

---

## 0. Host Capability Snapshot (constrains all scores)

| Fact | Value | Impact on matrix |
|------|-------|------------------|
| QEMU | 8.2.2 (Debian 1:8.2.2+ds) | all display backends below validated via `-display help` / `-device ?` |
| `/dev/kvm` | `crw-rw---- root:kvm`, `kvm_intel` loaded, `-enable-kvm -cpu host` OK | no penalty — all alternatives benefit |
| Display backends | `none` `gtk` `sdl` `egl-headless` `curses` `spice-app` `dbus` | `egl-headless,gl=on` exists → VirGL syntactically valid |
| VGA options | `none` `std` `cirrus` `vmware` `qxl` `virtio` | `qxl` confirmed via `hw-display-qxl.so` |
| Display devices | `virtio-gpu-gl`, `virtio-vga-gl`, `qxl`, `usb-tablet`, `virtio-tablet` all present | A + E zero-risk; tablet fixes VNC drift immediately |
| SPICE | `libspice-server 0.15.1`, `ui-spice-core.so` `ui-spice-app.so` `hw-display-qxl.so` present, `-spice help` full | **A ✅ READY**, E ✅ syntactically ready |
| VirGL / OpenGL | `libvirglrenderer 1.0.0`, `hw-display-virtio-gpu-gl.so` `ui-egl-headless.so` present | **E ⚠️ PARTIAL** — `/dev/dri/card0` exists but **no `renderD128`** → llvmpipe CPU fallback only |
| RAM | **5.8 GiB total, 136 MiB free, 278 MiB avail**, QEMU 3.1 GiB RSS, swap 8 GiB (3.9 GiB used), load 2.59 | penalises CPU-heavy encode (D) and extra daemons (F); favours QEMU-flag-only (A) |
| Disk | `/ 48G 94% 3.2G free` (was 91%) | qcow2 growth risky; host package installs need `apt clean` first |
| Network | `ss` shows `0.0.0.0:2222→22`, `0.0.0.0:3389→3389`, `127.0.0.1:5901` VNC; ping 1.1.1.1 1.6 ms | SSH (2222) TCP OK but guest banner timeout (overload) — hostfwd required for new ports |
| Guest | Omarchy = Arch + **Hyprland (Wayland compositor)** | Wayland-native column is decisive; Xorg-only solutions penalised |

**Derived verdicts used below:** `SPICE=YES` · `QXL=YES` · `usb-tablet=YES` · `VirGL=PARTIAL (llvmpipe)` — not GPU.

---

## 1. Scored Matrix (1–5, 5 = best)

> **Scoring rubric — higher is better in every column:**
> - **Wayland Hyprland native** — renders Hyprland/Wayland without XWayland or Xorg shim; 5 = native Wayland capture/forward.
> - **Latency WAN** — expected input→photon over internet (VPS NAT, TCP unless noted UDP); 5 = <35 ms.
> - **Setup friction** — inverse of effort; 5 = QEMU flags only, no guest build.
> - **Bandwidth** — efficiency at 1080p desktop + light video; 5 = <5 Mbps.
> - **Security** — encryption/auth by default, safe over internet; 5 = TLS/SSH/NLA out of box.
> - **VPS 5.8 GB friendly** — fits 136 MiB free / 3.2G disk / no render node; 5 = <50 MiB extra RAM, no compile.

| # | Alternative | Wayland native | Latency WAN | Setup friction | Bandwidth | Security | VPS 5.8 GB friendly | **Weighted total /30** | Verdict |
|---|-------------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|---------|
| **A** | **SPICE + QXL + usb-tablet + vdagent** | 4 | 3 | **5** | 3 | 3 | **5** | **23** | **#1 — Implement first** |
| **B** | **RDP via xrdp / xorgxrdp** | 2 | 4 | 3 | **5** | 4 | 4 | 22 | **#2 candidate — test Wayland first** |
| **C** | **Waypipe (SSH Wayland forward)** | **5** | 4 | 3 | 3 | **5** | **5** | 25* | **#2 candidate — Wayland-native fallback** |
| **D** | **Sunshine (guest) + Moonlight (client) — H.264/AV1** | 4 | **5** | 2 | 2 | 4 | 2 | 19 | Specialist — lowest latency, highest cost |
| **E** | **VirGL + SPICE (`virtio-vga-gl` + `egl-headless,gl=on`)** | 4 | 3 | 3 | 3 | 3 | 3 | 19 | Partial — llvmpipe only, A/B test later |
| **F** | **NoMachine / RustDesk / Tailscale-serve** | 3 | 3 | 2 | 3 | 3 | 2 | 16 | Not recommended on this host |

\* C scores 25 raw but is **scoped**: per-app forwarding, not full desktop. See §3 for why ranking is conditional — raw total ≠ winner on this host.

### How to read this table
- Scores incorporate **actual host probes** — E is capped at 3 for VPS-friendly because llvmpipe adds CPU on a 100%-CPU host; D is capped at 2 for same reason (software H.264 encode).
- B's Wayland column is 2 because `xrdp` is Xorg-based; it needs `xorgxrdp` X session or `gnome-remote-desktop` RDP backend via `xdg-desktop-portal-wlr` — both unproven on Hyprland without guest SSH test.
- VNC baseline (current `-vnc 127.0.0.1:1 -vga virtio -display none`, no tablet) would score **1 / 2 / 5 / 2 / 2 / 5 = 17** — every alternative beats it on latency and cursor, but A beats it cheapest.

---

## 2. Per-Alternative Deep Dive

### A — SPICE + QXL + usb-tablet (QEMU-native, zero guest-build fix)

| Dimension | Details |
|-----------|---------|
| **What changes** | Host: `run-vm.sh` → add `-spice port=5930,disable-ticketing -vga qxl -device usb-tablet -device virtio-serial-pci -chardev spicevmc,id=vdagent,name=vdagent -device virtserialport,chardev=vdagent,name=com.redhat.spice.0` + `hostfwd=tcp::5930-:5930`. Keep `-vnc 127.0.0.1:1` as fallback. Guest: `pacman -S spice-vdagent qemu-guest-agent && systemctl enable --now spice-vdagentd` |
| **Wayland Hyprland native (4/5)** | SPICE captures the QXL framebuffer regardless of compositor — Hyprland included. Not Wayland-protocol-native (no `wlr` portal), but displays correctly. Loses 1 point vs Waypipe because no per-surface forwarding. |
| **Latency WAN (3/5)** | 40–80 ms WAN (TCP). Fixes the *perceived* bottleneck immediately: `usb-tablet` gives absolute pointer (eliminates VNC drift/lag even before SPICE streaming). SPICE's adaptive streaming (~5–10 Mbps) beats VNC polling 2×, but still TCP head-of-line blocking → jitter on lossy links. |
| **Setup friction (5/5)** | Lowest of all 6. Modules already on host. Edit one file, restart QEMU, `ss -tlnp \| grep 5930` to verify. No compile, no host `apt install`. |
| **Bandwidth (3/5)** | ~5–10 Mbps at 1080p (QXL + SPICE image compression, `streaming-video=filter`). Better than VNC raw, worse than RDP's RLE. |
| **Security (3/5)** | `disable-ticketing` = unauth TCP by default. **Mitigate:** SSH tunnel `ssh -L 5930:localhost:5930 root@VPS` → `spice://localhost:5930`, or add `-spice tls-port=5931,x509-dir=/etc/spice` (needs certs). Score 3 reflects tunnel-required. |
| **VPS 5.8 GB friendly (5/5)** | Zero extra RAM (QEMU flag only), zero disk beyond `spice-vdagent` (~2 MB) in qcow2. Only option safe at 136 MiB free without `apt clean`. |
| **Host cap tie-in** | Directly uses verified `QXL YES` `usb-tablet YES` `SPICE YES`. No dependency on missing `renderD128`. |
| **When it fails** | User on CGNAT/strict firewall that blocks 5930 — use SSH tunnel. Very high-loss WAN — consider D. |

### B — RDP via xrdp / xorgxrdr / gnome-remote-desktop

| Dimension | Details |
|-----------|---------|
| **What changes** | Guest: `pacman -S xrdp xorgxrdp` (or `gnome-remote-desktop` for Wayland RDP backend), `systemctl enable --now xrdp`, `hostfwd` already `3389→3389`. Optional `hyprland.conf` exec-once for `gnome-remote-desktop --rdp`. Host: no change. |
| **Wayland Hyprland native (2/5)** | **Biggest risk.** `xrdp` is Xorg. Two paths: (i) xorgxrdp creates a separate Xorg session — Hyprland Wayland session is *not* visible (user gets X desktop, not Hyprland). (ii) `gnome-remote-desktop` RDP via `xdg-desktop-portal-wlr` *can* share Wayland, but untested on Omarchy/Hyprland; needs portal + pipewire. Scores 2 until guest SSH probe proves path (ii). |
| **Latency WAN (4/5)** | 30–60 ms WAN when it works. RDP is the most WAN-optimised TCP protocol here (RLE, progressive, `/dynamic-resolution`). Beats SPICE on slow links. |
| **Setup friction (3/5)** | Medium. Guest package + service + firewall + test. No host compile, but Hyprland config may need branching. SSH timeout at probe time means this cannot be validated without guest recovery. |
| **Bandwidth (5/5)** | 3–8 Mbps — best in matrix for desktop use (RDP codecs tuned for text/windows). |
| **Security (4/5)** | NLA + TLS by default (`xrdp` negotiates TLS). Better than SPICE unauth. Still recommend `3389` not exposed without firewall; SSH `-L 3389:localhost:3389` is option. |
| **VPS 5.8 GB friendly (4/5)** | `xrdp` ~30–60 MiB RAM. Fits, but on 136 MiB free any daemon matters — SPICE is leaner. Disk: xorgxrdp ~10 MB in qcow2, acceptable. |
| **Host cap tie-in** | Host forwards 3389 already (`ss` shows `0.0.0.0:3389`). No host GPU needed. VPS-friendly, but guest `pacman` growth watches 94% disk. |
| **Go / no-go test** | `ssh -p 2222 user@localhost 'systemctl status xrdp; loginctl show-session $(loginctl \| awk \"/$(whoami)/{print \\$1}\") -p Type'` — if `Type=wayland` and RDP shows Xorg desktop only → fail, pivot to C. |

### C — Waypipe (SSH-native Wayland forwarding)

| Dimension | Details |
|-----------|---------|
| **What changes** | Host: `apt install waypipe` (or build). Guest: `pacman -S waypipe`. No QEMU flag change. Usage is SSH-transported per-app or per-compositor forwarding. |
| **Wayland Hyprland native (5/5)** | **Only true Wayland-native option.** Forwards `wl_display` protocol, not framebuffer. Hyprland surfaces pass unmodified; no XWayland. Ideal for Omarchy. |
| **Latency WAN (4/5)** | 20–50 ms on localhost/WAN with good link; protocol-level forwarding avoids framebuffer encode. But **TCP-only** (SSH) → head-of-line blocking on lossy WAN limits it to 4, not 5. LAN it would be 5/5. |
| **Setup friction (3/5)** | Medium. Two `waypipe` installs + SSH key workflow. No QEMU restart, but user must learn `waypipe ssh -p 2222 user@VPS -- foot` pattern. Simpler than D/F, harder than A. |
| **Bandwidth (3/5)** | 5–15 Mbps — forwards dmabuf/shm buffers; can be heavier than RDP for full desktop (no RDP-style RLE). Efficient for single apps, less for 1080p video. |
| **Security (5/5)** | Inherits SSH — encrypted, authenticated, no new open port. Best security score. |
| **VPS 5.8 GB friendly (5/5)** | Negligible RAM (SSH child only). No QEMU overhead, no encoder thread. Best alongside A for constrained host. |
| **Host cap tie-in** | Independent of QXL/VirGL/render node. Works even during swap pressure (no extra QEMU CPU). Needs host `apt` disk headroom (3.2G free → run `apt clean`/`journalctl --vacuum-size=100M` first). |
| **Scope caveat** | Waypipe is **per-app** (or `waypipe ssh … -- hyprland` nested compositor), not a drop-in full-desktop viewer. For a full Omarchy desktop, SPICE/RDP remain more ergonomic. Hence conditional ranking. |

### D — Sunshine (guest) + Moonlight (client) — Game-streaming over UDP

| Dimension | Details |
|-----------|---------|
| **What changes** | Guest: build/install `sunshine` (Arch AUR `sunshine`), enable KMS capture (`cap_kms`), open UDP 47984-48010. Host: nothing (tunnel unchanged) but UDP `hostfwd` doesn't exist in QEMU user-net — needs host iptables/UDP forward or Tailscale. Client: Moonlight. |
| **Wayland Hyprland native (4/5)** | Sunshine captures via KMS/DRM on Wayland (works on Hyprland with `cap_kms`). Better than RDP's Xorg gap, but not protocol-native like Waypipe. |
| **Latency WAN (5/5)** | **15–35 ms** — best in matrix. H.264/H.265 over UDP with low-latency encode, FEC, no TCP blocking. Gaming-grade. |
| **Setup friction (2/5)** | **Highest.** Guest build (needs `boost`, `ffmpeg`, `cuda` optional), KMS permissions, UDP firewall/NAT traversal, QEMU user-net has no UDP `hostfwd` helper — must add host-level forward or run behind Tailscale. |
| **Bandwidth (2/5)** | 10–30 Mbps at 1080p60 (even with H.264). Egress cost on metered VPS. Worst for bandwidth / cost. |
| **Security (4/5)** | HTTPS pairing + optional UPnP. Good, but UDP port range expands attack surface; needs firewall pin. |
| **VPS 5.8 GB friendly (2/5)** | **Worst fit.** Software x264 at 1080p adds ~0.8–1.2 vCPU continuous on a host already at 100% QEMU CPU + swap thrashing. No `renderD128` → no VAAPI/GPU encode; pure CPU. 136 MiB free host RAM leaves no headroom for encoder. Disk build deps ~500 MB. **Not recommended until host is upsized or GPU node appears.** |
| **Host cap tie-in** | llvmpipe host cannot accelerate encode. Would need `apt install sunshine` on host? No — Sunshine runs *in guest*, but QEMU user-net UDP forward gap is host limitation. |
| **When to use** | Only if user demands LAN-like latency for Hyprland animations/gaming and accepts CPU/bandwidth cost. Lab test only. |

### E — VirGL + SPICE (`virtio-vga-gl` + `egl-headless,gl=on`)

| Dimension | Details |
|-----------|---------|
| **What changes** | Host: `run-vm.sh` swap `-vga virtio -display none` → `-device virtio-vga-gl -display egl-headless,gl=on` (or `-display sdl,gl=on` if host had display). Guest: `glxinfo \| grep virgl` to verify, re-enable Hyprland animations. Keep SPICE from A. |
| **Wayland Hyprland native (4/5)** | Same framebuffer capture as A, but compositor offloads to host GL. Hyprland sees `virgl` renderer. |
| **Latency WAN (3/5)** | Same WAN as A (TCP SPICE), but **smoother** — llvmpipe offloads compositing, raising fps 15→~40, reducing perceived latency. No network latency win. |
| **Setup friction (3/5)** | Medium. One flag change, but must test `egl-headless` cold boot; broken GL can prevent VM start (rollback needed). Validated syntactically (`ui-egl-headless.so` exists), not runtime-tested. |
| **Bandwidth (3/5)** | Same as A (~5–10 Mbps). VirGL doesn't compress; it just smooths. |
| **Security (3/5)** | Same as A (SPICE channel). |
| **VPS 5.8 GB friendly (3/5)** | **Capped by llvmpipe.** `virtio-vga-gl` + `egl-headless,gl=on` works, but host renders with **llvmpipe (CPU)** — adds ~15–25% CPU on already-saturated host (load 2.59, si 3096). No `renderD128` means no GPU offload. **Worth A/B test after A is stable, not as primary.** If host later exposes `renderD128` or `card0` render node, score rises to 4–5. |
| **Host cap tie-in** | Directly reflects `VirGL PARTIAL` verdict. Modules ready, render node missing. Recommendation: ship A first, add E as optional flag flip with 10 s rollback (`run-vm.sh.bak`). |
| **Rollback** | `cp /root/omarchy/run-vm.sh.bak /root/omarchy/run-vm.sh; pkill -9 qemu-system-x86_64; bash /root/omarchy/run-vm.sh` — keep VNC+SPICE fallback. |

### F — NoMachine / RustDesk / Tailscale + RustDesk relay

| Dimension | Details |
|-----------|---------|
| **What changes** | Guest: install `nomachine` (proprietary .deb/tar) or `rustdesk` + relay; Host: install relay or Tailscale; open extra ports. |
| **Wayland Hyprland native (3/5)** | RustDesk captures Wayland via `xdg-desktop-portal + pipewire` (partial); NoMachine has experimental Wayland but prefers Xorg. Both variable. |
| **Latency WAN (3/5)** | 30–70 ms — RustDesk's UDP can match RDP, NoMachine's NX is TCP. Neither beats D or tuned RDP. |
| **Setup friction (2/5)** | Medium-High. Proprietary binaries, extra repo, relay setup, Tailscale coordination. More moving parts than xrdp/waypipe. |
| **Bandwidth (3/5)** | 5–20 Mbps (VP8/H.264). RustDesk adaptive, NoMachine NX efficient for desktop. Middle of pack. |
| **Security (3/5)** | RustDesk self-hosted relay + TLS; NoMachine SSH tunnel. Both OK but third-party trust + extra open ports. Varies. |
| **VPS 5.8 GB friendly (2/5)** | **Poor fit.** Background daemons (RustDesk `hbbs`/`hbbr` or NoMachine `nxserver`) add 100–300 MiB RAM + persistent CPU. On 136 MiB free that's OOM risk. Extra deps on 94% disk. Third-party update burden. |
| **Host cap tie-in** | No QEMU integration; bypasses verified SPICE/QXL path. Adds host-level services competing with QEMU for scarce RAM/swap. **Not recommended** unless user already runs Tailscale mesh. |
| **When to use** | User already has Tailscale tailnet and wants zero-port-forward convenience — then RustDesk-over-Tailscale is viable, but still heavier than A/B/C. |

---

## 3. Ranking & Implementation Order

### Ordered winners (as tasked: A first, then B-or-C conditional)

```
#1  A  SPICE + QXL + usb-tablet          ← implement immediately (Task 3)
#2  B  RDP (xrdp)  — IF Hyprland RDP backend works   ─┐
    C  Waypipe     — ELSE (Wayland-native fallback)    ├─ Task 4: test B, ship C if B fails
#3  E  VirGL + SPICE (llvmpipe A/B test) ← after A is stable (Task 5, optional)
#4  D  Sunshine/Moonlight                ← specialist only, not on this VPS
#5  F  NoMachine / RustDesk              ← not recommended
```

### Decision tree for Task 4 (B vs C)

```text
Guest SSH recovers (retry when load <1.5 or after reboot)
        │
        ├─ ssh -p 2222 user@localhost "pacman -Q xrdp gnome-remote-desktop; loginctl show-session -p Type"
        │
        ├─ Install xrdp + test xfreerdp to :3389
        │     ├─ RDP shows Hyprland Wayland desktop (via gnome-remote-desktop + portal)
        │     │     └─► SHIP B — RDP is #2 (best bandwidth, good WAN)
        │     │
        │     └─ RDP shows Xorg session only / fails on Wayland
        │           └─► SHIP C — Waypipe is #2 (true Wayland, SSH security)
        │
        └─ Even if B ships, document C as Wayland-purist option
             (some users prefer per-app forwarding for Hyprland tiled workflow)
```

**Why A is unconditionally #1 on this host:**
- Only alternative that is **5/5 frictionless + 5/5 VPS-friendly + uses already-verified modules**. Every other path needs guest `pacman` installs while host is at 94% disk and guest SSH is timing out. A unblocks cursor latency *before* guest recovery.
- Keeps VNC 5901 as fallback (additive change), so rollback is 10 s.
- Unlocks every later test: once `usb-tablet` + SPICE are in, `spice-vdagent` clipboard and absolute pointer make B/C/D testing actually usable.

---

## 4. Client Requirements per Alternative

| Alt | Client OS | Required client + command | Ports / tunnel | Notes |
|-----|-----------|---------------------------|----------------|-------|
| **A** | **Linux** | `sudo apt install virt-viewer` → `remote-viewer spice://VPS_IP:5930` or `virt-viewer -c spice://VPS_IP:5930` | TCP 5930 (or `ssh -L 5930:localhost:5930 root@VPS` → `spice://localhost:5930`) | Best Linux client; `spicy` also works. Clipboard needs `spice-vdagent` in guest. |
| **A** | **macOS** | `brew install virt-viewer` (or `remote-viewer` dmg) → same URI | same | macOS virt-viewer is XQuartz-based; `spicy --uri spice://…` alternative. |
| **A** | **Windows** | `virt-viewer` for Windows (virt-manager downloads) → `remote-viewer spice://VPS_IP:5930` | same | Windows SPICE client exists but less polished than RDP; recommend SSH tunnel via PuTTY `-L 5930:localhost:5930`. |
| **B** | **Linux** | `sudo apt install freerdp2-x11` → `xfreerdp /v:VPS_IP:3389 /u:USER /p:PASS +clipboard /dynamic-resolution /cert:ignore` | TCP 3389 (`hostfwd` already) | `/dynamic-resolution` resizes with window; `+clipboard` for copy-paste. Remmina also works. |
| **B** | **macOS** | Microsoft Remote Desktop (App Store) → `VPS_IP:3389` | same | Native, best macOS path for B. |
| **B** | **Windows** | `mstsc` (built-in) → `VPS_IP:3389` | same | Zero install; `xfreerdp` alternative via WSL. |
| **C** | **Linux** | Host + guest: `waypipe` installed; `waypipe ssh -p 2222 USER@VPS_IP -- foot` (single app) or `waypipe ssh -p 2222 USER@VPS "waypipe ssh USER@localhost weston-terminal"` | SSH 2222 only (no new port) | Requires Wayland compositor on **client** too (Weston/Sway/Hyprland). X11-only clients cannot run Waypipe. |
| **C** | **macOS / Windows** | **Not directly supported** — needs Linux Wayland client (VM/WSL2 with Wayland) | — | Use A or B on macOS/Windows; Waypipe is Linux→Linux. |
| **D** | **Linux/macOS/Windows** | Guest: `sunshine` (AUR); Client: `moonlight-qt` (all platforms) → pair via PIN `https://VPS_IP:47984` | UDP 47984-48010 + TCP 47989 (+ host UDP fwd/Tailscale — not QEMU user-net) | Needs host iptables `DNAT` for UDP or Tailscale; CPU encode without VAAPI → high load. |
| **E** | **Linux/macOS/Windows** | Same as A (SPICE client) + guest `glxinfo` check; `virt-viewer` benefits from smoother host GL | same as A | No extra client; flag flip on host only. Verify with `glxinfo \| grep virgl` in guest after. |
| **F** | **Linux/macOS/Windows** | NoMachine Enterprise Client or RustDesk client → `VPS_IP` or Tailscale hostname | RustDesk: TCP 21115-21119 + UDP; NoMachine: TCP 4000; Tailscale: DERP | Self-hosted relay needed for RustDesk without Tailscale. Heaviest setup. |
| **Fallback** | All | `vncviewer VPS_IP:5901` (TigerVNC / RealVNC) | TCP 5901, `127.0.0.1` only → needs `ssh -L 5901:localhost:5901 root@VPS` | Keep as emergency rollback; VNC without `usb-tablet` drifts. |

### Quick-pick by client OS

- **Linux Wayland desktop (Hyprland/Sway/Weston)** → **A (immediate) + C (purist)**. Waypipe is most native; SPICE is most compatible.
- **Windows** → **A (tunnel) or B (mstsc)**. B needs zero client install.
- **macOS** → **B (Microsoft Remote Desktop)** or **A (virt-viewer)**. Waypipe not an option.

---

## 5. Security Notes (applies to all)

- **Never expose 5930/3389/5901 to 0.0.0.0 without auth.** Baseline `ss` shows `0.0.0.0:2222/3389` bridged via QEMU user-net — guest firewall (`ufw`/`iptables`) + host SSH tunnel recommended.
- SPICE: add `-spice tls-port=5931,x509-dir=/etc/spice-certs` or tunnel. RDP: NLA/TLS on by default — keep it. VNC: `127.0.0.1` already loopback-only (good).
- Waypipe inherits SSH — strongest default (key auth, no new port).
- Sunshine/Moonlight: pair via HTTPS PIN, then UDP — ensure `ufw allow 47984:48010/udp` scoped, not open.

---

## 6. What Task 4 Must Validate (guest SSH required)

Guest SSH timed out at probe (`banner exchange timeout`, QEMU 100% CPU, swap thrashing). Before scoring B definitively, retry when load drops:

```bash
# Host — check guest recovers
ssh -p 2222 -o ConnectTimeout=10 omarchy@localhost "echo ok; cat ~/.config/hypr/hyprland.conf | head -80; pacman -Q | grep -E 'xrdp|waypipe|sunshine|gnome-remote-desktop' || true; loginctl show-session \$(loginctl | awk '/omarchy/{print \$1; exit}') -p Type -p Desktop 2>&1 | head"

# If timeout persists — reboot gracefully (requires approval):
# pkill -9 qemu-system-x86_64; sleep 2; bash /root/omarchy/run-vm.sh; sleep 20; ssh -p 2222 localhost "echo ok"
```

- If `Type=wayland` + `gnome-remote-desktop` present → B can be Wayland-native → keep B as #2.
- If no RDP daemon or Xorg-only → C is #2.
- Record result in `benchmark.md` (Task 6).

---

## 7. Summary for Implementer

1. **Task 3 — Do A now.** One-file patch to `run-vm.sh`, keep VNC fallback, verify `ss -tlnp | grep 5930`. Host caps guarantee it.
2. **Task 4 — Test B, fall back to C.** Outcome depends on Hyprland RDP portal — cannot score without guest probe. Document both; ship one as primary.
3. **Task 5 — Optional E.** Flip `virtio-vga-gl` + `egl-headless,gl=on` after A proves stable; expect llvmpipe CPU cost — A/B test, keep rollback ready. Do not block on it.
4. **Do not implement D/F on this VPS** without upsizing RAM/disk or adding `renderD128`. Note as lab-only.

---

*Matrix generated 2026-08-29 SAST for Task 2. Next: Task 3 implements A; Task 4 resolves B-vs-C via Wayland test.*
