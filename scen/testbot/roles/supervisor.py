from typing import Tuple, Optional

from testbot.llm import LLMChatManager
from testbot.logger import logger
from testbot.memory import Memory
from testbot.prompt.supervisor import (
    system_prompt_effect_check,
    system_prompt_ending_check,
    system_prompt_loading_check,
    user_prompt_ending_check,
    user_prompt_loading_check,
    user_prompt_page_change_check,
    user_prompt_valid_change_check,
)
from testbot.utils import extract_json


def _normalize_answer_token(value) -> Optional[str]:
    if value is None:
        return None
    token = str(value).strip().strip('"').strip("'").upper()
    if token in ("T", "TRUE", "YES", "Y"):
        return "YES"
    if token in ("F", "FALSE", "NO", "N"):
        return "NO"
    return None


def _parse_binary_response(response: str, true_tokens, false_tokens) -> Optional[bool]:
    raw = extract_json(response)
    if raw is not None:
        token = _normalize_answer_token(raw.get("answer"))
        if token is not None:
            if token in true_tokens:
                return True
            if token in false_tokens:
                return False

    index = response.find("answer:")
    if index == -1:
        token = _normalize_answer_token(response)
        if token is not None:
            logger.warning("Non-standardized Response Format")
            if token in true_tokens:
                return True
            if token in false_tokens:
                return False
        logger.error("Invalid Response Format")
        return None

    response = response[index + len("answer:"):].strip()
    token = _normalize_answer_token(response.splitlines()[0] if response else "")
    if token is None:
        logger.error("Invalid Response Format")
        return None
    if token in true_tokens:
        return True
    if token in false_tokens:
        return False
    logger.error("Invalid Response Format")
    return None


class TestSupervisor:
    def __init__(self, chat_manager: LLMChatManager):
        self.chat_manager = chat_manager
        self.stage_load = "loading-check"
        self.stage_end = "ending-check"
        self.stage_visual_change = "visual-change-check"
        self.stage_valid_change = "valid-change-check"

    def check_loading(self, memory: Memory) -> Optional[bool]:
        sys_prompt = system_prompt_loading_check()
        user_prompt = user_prompt_loading_check()
        user_message = {"text": user_prompt, "image": memory.cached_screenshot}
        self.chat_manager.context_pool[self.stage_load].refresh()

        logger.info("Start Loading Check")
        response, p_usage, r_usage = self.chat_manager.get_response(
            stage=self.stage_load,
            model="gpt-4-vision-preview",
            prompt=user_message,
            system=sys_prompt,
        )
        logger.info("Check Result Received")
        logger.info(f"Token Cost: {p_usage} + {r_usage}")
        logger.debug(f"Response: ```{response}```")

        return _parse_binary_response(response, true_tokens={"YES"}, false_tokens={"NO"})

    def check_end(self, memory: Memory) -> Optional[bool]:
        sys_prompt = system_prompt_ending_check(memory)
        task_prompt, prev_screen_prompt, curr_screen_prompt, init_screen_prompt \
            = user_prompt_ending_check(memory)
        prev_screen_message = {"text": prev_screen_prompt, "image": memory.current_screenshot}
        curr_screen_message = {"text": curr_screen_prompt, "image": memory.cached_screenshot}
        init_screen_message = {"text": init_screen_prompt, "image": memory.initial_screenshot}

        self.chat_manager.context_pool[self.stage_end].refresh()
        self.chat_manager.context_pool[self.stage_end].set_system_message(sys_prompt)
        self.chat_manager.context_pool[self.stage_end].append_user_message(init_screen_message)
        self.chat_manager.context_pool[self.stage_end].append_assistant_message("")
        self.chat_manager.context_pool[self.stage_end].append_user_message(prev_screen_message)
        self.chat_manager.context_pool[self.stage_end].append_assistant_message("")
        self.chat_manager.context_pool[self.stage_end].append_user_message(curr_screen_message)
        self.chat_manager.context_pool[self.stage_end].append_assistant_message("")

        logger.info("Start Ending Check")
        response, p_usage, r_usage = self.chat_manager.get_response(
            stage=self.stage_end,
            model="gpt-4-vision-preview",
            prompt=task_prompt,
        )
        logger.info("Check Result Received")
        logger.info(f"Token Cost: {p_usage} + {r_usage}")
        logger.debug(f"Response: ```{response}```")

        return _parse_binary_response(response, true_tokens={"YES"}, false_tokens={"NO"})

    def check_effect(self, memory: Memory) -> Tuple[Optional[bool], Optional[bool]]:
        valid_change = self._check_valid_page_change(memory)
        if valid_change is None:
            return None, None
        if valid_change:
            return True, False
        page_change = self._check_page_change(memory)
        if page_change is None:
            return None, None
        if page_change:
            return False, True
        return False, False

    def _check_page_change(self, memory: Memory) -> Optional[bool]:
        """check if the page changes"""
        sys_prompt = system_prompt_effect_check()
        task_prompt, prev_screen_prompt, curr_screen_prompt = user_prompt_page_change_check()
        prev_screen_message = {"text": prev_screen_prompt, "image": memory.current_screenshot}
        curr_screen_message = {"text": curr_screen_prompt, "image": memory.cached_screenshot}

        self.chat_manager.context_pool[self.stage_visual_change].refresh()
        self.chat_manager.context_pool[self.stage_visual_change].set_system_message(sys_prompt)
        self.chat_manager.context_pool[self.stage_visual_change].append_user_message(task_prompt)
        self.chat_manager.context_pool[self.stage_visual_change].append_assistant_message("")
        self.chat_manager.context_pool[self.stage_visual_change].append_user_message(prev_screen_message)
        self.chat_manager.context_pool[self.stage_visual_change].append_assistant_message("")

        logger.info("Checking Page Change")
        response, p_usage, r_usage = self.chat_manager.get_response(
            stage=self.stage_visual_change,
            model="gpt-4-vision-preview",
            prompt=curr_screen_message,
        )
        logger.info("Check Result Received")
        logger.info(f"Token Cost: {p_usage} + {r_usage}")
        logger.debug(f"Response: ```{response}```")

        return _parse_binary_response(response, true_tokens={"YES"}, false_tokens={"NO"})

    def _check_valid_page_change(self, memory: Memory) -> Optional[bool]:
        """check if the page makes scenario-oriented change"""
        sys_prompt = system_prompt_effect_check()
        task_prompt, prev_screen_prompt, curr_screen_prompt, init_screen_prompt \
            = user_prompt_valid_change_check(memory)
        prev_screen_message = {"text": prev_screen_prompt, "image": memory.current_screenshot}
        curr_screen_message = {"text": curr_screen_prompt, "image": memory.cached_screenshot}
        init_screen_message = {"text": init_screen_prompt, "image": memory.initial_screenshot}

        self.chat_manager.context_pool[self.stage_valid_change].refresh()
        self.chat_manager.context_pool[self.stage_valid_change].set_system_message(sys_prompt)
        self.chat_manager.context_pool[self.stage_valid_change].append_user_message(task_prompt)
        self.chat_manager.context_pool[self.stage_valid_change].append_assistant_message("")
        self.chat_manager.context_pool[self.stage_valid_change].append_user_message(init_screen_message)
        self.chat_manager.context_pool[self.stage_valid_change].append_assistant_message("")
        self.chat_manager.context_pool[self.stage_valid_change].append_user_message(prev_screen_message)
        self.chat_manager.context_pool[self.stage_valid_change].append_assistant_message("")

        logger.info("Checking Valid Page Change")
        response, p_usage, r_usage = self.chat_manager.get_response(
            stage=self.stage_valid_change,
            model="gpt-4-vision-preview",
            prompt=curr_screen_message,
        )
        logger.info("Check Result Received")
        logger.info(f"Token Cost: {p_usage} + {r_usage}")
        logger.debug(f"Response: ```{response}```")

        return _parse_binary_response(response, true_tokens={"YES"}, false_tokens={"NO"})
