# Sample run — Runway Aleph video-to-video (TV2V)

Live end-to-end result of the `runway-aleph-v2v` model on one VBVR
object-permanence task, used to verify the text+video → video pipeline.

## Files
- `inputs/prompt.txt` — text prompt (the reasoning question / scene description)
- `inputs/first_frame.png` — first frame (for reference; v2v does **not** use it)
- `inputs/first_video.mp4` — the v2v conditioning input (first half of the simulation)
- `output.mp4` — video returned by the Runway Aleph API (h264, 1080p)
- `run.log` — full runner log for this generation

## How it was produced
```bash
export RUNWAYML_API_SECRET=...        # Runway developer key (dev.runwayml.com)
python examples/generate_videos.py \
  --model runway-aleph-v2v \
  --questions-dir <dir with {domain}_task/{task_id}/ holding prompt.txt + first_video.mp4> \
  --output-dir ./outputs
```

## Notes
- Aleph derives its output length from the input video and rejects a `duration`
  key — the wrapper does not send one (see the `runway_inference.py` fix).
- The input clip must be ≥ 2 s (Runway asset minimum). Full (non-preview) VBVR
  renders clear this; preview-mode clips may be too short.
