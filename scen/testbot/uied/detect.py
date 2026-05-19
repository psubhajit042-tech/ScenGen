import json
import os
from os.path import join as p_join, dirname, abspath
from typing import List, Tuple, Dict, Any

import cv2

import testbot.uied.detect_merge.merge as merge_mod
import testbot.uied.detect_compo.ip_region_proposal as ip
import testbot.uied.detect_text.text_detection as text
from testbot.logger import logger
from testbot.uied.CONFIG_UIED import Config

C = Config()

DEFAULT_UIED_PARAMS = {
    "min-grad": 3,
    "ffl-block": 5,
    "min-ele-area": 50,
    "merge-contained-ele": True,
}
DEFAULT_RESIZE_HEIGHT = 800


class WidgetDetector:
    def __init__(self):
        self.img = None
        self.img_path = None
        self.output_dir = None
        self.uied_params = DEFAULT_UIED_PARAMS
        self.resize_by_height = DEFAULT_RESIZE_HEIGHT

    def _resolve_output_dir(self, img_path: str) -> str:
        norm = img_path.replace("\\", "/")
        parts = norm.split("/")
        for i in range(len(parts) - 1, 0, -1):
            if parts[i].lower() == "data":
                return "/".join(parts[:i + 1]) + "/output"
        return os.path.join(dirname(abspath(img_path)), "output")

    def detect_compo(self, debug: bool = False):
        try:
            ip.compo_detection(
                img_path=self.img_path,
                output_root=self.output_dir,
                uied_params=self.uied_params,
                resize_by_height=self.resize_by_height,
            )
        except Exception as e:
            logger.warning(f"Component detection failed (screen may be blank): {e}")
            name = (
                self.img_path.split("/")[-1][:-4]
                if "/" in self.img_path
                else self.img_path.split("\\")[-1][:-4]
            )
            ip_root = p_join(self.output_dir, "ip")
            os.makedirs(ip_root, exist_ok=True)
            fallback = {"img_shape": list(self.img.shape), "compos": []}
            with open(p_join(ip_root, name + ".json"), "w") as f:
                json.dump(fallback, f)

    def detect_text(self, debug: bool = False):
        text.text_detection(
            input_file=self.img_path,
            output_file=self.output_dir,
            show=debug,
        )

    def detect_merge(self, debug: bool = False):
        name = (
            self.img_path.split("/")[-1][:-4]
            if "/" in self.img_path
            else self.img_path.split("\\")[-1][:-4]
        )
        img_res_path, components, resize_ratio = merge_mod.merge(
            img_path=self.img_path,
            compo_path=p_join(self.output_dir, "ip", name + ".json"),
            text_path=p_join(self.output_dir, "ocr", name + ".json"),
            merge_root=self.output_dir,
        )
        # components = {"compos": [...], "img_shape": ...}
        # Log first compo's keys so we can verify field names
        if components.get("compos"):
            logger.debug(f"[detect] First compo keys: {list(components['compos'][0].keys())}")
        # Each compo dict comes from Element.wrap_info() — inspect all keys
        # and map whatever carries text to text_content.
        elements = []
        for c in components.get("compos", []):
            pos = c.get("position", {})
            # wrap_info() stores text under "text_content" for Text elements
            # and leaves it absent/None for non-text compos
            # wrap_info() saves text under "text_content" for Text/Combined elements
            # Try every possible key name the Element class might use
            text_val = ""
            for key in ("text_content", "text", "content", "label"):
                v = c.get(key)
                if v and str(v).strip():
                    text_val = str(v).strip()
                    break
            # position is stored as nested dict OR flat keys
            col_min = pos.get("column_min") or c.get("column_min", 0)
            row_min = pos.get("row_min") or c.get("row_min", 0)
            col_max = pos.get("column_max") or c.get("column_max", 0)
            row_max = pos.get("row_max") or c.get("row_max", 0)
            elements.append({
                "id": c.get("id", 0),
                "text_content": text_val,
                "content_desc": c.get("content_desc", "") or "",
                "resource_id": c.get("resource_id", "") or "",
                "class": c.get("class", ""),
                "column_min": col_min,
                "row_min": row_min,
                "column_max": col_max,
                "row_max": row_max,
                "position": {
                    "column_min": int(col_min),
                    "row_min": int(row_min),
                    "column_max": int(col_max),
                    "row_max": int(row_max),
                },
                "_raw": c,  # keep raw so we can debug field names if still empty
            })
        return img_res_path, resize_ratio, elements

    def detect(
        self, img_path: str, debug: bool = False
    ) -> Tuple[str, float, List[Dict[str, Any]]]:
        self.img_path = img_path
        self.img = cv2.imread(img_path)
        self.output_dir = self._resolve_output_dir(img_path)

        self.detect_compo(debug)
        self.detect_text(debug)
        img_res_path, resize_ratio, elements = self.detect_merge(debug)
        return img_res_path, resize_ratio, elements
