from typing import Any, Dict, List, Tuple

import cv2

from testbot.device import DeviceManager
from testbot.llm import LLMChatManager
from testbot.logger import logger
from testbot.uied.detect import WidgetDetector


class Observer:
    def __init__(self, device_manager: DeviceManager, chat_manager: LLMChatManager):
        self.widget_detector = WidgetDetector()
        self.device_manager = device_manager
        self.chat_manager = chat_manager
        self.screen_size_fixed = False

    def capture_screenshot(self, rotate: int = 0) -> str:
        screenshot_path = self.device_manager.get_screenshot()
        if rotate >= 90:
            screen = cv2.imread(screenshot_path)
            rotate_times = rotate // 90
            for _ in range(rotate_times):
                screen = cv2.rotate(screen, cv2.ROTATE_90_CLOCKWISE)
            cv2.imwrite(screenshot_path, screen)
            if rotate % 90 == 0 and rotate % 180 != 0 and not self.screen_size_fixed:
                tmp = self.device_manager.device.width
                self.device_manager.device.width = self.device_manager.device.height
                self.device_manager.device.height = tmp
                self.screen_size_fixed = True
        logger.info("Current Screenshot Captured")
        return screenshot_path

    def detect_widgets(self, screenshot_path: str, max_retries: int = 3) -> Tuple[str, int, Dict[str, List[Any]]]:
        import time
        logger.info("Detecting GUI Widgets")
        for attempt in range(1, max_retries + 1):
            screenshot_with_bbox_path, resize_ratio, elements = self.widget_detector.detect(screenshot_path)
            if elements:
                logger.info("Widget Detection Finished")
                return screenshot_with_bbox_path, resize_ratio, elements
            if attempt < max_retries:
                logger.warning(
                    f"No widgets detected (blank/loading screen?) — "
                    f"retrying screenshot in 2s (attempt {attempt}/{max_retries})"
                )
                time.sleep(2)
                screenshot_path = self.capture_screenshot()
            else:
                logger.warning("No widgets detected after all retries — proceeding with empty element list")
        logger.info("Widget Detection Finished")
        return screenshot_with_bbox_path, resize_ratio, elements