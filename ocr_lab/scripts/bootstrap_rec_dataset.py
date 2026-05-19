import argparse
import csv
import sys
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
from paddleocr import PaddleOCR


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def build_ocr(det_dir: Path, cls_dir: Path, rec_dir: Path) -> PaddleOCR:
    for path in (det_dir, cls_dir, rec_dir):
        if not path.exists():
            raise FileNotFoundError(f"Missing model folder: {path}")
    return PaddleOCR(
        lang="ch",
        det_model_dir=str(det_dir),
        cls_model_dir=str(cls_dir),
        rec_model_dir=str(rec_dir),
        use_gpu=False,
        use_mp=False,
        show_log=False,
    )


def clamp_box(points: np.ndarray, width: int, height: int) -> Tuple[int, int, int, int]:
    left = max(0, int(min(points[:, 0])))
    top = max(0, int(min(points[:, 1])))
    right = min(width, int(max(points[:, 0])))
    bottom = min(height, int(max(points[:, 1])))
    return left, top, right, bottom


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create cropped recognition images and seed labels from benchmark screenshots."
    )
    parser.add_argument("--images-dir", required=True, help="Folder of screenshots to process.")
    parser.add_argument("--crop-dir", required=True, help="Output folder for cropped text images.")
    parser.add_argument("--labels-out", required=True, help="TSV file of crop path and seed label.")
    parser.add_argument("--review-out", required=True, help="CSV file with metadata for manual review.")
    parser.add_argument("--model-root", default=".", help="Root folder that contains the model directories.")
    parser.add_argument("--det-dir", default="ch_ppocr_mobile_v2.0_det_infer", help="Detection model folder name.")
    parser.add_argument("--cls-dir", default="ch_ppocr_mobile_v2.0_cls_infer", help="Classifier model folder name.")
    parser.add_argument("--rec-dir", default="ch_ppocr_mobile_v2.0_rec_infer", help="Recognition model folder name.")
    parser.add_argument("--min-text-len", type=int, default=1, help="Minimum predicted text length to keep.")
    args = parser.parse_args()

    images_dir = (REPO_ROOT / args.images_dir).resolve() if not Path(args.images_dir).is_absolute() else Path(args.images_dir)
    crop_dir = (REPO_ROOT / args.crop_dir).resolve() if not Path(args.crop_dir).is_absolute() else Path(args.crop_dir)
    labels_out = (REPO_ROOT / args.labels_out).resolve() if not Path(args.labels_out).is_absolute() else Path(args.labels_out)
    review_out = (REPO_ROOT / args.review_out).resolve() if not Path(args.review_out).is_absolute() else Path(args.review_out)
    model_root = (REPO_ROOT / args.model_root).resolve() if not Path(args.model_root).is_absolute() else Path(args.model_root)

    crop_dir.mkdir(parents=True, exist_ok=True)
    labels_out.parent.mkdir(parents=True, exist_ok=True)
    review_out.parent.mkdir(parents=True, exist_ok=True)

    if not images_dir.exists():
        raise SystemExit(f"Image folder not found: {images_dir}")

    ocr = build_ocr(model_root / args.det_dir, model_root / args.cls_dir, model_root / args.rec_dir)
    images = sorted(p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)

    seed_rows: List[Tuple[str, str]] = []
    review_rows: List[List[object]] = []
    crop_count = 0

    for image_path in images:
        image = cv2.imread(str(image_path))
        if image is None:
            continue
        height, width = image.shape[:2]
        results = ocr.ocr(np.array(image), cls=False)[0]

        for idx, line in enumerate(results or []):
            text = str(line[1][0]).strip()
            if len(text) < args.min_text_len:
                continue

            points = np.array(line[0])
            left, top, right, bottom = clamp_box(points, width, height)
            if right <= left or bottom <= top:
                continue

            crop = image[top:bottom, left:right]
            crop_name = f"{image_path.stem}__{idx:03d}.png"
            crop_path = crop_dir / crop_name
            cv2.imwrite(str(crop_path), crop)

            relative_crop = crop_path.relative_to(REPO_ROOT).as_posix()
            seed_rows.append((relative_crop, text))
            review_rows.append([relative_crop, text, image_path.name, left, top, right, bottom])
            crop_count += 1

    with labels_out.open("w", encoding="utf-8", newline="") as handle:
        for crop_path, text in seed_rows:
            handle.write(f"{crop_path}\t{text}\n")

    with review_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["crop_path", "predicted_text", "source_image", "left", "top", "right", "bottom"])
        writer.writerows(review_rows)

    print(f"Created {crop_count} crop(s) in {crop_dir}")
    print(f"Wrote seed labels to {labels_out}")
    print(f"Wrote review CSV to {review_out}")


if __name__ == "__main__":
    main()
