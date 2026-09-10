import base64
import os
import re

import requests

from testbot.logger import logger

OLLAMA_URL = os.environ.get("SCENGEN_OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL_NAME = os.environ.get("SCENGEN_LLM", "qwen2.5vl:7b")


class ChatContext:
    def __init__(self):
        self.user_messages = []
        self.assistant_messages = []
        self.system_message = None

    def append_user_message(self, msg):
        self.user_messages.append(msg)

    def append_assistant_message(self, msg):
        self.assistant_messages.append(msg)

    def set_system_message(self, msg):
        self.system_message = msg

    def refresh(self):
        self.user_messages = []
        self.assistant_messages = []
        self.system_message = None

    def copy_from(self, other):
        self.user_messages = list(other.user_messages)
        self.assistant_messages = list(other.assistant_messages)
        self.system_message = other.system_message

    def messages(self):
        text = ""
        if self.system_message:
            text += "SYSTEM:\n" + self.system_message + "\n\n"
        for m in self.user_messages:
            text += "USER:\n" + str(m) + "\n\n"
        for m in self.assistant_messages:
            text += "ASSISTANT:\n" + str(m) + "\n\n"
        return text


class LLMChatManager:
    def __init__(self):
        self.context_pool = {
            "action-decision": ChatContext(),
            "loading-check": ChatContext(),
            "ending-check": ChatContext(),
            "visual-change-check": ChatContext(),
            "valid-change-check": ChatContext(),
            "temporary": ChatContext(),
        }

    def refresh_context(self):
        for c in self.context_pool.values():
            c.refresh()

    def context_pool2string(self):
        text = ""
        for name, ctx in self.context_pool.items():
            text += f"=== {name} ===\n"
            text += ctx.messages()
            text += "\n\n"
        return text

    @staticmethod
    def _prompt_text(prompt) -> str:
        if isinstance(prompt, dict):
            text = prompt.get("text")
            return text if isinstance(text, str) else ""
        if isinstance(prompt, str):
            return prompt
        return ""

    @staticmethod
    def _prompt_images(prompt):
        if isinstance(prompt, dict):
            path = prompt.get("image")
            if isinstance(path, str) and path:
                return [path]
        return []

    def _context_images(self, ctx):
        images = []
        for msg in ctx.user_messages:
            images.extend(self._prompt_images(msg))
        deduped = []
        for path in images:
            if not deduped or deduped[-1] != path:
                deduped.append(path)
        return deduped

    @staticmethod
    def _encode_image(path):
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except OSError as e:
            logger.error(f"Could not read image {path}: {e}")
            return None

    _BINARY_SCHEMA = {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "enum": ["YES", "NO"]},
            "reason": {"type": "string"},
        },
        "required": ["answer"],
    }

    @classmethod
    def _json_schema_for_prompt(cls, stage, prompt):
        text = cls._prompt_text(prompt)
        if stage in ("visual-change-check", "valid-change-check", "loading-check", "ending-check"):
            return cls._BINARY_SCHEMA
        if "`target-widget-number`" in text:
            return {
                "type": "object",
                "properties": {"target-widget-number": {"type": "integer"}},
                "required": ["target-widget-number"],
            }
        if "`widget-number` and `position`" in text:
            return {
                "type": "object",
                "properties": {
                    "widget-number": {"type": "integer"},
                    "position": {"type": "string"},
                },
                "required": ["widget-number", "position"],
            }
        if "`position`" in text:
            return {
                "type": "object",
                "properties": {"position": {"type": "string"}},
                "required": ["position"],
            }
        if "`option-number`" in text:
            return {
                "type": "object",
                "properties": {"option-number": {"type": "integer"}},
                "required": ["option-number"],
            }
        if "`situation-number`" in text:
            return {
                "type": "object",
                "properties": {"situation-number": {"type": "integer"}},
                "required": ["situation-number"],
            }
        return {
            "type": "object",
            "properties": {
                "intent": {"type": "string"},
                "action-type": {
                    "type": "string",
                    "enum": ["touch", "input", "scroll", "back"],
                },
            },
            "required": ["intent", "action-type"],
        }

    @classmethod
    def _strict_rules_for_prompt(cls, stage, prompt) -> str:
        prompt_text = cls._prompt_text(prompt)
        base_rules = [
            "You are an automated mobile GUI testing engine.",
            "CRITICAL OUTPUT RULES:",
            "1. Return ONLY raw JSON.",
            "2. No explanations.",
            "3. No markdown.",
            "4. No extra keys.",
            "5. Match the exact schema requested by the current prompt.",
        ]

        if stage in ("visual-change-check", "valid-change-check"):
            allowed = [
                "Allowed outputs ONLY:",
                "{\"answer\":\"YES\",\"reason\":\"brief reason\"}",
                "{\"answer\":\"NO\",\"reason\":\"brief reason\"}",
            ]
        elif stage in ("loading-check", "ending-check"):
            allowed = [
                "Allowed outputs ONLY:",
                "{\"answer\":\"T\",\"reason\":\"brief reason\"}",
                "{\"answer\":\"F\",\"reason\":\"brief reason\"}",
            ]
        elif "`target-widget-number`" in prompt_text:
            allowed = [
                "Allowed outputs ONLY:",
                "{\"target-widget-number\":7}",
                "{\"target-widget-number\":-1}",
            ]
        elif "`widget-number` and `position`" in prompt_text:
            allowed = [
                "Allowed outputs ONLY:",
                "{\"widget-number\":7,\"position\":\"right\"}",
            ]
        elif "`position`" in prompt_text:
            allowed = [
                "Allowed outputs ONLY:",
                "{\"position\":\"self\"}",
            ]
        elif "`option-number`" in prompt_text:
            allowed = [
                "Allowed outputs ONLY:",
                "{\"option-number\":1}",
            ]
        elif "`situation-number`" in prompt_text:
            allowed = [
                "Allowed outputs ONLY:",
                "{\"situation-number\":1}",
            ]
        elif "answer: YES/NO" in prompt_text:
            allowed = [
                "Allowed outputs ONLY:",
                "{\"answer\":\"YES\",\"reason\":\"brief reason\"}",
                "{\"answer\":\"NO\",\"reason\":\"brief reason\"}",
            ]
        elif "answer: T/F" in prompt_text:
            allowed = [
                "Allowed outputs ONLY:",
                "{\"answer\":\"T\",\"reason\":\"brief reason\"}",
                "{\"answer\":\"F\",\"reason\":\"brief reason\"}",
            ]
        else:
            allowed = [
                "Allowed outputs ONLY:",
                "{\"intent\":\"tap button\",\"action-type\":\"touch\"}",
                "{\"intent\":\"enter value\",\"action-type\":\"input\"}",
                "{\"intent\":\"go back\",\"action-type\":\"back\"}",
                "{\"intent\":\"scroll down\",\"action-type\":\"scroll\"}",
            ]

        return "\n".join(base_rules + allowed)

    def get_response(
        self,
        stage,
        model,
        prompt,
        system=None,
        max_tokens=1024,
        temperature=0.0,
    ):
        ctx = self.context_pool[stage]
        ctx.append_user_message(prompt)
        if system:
            ctx.set_system_message(system)

        strict_rules = self._strict_rules_for_prompt(stage, prompt)
        final_prompt = strict_rules + "\n\n" + ctx.messages()

        payload = {
            "model": MODEL_NAME,
            "prompt": final_prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "temperature": 0,
                "top_p": 0.1,
                "num_ctx": 8192,
            },
        }

        schema = self._json_schema_for_prompt(stage, prompt)
        if schema:
            payload["format"] = schema

        image_paths = self._context_images(ctx)
        if image_paths:
            encoded = [b64 for b64 in map(self._encode_image, image_paths) if b64]
            if encoded:
                payload["images"] = encoded

        try:
            r = requests.post(
                OLLAMA_URL,
                json=payload,
                timeout=300,
            )
            r.raise_for_status()
            data = r.json()
        except requests.exceptions.ConnectionError:
            logger.error("Ollama not reachable at localhost:11434 — is it running?")
            return "{}", 0, 0
        except requests.exceptions.Timeout:
            logger.error(f"Ollama request timed out after 300s")
            return "{}", 0, 0
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return "{}", 0, 0

        # Ollama /api/generate returns {"response": "..."} on success.
        # On error it returns {"error": "..."}.
        if "response" not in data:
            logger.error(f"Ollama returned unexpected shape: {data}")
            return "{}", 0, 0

        answer = data["response"]
        # Normalise bare F/T/"F"/"T"/True/False -> JSON true/false
        answer = re.sub(r':\s*"F"', ': false', answer)
        answer = re.sub(r':\s*"T"', ': true',  answer)
        answer = re.sub(r':\s*True',  ': true',  answer)
        answer = re.sub(r':\s*False', ': false', answer)
        answer = re.sub(r':\s*F',  ': false', answer)
        answer = re.sub(r':\s*T',  ': true',  answer)
        ctx.append_assistant_message(answer)
        return answer, 0, 0
