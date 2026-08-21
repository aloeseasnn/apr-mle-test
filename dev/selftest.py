import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.attributes import (
    constraint_score,
    parse_constraints,
    parse_measures,
    quota_score,
)
from src.io_utils import validate_predictions
from src.negation import contradiction_score, split_polarity
from src.normalize import normalize, tokenize

DECLARATIONS = ["D1", "D2"]
REGULATIONS = [f"R{i}" for i in range(20)]


def _rows(declaration_id, regulation_ids, scores=None):
    scores = scores or [float(10 - i) for i in range(len(regulation_ids))]
    return [
        (declaration_id, rank, regulation_id, score)
        for rank, (regulation_id, score) in enumerate(zip(regulation_ids, scores), start=1)
    ]


def _rejects(rows, reason):
    try:
        validate_predictions(rows, DECLARATIONS, REGULATIONS)
    except ValueError:
        return
    raise AssertionError(f"валидатор пропустил: {reason}")


def test_format_contract():
    good = _rows("D1", REGULATIONS[:10]) + _rows("D2", REGULATIONS[5:15])
    validate_predictions(good, DECLARATIONS, REGULATIONS)

    _rejects(_rows("D1", REGULATIONS[:10]), "нет строк для D2")
    _rejects(good + _rows("D3", REGULATIONS[:10]), "неизвестная декларация")
    _rejects(_rows("D1", REGULATIONS[:9]) + _rows("D2", REGULATIONS[:10]), "девять строк")
    _rejects(
        _rows("D1", REGULATIONS[:9] + ["R0"]) + _rows("D2", REGULATIONS[:10]),
        "повтор regulation_id",
    )
    _rejects(
        _rows("D1", REGULATIONS[:9] + ["НЕТ_ТАКОГО"]) + _rows("D2", REGULATIONS[:10]),
        "неизвестный regulation_id",
    )
    _rejects(
        _rows("D1", REGULATIONS[:10], [float("nan")] * 10) + _rows("D2", REGULATIONS[:10]),
        "score равен nan",
    )
    _rejects(
        _rows("D1", REGULATIONS[:10], [float(i) for i in range(10)])
        + _rows("D2", REGULATIONS[:10]),
        "score возрастает по рангу",
    )


def test_normalize():
    assert normalize("более 1000 см?") == "более 1000 см3"
    assert normalize("плотностью 170 г/м?") == "плотностью 170 г/м2"
    assert normalize("ЁМКОСТЬ 1,5 Л") == "емкость 1.5 л"
    # коды ТН ВЭД записаны группами цифр и не должны слипаться
    assert normalize("подсубпозиция 8471 70 300 0") == "подсубпозиция 8471 70 300 0"
    assert tokenize("САХАРОЗА 12,0 МАС.%") == ["сахароза", "12.0", "мас.%"]


def test_numeric_thresholds():
    sulphur = parse_measures("газойль, сера 0,12 мас.%; плотность 842 кг/м3")
    assert sulphur["сера"] == [(0.12, "мас.%")]
    # плотность в кг/м3 не должна попасть в атрибут "сера"
    assert all(unit == "мас.%" for _, unit in sulphur["сера"])

    inside = parse_constraints("с содержанием серы более 0,05 мас.%, но не более 0,2 мас.%")
    assert constraint_score(sulphur, inside) > 0
    assert constraint_score(sulphur, parse_constraints("с содержанием серы более 0,2 мас.%")) < 0

    # мас.% и об.% - разные величины: сахароза не должна удовлетворять порог по спирту
    cola = parse_measures("сахароза 12,0 мас.%, этиловый спирт 0,10 об.%")
    assert constraint_score(cola, parse_constraints("содержащие более 0,5 об.% спирта")) < 0

    board = parse_measures("доска, сечение 32 x 140 мм")
    assert board["толщина"] == [(32.0, "мм")] and board["ширина"] == [(140.0, "мм")]
    assert constraint_score(board, parse_constraints("толщиной более 6 мм")) > 0
    assert constraint_score(board, parse_constraints("толщиной не менее 100 мм")) < 0


def test_age_from_year():
    assert parse_measures("год выпуска 2020", 2026)["возраст"] == [(6.0, "лет")]
    assert "возраст" not in parse_measures("год выпуска 2020")


def test_negation():
    negated, positive = split_polarity("комбинезон, не является производственной спецодеждой")
    assert contradiction_score(negated, positive, "комбинезоны производственные") < 0
    assert contradiction_score(negated, positive, "прочие комбинезоны") == 0

    # отрицание с обеих сторон согласуется, а не конфликтует
    negated, positive = split_polarity("газойль, биодизель не содержит")
    assert contradiction_score(negated, positive, "газойли, не содержащие биодизель") == 0

    assert "семен" in split_polarity("семена несеменного назначения")[0]


def test_quota():
    inside = "мясо, ввоз в рамках тарифной квоты по лицензии"
    outside = "мясо, поставка вне тарифной квоты"
    with_reference = "мясо, в порядке, указанном в дополнительном примечании"
    assert quota_score(inside, with_reference) > 0
    assert quota_score(inside, "мясо, прочее") < 0
    assert quota_score(outside, with_reference) < 0
    assert quota_score("мясо без упоминания квоты", with_reference) == 0


def main() -> None:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\nПройдено проверок: {len(tests)}")


if __name__ == "__main__":
    main()
