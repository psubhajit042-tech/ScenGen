# Final OCR Runbook

This is the final command sheet for:

- running ScenGen with the old OCR model
- running ScenGen with the new OCR model
- checking which OCR model is active
- running the OCR benchmark lane
- comparing old vs new OCR benchmark results
- running the separate recognition training flow

All commands below assume you are in:

```powershell
C:\Users\psubh\ScenGen
```

Use the project Python:

```powershell
venv\Scripts\python.exe
```

## Model paths

Old recognition model:

```text
C:\Users\psubh\ScenGen\ch_ppocr_mobile_v2.0_rec_infer
```

New recognition model:

```text
C:\Users\psubh\ScenGen\ocr_lab\models\candidate_finetuned\my_rec_infer
```

## Check which OCR is active

Quick check:

```powershell
echo $env:SCENGEN_OCR_REC_DIR
```

- blank output means the old OCR is active
- `ocr_lab\models\candidate_finetuned\my_rec_infer` means the new OCR is active

Scripted status check:

```powershell
powershell -ExecutionPolicy Bypass -File ocr_lab\scripts\run_scengen_ocr_mode.ps1 -Mode status
```

## Run ScenGen with the old OCR model

Manual command:

```powershell
Remove-Item Env:SCENGEN_OCR_REC_DIR -ErrorAction SilentlyContinue
venv\Scripts\python.exe test.py <APP-ID> <SCENARIO-ID>
```

Helper script:

```powershell
powershell -ExecutionPolicy Bypass -File ocr_lab\scripts\run_scengen_ocr_mode.ps1 `
  -Mode baseline `
  -AppId <APP-ID> `
  -ScenarioId <SCENARIO-ID>
```

## Run ScenGen with the new OCR model

Manual command:

```powershell
$env:SCENGEN_OCR_REC_DIR = "ocr_lab\models\candidate_finetuned\my_rec_infer"
venv\Scripts\python.exe test.py <APP-ID> <SCENARIO-ID>
Remove-Item Env:SCENGEN_OCR_REC_DIR
```

Helper script:

```powershell
powershell -ExecutionPolicy Bypass -File ocr_lab\scripts\run_scengen_ocr_mode.ps1 `
  -Mode candidate `
  -AppId <APP-ID> `
  -ScenarioId <SCENARIO-ID>
```

## Run ScenGen with both old and new OCR

This runs baseline first, then candidate, and clears the override automatically at the end.

```powershell
powershell -ExecutionPolicy Bypass -File ocr_lab\scripts\run_scengen_ocr_mode.ps1 `
  -Mode both `
  -AppId <APP-ID> `
  -ScenarioId <SCENARIO-ID>
```

## Run baseline OCR benchmark

```powershell
venv\Scripts\python.exe ocr_lab\scripts\run_ocr_benchmark.py `
  --images-dir ocr_lab\dataset\benchmark_images `
  --output ocr_lab\results\baseline_predictions.json
```

## Run candidate OCR benchmark

This keeps the old detection and classifier folders and swaps only the recognition model:

```powershell
venv\Scripts\python.exe ocr_lab\scripts\run_ocr_benchmark.py `
  --images-dir ocr_lab\dataset\benchmark_images `
  --output ocr_lab\results\candidate_predictions.json `
  --model-root . `
  --rec-dir ocr_lab\models\candidate_finetuned\my_rec_infer
```

## Compare benchmark results

```powershell
venv\Scripts\python.exe ocr_lab\scripts\compare_benchmarks.py `
  --ground-truth ocr_lab\dataset\ground_truth\benchmark_ground_truth.json `
  --baseline ocr_lab\results\baseline_predictions.json `
  --candidate ocr_lab\results\candidate_predictions.json `
  --output ocr_lab\results\comparison_summary.json
```

## Generate or refresh the ground-truth template

```powershell
venv\Scripts\python.exe ocr_lab\scripts\generate_ground_truth_template.py
```

## Build the training crops and seed labels

```powershell
venv\Scripts\python.exe ocr_lab\scripts\bootstrap_rec_dataset.py `
  --images-dir ocr_lab\dataset\benchmark_images `
  --crop-dir ocr_lab\dataset\rec_images `
  --labels-out ocr_lab\dataset\manifests\rec_gt_seed.txt `
  --review-out ocr_lab\dataset\manifests\rec_review.csv
```

## Split corrected labels into train and validation files

```powershell
venv\Scripts\python.exe ocr_lab\scripts\split_rec_manifest.py `
  --input ocr_lab\dataset\manifests\rec_gt_seed.txt `
  --train-out ocr_lab\dataset\manifests\rec_gt_train.txt `
  --val-out ocr_lab\dataset\manifests\rec_gt_val.txt `
  --val-ratio 0.2
```

## Train and export the new recognition model

```powershell
venv\Scripts\python.exe ocr_lab\scripts\train_rec_model.py `
  --paddleocr-dir C:\Users\psubh\ScenGen\PaddleOCR `
  --base-config configs\rec\PP-OCRv3\PP-OCRv3_mobile_rec.yml `
  --pretrained-model C:\Users\psubh\ScenGen\ocr_lab\pretrain_models\ch_PP-OCRv3_rec_train\best_accuracy `
  --train-label ocr_lab\dataset\manifests\rec_gt_train.txt `
  --val-label ocr_lab\dataset\manifests\rec_gt_val.txt `
  --save-dir ocr_lab\models\candidate_training_run `
  --export-dir ocr_lab\models\candidate_finetuned\my_rec_infer `
  --epochs 20 `
  --batch-size 32 `
  --learning-rate 0.00005 `
  --run-train `
  --run-eval `
  --run-export
```

## Best practice for comparing ScenGen runs

1. Run the old OCR model once on the same app and scenario.
2. Run the new OCR model once on the same app and scenario.
3. Compare the generated OCR JSONs, merged GUI outputs, and final scenario behavior.
4. Keep the old model folders unchanged.
5. Use the env-var override only for the candidate run.

## Important notes

- The live default model is still the old OCR unless `SCENGEN_OCR_REC_DIR` is set.
- The candidate run changes only the recognition model, not detection or classification.
- If `benchmark_ground_truth.json` has empty `expected_text` fields, the benchmark comparison can look misleading.
- Training happens in the separate `ocr_lab` lane and does not retrain the live ScenGen OCR in place.
