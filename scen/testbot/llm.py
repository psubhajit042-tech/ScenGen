import requests
from testbot.logger import logger


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
            "model": "llama3:8b",
            "prompt": final_prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "top_p": 0.1
            }
        }

        try:
            r = requests.post(
                "http://localhost:11434/api/generate",
                json=payload,
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()
        except requests.exceptions.ConnectionError:
            logger.error("Ollama not reachable at localhost:11434 — is it running?")
            return "{}", 0, 0
        except requests.exceptions.Timeout:
            logger.error("Ollama request timed out after 120s")
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
        import re as _re
        answer = _re.sub(r':\s*"F"', ': false', answer)
        answer = _re.sub(r':\s*"T"', ': true',  answer)
        answer = _re.sub(r':\s*True',  ': true',  answer)
        answer = _re.sub(r':\s*False', ': false', answer)
        answer = _re.sub(r':\s*F',  ': false', answer)
        answer = _re.sub(r':\s*T',  ': true',  answer)
        ctx.append_assistant_message(answer)
        return answer, 0, 0
