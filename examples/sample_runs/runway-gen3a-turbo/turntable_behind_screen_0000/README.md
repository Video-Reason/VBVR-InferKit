# Sample run — Runway ML (runway-gen3a-turbo)

Live end-to-end result of the `runway-gen3a-turbo` model on one VBVR object-permanence task
(`turntable_behind_screen_0000`), from the 2026-06-22 batch run.

## Files
- `inputs/prompt.txt` — scene description / reasoning prompt
- `inputs/first_frame.png` — first frame (i2v conditioning image)
- `output.mp4` — video returned by the API

## Result data
| Field | Value |
|-------|-------|
| Provider / catalog id | Runway ML · `runway-gen3a-turbo` (model `gen3a_turbo`) |
| Modality | image → video (i2v) |
| Status | ✅ Completed (1/1) |
| Wall-clock | 0m25s |
| Output | 1280×768, h264, 24fps, 5.21s, 837KB |
| Audio | none |

## How it was produced
```bash
python examples/generate_videos.py --model runway-gen3a-turbo \
  --questions-dir <dir with {domain}_task/{task_id}/ holding prompt.txt + first_frame.png> \
  --output-dir ./outputs
```
