import argparse
import time
from pathlib import Path

from src.io_utils import write_predictions
from src.pipeline import load_data, rank

PREDICTIONS_FILE = "predictions.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ранжирование регуляций ТН ВЭД по декларациям")
    parser.add_argument("--data", default="./data", type=Path)
    parser.add_argument("--out", default="./out", type=Path)
    parser.add_argument("--models", default="./models", type=Path)
    args = parser.parse_args()

    started = time.perf_counter()
    declarations, regulations, tree = load_data(args.data)
    print(f"Загружено {len(declarations)} деклараций, {len(regulations)} регуляций, {len(tree.nodes)} узлов ТН ВЭД")

    rows = rank(declarations, regulations, tree, args.models)

    output_path = args.out / PREDICTIONS_FILE
    write_predictions(
        output_path,
        rows,
        [d.declaration_id for d in declarations],
        [r.regulation_id for r in regulations],
    )
    print(f"Записано {len(rows)} строк в {output_path} за {time.perf_counter() - started:.1f} с")


if __name__ == "__main__":
    main()
