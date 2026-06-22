# Sample run — OpenAI Sora-2-Pro via WaveSpeed (sora-2-pro-wavespeed)

Live end-to-end result of the `sora-2-pro-wavespeed` model on one VBVR object-permanence task
(`turntable_behind_screen_0000`), from the 2026-06-22 batch run.

## Files
- `inputs/prompt.txt` — scene description / reasoning prompt
- `inputs/first_frame.png` — first frame (i2v conditioning image)
- `output.mp4` — video returned by the API

## Result data
| Field | Value |
|-------|-------|
| Provider / catalog id | OpenAI Sora-2-Pro via WaveSpeed · `sora-2-pro-wavespeed` (model `sora-2-pro`) |
| Modality | image → video (i2v) |
| Status | ✅ Completed (1/1) |
| Wall-clock | 2m48s |
| Output | 1280×720, h264+aac, 24fps, 4.04s, 584KB |
| Audio | aac 44.1kHz stereo |

## How it was produced
```bash
python examples/generate_videos.py --model sora-2-pro-wavespeed \
  --questions-dir <dir with {domain}_task/{task_id}/ holding prompt.txt + first_frame.png> \
  --output-dir ./outputs
```
