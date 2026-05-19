import argparse
import json
from pathlib import Path


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a benchmark ground-truth JSON template from a folder of images."
    )
    parser.add_argument(
        "--images-dir",
        default="ocr_lab/dataset/benchmark_images",
        help="Folder containing benchmark screenshots.",
    )
    parser.add_argument(
        "--output",
        default="ocr_lab/dataset/ground_truth/benchmark_ground_truth.json",
        help="Ground-truth JSON output path.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output file completely. Without this flag, existing expected_text values are preserved by filename.",
    )
    args = parser.parse_args()

    images_dir = Path(args.images_dir)
    output_path = Path(args.output)

    if not images_dir.exists():
        raise SystemExit(f"Image folder not found: {images_dir}")

    existing_map = {}
    if output_path.exists() and not args.overwrite:
        try:
            existing_payload = json.loads(output_path.read_text(encoding="utf-8"))
            for item in existing_payload.get("images", []):
                existing_map[item.get("file", "")] = item.get("expected_text", "")
        except json.JSONDecodeError:
            pass

    image_files = sorted(
        path.name
        for path in images_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    )

    payload = {
        "images": [
            {
                "file": name,
                "expected_text": existing_map.get(name, ""),
            }
            for name in image_files
        ]
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(image_files)} image entries to {output_path}")


if __name__ == "__main__":
    main()
