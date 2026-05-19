import argparse
import random
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Split a corrected recognition manifest into train and validation files.")
    parser.add_argument("--input", required=True, help="Corrected manifest file.")
    parser.add_argument("--train-out", required=True, help="Output train manifest.")
    parser.add_argument("--val-out", required=True, help="Output validation manifest.")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation ratio between 0 and 1.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args()

    input_path = Path(args.input)
    train_out = Path(args.train_out)
    val_out = Path(args.val_out)

    if not input_path.exists():
        raise SystemExit(f"Manifest not found: {input_path}")
    if not 0 < args.val_ratio < 1:
        raise SystemExit("--val-ratio must be between 0 and 1")

    lines = [line for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) < 2:
        raise SystemExit("Need at least 2 labeled rows to split.")

    rng = random.Random(args.seed)
    rng.shuffle(lines)

    val_count = max(1, int(len(lines) * args.val_ratio))
    val_lines = lines[:val_count]
    train_lines = lines[val_count:]

    if not train_lines:
        raise SystemExit("Validation split consumed all rows. Lower --val-ratio.")

    train_out.parent.mkdir(parents=True, exist_ok=True)
    val_out.parent.mkdir(parents=True, exist_ok=True)
    train_out.write_text("\n".join(train_lines) + "\n", encoding="utf-8")
    val_out.write_text("\n".join(val_lines) + "\n", encoding="utf-8")

    print(f"Train rows: {len(train_lines)} -> {train_out}")
    print(f"Val rows: {len(val_lines)} -> {val_out}")


if __name__ == "__main__":
    main()
