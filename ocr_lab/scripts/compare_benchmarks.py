import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple


def normalize_text(value: str) -> str:
    return " ".join((value or "").lower().split())


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        curr = [i]
        for j, char_b in enumerate(b, start=1):
            cost = 0 if char_a == char_b else 1
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def char_accuracy(expected: str, predicted: str) -> float:
    if not expected and not predicted:
        return 1.0
    denom = max(len(expected), len(predicted), 1)
    return 1.0 - (levenshtein(expected, predicted) / denom)


def load_predictions(path: Path) -> Dict[str, Dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {item["file"]: item for item in payload.get("results", [])}


def evaluate_run(
    ground_truth: List[Dict[str, str]], predictions: Dict[str, Dict[str, object]]
) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    rows: List[Dict[str, object]] = []
    exact_matches = 0
    total_accuracy = 0.0

    for item in ground_truth:
        file_name = item["file"]
        expected = normalize_text(item.get("expected_text", ""))
        predicted_item = predictions.get(file_name, {})
        predicted = normalize_text(str(predicted_item.get("normalized_text", "")))
        exact = expected == predicted
        accuracy = char_accuracy(expected, predicted)
        if exact:
            exact_matches += 1
        total_accuracy += accuracy
        rows.append(
            {
                "file": file_name,
                "expected_text": expected,
                "predicted_text": predicted,
                "exact_match": exact,
                "char_accuracy": round(accuracy, 4),
            }
        )

    count = len(rows)
    summary = {
        "image_count": count,
        "exact_match_count": exact_matches,
        "exact_match_rate": round(exact_matches / count, 4) if count else 0.0,
        "average_char_accuracy": round(total_accuracy / count, 4) if count else 0.0,
    }
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare OCR benchmark outputs against ground truth.")
    parser.add_argument("--ground-truth", required=True, help="Ground-truth benchmark JSON.")
    parser.add_argument("--baseline", required=True, help="Baseline prediction JSON.")
    parser.add_argument("--candidate", help="Candidate prediction JSON.")
    parser.add_argument("--output", required=True, help="Output summary JSON.")
    args = parser.parse_args()

    gt_path = Path(args.ground_truth)
    baseline_path = Path(args.baseline)
    output_path = Path(args.output)

    ground_truth = json.loads(gt_path.read_text(encoding="utf-8")).get("images", [])
    baseline_predictions = load_predictions(baseline_path)
    baseline_summary, baseline_rows = evaluate_run(ground_truth, baseline_predictions)

    payload: Dict[str, object] = {
        "baseline": {
            "summary": baseline_summary,
            "rows": baseline_rows,
        }
    }

    if args.candidate:
        candidate_path = Path(args.candidate)
        candidate_predictions = load_predictions(candidate_path)
        candidate_summary, candidate_rows = evaluate_run(ground_truth, candidate_predictions)
        payload["candidate"] = {
            "summary": candidate_summary,
            "rows": candidate_rows,
        }
        payload["delta"] = {
            "exact_match_rate": round(
                candidate_summary["exact_match_rate"] - baseline_summary["exact_match_rate"], 4
            ),
            "average_char_accuracy": round(
                candidate_summary["average_char_accuracy"] - baseline_summary["average_char_accuracy"], 4
            ),
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("Baseline:", baseline_summary)
    if "candidate" in payload:
        print("Candidate:", payload["candidate"]["summary"])
        print("Delta:", payload["delta"])
    print(f"Wrote comparison summary to {output_path}")


if __name__ == "__main__":
    main()
