import argparse
import shutil
from pathlib import Path


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy a sample of existing ScenGen screenshots into the OCR benchmark folder."
    )
    parser.add_argument("--source", default="data/input", help="Source folder of screenshots.")
    parser.add_argument(
        "--dest",
        default="ocr_lab/dataset/benchmark_images",
        help="Destination benchmark image folder.",
    )
    parser.add_argument("--limit", type=int, default=30, help="Maximum number of images to copy.")
    args = parser.parse_args()

    source = Path(args.source)
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    if not source.exists():
        raise SystemExit(f"Source folder not found: {source}")

    copied = 0
    for image_path in sorted(source.iterdir()):
        if image_path.is_file() and image_path.suffix.lower() in IMAGE_EXTS:
            shutil.copy2(image_path, dest / image_path.name)
            copied += 1
            if copied >= args.limit:
                break

    print(f"Copied {copied} image(s) from {source} to {dest}")


if __name__ == "__main__":
    main()
