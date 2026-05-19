import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


REPO_ROOT = Path(__file__).resolve().parents[2]


def resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def windows_safe(path: Path) -> str:
    return str(path)


def ensure_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"{label} not found: {path}")


def ensure_pretrained_prefix(path: Path) -> None:
    if path.exists():
        return
    candidate = Path(str(path) + ".pdparams")
    if candidate.exists():
        return
    raise SystemExit(
        "Pretrained model prefix not found. Expected either the prefix path itself or a matching "
        f"'.pdparams' file for: {path}"
    )


def run_command(command: List[str], cwd: Path) -> None:
    printable = " ".join(f'"{part}"' if " " in part else part for part in command)
    print(f"\n[run] {printable}\n")
    completed = subprocess.run(command, cwd=str(cwd))
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Launch PaddleOCR recognition fine-tuning for the separate ScenGen OCR lab."
    )
    parser.add_argument("--paddleocr-dir", required=True, help="Path to a local PaddleOCR repository checkout.")
    parser.add_argument(
        "--base-config",
        default=r"configs\rec\PP-OCRv3\PP-OCRv3_mobile_rec.yml",
        help="Base PaddleOCR recognition config path relative to the PaddleOCR repo.",
    )
    parser.add_argument(
        "--pretrained-model",
        required=True,
        help="Path to the pretrained model prefix, for example ...\\best_accuracy",
    )
    parser.add_argument(
        "--train-label",
        default=r"ocr_lab\dataset\manifests\rec_gt_train.txt",
        help="Training manifest path.",
    )
    parser.add_argument(
        "--val-label",
        default=r"ocr_lab\dataset\manifests\rec_gt_val.txt",
        help="Validation manifest path.",
    )
    parser.add_argument(
        "--data-dir",
        default=".",
        help="Dataset root directory used by PaddleOCR. Repo root works with repo-relative manifests.",
    )
    parser.add_argument(
        "--save-dir",
        default=r"ocr_lab\models\candidate_training_run",
        help="Folder for training checkpoints and logs.",
    )
    parser.add_argument(
        "--export-dir",
        default=r"ocr_lab\models\candidate_finetuned\my_rec_infer",
        help="Folder for exported inference model.",
    )
    parser.add_argument("--epochs", type=int, default=20, help="Epoch count override.")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size per card.")
    parser.add_argument("--learning-rate", type=float, default=5e-5, help="Learning rate override.")
    parser.add_argument(
        "--dict-path",
        help="Optional character dictionary path. Leave unset to use the base config default.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable to use inside PaddleOCR.")
    parser.add_argument("--run-train", action="store_true", help="Run the training step.")
    parser.add_argument("--run-eval", action="store_true", help="Run evaluation against best_accuracy.")
    parser.add_argument("--run-export", action="store_true", help="Export the trained model to inference format.")
    args = parser.parse_args()

    paddleocr_dir = resolve_path(args.paddleocr_dir)
    base_config = (paddleocr_dir / args.base_config).resolve()
    pretrained_model = resolve_path(args.pretrained_model)
    train_label = resolve_path(args.train_label)
    val_label = resolve_path(args.val_label)
    data_dir = resolve_path(args.data_dir)
    save_dir = resolve_path(args.save_dir)
    export_dir = resolve_path(args.export_dir)

    ensure_exists(paddleocr_dir, "PaddleOCR repo")
    ensure_exists(base_config, "Base config")
    ensure_pretrained_prefix(pretrained_model)
    ensure_exists(train_label, "Train manifest")
    ensure_exists(val_label, "Validation manifest")
    ensure_exists(data_dir, "Data dir")

    save_dir.mkdir(parents=True, exist_ok=True)
    export_dir.parent.mkdir(parents=True, exist_ok=True)

    overrides = [
    f"Global.pretrained_model={windows_safe(pretrained_model)}",
    f"Global.save_model_dir={windows_safe(save_dir)}",
    f"Global.epoch_num={args.epochs}",
    f"Train.dataset.data_dir={windows_safe(data_dir)}",
    f"Train.dataset.label_file_list=['{windows_safe(train_label)}']",
    "Train.dataset.ratio_list=[1.0]",
    f"Train.loader.batch_size_per_card={args.batch_size}",
    f"Eval.dataset.data_dir={windows_safe(data_dir)}",
    f"Eval.dataset.label_file_list=['{windows_safe(val_label)}']",
    f"Eval.loader.batch_size_per_card={args.batch_size}",

    # ✅ keep these
    "Global.eval_batch_step=[0,10]",
    "Global.save_epoch_step=1",
    ]
 
    if args.dict_path:
        dict_path = resolve_path(args.dict_path)
        ensure_exists(dict_path, "Dictionary file")
        overrides.append(f"Global.character_dict_path={windows_safe(dict_path)}")

    train_command = [args.python, "tools/train.py", "-c", str(base_config), "-o", *overrides]

    best_accuracy = save_dir / "best_accuracy"
    eval_overrides = [
        f"Global.checkpoints={windows_safe(best_accuracy)}",
        f"Eval.dataset.data_dir={windows_safe(data_dir)}",
        f"Eval.dataset.label_file_list=['{windows_safe(val_label)}']",
        f"Eval.loader.batch_size_per_card={args.batch_size}",
    ]
    if args.dict_path:
        dict_path = resolve_path(args.dict_path)
        eval_overrides.append(f"Global.character_dict_path={windows_safe(dict_path)}")
    eval_command = [args.python, "tools/eval.py", "-c", str(base_config), "-o", *eval_overrides]

    export_overrides = [
        f"Global.pretrained_model={windows_safe(best_accuracy)}",
        f"Global.save_inference_dir={windows_safe(export_dir)}",
    ]
    if args.dict_path:
        dict_path = resolve_path(args.dict_path)
        export_overrides.append(f"Global.character_dict_path={windows_safe(dict_path)}")
    export_command = [args.python, "tools/export_model.py", "-c", str(base_config), "-o", *export_overrides]

    if not any((args.run_train, args.run_eval, args.run_export)):
        print("No run flags were selected. Here are the commands that would be used:")
        print("train :", " ".join(train_command))
        print("eval  :", " ".join(eval_command))
        print("export:", " ".join(export_command))
        return

    if args.run_train:
        run_command(train_command, paddleocr_dir)
    if args.run_eval:
        run_command(eval_command, paddleocr_dir)
    if args.run_export:
        run_command(export_command, paddleocr_dir)


if __name__ == "__main__":
    main()
