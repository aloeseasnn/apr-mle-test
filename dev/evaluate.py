import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.io_utils import TOP_K

LABELS_FILE = "dev_labels.jsonl"


def load_labels(path: Path) -> dict[str, str]:
    labels = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                labels[row["declaration_id"]] = row["gold"]
    return labels


def load_predictions(path: Path) -> dict[str, list[str]]:
    ranked: dict[str, list[tuple[int, str]]] = defaultdict(list)
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ranked[row["declaration_id"]].append((int(row["rank"]), row["regulation_id"]))
    return {k: [r for _, r in sorted(v)] for k, v in ranked.items()}


def evaluate(predictions: dict[str, list[str]], labels: dict[str, str]) -> dict[str, float]:
    hits_at_1 = 0
    hits_at_10 = 0
    reciprocal = 0.0
    for declaration_id, gold in labels.items():
        ranking = predictions.get(declaration_id, [])
        position = ranking.index(gold) + 1 if gold in ranking else 0
        if position == 1:
            hits_at_1 += 1
        if position:
            hits_at_10 += 1
            reciprocal += 1.0 / position
    total = len(labels)
    return {
        "P@1": hits_at_1 / total,
        f"Recall@{TOP_K}": hits_at_10 / total,
        f"MRR@{TOP_K}": reciprocal / total,
        "n": total,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", default="./out/predictions.csv", type=Path)
    parser.add_argument("--labels", default=Path(__file__).parent / LABELS_FILE, type=Path)
    parser.add_argument("--errors", action="store_true", help="показать промахи по рангу")
    args = parser.parse_args()

    labels = load_labels(args.labels)
    predictions = load_predictions(args.predictions)
    metrics = evaluate(predictions, labels)
    print(" ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}" for k, v in metrics.items()))

    if args.errors:
        for declaration_id, gold in labels.items():
            ranking = predictions.get(declaration_id, [])
            position = ranking.index(gold) + 1 if gold in ranking else 0
            if position != 1:
                place = position or f">{TOP_K}"
                print(f"  {declaration_id}: gold {gold} на месте {place}, выдан {ranking[0]}")


if __name__ == "__main__":
    main()
