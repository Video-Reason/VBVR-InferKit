# Sample run — Runway Aleph video-to-video (TV2V)

Live end-to-end result of the `runway-aleph-v2v` model on one VBVR
object-permanence task, used to verify the text+video → video pipeline.

## Files
- `inputs/prompt.txt` — text prompt (the reasoning question / scene description)
- `inputs/first_frame.png` — first frame (for reference; v2v does **not** use it)
- `inputs/first_video.mp4` — the v2v conditioning input (first half of the simulation)
- `output.mp4` — video returned by the Runway Aleph API (1920×1080 h264, 24 fps, **5.71 s**)

## Result data
| Field | Value |
|-------|-------|
| Provider / model | Runway ML · `runway-aleph-v2v` (model `aleph2`) |
| Modality | text + video → video (v2v) |
| Status | ✅ Completed |
| Wall-clock | 3m 09s |
| Input | 1280×720, 24 fps, 5.6 s |
| Output | 1920×1080, h264, 24 fps, 5.71 s, 1.24 MB, no audio |

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
- **Input quality matters (updated 2026-06-22):** an earlier run on a degraded
  2.67 s / 640×360 / 10 KB preview clip produced a truncated **0.375 s** output.
  Re-encoding the input to 1280×720 / 24 fps / 5.6 s yields a full **5.71 s** output
  (this sample). For a content-complete 360° turntable v2v, render a full
  `first_video.mp4` on a GPU box (VROP generator).
