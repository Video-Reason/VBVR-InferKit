# Data Generation → Inference End-to-End Workflow

This document walks through the pipeline — from generating questions to running model inference — using `O-9_shape_scaling_data-generator` (shape scaling analogy reasoning) as an example. All 100 VBVR data-generators follow the same pattern.

## Prerequisites

```bash
# 1. Install VBVR-InferKit
cd /path/to/VBVR-InferKit
pip install -e .

# 2. Install at least one video generation model (SVD as example)
bash setup/install_model.sh --model svd --validate

# 3. Clone a data-generator (O-9 as example)
git clone https://github.com/VBVR-DataFactory/O-9_shape_scaling_data-generator.git
cd O-9_shape_scaling_data-generator
pip install -r requirements.txt
```

## Full Pipeline

### Step 1: Generate Questions

Use the data-generator to produce task samples. Each sample contains: first frame (`first_frame.png`), final frame (`final_frame.png`), prompt (`prompt.txt`), and reference video (`ground_truth.mp4`).

```bash
cd /path/to/O-9_shape_scaling_data-generator

# Generate 1 sample (for testing)
python examples/generate.py --num-samples 1 --seed 42 --output /path/to/VBVR-InferKit/questions

# Generate 100 samples (full benchmark)
python examples/generate.py --num-samples 100 --seed 42 --output /path/to/VBVR-InferKit/questions
```

Output structure:

```
VBVR-InferKit/questions/
└── shape_scaling_task/
    └── shape_scaling_00000000/
        ├── first_frame.png       # Initial state (analogy A:B :: C:?)
        ├── final_frame.png       # Goal state (correct answer for ?)
        ├── prompt.txt            # Task description
        ├── ground_truth.mp4      # Reference video (16fps, ~3.8s)
        └── metadata.json         # Generation metadata
```

### Step 2: Run Model Inference

Use VBVR-InferKit's inference pipeline to generate videos.

```bash
cd /path/to/VBVR-InferKit

# Generate with SVD
python examples/generate_videos.py \
  --questions-dir ./questions \
  --output-dir ./outputs \
  --model svd

# Or use other models
python examples/generate_videos.py \
  --questions-dir ./questions \
  --output-dir ./outputs \
  --model luma-ray-2
```

Inference output is a flat structure:

```
outputs/svd/shape_scaling_task/shape_scaling_00000000.mp4
```

## Parameter Reference

### Data-Generator Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--num-samples` | Number of samples to generate | `100` |
| `--seed` | Random seed for reproducibility | `42` |
| `--output` | Output directory | `./questions` |

### Inference Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--model` | Model name(s) | `svd`, `luma-ray-2` |
| `--questions-dir` | Questions directory | `./questions` |
| `--output-dir` | Output directory | `./outputs` |
| `--domains` | Process only specified domains | `shape_scaling_task` |