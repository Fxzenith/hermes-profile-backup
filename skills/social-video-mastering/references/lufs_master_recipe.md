# LUFS Master Recipe (validated — ffmpeg has all filters)

Two-pass loudnorm. Pass 1 measures, pass 2 applies using measured stats.

## Pass 1 (measure)
```
ffmpeg -y -hide_banner -i in.mp4 -af "highpass=f=80,deesser,acompressor=ratio=3:threshold=-20dB:attack=5:release=50:makeup=2dB,loudnorm=I=-14.0:TP=-1.0:LRA=11.0:print_format=json" -f null -
```
Parse the JSON block from stderr: `input_i`, `input_tp`, `input_lra`, `input_thresh`,
`target_offset`. Regex: `\{\s*"input_i"\s*:.*?\}`.

## Pass 2 (apply)
```
ffmpeg -y -hide_banner -threads 2 -i in.mp4 \
  -af "highpass=f=80,deesser,acompressor=ratio=3:threshold=-20dB:attack=5:release=50:makeup=2dB,loudnorm=I=-14.0:TP=-1.0:LRA=11.0:measured_I=<i>:measured_TP=<tp>:measured_LRA=<lra>:measured_thresh=<thresh>:offset=<offset>:linear=true" \
  -ar 48000 -c:v copy -c:a aac -b:a 192k -max_muxing_queue_size 1024 out.mp4
```
- If measurement parse fails, fall back to `linear=true` single-pass (still safe).
- `out.mp4` MUST differ from `in.mp4` (ffmpeg refuses in-place). Stage to
  `in.audio_master.mp4` then `shutil.move` over the original.
- Platform targets: Shorts I=-14.0/TP=-1.0; TikTok+Reels I=-11.0/TP=-1.5.
  Mastering to Shorts -14 avoids YouTube's -8 dB attenuation penalty (worst case);
  TikTok/Reels then play -14 slightly quiet but clean.

## Filter availability probe
```
ffmpeg -hide_banner -filters 2>/dev/null | grep -E ' (loudnorm|highpass|deesser|acompressor|alimiter|afftdn) '
```
On the tested box all are present. Degrade gracefully: if `deesser`/`acompressor`
absent, drop them and keep loudnorm (the part that prevents platform penalties).
