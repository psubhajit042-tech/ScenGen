import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
from paddleocr import PaddleOCR


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbot.uied.detect_text.Text import Text
from testbot.uied.detect_text.text_detection import (  # noqa: E402
    merge_intersected_texts,
    text_filter_noise,
    text_sentences_recognition,
)


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def paddle_lines_to_texts(lines: List[List[object]]) -> List[Text]:
    texts: List[Text] = []
    for i, line in enumerate(lines or []):
        points = np.array(line[0])
        location = {
            "left": int(min(points[:, 0])),
            "top": int(min(points[:, 1])),
            "right": int(max(points[:, 0])),
            "bottom": int(max(points[:, 1])),
        }
        content = line[1][0]
        texts.append(Text(i, content, location))
    return texts


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


def run_image(ocr: PaddleOCR, image_path: Path) -> Dict[str, object]:
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")

    raw_lines = ocr.ocr(np.array(image), cls=False)[0]
    texts = paddle_lines_to_texts(raw_lines)
    texts = merge_intersected_texts(texts)
    texts = text_filter_noise(texts)
    texts = text_sentences_recognition(texts)

    merged_texts = []
    for text in texts:
        merged_texts.append(
            {
                "text": text.content,
                "bbox": {
                    "left": text.location["left"],
                    "top": text.location["top"],
                    "right": text.location["right"],
                    "bottom": text.location["bottom"],
                },
            }
        )

    flat_text = " ".join(item["text"] for item in merged_texts).strip()
    return {
        "file": image_path.name,
        "image_path": str(image_path.as_posix()),
        "raw_count": len(raw_lines or []),
        "merged_count": len(merged_texts),
        "merged_texts": merged_texts,
        "flat_text": flat_text,
        "normalized_text": normalize_text(flat_text),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a PaddleOCR benchmark on a folder of screenshots.")
    parser.add_argument("--images-dir", required=True, help="Folder of benchmark screenshots.")
    parser.add_argument("--output", required=True, help="Output JSON file for predictions.")
    parser.add_argument("--model-root", default=".", help="Root folder that contains the model directories.")
    parser.add_argument("--det-dir", default="ch_ppocr_mobile_v2.0_det_infer", help="Detection model folder name.")
    parser.add_argument("--cls-dir", default="ch_ppocr_mobile_v2.0_cls_infer", help="Classifier model folder name.")
    parser.add_argument("--rec-dir", default="ch_ppocr_mobile_v2.0_rec_infer", help="Recognition model folder name.")
    args = parser.parse_args()

    images_dir = Path(args.images_dir)
    output_path = Path(args.output)
    model_root = Path(args.model_root)

    if not images_dir.exists():
        raise SystemExit(f"Image folder not found: {images_dir}")

    ocr = build_ocr(model_root / args.det_dir, model_root / args.cls_dir, model_root / args.rec_dir)
    images = sorted(p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)

    results = [run_image(ocr, image_path) for image_path in images]
    payload = {
        "images_dir": str(images_dir.as_posix()),
        "model_root": str(model_root.as_posix()),
        "det_dir": args.det_dir,
        "cls_dir": args.cls_dir,
        "rec_dir": args.rec_dir,
        "image_count": len(results),
        "results": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote benchmark predictions to {output_path}")


if __name__ == "__main__":
    main()
