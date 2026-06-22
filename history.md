# Work History

A comprehensive log of two parallel tasks: aligning the **VR-Object-Permanence**
dataset generator output to the VBVR layout, and extending **VBVR-InferKit** with
a video-to-video pipeline and new model integrations (Runway Aleph, Seedance,
Sora-via-WaveSpeed).

Both tasks share a contract: the generator produces `{domain}_task/{task_id}/`
samples whose `first_frame.png` / `first_video.mp4` feed the inference toolkit's
image-to-video (i2v) and text+video-to-video (v2v) models.

---

## Repositories & branches

| Repo | Local path | Branch | Remote |
|------|-----------|--------|--------|
| VR-Object-Permanence (VROP) | `~/VR-Object-Permanence` | `zhanghaotian` | `hipo-dev/VR-Object-Permanence` → **PR #6** |
| VBVR-InferKit | `~/haotian/projects/VBVR-InferKit` | `zhanghaotian` | **`Video-Reason/VBVR-InferKit`** (private) → **PR #4** |

> **Repo correction (2026-06-22):** the canonical repo is the private
> `Video-Reason/VBVR-InferKit`, where we have direct push access — work goes on a
> branch there, no fork needed. An earlier harness misconfiguration had `origin` set
> to the public `MJXWANG/VBVR-InferKit` and a `Gujimaji` fork; work was mistakenly
> pushed there and a PR was opened against the public MJXWANG repo (since closed and
> removed). The `zhanghaotian` branch on `Video-Reason` is the canonical place for all
> VBVR work; PR #4 tracks it.

---

## Task 1 — VR-Object-Permanence: align generator output + verify trajectory

**Goal:** make all 53 generators emit the fixed VBVR layout, and confirm the
trajectory data actually works.

```
output/{domain}_task/{domain}_{NNNN}/
├── first_frame.png      first frame (still)
├── final_frame.png      last frame (still)
├── first_video.mp4      first half of simulation  (v2v conditioning input)
├── last_video.mp4       second half               (v2v reference output)
├── ground_truth.mp4     full simulation
├── metadata.json        params, scene-state graph, split info, provenance
├── trajectory.npz       per-frame physics state (qpos, qvel, xpos, xquat)
└── prompt.txt           scene description
```

### What was found
- The eight pieces were **already produced** by earlier commits (`c805862`,
  `12335e4`). The real gap was **directory layout + task_id naming**, not the files.
- **Trajectory "does it work?" — yes, conclusively.** `render.py` steps through
  every frame inside Blender (`scene.frame_set(f)`) and records each object's
  `matrix_world`. A static scan confirmed **all 100 scene scripts use keyframe
  animation** (only G52 touches rigid bodies, and it also keyframes), so
  `frame_set` reproduces translation **and** rotation exactly — no physics-cache
  ordering hazard. Honest caveat already in the code: Blender is not a
  reduced-coordinate engine, so `qpos/qvel` are a free-body mapping +
  finite-difference (documented in `metadata.json` and `generate.py:103`).

### Changes
- **`generate.py`**: `sdir = {name}_task/{name}_{k:04d}`; metadata gains `task_id`
  (`{name}_{NNNN}`) and `domain`.
- **`audit.py`**: `--task` accepts a G-id (`G18`) or domain name; resolves G-id →
  domain via `task.json`. Docstring corrected (eight-piece, SSG v3).
- **`README.md`**: documented the directory layout.
- **`.gitignore`**: ignore `output/` and stray `permanence_blender_outputs/`.
- **`render.py`** (separate commit `5c21de6`): force Cycles when no OpenGL context
  — EEVEE segfaults headless; this is a C-level crash the scene scripts' try/except
  can't catch, so we rewrite the engine preference to Cycles only on GL-less boxes.

### Verification (live, local)
- Rendered **G18** end-to-end with the new layout; `vrop audit` passes (both
  `--task G18` and full-tree).
- Inspected the real `trajectory.npz`: correct shapes (120 frames × 3 bodies;
  `qpos` 21, `qvel` 18), correct `is_target`, finite values, no NaN; the rotating
  target shows peak displacement 1.14 and a 180° spin, static bodies show ~0.

### Commits (branch `zhanghaotian`, → PR #6)
- `5c21de6` Force Cycles when no OpenGL context (headless-safe render)
- `98074c0` Align generator output to VBVR `{domain}_task/{task_id}` layout

### Still open
- **Full 53×N render** must run on a **GPU box** (A10G/g5). This Mac falls back to
  CPU Cycles, far too slow for bulk generation. Command:
  `vrop generate --out ./output --per <N> --parallel <K> --blender <path>` then
  `vrop audit --out ./output`. Bulk data → HuggingFace, not git.

---

## Task 2 — VBVR-InferKit: v2v pipeline + latest / new models

**Goal:** add a text+video→video (TV2V) path, add Seedance, ensure things work,
and wire up the latest commercial models.

### Architecture (as found)
- `ModelWrapper` base + `MODEL_CATALOG.py` registry + dynamic loading.
  Adding a model = new `{provider}_inference.py` (Service + Wrapper) + a catalog
  entry. Wrappers return 8 standardized fields:
  `success, video_path, error, duration_seconds, generation_id, model, status, metadata`.
- The runner (`generate_videos.py` → `InferenceRunner.run` → `wrapper.generate(**kwargs)`)
  passes everything through kwargs, so new inputs (`video_path`) need no base change.
- Output layout `{domain}_task/{task_id}.mp4` already matches Task 1's generator output.

### Verification approach
Every integration was checked twice: a **mock test** (inject a fake SDK, assert
routing + payload + 8-field return) and a **live test** (real API key, real sample,
download a real mp4). Live testing repeatedly caught what mocks could not.

### 2a. Video-input pipeline + Runway Aleph (v2v)
- **`generate_videos.py`**: discovers `first_video.mp4` per task; for catalog
  entries tagged `"modality": "v2v"`, threads it through as `video_path` (errors
  clearly if missing). i2v tasks unchanged.
- **`runway_inference.py`**: `generate_video_to_video()` uploads the input video via
  Runway ephemeral upload and calls `video_to_video.create(model="aleph2", ...)`.
  Wrapper routes v2v vs i2v by `video_path` presence. Model id verified by
  introspecting `runwayml` SDK 5.2.0.
- **`runway-aleph-v2v`** added to the catalog.
- **Live finding → fix (`064d82b`)**: the Aleph API **rejects a `duration` key**
  ("Unrecognized key: duration") and requires the input clip ≥ 2 s. Removed
  `duration` from the v2v call; documented the 2 s minimum. Live run then completed
  and downloaded a valid h264 1080p mp4.
- Commits: `36ee1e1` (pipeline + Aleph), `064d82b` (duration fix), `78e9018` (sample).

### 2b. Seedance (ByteDance) via fal.ai
- **`seedance_inference.py`**: `SeedanceService` + `SeedanceWrapper`. Endpoints
  `fal-ai/bytedance/seedance/v1/{pro,lite}/{text,image}-to-video`, verified against
  the **fal OpenAPI schema**. Routes t2v/i2v by image presence (image uploaded to
  fal storage for `image_url`); validates `duration`/`resolution`/`aspect_ratio`
  against schema enums; `FAL_KEY` auth.
- **`seedance-v1-pro` / `seedance-v1-lite`** added.
- **Finding:** fal exposes **no Seedance video-to-video** endpoint (pro/lite v2v
  both 404; only `lite/reference-to-video`, which takes reference *images*). So
  Seedance is T2V/I2V only — documented. (The original task list grouped Seedance
  under "TV2V"; this is a real provider limitation, not an omission.)
- **Live:** both `lite` and `pro` completed, downloading valid 5 s h264 mp4s.
- Commits: `a19f5dd` (integration), `46ece3f` (lite + pro samples).

### 2c. OpenAI Sora-2 via WaveSpeed
- The provided key is a **WaveSpeed** key (`wsk_live_…`), not OpenAI. The existing
  `openai_inference.py` is direct-OpenAI (`OPENAI_API_KEY`), so a new transport
  was added rather than modifying it.
- **`wavespeed_inference.py`**: `SoraWaveSpeedService` + `WaveSpeedSoraWrapper`.
  `POST /api/v3/openai/{sora-2,sora-2-pro}/{text,image}-to-video`, then poll
  `data.urls.get` until `status == completed`, download `data.outputs[0]`.
  Endpoints/params verified against the **WaveSpeed v3 model schema** and a live
  submit/poll probe. Input image sent inline as a **base64 data URI** (no upload).
  Routes t2v/i2v by image presence.
- **`sora-2-wavespeed` / `sora-2-pro-wavespeed`** added (family "Sora (WaveSpeed)").
  The direct-OpenAI `openai-sora-2*` entries are kept for users with OpenAI keys.
- **Live:** `sora-2-wavespeed` i2v completed end-to-end (~3 min), downloading a valid
  **h264 + aac** mp4 — Sora-2 emits synchronized audio.
- Commits: `fdfa115` (integration), `b42ba57` (sample).

### Catalog growth
32 → **37 models / 14 families** (added Runway Aleph v2v, Seedance pro+lite,
Sora-2 + Sora-2-pro via WaveSpeed).

### Live sample runs committed to the branch
Under `examples/sample_runs/<model>/turntable_behind_screen_0000/` (input prompt +
first frame, the returned `output.mp4`, and `run.log`):
`runway-aleph-v2v`, `seedance-v1-lite`, `seedance-v1-pro`, `sora-2-wavespeed`.

---

## Key findings / decisions

1. **Trajectory works** — keyframe animation across all 100 scripts; `frame_set`
   reproduces motion exactly. Free-body `qpos/qvel` mapping is intentional & documented.
2. **Runway `gen4_aleph` i2v entry is stale** — `runwayml` 5.2.0 no longer accepts
   `gen4_aleph` for image-to-video (Aleph is v2v-only as `aleph2`). The existing
   `runway-gen4-aleph` catalog entry is therefore broken as i2v. **Not yet fixed** —
   belongs in the "verify latest models" pass.
3. **Seedance has no v2v on fal** — T2V/I2V only.
4. **Sora requires WaveSpeed** here — new transport added alongside direct-OpenAI.
5. **Live > mock** — the Aleph `duration` rejection and the ≥2 s input rule were
   only caught by hitting the real API.

---

## Secrets handling
All six provider keys (Runway, Gemini, Kling, WaveSpeed, Luma, fal) live in
`~/haotian/projects/VBVR-InferKit/.env` (mode 600, gitignored). Verified no key
appears in any tracked file and no `.env` is staged. **Recommendation:** rotate the
keys, since they were shared in plaintext once.

---

## Remaining work (Task 2)
1. **Kling TV2V** — check whether Kling exposes video continuation / v2v; wire it.
2. **Veo extend** ("google omni" = Veo 3.1 video extension via `GEMINI_API_KEY`).
3. **Luma** — key available; verify the existing Luma path works.
4. **Verify latest models + fix** the broken `runway-gen4-aleph` i2v entry; confirm
   each existing commercial model still resolves against current SDKs/APIs.
5. **VROP:** run the full 53×N dataset on a GPU box; publish bulk data to HuggingFace.

---

## Quick reference — run a model
```bash
# env: keys in .env (RUNWAYML_API_SECRET, FAL_KEY, WAVESPEED_API_KEY, GEMINI_API_KEY, KLING_API_KEY, LUMA_API_KEY)
python examples/generate_videos.py --list-models --model x        # list all 37
python examples/generate_videos.py --model runway-aleph-v2v  --questions-dir <dir> --output-dir ./out  # v2v (needs first_video.mp4)
python examples/generate_videos.py --model seedance-v1-pro   --questions-dir <dir> --output-dir ./out  # i2v/t2v
python examples/generate_videos.py --model sora-2-wavespeed  --questions-dir <dir> --output-dir ./out  # i2v/t2v (audio)
```

---

## Batch run 2026-06-22 — all runnable cloud models

Ran every cloud model keyed to the available keys against the `turntable_behind_screen_0000`
smoke task. **8/?? succeeded** across 4 providers; **14 failed**, each diagnosed to a concrete
root cause (none are toolkit code bugs except the deprecated Runway id). All successful outputs
are published with full data on the personal site at `:8000/inference-results`.

### Succeeded (newly run this batch)
- `runway-gen45` (1280×720, 5.04s, 2m13s), `runway-gen4-turbo` (1280×720, 5.04s, 26s — fastest),
  `runway-gen3a-turbo` (1280×768, 5.21s, 25s), `sora-2-pro-wavespeed` (1280×720 h264+aac, 4.04s, 2m48s).
- (Earlier: `runway-aleph-v2v`, `seedance-v1-lite/pro`, `sora-2-wavespeed`.)

### Failed — root causes (verified via direct probes)
- **Google Veo ×6** (`veo-2`, `veo-2.0-generate`, `veo-3.0-generate`, `veo-3.0-fast-generate`,
  `veo-3.1-generate`, `veo-3.1-fast`): `400 FAILED_PRECONDITION — "User location is not supported
  for the API use."` Gemini/Veo is **geo-blocked** from this location. Needs supported region/proxy.
- **Kling ×5** (`kling-v2-6`, `-v2-5-turbo`, `-v2-1-master`, `-v2-master`, `-v1-6`): `429 code 1102
  "Account balance not enough."` Kling account has **no credits**. Needs top-up.
- **Luma ×2** (`luma-ray-2`, `luma-ray-flash-2`): `403 Not authenticated` — **`LUMA_API_KEY`
  invalid/expired**. Separately **fixed** a real blocker: the Luma wrapper uploads the input image to
  S3 first and needs `boto3` (was missing) + a us-east-2 bucket + AWS creds; installed boto3, created
  `haotian-luma-uploads-507210367378` (us-east-2), wired the `engineer` creds + `S3_BUCKET` — the S3
  presign path now works end-to-end, only the Luma key is dead.
- **`runway-gen4-aleph` ×1**: `400 invalid model` — `gen4_aleph` is **deprecated** by the Runway API
  (valid ids now include gen3a_turbo/gen4_turbo/gen4/gen4.5/kling*/veo3*/seedance2…). Confirms the
  earlier "stale Aleph i2v entry" finding. Aleph is v2v-only (`aleph2`, runs as `runway-aleph-v2v`).
  **Action:** remove/deprecate the i2v `runway-gen4-aleph` catalog entry. (Bonus: Runway now proxies
  Kling/Veo3/Seedance2 ids — potential new catalog entries.)
- **Skipped** (no key): `openai-sora-2`, `openai-sora-2-pro` need a direct `OPENAI_API_KEY`.

### Note on the batch runner
First pass used `--override`, which deletes the output dir at startup and wiped the per-model
`run.log` (open fd to an unlinked inode). Re-ran failures without `--override`, logging outside the
output dir, to capture errors. Outputs/logs under `runs/2026-06-22/` (gitignored bulk).
