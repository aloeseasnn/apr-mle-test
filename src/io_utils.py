import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Sequence

TOP_K = 10
CSV_COLUMNS = ["declaration_id", "rank", "regulation_id", "score"]

# номер декларации вида 10364274/020326/0000046, в середине дата ДДММГГ
_DECLARATION_DATE = re.compile(r"/\d{4}(\d{2})/")
CENTURY = 2000


@dataclass
class Declaration:
    declaration_id: str
    direction: str  # ИМ / ЭК
    description: str  # G31_1
    description_ext: str  # desc_extention
    permitting_docs: str
    has_acceptance_docs: int
    year: int | None  # год подачи декларации, нужен чтобы считать возраст товара
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


@dataclass
class Regulation:
    regulation_id: str
    code: str
    description: str
    notes: str
    explanation: str
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _declaration_year(number: str) -> int | None:
    match = _DECLARATION_DATE.search(number)
    return CENTURY + int(match.group(1)) if match else None


def load_declarations(path: Path) -> list[Declaration]:
    items = []
    for row in read_jsonl(path):
        items.append(
            Declaration(
                declaration_id=_text(row.get("declaration_id")),
                direction=_text(row.get("G011")),
                description=_text(row.get("G31_1")),
                description_ext=_text(row.get("desc_extention")),
                permitting_docs=_text(row.get("permitting_docs")),
                has_acceptance_docs=int(row.get("has_acceptance_docs") or 0),
                year=_declaration_year(_text(row.get("ND"))),
                raw=row,
            )
        )
    return items


def load_regulations(path: Path) -> list[Regulation]:
    items = []
    for row in read_jsonl(path):
        items.append(
            Regulation(
                regulation_id=_text(row.get("regulation_id")),
                code=_text(row.get("code")),
                description=_text(row.get("description")),
                notes=_text(row.get("notes")),
                explanation=_text(row.get("explanation")),
                raw=row,
            )
        )
    return items


def validate_predictions(
    rows: Sequence[tuple[str, int, str, float]],
    declaration_ids: Sequence[str],
    regulation_ids: Sequence[str],
) -> None:
    """падаем, если формат нарушен - это отдельный критерий оценки"""
    known_regs = set(regulation_ids)
    by_declaration: dict[str, list[tuple[int, str, float]]] = {}
    for declaration_id, rank, regulation_id, score in rows:
        if regulation_id not in known_regs:
            raise ValueError(f"{declaration_id}: неизвестный regulation_id {regulation_id}")
        if not isinstance(score, float) or score != score or score in (float("inf"), float("-inf")):
            raise ValueError(f"{declaration_id}: score не является конечным числом: {score}")
        by_declaration.setdefault(declaration_id, []).append((rank, regulation_id, score))

    missing = set(declaration_ids) - set(by_declaration)
    if missing:
        raise ValueError(f"нет предсказаний для {len(missing)} деклараций: {sorted(missing)[:5]}")
    extra = set(by_declaration) - set(declaration_ids)
    if extra:
        raise ValueError(f"предсказания для неизвестных деклараций: {sorted(extra)[:5]}")

    for declaration_id, entries in by_declaration.items():
        if len(entries) != TOP_K:
            raise ValueError(f"{declaration_id}: {len(entries)} строк вместо {TOP_K}")
        ranks = sorted(rank for rank, _, _ in entries)
        if ranks != list(range(1, TOP_K + 1)):
            raise ValueError(f"{declaration_id}: ранги {ranks} вместо 1..{TOP_K}")
        regs = {regulation_id for _, regulation_id, _ in entries}
        if len(regs) != TOP_K:
            raise ValueError(f"{declaration_id}: повторяющиеся regulation_id")
        scores = [score for _, _, score in sorted(entries)]
        if any(a < b for a, b in zip(scores, scores[1:])):
            raise ValueError(f"{declaration_id}: score не убывает по рангу")


def write_predictions(
    path: Path,
    rows: Sequence[tuple[str, int, str, float]],
    declaration_ids: Sequence[str],
    regulation_ids: Sequence[str],
) -> None:
    validate_predictions(rows, declaration_ids, regulation_ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    order = {declaration_id: i for i, declaration_id in enumerate(declaration_ids)}
    ordered = sorted(rows, key=lambda r: (order[r[0]], r[1]))
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        for declaration_id, rank, regulation_id, score in ordered:
            writer.writerow([declaration_id, rank, regulation_id, f"{score:.6f}"])
