# Sample run — Runway ML (runway-gen45)

Live end-to-end result of the `runway-gen45` model on one VBVR object-permanence task
(`turntable_behind_screen_0000`), from the 2026-06-22 batch run.

## Files
- `inputs/prompt.txt` — scene description / reasoning prompt
- `inputs/first_frame.png` — first frame (i2v conditioning image)
- `output.mp4` — video returned by the API

## Result data
| Field | Value |
|-------|-------|
| Provider / catalog id | Runway ML · `runway-gen45` (model `gen4.5`) |
| Modality | image → video (i2v) |
| Status | ✅ Completed (1/1) |
| Wall-clock | 2m13s |
| Output | 1280×720, h264, 24fps, 5.04s, 670KB |
| Audio | none |

## How it was produced
```bash
python examples/generate_videos.py --model runway-gen45 \
  --questions-dir <dir with {domain}_task/{task_id}/ holding prompt.txt + first_frame.png> \
  --output-dir ./outputs
```
