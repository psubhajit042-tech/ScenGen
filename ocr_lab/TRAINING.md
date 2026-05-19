# OCR Training Flow

This is the separate OCR training lane for ScenGen.

It does not modify the live ScenGen runtime under `testbot/`.

## What you need before training

1. Correct the seed labels in `ocr_lab/dataset/manifests/rec_gt_seed.txt`
2. Split the corrected labels into train and validation files
3. Have a local checkout of the PaddleOCR repository
4. Have a pre-trained PaddleOCR recognition model for fine-tuning

## Step 1: split the corrected labels

If `rec_gt_seed.txt` has already been corrected, split it like this:

```powershell
venv\Scripts\python.exe ocr_lab\scripts\split_rec_manifest.py `
  --input ocr_lab\dataset\manifests\rec_gt_seed.txt `
  --train-out ocr_lab\dataset\manifests\rec_gt_train.txt `
  --val-out ocr_lab\dataset\manifests\rec_gt_val.txt `
  --val-ratio 0.2
```

## Step 2: fine-tune in PaddleOCR

Example:

```powershell
venv\Scripts\python.exe ocr_lab\scripts\train_rec_model.py `
  --paddleocr-dir C:\path\to\PaddleOCR `
  --base-config configs\rec\PP-OCRv3\PP-OCRv3_mobile_rec.yml `
  --pretrained-model C:\path\to\pretrain_models\ch_PP-OCRv3_rec_train\best_accuracy `
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

## What this does

- `--run-train`: trains a new recognition model
- `--run-eval`: evaluates the saved `best_accuracy`
- `--run-export`: exports an inference-ready model for ScenGen benchmarking

## After export

Then run the separate benchmark lane:

```powershell
venv\Scripts\python.exe ocr_lab\scripts\run_ocr_benchmark.py `
  --images-dir ocr_lab\dataset\benchmark_images `
  --output ocr_lab\results\candidate_predictions.json `
  --model-root ocr_lab\models\candidate_finetuned `
  --rec-dir my_rec_infer
```

And compare:

```powershell
venv\Scripts\python.exe ocr_lab\scripts\compare_benchmarks.py `
  --ground-truth ocr_lab\dataset\ground_truth\benchmark_ground_truth.json `
  --baseline ocr_lab\results\baseline_predictions.json `
  --candidate ocr_lab\results\candidate_predictions.json `
  --output ocr_lab\results\comparison_summary.json
```

## Notes

- For this project, train only the recognition model first.
- Detection fine-tuning can come later if text boxes are being missed.
- No phone cable is needed for the training itself.
- A phone is only needed when collecting fresh screenshots through the live ScenGen app/device path.

## Official references

- PaddleOCR recognition training: https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html
- PaddleOCR fine-tuning: https://paddlepaddle.github.io/PaddleOCR/v2.9.1/en/ppocr/model_train/finetune.html
- PaddleOCR dataset format: https://paddlepaddle.github.io/PaddleOCR/v2.9/en/datasets/ocr_datasets.html
