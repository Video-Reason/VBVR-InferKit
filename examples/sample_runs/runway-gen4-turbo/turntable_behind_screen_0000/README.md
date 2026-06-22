# Sample run — Runway ML (runway-gen4-turbo)

Live end-to-end result of the `runway-gen4-turbo` model on one VBVR object-permanence task
(`turntable_behind_screen_0000`), from the 2026-06-22 batch run.

## Files
- `inputs/prompt.txt` — scene description / reasoning prompt
- `inputs/first_frame.png` — first frame (i2v conditioning image)
- `output.mp4` — video returned by the API

## Result data
| Field | Value |
|-------|-------|
| Provider / catalog id | Runway ML · `runway-gen4-turbo` (model `gen4_turbo`) |
| Modality | image → video (i2v) |
| Status | ✅ Completed (1/1) |
| Wall-clock | 0m26s (fastest) |
| Output | 1280×720, h264, 24fps, 5.04s, 613KB |
| Audio | none |

## How it was produced
```bash
python examples/generate_videos.py --model runway-gen4-turbo \
  --questions-dir <dir with {domain}_task/{task_id}/ holding prompt.txt + first_frame.png> \
  --output-dir ./outputs
```
