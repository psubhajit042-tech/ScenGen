# ScenGen Linux Runbook

This is the Linux command sheet for:

- setting up ScenGen on a Linux machine
- running ScenGen with the baseline OCR model
- running ScenGen with the candidate OCR model
- checking which OCR model is active
- running OCR benchmarks
- comparing benchmark results
- preparing and training the recognition model

All commands below assume you are in the project root:

```bash
cd /path/to/ScenGen
```

Use the project Python:

```bash
venv/bin/python
```

## What already exists in this repo

Linux-friendly helpers already exist:

- `scripts/setup_scengen_from_scratch.sh`
- `scripts/start_scengen.sh`
- `run_scengen_here.sh`
- `ocr_lab/scripts/run_pipeline.py`

So you do not need a brand-new Linux runner from scratch. The main missing piece was a Linux runbook for the OCR workflow.

## First-time setup on Linux

Make the helper scripts executable:

```bash
chmod +x run_scengen_here.sh scripts/setup_scengen_from_scratch.sh scripts/start_scengen.sh
```

Run setup:

```bash
./scripts/setup_scengen_from_scratch.sh
```

Or use the root helper:

```bash
./run_scengen_here.sh
```

## Linux prerequisites

Make sure these are installed and working:

```bash
python3 --version
adb version
ollama --version
```

Then install and run the Ollama model used by the project:

```bash
ollama pull qwen2.5vl:7b
ollama serve
```

In another terminal, verify your phone is visible:

```bash
adb devices
```

## Model paths on Linux

Old recognition model:

```text
/path/to/ScenGen/ch_ppocr_mobile_v2.0_rec_infer
```

New recognition model:

```text
/path/to/ScenGen/ocr_lab/models/candidate_finetuned/my_rec_infer
```

## Check which OCR is active

Quick check:

```bash
echo "$SCENGEN_OCR_REC_DIR"
```

- blank output means the baseline OCR is active
- `ocr_lab/models/candidate_finetuned/my_rec_infer` or an absolute path means the candidate OCR is active

Scripted status check:

```bash
venv/bin/python ocr_lab/scripts/run_pipeline.py status
```

## Run ScenGen with the baseline OCR model

Manual command:

```bash
unset SCENGEN_OCR_REC_DIR
venv/bin/python test.py <APP-ID> <SCENARIO-ID>
```

Python helper:

```bash
venv/bin/python ocr_lab/scripts/run_pipeline.py scengen \
  --mode baseline \
  --app-id <APP-ID> \
  --scenario-id <SCENARIO-ID>
```

Existing Linux start script:

```bash
./scripts/start_scengen.sh <APP-ID> <SCENARIO-ID>
```

## Run ScenGen with the candidate OCR model

Manual command:

```bash
export SCENGEN_OCR_REC_DIR="ocr_lab/models/candidate_finetuned/my_rec_infer"
venv/bin/python test.py <APP-ID> <SCENARIO-ID>
unset SCENGEN_OCR_REC_DIR
```

Python helper:

```bash
venv/bin/python ocr_lab/scripts/run_pipeline.py scengen \
  --mode candidate \
  --app-id <APP-ID> \
  --scenario-id <SCENARIO-ID>
```

## Run ScenGen with both baseline and candidate OCR

This runs baseline first and then candidate:

```bash
venv/bin/python ocr_lab/scripts/run_pipeline.py scengen \
  --mode both \
  --app-id <APP-ID> \
  --scenario-id <SCENARIO-ID>
```

## Run baseline OCR benchmark

Direct command:

```bash
venv/bin/python ocr_lab/scripts/run_ocr_benchmark.py \
  --images-dir ocr_lab/dataset/benchmark_images \
  --output ocr_lab/results/baseline_predictions.json
```

Helper command:

```bash
venv/bin/python ocr_lab/scripts/run_pipeline.py benchmark \
  --mode baseline \
  --images-dir ocr_lab/dataset/benchmark_images \
  --output ocr_lab/results/baseline_predictions.json
```

## Run candidate OCR benchmark

Direct command:

```bash
venv/bin/python ocr_lab/scripts/run_ocr_benchmark.py \
  --images-dir ocr_lab/dataset/benchmark_images \
  --output ocr_lab/results/candidate_predictions.json \
  --model-root . \
  --rec-dir ocr_lab/models/candidate_finetuned/my_rec_infer
```

Helper command:

```bash
venv/bin/python ocr_lab/scripts/run_pipeline.py benchmark \
  --mode candidate \
  --images-dir ocr_lab/dataset/benchmark_images \
  --output ocr_lab/results/candidate_predictions.json
```

## Run both OCR benchmarks

```bash
venv/bin/python ocr_lab/scripts/run_pipeline.py benchmark \
  --mode both \
  --images-dir ocr_lab/dataset/benchmark_images \
  --baseline-output ocr_lab/results/baseline_predictions.json \
  --candidate-output ocr_lab/results/candidate_predictions.json
```

## Compare benchmark results

Direct command:

```bash
venv/bin/python ocr_lab/scripts/compare_benchmarks.py \
  --ground-truth ocr_lab/dataset/ground_truth/benchmark_ground_truth.json \
  --baseline ocr_lab/results/baseline_predictions.json \
  --candidate ocr_lab/results/candidate_predictions.json \
  --output ocr_lab/results/comparison_summary.json
```

Helper command:

```bash
venv/bin/python ocr_lab/scripts/run_pipeline.py compare \
  --ground-truth ocr_lab/dataset/ground_truth/benchmark_ground_truth.json \
  --baseline ocr_lab/results/baseline_predictions.json \
  --candidate ocr_lab/results/candidate_predictions.json \
  --output ocr_lab/results/comparison_summary.json
```

## Generate or refresh the ground-truth template

```bash
venv/bin/python ocr_lab/scripts/generate_ground_truth_template.py
```

## Build the training crops and seed labels

```bash
venv/bin/python ocr_lab/scripts/bootstrap_rec_dataset.py \
  --images-dir ocr_lab/dataset/benchmark_images \
  --crop-dir ocr_lab/dataset/rec_images \
  --labels-out ocr_lab/dataset/manifests/rec_gt_seed.txt \
  --review-out ocr_lab/dataset/manifests/rec_review.csv
```

## Split corrected labels into train and validation files

```bash
venv/bin/python ocr_lab/scripts/split_rec_manifest.py \
  --input ocr_lab/dataset/manifests/rec_gt_seed.txt \
  --train-out ocr_lab/dataset/manifests/rec_gt_train.txt \
  --val-out ocr_lab/dataset/manifests/rec_gt_val.txt \
  --val-ratio 0.2
```

## Train and export the new recognition model

Replace the two absolute paths below with your Linux paths:

- `/path/to/PaddleOCR`
- `/path/to/ScenGen/ocr_lab/pretrain_models/ch_PP-OCRv3_rec_train/best_accuracy`

```bash
venv/bin/python ocr_lab/scripts/train_rec_model.py \
  --paddleocr-dir /path/to/PaddleOCR \
  --base-config configs/rec/PP-OCRv3/PP-OCRv3_mobile_rec.yml \
  --pretrained-model /path/to/ScenGen/ocr_lab/pretrain_models/ch_PP-OCRv3_rec_train/best_accuracy \
  --train-label ocr_lab/dataset/manifests/rec_gt_train.txt \
  --val-label ocr_lab/dataset/manifests/rec_gt_val.txt \
  --save-dir ocr_lab/models/candidate_training_run \
  --export-dir ocr_lab/models/candidate_finetuned/my_rec_infer \
  --epochs 20 \
  --batch-size 32 \
  --learning-rate 0.00005 \
  --run-train \
  --run-eval \
  --run-export
```

## Fastest day-to-day Linux commands

Setup once:

```bash
./scripts/setup_scengen_from_scratch.sh
```

Normal baseline run:

```bash
./scripts/start_scengen.sh A34 S8
```

Candidate OCR run:

```bash
venv/bin/python ocr_lab/scripts/run_pipeline.py scengen --mode candidate --app-id A34 --scenario-id S8
```

Benchmark both OCR models:

```bash
venv/bin/python ocr_lab/scripts/run_pipeline.py benchmark --mode both
```

Compare results:

```bash
venv/bin/python ocr_lab/scripts/run_pipeline.py compare
```
