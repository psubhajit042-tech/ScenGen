import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from testbot.llm import LLMChatManager
from testbot.logger import logger
from testbot.memory import Memory
from testbot.prompt.decider import (
    system_prompt_next_action,
    user_prompt_rematch_widget,
    user_prompt_confirm_input_action,
    user_prompt_next_action,
    user_prompt_modify_next_action,
    user_prompt_confirm_touch_action,
    user_prompt_confirm_next_action,
    user_prompt_fix_location,
    user_prompt_analyze_situation,
    user_prompt_analyze_missing_widget
)
from testbot.utils import (
    extract_json,
    remove_punctuation,
    literally_related
)


# ---------------------------------------------------------------------------
# Response normalisation helpers
# ---------------------------------------------------------------------------

def _unwrap_action(raw: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Llama often wraps the real action payload inside a parent envelope:
        {"description": "...", "reasoning": "...", "action": {<real payload>}}

    Strategy (applied in order):
    1. If the dict already has intent/action-type at the top level, return as-is.
    2. If there is a nested "action" dict, unwrap it and merge extra top-level keys.
    3. Otherwise return unchanged (caller's validator will reject it).
    """
    if raw is None:
        return None
    if raw.get("intent") is not None or raw.get("action-type") is not None:
        return raw
    nested = raw.get("action")
    if isinstance(nested, dict):
        for k, v in raw.items():
            if k not in ("action", "description", "reasoning") and k not in nested:
                nested[k] = v
        return nested
    return raw


def _deep_find(raw: Optional[Dict[str, Any]], *keys: str) -> Optional[Dict[str, Any]]:
    """
    Search for any of the given keys anywhere in a (possibly nested) dict.
    Returns a flat dict that contains the first key found, promoting it to the
    top level if it was buried inside a nested object.

    Handles Llama returning the wrong schema for a sub-prompt
    (e.g. target-widget-number or position buried inside "action": {...}).
    """
    if raw is None:
        return None
    for k in keys:
        if k in raw:
            return raw
    for v in raw.values():
        if isinstance(v, dict):
            for k in keys:
                if k in v:
                    merged = dict(v)
                    for pk, pv in raw.items():
                        if pk not in ("action", "description", "reasoning") and pk not in merged:
                            merged[pk] = pv
                    return merged
    return raw


# ---------------------------------------------------------------------------
# Widget-matching fallback
# ---------------------------------------------------------------------------

# Fields on a UI element that may carry human-readable label text.
# Checked in priority order: text_content first, then accessibility fields.
_ELEMENT_LABEL_FIELDS = (
    "text_content",
    "content_desc",
    "resource_id",   # last-segment only, e.g. "com.app:id/btn_8" -> "btn_8" / "8"
)


def _element_labels(element: Dict[str, Any]) -> List[str]:
    """Return all non-empty label strings for an element, normalised."""
    import re
    labels: List[str] = []
    for field in _ELEMENT_LABEL_FIELDS:
        val = element.get(field)
        if not val:
            continue
        val = str(val).strip()
        if not val:
            continue
        labels.append(val)
        # For resource_id strip the package prefix: "com.foo:id/btn_8" -> "btn_8", "8"
        if field == "resource_id" and "/" in val:
            suffix = val.split("/")[-1]          # "btn_8"
            labels.append(suffix)
            # also try digits / letters only from suffix
            digits = re.sub(r"[^0-9]", "", suffix)
            if digits:
                labels.append(digits)
    return labels


def _extract_value_tokens(text: str) -> List[str]:
    """
    Pull out short concrete tokens from a free-text string that might
    directly match a UI element label.
    E.g. "the user entered 8"  -> ["8"]
         "tap the plus button" -> ["plus", "+"]
    """
    import re
    tokens: List[str] = []
    # numbers (including decimals)
    for m in re.finditer(r'\b(\d+\.?\d*)\b', text):
        tokens.append(m.group(1))
    # operator words and their symbol equivalents
    operator_map = {
        "plus": "+", "minus": "-", "times": "×", "multiply": "×",
        "divide": "÷", "divided": "÷", "equals": "=", "equal": "=",
        "percent": "%", "dot": ".", "decimal": ".",
    }
    for w in re.findall(r'[a-zA-Z]+', text.lower()):
        if w in operator_map:
            tokens.append(operator_map[w])
            tokens.append(w)
    # bare operator symbols
    for sym in "+-×÷=%.*/":
        if sym in text:
            tokens.append(sym)
    return tokens


def _match_candidate_to_elements(
        candidate: str,
        elements: List[Dict[str, Any]],
        tag: str,
) -> Optional[int]:
    """
    Try to match a single candidate string against every label field of
    every element.  Returns element id on first match, else None.
    """
    import re as _re
    candidate_clean = remove_punctuation(candidate.lower()).strip()

    # Tier 1 – exact match
    for element in elements:
        for label in _element_labels(element):
            label_clean = remove_punctuation(label.lower()).strip()
            if label_clean == candidate_clean:
                logger.info(
                    f"[{tag}] Exact match: id={element['id']} label='{label}' <- '{candidate}'"
                )
                return element["id"]

    # Tier 2 – literally_related (substring / semantic)
    for element in elements:
        for label in _element_labels(element):
            label_clean = remove_punctuation(label.lower()).strip()
            if literally_related(label_clean, candidate_clean):
                logger.info(
                    f"[{tag}] Related match: id={element['id']} label='{label}' <- '{candidate}'"
                )
                return element["id"]

    # Tier 3 – short alphanumeric exact match only
    # Only fires for purely alphanumeric candidates (digits/letters).
    # This prevents '.' from matching punctuation-only labels like '（）'.
    if len(candidate_clean) <= 4 and _re.match(r'^[a-z0-9]+$', candidate_clean):
        for element in elements:
            for label in _element_labels(element):
                label_clean = remove_punctuation(label.lower()).strip()
                if label_clean == candidate_clean:
                    logger.info(
                        f"[{tag}] Short-exact match: id={element['id']} label='{label}' <- '{candidate}'"
                    )
                    return element["id"]

    return None


def _infer_widget_from_action(
        action: Dict[str, Any],
        elements: List[Dict[str, Any]],
        model_response_raw: Optional[str] = None,
) -> Optional[int]:
    """
    Multi-pass widget inference used when the model does not return a
    target-widget-number.

    Pass 1 — match action fields (target-widget, value, input-value, intent)
              against ALL label fields on each element (text_content,
              content_desc, resource_id).
    Pass 2 — extract concrete tokens (digits, operator symbols/words) from
              the raw model response string and description/reasoning fields,
              then match those tokens against element labels.
    Pass 3 — single-element shortcut (unambiguous screen).

    Logs a rich diagnostic line on total failure so the next iteration is
    easy to debug.
    """
    import re

    # Dump element label fields once at DEBUG level so we can see what's there
    elem_summary = {
        e["id"]: {f: e.get(f) for f in _ELEMENT_LABEL_FIELDS}
        for e in elements
    }
    logger.debug(f"[Inference] Element label dump: {elem_summary}")

    # ---- Pass 0: input-text is the highest-confidence candidate -----------
    # For input actions the model sometimes already carries "input-text": "8".
    # Match this first before anything else to avoid status-bar false positives.
    input_text = action.get("input-text")
    if isinstance(input_text, str) and input_text.strip():
        eid = _match_candidate_to_elements(input_text.strip(), elements, "P0")
        if eid is not None:
            return eid

    # ---- Pass 1: action field candidates ---------------------------------
    candidates: List[str] = []
    for field in ("target-widget", "value", "input-value"):
        val = action.get(field)
        if isinstance(val, str) and val.strip():
            candidates.append(val.strip())
    intent = action.get("intent")
    if isinstance(intent, str) and intent.strip():
        candidates.append(intent.strip())

    for candidate in candidates:
        eid = _match_candidate_to_elements(candidate, elements, "P1")
        if eid is not None:
            return eid

    # ---- Pass 2: token extraction from free-text sources -----------------
    text_sources: List[str] = []
    if model_response_raw:
        text_sources.append(model_response_raw)
    for field in ("description", "reasoning"):
        val = action.get(field)
        if isinstance(val, str):
            text_sources.append(val)

    raw_tokens: List[str] = []
    for src in text_sources:
        raw_tokens.extend(_extract_value_tokens(src))
    # deduplicate preserving order
    seen: set = set()
    unique_tokens: List[str] = []
    for t in raw_tokens:
        if t not in seen:
            seen.add(t)
            unique_tokens.append(t)

    for token in unique_tokens:
        eid = _match_candidate_to_elements(token, elements, "P2")
        if eid is not None:
            return eid

    # ---- Pass 3: single element ------------------------------------------
    if len(elements) == 1:
        logger.warning("[Inference P3] Only one element — using as fallback")
        return elements[0]["id"]

    # Collect all labels for the diagnostic message
    all_labels = []
    for e in elements:
        all_labels.append((e["id"], _element_labels(e)))
    logger.warning(
        f"[Inference] All passes failed.\n"
        f"  candidates={candidates}\n"
        f"  tokens={unique_tokens}\n"
        f"  element labels={all_labels}"
    )
    return None


def _resolve_widget_number(
        raw: Optional[Dict[str, Any]],
        action: Dict[str, Any],
        elements: List[Dict[str, Any]],
        raw_response_str: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Full resolution pipeline for a sub-prompt response that should contain
    target-widget-number:
      1. Try _deep_find (handles nested wrappers).
      2. If still missing, run multi-pass text inference against element list.
    Returns a dict with "target-widget-number" set, or None.
    """
    found = _deep_find(raw, "target-widget-number")
    if found is not None and found.get("target-widget-number") is not None:
        return found

    # Model ignored the sub-prompt — fall back to text inference
    logger.warning("target-widget-number missing from model response; attempting text inference")
    inferred_id = _infer_widget_from_action(action, elements, model_response_raw=raw_response_str)
    if inferred_id is not None:
        return {"target-widget-number": inferred_id}

    return None


def _resolve_position(
        raw: Optional[Dict[str, Any]],
        default: str = "self",
) -> str:
    """
    Extract position from a sub-prompt response, with a safe default.
    """
    found = _deep_find(raw, "position")
    if found is not None:
        pos = found.get("position")
        if pos in ("up", "down", "left", "right", "self"):
            return pos
    logger.warning(f"No valid position in response; using default '{default}'")
    return default


def _with_widget_position(element: Dict[str, Any]) -> Dict[str, Any]:
    resolved = dict(element)
    position = resolved.get("position")
    if not isinstance(position, dict):
        keys = ("column_min", "row_min", "column_max", "row_max")
        if all(resolved.get(k) is not None for k in keys):
            resolved["position"] = {
                "column_min": int(resolved["column_min"]),
                "row_min": int(resolved["row_min"]),
                "column_max": int(resolved["column_max"]),
                "row_max": int(resolved["row_max"]),
            }
    return resolved


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class ActionDecider:
    def __init__(self, chat_manager: LLMChatManager):
        self.chat_manager = chat_manager
        self.stage = "action-decision"
        self.enable_text_match = True

    # ------------------------------------------------------------------
    # next_action
    # ------------------------------------------------------------------

    def next_action(
            self,
            memory: Memory,
            correcting: bool = False,
            situation: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        planned_camera_action = self._next_camera_action(memory)
        if planned_camera_action is not None:
            logger.info("Using deterministic camera action planner")
            return planned_camera_action

        planned_action = self._next_calculator_action(memory)
        if planned_action is not None:
            logger.info("Using deterministic calculator action planner")
            return planned_action

        if not correcting:
            sys_prompt = system_prompt_next_action(memory=memory)
            user_prompt = user_prompt_next_action(memory=memory)
            user_message = {"text": user_prompt, "image": memory.current_screenshot}
            self.chat_manager.context_pool[self.stage].refresh()
            logger.info("Deciding Next Action")
        else:
            assert situation is not None
            sys_prompt = None
            user_message = user_prompt_modify_next_action(situation)
            logger.info("Re-Deciding Next Action")

        response, p_usage, r_usage = self.chat_manager.get_response(
            stage=self.stage,
            model="gpt-4-vision-preview",
            prompt=user_message,
            system=sys_prompt,
        )
        logger.info("Action Decision Received.")
        logger.info(f"Token Cost: {p_usage} + {r_usage}")
        logger.debug(f"Response: ```{response}```")

        action = _unwrap_action(extract_json(response))
        if action is None \
                or action.get("intent") is None \
                or action.get("action-type") is None:
            logger.error("No Valid Action Found")
            return None

        logger.info("Action Decision Parsed.")
        return action

    def expected_calculator_step_count(self, memory: Memory) -> Optional[int]:
        tokens = self._parse_calculator_tokens(memory)
        if tokens is None:
            return None
        return len(tokens)

    # ------------------------------------------------------------------
    # confirm_next_action
    # ------------------------------------------------------------------

    def confirm_next_action(
            self,
            memory: Memory,
            action: Dict[str, Any],
            repeat_times: int = 0,
    ) -> Optional[Dict[str, Any]]:
        if repeat_times > 2:
            logger.error("Repeat Confirming Too Many Times")
            return None

        if action is None:
            raise RuntimeError("Model returned invalid action JSON")

        if isinstance(action.get("target-widget"), dict):
            logger.info("Target Widget Already Resolved")
            return action

        # directly return `back` and `scroll` action
        if action["action-type"] == "back" or action["action-type"] == "scroll":
            logger.info(f"Action {action['action-type']} requires no target widget")
            action["target-widget"] = None
            return action

        # ------------------------------------------------------------------
        # Step 1: try to match target widget by text (fast path, no LLM call)
        # ------------------------------------------------------------------
        matched_element = None
        if action.get("target-widget") is not None and self.enable_text_match:
            for element in memory.current_elements:
                if element.get("text_content") is not None:
                    ocr_text = remove_punctuation(element["text_content"].lower())
                    wid_desc = remove_punctuation(action["target-widget"].lower())
                    if literally_related(ocr_text, wid_desc):
                        matched_element = element
                        break

        if matched_element is not None:
            matched_element = _with_widget_position(matched_element)
            matched_element["description"] = action["target-widget"]
            action["target-widget"] = matched_element
            logger.info("Target Widget Found By Text Matching")
            # record in context so follow-up calls have history
            user_prompt = user_prompt_confirm_next_action()
            user_message = {"text": user_prompt, "image": memory.current_screenshot_with_bbox}
            self.chat_manager.context_pool[self.stage].append_user_message(user_message)
            self.chat_manager.context_pool[self.stage].append_assistant_message(
                f"Widget: {{\"target-widget-number\": {matched_element['id']}}}"
            )
            if action["action-type"] == "input":
                action = self._confirm_input_position(action, memory)
            return action

        # ------------------------------------------------------------------
        # Step 2: ask the LLM to identify the widget visually
        # ------------------------------------------------------------------
        user_prompt = user_prompt_confirm_next_action()
        user_message = {"text": user_prompt, "image": memory.current_screenshot_with_bbox}
        logger.info("Querying Target Widget")
        response, p_usage, r_usage = self.chat_manager.get_response(
            stage=self.stage,
            model="gpt-4-vision-preview",
            prompt=user_message,
        )
        logger.info("Query Result Received")
        logger.info(f"Token Cost: {p_usage} + {r_usage}")
        logger.debug(f"Response: ```{response}```")

        widget = _resolve_widget_number(
            _deep_find(extract_json(response), "target-widget-number"),
            action,
            memory.current_elements,
            raw_response_str=response,
        )
        if widget is None:
            logger.error("No Widget Number Found (and inference failed)")
            return None

        # ------------------------------------------------------------------
        # Step 3: no widget matched at all → predict location
        # ------------------------------------------------------------------
        if int(widget["target-widget-number"]) == -1:
            logger.warning("No Target Widget Detected")
            user_message = user_prompt_analyze_missing_widget()
            self.chat_manager.context_pool["temporary"].refresh()
            self.chat_manager.context_pool["temporary"].copy_from(
                self.chat_manager.context_pool[self.stage]
            )
            logger.info("Analyzing Missing Target Widget")
            response, p_usage, r_usage = self.chat_manager.get_response(
                stage="temporary",
                model="gpt-4-vision-preview",
                prompt=user_message,
            )
            logger.info("Analysis Result Received")
            logger.info(f"Token Cost: {p_usage} + {r_usage}")
            logger.debug(f"Response: ```{response}```")

            option = _deep_find(extract_json(response), "option-number")
            if option is None \
                    or option.get("option-number") is None \
                    or option["option-number"] not in (1, 2):
                logger.error("No Valid Option Found")
                return None

            option_num = option["option-number"]
            logger.info(f"Option Number Extracted: {option_num}")
            if option_num == 1:
                action = self.next_action(
                    memory,
                    correcting=True,
                    situation=(
                        "necessary preliminary action was neglected"
                        " causing the app to not respond correctly"
                    )
                )
                return self.confirm_next_action(memory, action, repeat_times + 1)

            if action["action-type"] == "input":
                user_message = user_prompt_confirm_input_action()
            elif action["action-type"] == "touch":
                user_message = user_prompt_confirm_touch_action()
            else:
                logger.error(f"Invalid Action Type: {action['action-type']}")
                return None

            logger.info("Querying Possible Location")
            response, p_usage, r_usage = self.chat_manager.get_response(
                stage="action-decision",
                model="gpt-4-vision-preview",
                prompt=user_message,
            )
            logger.info("Possible Location Received")
            logger.info(f"Token Cost: {p_usage} + {r_usage}")
            logger.debug(f"Response: ```{response}```")

            location = _deep_find(extract_json(response), "position", "widget-number")
            if location is None \
                    or location.get("position") is None \
                    or location.get("widget-number") is None \
                    or location["position"] not in ("up", "down", "left", "right"):
                logger.error("No Valid Location Clarified")
                return None

            for element in memory.current_elements:
                if element["id"] == int(location["widget-number"]):
                    action["target-widget"] = element
                    action["target-widget"]["id"] = -1
                    action["target-widget"]["description"] = (
                        "blank_field" if action["action-type"] == "input" else "undetected_button"
                    )
                    break
            action["position"] = location["position"]
            return action

        # ------------------------------------------------------------------
        # Step 4: widget matched — resolve element and confirm position
        # ------------------------------------------------------------------
        for element in memory.current_elements:
            if element["id"] == int(widget["target-widget-number"]):
                element = _with_widget_position(element)
                element["description"] = (
                    action["target-widget"]
                    if action.get("target-widget") is not None
                    else "target widget"
                )
                action["target-widget"] = element
                logger.info("Target Widget Found By Vision")
                break

        if action["action-type"] == "input":
            action = self._confirm_input_position(action, memory)
        return action

    # ------------------------------------------------------------------
    # rematch_next_action
    # ------------------------------------------------------------------

    def rematch_next_action(self, memory: Memory) -> Optional[Dict[str, Any]]:
        action = memory.performed_actions[-1]

        if action["target-widget"]["id"] != -1:
            user_message = user_prompt_rematch_widget()
            logger.info("Rematching Target Widget")
            response, p_usage, r_usage = self.chat_manager.get_response(
                stage=self.stage,
                model="gpt-4-vision-preview",
                prompt=user_message,
            )
            logger.info("Rematch Result Received")
            logger.info(f"Token Cost: {p_usage} + {r_usage}")
            logger.debug(f"Response: ```{response}```")

            widget = _resolve_widget_number(
                _deep_find(extract_json(response), "target-widget-number"),
                action,
                memory.current_elements,
                raw_response_str=response,
            )
            if widget is None:
                logger.error("No Widget Number Found (and inference failed)")
                return None

            if int(widget["target-widget-number"]) == -1:
                logger.warning("No Widget Rematched")
                if action["action-type"] == "input":
                    user_message = user_prompt_confirm_input_action()
                elif action["action-type"] == "touch":
                    user_message = user_prompt_confirm_touch_action()
                else:
                    logger.error(f"Invalid Action Type: {action['action-type']}")
                    return None

                logger.info("Querying Possible Location")
                response, p_usage, r_usage = self.chat_manager.get_response(
                    stage="action-decision",
                    model="gpt-4-vision-preview",
                    prompt=user_message,
                )
                logger.info("Possible Location Received")
                logger.info(f"Token Cost: {p_usage} + {r_usage}")
                logger.debug(f"Response: ```{response}```")

                location = _deep_find(extract_json(response), "position", "widget-number")
                if location is None \
                        or location.get("position") is None \
                        or location.get("widget-number") is None \
                        or location["position"] not in ("up", "down", "left", "right"):
                    logger.error("No Valid Location Clarified")
                    return None

                for element in memory.current_elements:
                    if element["id"] == int(location["widget-number"]):
                        action["target-widget"] = element
                        action["target-widget"]["id"] = -1
                        action["target-widget"]["description"] = (
                            "blank_field" if action["action-type"] == "input"
                            else "undetected_button"
                        )
                        break
                action["position"] = location["position"]
                return action

            for element in memory.current_elements:
                if element["id"] == int(widget["target-widget-number"]):
                    element = _with_widget_position(element)
                    if action["target-widget"].get("description") is not None:
                        widget_desc = action["target-widget"]["description"]
                        action["target-widget"] = element
                        action["target-widget"]["description"] = widget_desc
                    else:
                        action["target-widget"] = element
                        action["target-widget"]["description"] = "target widget"
                    logger.info("Target Widget Found By Vision")
                    break

            if action["action-type"] == "input":
                action = self._confirm_input_position(action, memory)
            return action

        else:
            user_message = user_prompt_fix_location()
            logger.info("Re-predicting Target Widget Location")
            response, p_usage, r_usage = self.chat_manager.get_response(
                stage=self.stage,
                model="gpt-4-vision-preview",
                prompt=user_message,
            )
            logger.info("Prediction Result Received")
            logger.info(f"Token Cost: {p_usage} + {r_usage}")
            logger.debug(f"Response: ```{response}```")

            location = _deep_find(extract_json(response), "position", "widget-number")
            if location is None \
                    or location.get("position") is None \
                    or location.get("widget-number") is None \
                    or location["position"] not in ("up", "down", "left", "right"):
                logger.error("No Valid Location Clarified")
                return None

            for element in memory.current_elements:
                if element["id"] == int(location["widget-number"]):
                    action["target-widget"] = element
                    action["target-widget"]["id"] = -1
                    action["target-widget"]["description"] = (
                        "blank_field" if action["action-type"] == "input"
                        else "undetected_button"
                    )
                    break
            action["position"] = location["position"]
            return action

    # ------------------------------------------------------------------
    # issue_feedback
    # ------------------------------------------------------------------

    def issue_feedback(self, need_back: bool) -> Optional[int]:
        self.chat_manager.context_pool["temporary"].refresh()
        self.chat_manager.context_pool["temporary"].copy_from(
            self.chat_manager.context_pool[self.stage]
        )
        user_prompt = user_prompt_analyze_situation(need_back)

        logger.info("Querying Situation")
        response, p_usage, r_usage = self.chat_manager.get_response(
            stage="temporary",
            model="gpt-4-vision-preview",
            prompt=user_prompt,
        )
        logger.info("Situation Feedback Received.")
        logger.info(f"Token Cost: {p_usage} + {r_usage}")
        logger.debug(f"Response: ```{response}```")

        situation = _deep_find(extract_json(response), "situation-number")
        if situation is None \
                or situation.get("situation-number") is None \
                or situation["situation-number"] not in (1, 2, 3, 4):
            logger.error("No Valid Action Found")
            return None
        logger.info(f"Situation Number Extracted: {situation['situation-number']}")
        return situation["situation-number"]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _confirm_input_position(
            self,
            action: Dict[str, Any],
            memory: Memory,
    ) -> Dict[str, Any]:
        """
        Ask the model where exactly to tap for an input action (up/down/left/right/self).
        Falls back to "self" on any failure.
        """
        if "target-widget" in action:
            w_id = action["target-widget"]["id"]
        elif "target-widget-number" in action:
            w_id = int(action["target-widget-number"])
        else:
            raise RuntimeError("No widget target found")

        user_prompt = user_prompt_confirm_input_action(w_id)
        user_message = {"text": user_prompt, "image": memory.current_screenshot_with_bbox}
        self.chat_manager.context_pool["temporary"].refresh()
        self.chat_manager.context_pool["temporary"].copy_from(
            self.chat_manager.context_pool[self.stage]
        )

        logger.info("Confirming Input Location")
        response, p_usage, r_usage = self.chat_manager.get_response(
            stage="temporary",
            model="gpt-4-vision-preview",
            prompt=user_message,
        )
        logger.info("Confirm Result Received")
        logger.info(f"Token Cost: {p_usage} + {r_usage}")
        logger.debug(f"Response: ```{response}```")

        action["position"] = _resolve_position(extract_json(response), default="self")
        return action

    def _next_calculator_action(self, memory: Memory) -> Optional[Dict[str, Any]]:
        tokens = self._parse_calculator_tokens(memory)
        if not tokens:
            return None

        action_index = len(memory.performed_actions or [])
        if action_index >= len(tokens):
            return None

        keypad = self._infer_calculator_keypad(memory.current_elements or [])
        if keypad is None:
            ip_elements = self._load_calculator_ip_elements(memory)
            keypad = self._infer_calculator_keypad(ip_elements)
        if keypad is None:
            logger.warning("Calculator keypad inference failed; falling back to LLM")
            return None

        token = tokens[action_index]
        target_widget = keypad.get(token)
        if target_widget is None:
            logger.warning(f"No calculator widget inferred for token '{token}'")
            return None

        return {
            "intent": f"press {token}",
            "action-type": "touch",
            "target-widget": dict(target_widget),
        }

    @staticmethod
    def _parse_calculator_tokens(memory: Memory) -> Optional[List[str]]:
        scenario = memory.target_scenario or ""
        if not isinstance(scenario, str) or not scenario.lower().startswith("calculate"):
            return None

        match = re.search(r"calculate\s+(.+)", scenario, re.IGNORECASE)
        if not match:
            return None

        expr = match.group(1).replace(" ", "")
        if not expr:
            return None

        token_map = {
            "x": "×",
            "X": "×",
            "*": "×",
            "/": "÷",
        }
        tokens: List[str] = []
        for ch in expr:
            mapped = token_map.get(ch, ch)
            if mapped.isdigit() or mapped in {"+", "-", "×", "÷", "%", "."}:
                tokens.append(mapped)
        if not tokens:
            return None
        if tokens[-1] != "=":
            tokens.append("=")
        return tokens

    @staticmethod
    def _infer_calculator_keypad(elements: List[Dict[str, Any]]) -> Optional[Dict[str, Dict[str, Any]]]:
        candidates: List[Dict[str, Any]] = []
        for element in elements:
            position = element.get("position") if isinstance(element.get("position"), dict) else None
            x_min = element.get("column_min", position.get("column_min") if position else None)
            x_max = element.get("column_max", position.get("column_max") if position else None)
            y_min = element.get("row_min", position.get("row_min") if position else None)
            y_max = element.get("row_max", position.get("row_max") if position else None)
            if None in (x_min, x_max, y_min, y_max):
                continue
            width = x_max - x_min
            height = y_max - y_min
            if y_min < 300 or y_max > 760:
                continue
            if width < 55 or height < 55:
                continue
            normalized = dict(element)
            normalized["column_min"] = int(x_min)
            normalized["column_max"] = int(x_max)
            normalized["row_min"] = int(y_min)
            normalized["row_max"] = int(y_max)
            candidates.append(normalized)

        if len(candidates) < 20:
            return None

        row_centers = ActionDecider._cluster_centers(
            [((e["row_min"] + e["row_max"]) / 2) for e in candidates],
            tolerance=20,
        )
        col_centers = ActionDecider._cluster_centers(
            [((e["column_min"] + e["column_max"]) / 2) for e in candidates],
            tolerance=20,
        )
        if len(row_centers) < 5 or len(col_centers) < 4:
            return None

        row_centers = row_centers[:5]
        col_centers = col_centers[:4]
        grid: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for element in candidates:
            y_center = (element["row_min"] + element["row_max"]) / 2
            x_center = (element["column_min"] + element["column_max"]) / 2
            row_index = ActionDecider._nearest_center_index(y_center, row_centers)
            col_index = ActionDecider._nearest_center_index(x_center, col_centers)
            if row_index is None or col_index is None:
                continue

            key = (row_index, col_index)
            current = grid.get(key)
            if current is None:
                grid[key] = element
                continue

            current_area = (
                (current["column_max"] - current["column_min"])
                * (current["row_max"] - current["row_min"])
            )
            new_area = (
                (element["column_max"] - element["column_min"])
                * (element["row_max"] - element["row_min"])
            )
            if new_area > current_area:
                grid[key] = element

        keypad_layout = {
            (0, 0): "AC",
            (0, 1): "%",
            (0, 2): "DEL",
            (0, 3): "÷",
            (1, 0): "7",
            (1, 1): "8",
            (1, 2): "9",
            (1, 3): "×",
            (2, 0): "4",
            (2, 1): "5",
            (2, 2): "6",
            (2, 3): "-",
            (3, 0): "1",
            (3, 1): "2",
            (3, 2): "3",
            (3, 3): "+",
            (4, 0): "00",
            (4, 1): "0",
            (4, 2): ".",
            (4, 3): "=",
        }
        resolved: Dict[str, Dict[str, Any]] = {}
        for position, label in keypad_layout.items():
            element = grid.get(position)
            if element is None:
                continue
            widget = dict(element)
            widget["description"] = label
            widget["position"] = {
                "column_min": int(element["column_min"]),
                "row_min": int(element["row_min"]),
                "column_max": int(element["column_max"]),
                "row_max": int(element["row_max"]),
            }
            resolved[label] = widget

        return resolved if {"8", "5", "+", "="}.issubset(resolved.keys()) else None

    @staticmethod
    def _cluster_centers(values: List[float], tolerance: int) -> List[float]:
        clusters: List[List[float]] = []
        for value in sorted(values):
            if not clusters or abs(value - clusters[-1][-1]) > tolerance:
                clusters.append([value])
            else:
                clusters[-1].append(value)
        centers = [sum(cluster) / len(cluster) for cluster in clusters]
        return centers

    @staticmethod
    def _nearest_center_index(value: float, centers: List[float]) -> Optional[int]:
        if not centers:
            return None
        distances = [abs(value - center) for center in centers]
        return distances.index(min(distances))

    @staticmethod
    def _load_calculator_ip_elements(memory: Memory) -> List[Dict[str, Any]]:
        screenshot_path = memory.current_screenshot
        if not screenshot_path:
            return []

        filename = os.path.splitext(os.path.basename(screenshot_path))[0] + ".json"
        candidates = []
        screenshot_norm = screenshot_path.replace("\\", "/")
        if "/data/input/" in screenshot_norm:
            root_prefix = screenshot_norm.split("/data/input/")[0]
            candidates.append(os.path.join(root_prefix, "data", "output", "ip", filename))
        candidates.append(os.path.join(os.path.dirname(screenshot_path), "ip", filename))

        ip_path = next((path for path in candidates if os.path.exists(path)), None)
        if ip_path is None:
            logger.warning(f"Calculator ip layout file not found for {screenshot_path}")
            return []

        try:
            with open(ip_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            logger.warning(f"Failed to load calculator ip layout from {ip_path}: {exc}")
            return []

        return data.get("compos", [])

    @staticmethod
    def _next_camera_action(memory: Memory) -> Optional[Dict[str, Any]]:
        scenario = (memory.target_scenario or "").strip().lower()
        app_name = (memory.app_name or "").strip().lower()
        app_package = (memory.app_package or "").strip().lower()
        scenario_tokens = {"camera", "photo", "shutter", "take photo", "take a photo"}
        if not any(token in scenario for token in scenario_tokens):
            return None
        if "camera" not in app_name and "camera" not in app_package:
            return None
        if memory.performed_actions:
            return None

        elements = memory.current_elements or []
        shutter_region = None
        for element in elements:
            pos = element.get("position") if isinstance(element.get("position"), dict) else None
            x_min = element.get("column_min", pos.get("column_min") if pos else None)
            x_max = element.get("column_max", pos.get("column_max") if pos else None)
            y_min = element.get("row_min", pos.get("row_min") if pos else None)
            y_max = element.get("row_max", pos.get("row_max") if pos else None)
            if None in (x_min, x_max, y_min, y_max):
                continue
            width = x_max - x_min
            height = y_max - y_min
            if y_min >= 620 and width >= 300 and 50 <= height <= 140:
                shutter_region = {
                    "id": element.get("id", -1),
                    "class": element.get("class", "Compo"),
                    "column_min": int(x_min),
                    "row_min": int(y_min),
                    "column_max": int(x_max),
                    "row_max": int(y_max),
                    "position": {
                        "column_min": int(x_min),
                        "row_min": int(y_min),
                        "column_max": int(x_max),
                        "row_max": int(y_max),
                    },
                    "description": "camera shutter area",
                }
                break

        if shutter_region is None:
            shutter_region = {
                "id": -1,
                "class": "Synthetic",
                "column_min": 110,
                "row_min": 640,
                "column_max": 250,
                "row_max": 760,
                "position": {
                    "column_min": 110,
                    "row_min": 640,
                    "column_max": 250,
                    "row_max": 760,
                },
                "description": "camera shutter area",
            }

        return {
            "intent": "take photo",
            "action-type": "touch",
            "target-widget": shutter_region,
        }
