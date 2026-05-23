import argparse
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PYTHON = REPO_ROOT / "venv" / "Scripts" / "python.exe"
DEFAULT_CANDIDATE_REC_DIR = REPO_ROOT / "ocr_lab" / "models" / "candidate_finetuned" / "my_rec_infer"
DEFAULT_BENCHMARK_IMAGES = REPO_ROOT / "ocr_lab" / "dataset" / "benchmark_images"
DEFAULT_BENCHMARK_OUTPUT = REPO_ROOT / "ocr_lab" / "results" / "pipeline_predictions.json"
DEFAULT_COMPARE_OUTPUT = REPO_ROOT / "ocr_lab" / "results" / "comparison_summary.json"
DEFAULT_GROUND_TRUTH = REPO_ROOT / "ocr_lab" / "dataset" / "ground_truth" / "benchmark_ground_truth.json"


def resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def print_status(candidate_rec_dir: Path) -> None:
    active_mode = "candidate" if os.environ.get("SCENGEN_OCR_REC_DIR") else "baseline"
    active_rec_dir = (
        resolve_path(os.environ["SCENGEN_OCR_REC_DIR"])
        if os.environ.get("SCENGEN_OCR_REC_DIR")
        else (REPO_ROOT / "ch_ppocr_mobile_v2.0_rec_infer").resolve()
    )
    print(f"Active OCR mode: {active_mode}")
    print(f"Detection model: {(REPO_ROOT / 'ch_ppocr_mobile_v2.0_det_infer').resolve()}")
    print(f"Classifier model: {(REPO_ROOT / 'ch_ppocr_mobile_v2.0_cls_infer').resolve()}")
    print(f"Recognition model: {active_rec_dir}")
    print(f"Candidate recognition model: {candidate_rec_dir}")


def run_command(command: list[str], env: Optional[Dict[str, str]] = None) -> None:
    printable = " ".join(f'"{part}"' if " " in part else part for part in command)
    print(f"\n[run] {printable}\n")
    completed = subprocess.run(command, cwd=str(REPO_ROOT), env=env)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


@contextmanager
def temporary_env(updates: Dict[str, Optional[str]]) -> Iterator[None]:
    original: Dict[str, Optional[str]] = {}
    try:
        for key, value in updates.items():
            original[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def build_scengen_env(mode: str, candidate_rec_dir: Path) -> Dict[str, Optional[str]]:
    env_updates: Dict[str, Optional[str]] = {
        "SCENGEN_OCR_MODEL_ROOT": None,
        "SCENGEN_OCR_MODEL_NAME": None,
        "SCENGEN_OCR_DET_DIR": None,
        "SCENGEN_OCR_CLS_DIR": None,
        "SCENGEN_OCR_REC_DIR": None,
    }
    if mode == "candidate":
        env_updates["SCENGEN_OCR_REC_DIR"] = str(candidate_rec_dir)
    return env_updates


def run_scengen(python_exe: Path, mode: str, candidate_rec_dir: Path, app_id: str, scenario_id: str) -> None:
    if mode == "candidate" and not candidate_rec_dir.exists():
        raise SystemExit(f"Candidate recognition folder not found: {candidate_rec_dir}")
    env = os.environ.copy()
    for key, value in build_scengen_env(mode, candidate_rec_dir).items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    print(f"Running ScenGen with the {mode} OCR model...")
    run_command([str(python_exe), "test.py", app_id, scenario_id], env=env)


def run_benchmark(
    python_exe: Path,
    mode: str,
    candidate_rec_dir: Path,
    images_dir: Path,
    output_path: Path,
) -> None:
    if mode == "candidate" and not candidate_rec_dir.exists():
        raise SystemExit(f"Candidate recognition folder not found: {candidate_rec_dir}")

    command = [
        str(python_exe),
        "ocr_lab/scripts/run_ocr_benchmark.py",
        "--images-dir",
        str(images_dir),
        "--output",
        str(output_path),
    ]
    if mode == "candidate":
        command.extend(["--model-root", ".", "--rec-dir", str(candidate_rec_dir)])

    run_command(command)


def run_compare(
    python_exe: Path,
    ground_truth: Path,
    baseline_path: Path,
    candidate_path: Optional[Path],
    output_path: Path,
) -> None:
    command = [
        str(python_exe),
        "ocr_lab/scripts/compare_benchmarks.py",
        "--ground-truth",
        str(ground_truth),
        "--baseline",
        str(baseline_path),
        "--output",
        str(output_path),
    ]
    if candidate_path:
        command.extend(["--candidate", str(candidate_path)])
    run_command(command)


def print_json_summary(path: Path) -> None:
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if "results" in payload:
        print(f"Wrote {payload.get('image_count', 0)} benchmark results to {path}")
    elif "baseline" in payload:
        baseline = payload["baseline"]["summary"]
        print(f"Baseline summary: {baseline}")
        if "candidate" in payload:
            candidate = payload["candidate"]["summary"]
            delta = payload.get("delta", {})
            print(f"Candidate summary: {candidate}")
            print(f"Delta: {delta}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Single entrypoint for the OCR lab pipeline.")
    parser.add_argument("--python", default=str(DEFAULT_PYTHON), help="Python executable to use.")
    parser.add_argument(
        "--candidate-rec-dir",
        default=str(DEFAULT_CANDIDATE_REC_DIR),
        help="Path to the exported candidate recognition model folder.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show which OCR model paths are active.")

    scengen_parser = subparsers.add_parser("scengen", help="Run ScenGen with baseline or candidate OCR.")
    scengen_parser.add_argument("--mode", choices=["baseline", "candidate", "both"], default="candidate")
    scengen_parser.add_argument("--app-id", required=True)
    scengen_parser.add_argument("--scenario-id", required=True)

    benchmark_parser = subparsers.add_parser("benchmark", help="Run OCR benchmark images through baseline or candidate OCR.")
    benchmark_parser.add_argument("--mode", choices=["baseline", "candidate", "both"], default="candidate")
    benchmark_parser.add_argument("--images-dir", default=str(DEFAULT_BENCHMARK_IMAGES))
    benchmark_parser.add_argument("--output", default=str(DEFAULT_BENCHMARK_OUTPUT))
    benchmark_parser.add_argument(
        "--baseline-output",
        default=str(REPO_ROOT / "ocr_lab" / "results" / "baseline_predictions.json"),
    )
    benchmark_parser.add_argument(
        "--candidate-output",
        default=str(REPO_ROOT / "ocr_lab" / "results" / "candidate_predictions.json"),
    )

    compare_parser = subparsers.add_parser("compare", help="Compare baseline and candidate benchmark outputs.")
    compare_parser.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH))
    compare_parser.add_argument(
        "--baseline",
        default=str(REPO_ROOT / "ocr_lab" / "results" / "baseline_predictions.json"),
    )
    compare_parser.add_argument(
        "--candidate",
        default=str(REPO_ROOT / "ocr_lab" / "results" / "candidate_predictions.json"),
    )
    compare_parser.add_argument("--output", default=str(DEFAULT_COMPARE_OUTPUT))

    args = parser.parse_args()
    python_exe = resolve_path(args.python)
    candidate_rec_dir = resolve_path(args.candidate_rec_dir)

    if not python_exe.exists():
        raise SystemExit(f"Python executable not found: {python_exe}")

    if args.command == "status":
        print_status(candidate_rec_dir)
        return

    if args.command == "scengen":
        modes = ["baseline", "candidate"] if args.mode == "both" else [args.mode]
        for mode in modes:
            run_scengen(python_exe, mode, candidate_rec_dir, args.app_id, args.scenario_id)
        return

    if args.command == "benchmark":
        images_dir = resolve_path(args.images_dir)
        if not images_dir.exists():
            raise SystemExit(f"Images folder not found: {images_dir}")
        if args.mode == "both":
            baseline_output = resolve_path(args.baseline_output)
            candidate_output = resolve_path(args.candidate_output)
            run_benchmark(python_exe, "baseline", candidate_rec_dir, images_dir, baseline_output)
            run_benchmark(python_exe, "candidate", candidate_rec_dir, images_dir, candidate_output)
            print_json_summary(baseline_output)
            print_json_summary(candidate_output)
        else:
            output_path = resolve_path(args.output)
            run_benchmark(python_exe, args.mode, candidate_rec_dir, images_dir, output_path)
            print_json_summary(output_path)
        return

    if args.command == "compare":
        ground_truth = resolve_path(args.ground_truth)
        baseline_path = resolve_path(args.baseline)
        candidate_path = resolve_path(args.candidate) if args.candidate else None
        output_path = resolve_path(args.output)
        run_compare(python_exe, ground_truth, baseline_path, candidate_path, output_path)
        print_json_summary(output_path)
        return


if __name__ == "__main__":
    main()
