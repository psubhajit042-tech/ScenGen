import os
import cv2
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR
from pathlib import Path


class OCRDetector:
    def __init__(self):
        self.threshold = 0.8
        self.model_folder = ''
        self.model_root = Path(os.environ.get('SCENGEN_OCR_MODEL_ROOT', self.model_folder or '.'))
        self.default_model_name = os.environ.get('SCENGEN_OCR_MODEL_NAME', 'ch_ppocr_mobile_v2.0_xx')
        self.model_configs = {
            'chinese_cht_mobile_v2.0': {
                'lang': 'chinese_cht',
                'det_dir': 'ch_ppocr_mobile_v2.0_det_infer',
                'cls_dir': 'ch_ppocr_mobile_v2.0_cls_infer',
                'rec_dir': 'chinese_cht_mobile_v2.0_rec_infer',
            },
            'ch_ppocr_mobile_v2.0_xx': {
                'lang': 'ch',
                'det_dir': 'ch_ppocr_mobile_v2.0_det_infer',
                'cls_dir': 'ch_ppocr_mobile_v2.0_cls_infer',
                'rec_dir': 'ch_ppocr_mobile_v2.0_rec_infer',
            },
            'ch_PP-OCRv2_xx': {
                'lang': 'ch',
                'det_dir': 'ch_PP-OCRv2_det_infer',
                'cls_dir': 'ch_ppocr_mobile_v2.0_cls_infer',
                'rec_dir': 'ch_PP-OCRv2_rec_infer',
            },
            'ch_ppocr_server_v2.0_xx': {
                'lang': 'ch',
                'det_dir': 'ch_ppocr_server_v2.0_det_infer',
                'cls_dir': 'ch_ppocr_mobile_v2.0_cls_infer',
                'rec_dir': 'ch_ppocr_server_v2.0_rec_infer',
            },
        }
        self.models = {}

    def _resolve_model_dir(self, override_key: str, default_value: str) -> str:
        override_value = os.environ.get(override_key)
        if not override_value:
            return str((self.model_root / default_value).resolve())

        override_path = Path(override_value)
        if override_path.is_absolute():
            return str(override_path)

        if "\\" in override_value or "/" in override_value or override_value.startswith("."):
            return str((Path.cwd() / override_path).resolve())

        return str((self.model_root / override_path).resolve())

    def _build_model(self, model_name: str) -> PaddleOCR:
        config = self.model_configs[model_name]
        return PaddleOCR(
            lang=config['lang'],
            det_model_dir=self._resolve_model_dir('SCENGEN_OCR_DET_DIR', config['det_dir']),
            cls_model_dir=self._resolve_model_dir('SCENGEN_OCR_CLS_DIR', config['cls_dir']),
            rec_model_dir=self._resolve_model_dir('SCENGEN_OCR_REC_DIR', config['rec_dir']),
            use_gpu=False,
            total_process_num=os.cpu_count(),
            use_mp=True,
            show_log=False,
        )

    def get_model(self, ocr_model: str):
        model_name = ocr_model if ocr_model in self.model_configs else self.default_model_name
        if model_name not in self.model_configs:
            model_name = 'ch_ppocr_server_v2.0_xx'
        if model_name not in self.models:
            self.models[model_name] = self._build_model(model_name)
        return self.models[model_name]

    def apply_model(self, ocr_model: PaddleOCR, img):
        boxes = ocr_model.ocr(np.array(img), cls=False)
        boxes_filtered = []
        for box in boxes[0]:
            pts = box[0]
            if box[1][1] > self.threshold:
                boxes_filtered.append(
                    [int(pts[0][0]), int(pts[0][1]), int(pts[2][0]), int(pts[2][1]), box[1][0]]
                )
        return boxes_filtered

    def detect(self, img):
        model = self.get_model(self.default_model_name)
        img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        return self.apply_model(model, img)
