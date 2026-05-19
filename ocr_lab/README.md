# OCR Lab

This folder is an isolated OCR experiment lane for ScenGen.

It does not change the live ScenGen runtime under `testbot/`.
Use it to:

- benchmark the current OCR model
- build a project-specific OCR dataset from GUI screenshots
- fine-tune a new OCR recognition model outside the main pipeline
- compare the current model against a candidate model

## Folder layout

- `configs/experiment.example.json`: example path settings
- `dataset/benchmark_images/`: screenshots used for OCR benchmarking
- `dataset/ground_truth/benchmark_ground_truth.json`: expected text for each benchmark screenshot
- `dataset/rec_images/`: cropped text images for OCR recognition training
- `dataset/manifests/`: label files for training and validation
- `models/baseline_current/`: notes about the current model
- `models/candidate_finetuned/`: put exported fine-tuned inference folders here
- `results/`: benchmark outputs and comparison summaries
- `scripts/`: helper scripts for sampling, benchmarking, dataset prep, and comparison

## Recommended workflow

1. Copy a small set of real GUI screenshots into `dataset/benchmark_images/`.
2. Create `dataset/ground_truth/benchmark_ground_truth.json` with the expected visible text.
3. Run the current model on the benchmark set.
4. Review the OCR errors.
5. Build cropped text images for recognition fine-tuning.
6. Correct the generated labels manually.
7. Fine-tune a new PaddleOCR recognition model outside this repo.
8. Export that trained model to inference format.
9. Put the exported inference folder under `models/candidate_finetuned/`.
10. Run the benchmark again with the candidate model.
11. Compare baseline vs candidate.

## Quick start

Sample a few existing screenshots from `data/input`:

```powershell
python ocr_lab/scripts/sample_benchmark_from_inputs.py --limit 30
```

Run the current model and save predictions:

```powershell
python ocr_lab/scripts/run_ocr_benchmark.py `
  --images-dir ocr_lab/dataset/benchmark_images `
  --output ocr_lab/results/baseline_predictions.json
```

Build training crops plus seed labels:

```powershell
python ocr_lab/scripts/bootstrap_rec_dataset.py `
  --images-dir ocr_lab/dataset/benchmark_images `
  --crop-dir ocr_lab/dataset/rec_images `
  --labels-out ocr_lab/dataset/manifests/rec_gt_seed.txt `
  --review-out ocr_lab/dataset/manifests/rec_review.csv
```

Run a candidate exported model:

```powershell
python ocr_lab/scripts/run_ocr_benchmark.py `
  --images-dir ocr_lab/dataset/benchmark_images `
  --output ocr_lab/results/candidate_predictions.json `
  --model-root ocr_lab/models/candidate_finetuned `
  --rec-dir my_rec_infer
```

Compare benchmark runs:

```powershell
python ocr_lab/scripts/compare_benchmarks.py `
  --ground-truth ocr_lab/dataset/ground_truth/benchmark_ground_truth.json `
  --baseline ocr_lab/results/baseline_predictions.json `
  --candidate ocr_lab/results/candidate_predictions.json `
  --output ocr_lab/results/comparison_summary.json
```

## Safe ScenGen experiment run

You can test ScenGen with the fine-tuned recognition model without replacing the existing OCR folders.

Default behavior is unchanged. The live runtime still uses the original OCR folders unless you set override environment variables for that terminal session.

Example:

```powershell
$env:SCENGEN_OCR_REC_DIR = "ocr_lab\models\candidate_finetuned\my_rec_infer"
venv\Scripts\python.exe test.py <APP-ID> <SCENARIO-ID>
Remove-Item Env:SCENGEN_OCR_REC_DIR
```

This keeps:

- detection model on the existing `ch_ppocr_mobile_v2.0_det_infer`
- classifier model on the existing `ch_ppocr_mobile_v2.0_cls_infer`
- recognition model on your exported `my_rec_infer`

You can also override detection or classifier paths if you later fine-tune those too:

```powershell
$env:SCENGEN_OCR_DET_DIR = "path\to\det_model"
$env:SCENGEN_OCR_CLS_DIR = "path\to\cls_model"
$env:SCENGEN_OCR_REC_DIR = "path\to\rec_model"
```

## Ground truth format

Create `dataset/ground_truth/benchmark_ground_truth.json` like this:

```json
{
  "images": [
    {
      "file": "screenshot-1776354130.png",
      "expected_text": "search settings account help"
    },
    {
      "file": "screenshot-1776354210.png",
      "expected_text": "compose send to subject"
    }
  ]
}
```

Keep the text simple:

- lowercase is fine
- punctuation does not matter much
- include the text that matters for task execution

## How to get the training dataset

This repo does not contain an official OCR training dataset.
For this project, the best dataset is your own GUI text data:

1. collect screenshots from the actual apps ScenGen tests
2. crop text regions from those screenshots
3. correct each crop's label manually
4. split the labeled crops into train and validation manifests

The `bootstrap_rec_dataset.py` script helps with steps 1 to 3 by using the current OCR model to create seed labels that you can fix instead of typing everything from scratch.

## Fine-tuning note

The actual fine-tuning step happens in the PaddleOCR training repo or environment, not in the live ScenGen runtime. After training, export the model to inference format and place the exported folder under `models/candidate_finetuned/`.

See `TRAINING.md` for the separate training and export flow.
See `FINAL_RUNBOOK.md` for the consolidated old-vs-new OCR run commands.
