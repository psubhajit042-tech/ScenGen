@echo off
setlocal

REM Edit these paths before running.
set "PADDLEOCR_DIR=C:\path\to\PaddleOCR"
set "PRETRAINED_MODEL=C:\path\to\pretrain_models\ch_PP-OCRv3_rec_train\best_accuracy"

venv\Scripts\python.exe ocr_lab\scripts\train_rec_model.py ^
  --paddleocr-dir "%PADDLEOCR_DIR%" ^
  --base-config "configs\rec\PP-OCRv3\PP-OCRv3_mobile_rec.yml" ^
  --pretrained-model "%PRETRAINED_MODEL%" ^
  --train-label "ocr_lab\dataset\manifests\rec_gt_train.txt" ^
  --val-label "ocr_lab\dataset\manifests\rec_gt_val.txt" ^
  --save-dir "ocr_lab\models\candidate_training_run" ^
  --export-dir "ocr_lab\models\candidate_finetuned\my_rec_infer" ^
  --epochs 20 ^
  --batch-size 32 ^
  --learning-rate 0.00005 ^
  --run-train ^
  --run-eval ^
  --run-export

endlocal
