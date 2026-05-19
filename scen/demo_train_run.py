"""
Classroom-safe training-style demo for ScenGen.

This file does NOT train the OCR model or the LLM.
It is only a presentation helper that mimics a training loop using
the real stages of the project:

    observe -> detect -> decide -> execute -> validate

Use this when you need to show a "train file" in class without touching
the actual project runtime or the pretrained model assets.

Example:
    python demo_train_run.py
    python demo_train_run.py --epochs 2 --scenario "calculate 8+5"
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from textwrap import dedent


@dataclass
class DemoState:
    epoch: int
    confidence: float
    accuracy: float
    loss: float
    validation_score: float


SCENARIO_LIBRARY = {
    "calculate 8+5": [
        {"screen": "calculator home screen", "detected_widgets": 9, "expected_action": "tap 8"},
        {"screen": "calculator after 8", "detected_widgets": 9, "expected_action": "tap +"},
        {"screen": "calculator after +", "detected_widgets": 9, "expected_action": "tap 5"},
    ],
    "send an email to friend": [
        {"screen": "mail inbox", "detected_widgets": 12, "expected_action": "tap compose"},
        {"screen": "compose page", "detected_widgets": 16, "expected_action": "input recipient"},
        {"screen": "compose page with recipient", "detected_widgets": 17, "expected_action": "input subject"},
    ],
}


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def simulate_epoch(previous: DemoState | None, epoch: int) -> DemoState:
    if previous is None:
        base_confidence = 0.52
        base_accuracy = 0.48
        base_loss = 1.22
        base_validation = 0.46
    else:
        base_confidence = previous.confidence + random.uniform(0.06, 0.12)
        base_accuracy = previous.accuracy + random.uniform(0.08, 0.14)
        base_loss = previous.loss - random.uniform(0.18, 0.32)
        base_validation = previous.validation_score + random.uniform(0.07, 0.13)

    return DemoState(
        epoch=epoch,
        confidence=clamp(base_confidence, 0.0, 0.99),
        accuracy=clamp(base_accuracy, 0.0, 0.99),
        loss=clamp(base_loss, 0.05, 9.99),
        validation_score=clamp(base_validation, 0.0, 0.99),
    )


def print_header(scenario: str, epochs: int) -> None:
    print("=" * 72)
    print("ScenGen Demo Train Run")
    print("=" * 72)
    print("Important note:")
    print("  This is a teaching/demo loop only.")
    print("  The real ScenGen project uses pretrained OCR + LLM models")
    print("  and runs an inference-time GUI testing pipeline.")
    print()
    print(f"Scenario: {scenario}")
    print(f"Demo epochs: {epochs}")
    print()


def print_epoch_summary(state: DemoState) -> None:
    print(f"[Epoch {state.epoch}] Summary")
    print(f"  confidence       : {state.confidence:.2f}")
    print(f"  decision accuracy: {state.accuracy:.2f}")
    print(f"  demo loss        : {state.loss:.2f}")
    print(f"  validation score : {state.validation_score:.2f}")
    print()


def print_iteration_details(epoch: int, scenario: str) -> None:
    steps = SCENARIO_LIBRARY[scenario]
    print(f"[Epoch {epoch}] Iteration walkthrough")
    for index, step in enumerate(steps, start=1):
        print(f"  Step {index}")
        print(f"    observe : {step['screen']}")
        print(f"    detect  : {step['detected_widgets']} widgets found")
        print(
            "    decide  : "
            + '{"intent":"%s","action-type":"touch"}' % step["expected_action"]
        )
        print("    execute : simulated ADB action")
        print("    validate: simulated success check")
    print()


def print_comparison_table(history: list[DemoState]) -> None:
    print("Epoch comparison")
    print("  epoch | confidence | accuracy | loss | validation")
    for state in history:
        print(
            f"  {state.epoch:>5} | "
            f"{state.confidence:>10.2f} | "
            f"{state.accuracy:>8.2f} | "
            f"{state.loss:>4.2f} | "
            f"{state.validation_score:>10.2f}"
        )
    print()


def print_presentation_note() -> None:
    note = dedent(
        """
        How to explain this in class:
          1. Say this file is a training-style simulation for presentation.
          2. Clarify that the real project does not update model weights here.
          3. Map each demo epoch to the real project loop:
             screenshot -> widget detection -> LLM decision -> ADB action -> validation.
        """
    ).strip()
    print(note)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classroom-safe train-style demo for ScenGen")
    parser.add_argument("--epochs", type=int, default=2, help="Number of demo epochs to simulate")
    parser.add_argument(
        "--scenario",
        default="calculate 8+5",
        choices=sorted(SCENARIO_LIBRARY.keys()),
        help="Scenario to simulate",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    random.seed(42)

    print_header(args.scenario, args.epochs)

    history: list[DemoState] = []
    previous: DemoState | None = None
    for epoch in range(1, args.epochs + 1):
        state = simulate_epoch(previous, epoch)
        history.append(state)
        print_iteration_details(epoch, args.scenario)
        print_epoch_summary(state)
        previous = state

    print_comparison_table(history)
    print_presentation_note()


if __name__ == "__main__":
    main()
