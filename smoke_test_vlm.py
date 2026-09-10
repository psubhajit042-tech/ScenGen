import json
import sys

sys.path.insert(0, ".")

from testbot.llm import LLMChatManager, MODEL_NAME


def main():
    print(f"Model: {MODEL_NAME}")
    manager = LLMChatManager()

    screenshot = "ocr/screenshot-1776532408.png"

    print("\n--- Test 1: loading-check (binary schema, with image) ---")
    manager.context_pool["loading-check"].refresh()
    resp, _, _ = manager.get_response(
        stage="loading-check",
        model=MODEL_NAME,
        prompt={
            "text": "Here is the screenshot of the current page during a GUI test of a mobile app.\n"
            "Is the page still loading? answer: YES/NO with brief reason.",
            "image": screenshot,
        },
        system="You judge mobile GUI screens. Reply with JSON only.",
    )
    print("Raw:", resp)
    parsed = json.loads(resp)
    assert "answer" in parsed and parsed["answer"] in ("YES", "NO"), f"bad schema: {parsed}"
    print("PASS: binary schema respected")

    print("\n--- Test 2: action-decision (intent schema, with image) ---")
    manager.context_pool["action-decision"].refresh()
    resp, _, _ = manager.get_response(
        stage="action-decision",
        model=MODEL_NAME,
        prompt={
            "text": "Widget list:\n1. button 'OK'\n2. text 'Settings'\n"
            "Choose the next action for scenario 'open settings'. "
            "Return 1 json object with keys `intent`, `action-type`.",
            "image": screenshot,
        },
    )
    print("Raw:", resp)
    parsed = json.loads(resp)
    assert "intent" in parsed and "action-type" in parsed, f"bad schema: {parsed}"
    assert parsed["action-type"] in ("touch", "input", "scroll", "back"), f"bad enum: {parsed}"
    print("PASS: intent schema + enum respected")

    print("\nALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
