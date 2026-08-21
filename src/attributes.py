import re

from .normalize import normalize

# канонический атрибут -> шаблон, по которому он опознается рядом с числом
ATTRIBUTE_PATTERNS: list[tuple[str, str]] = [
    ("влага_обезжиренная", r"влаг\w*\s+в\s+обезжиренном|обезжиренном веществе"),
    ("объем_цилиндров", r"цилиндров двигател\w*|рабоч\w+\s+объем\w*"),
    ("возраст", r"прошло|возраст\w*|с момента выпуска"),
    ("жир", r"жир\w*"),
    ("сахар", r"сахар\w*|сахароз\w*|глюкоз\w*|крахмал\w*"),
    ("сера", r"\bсер[аыуе]\b"),
    ("спирт", r"спирт\w*|крепост\w*|алкогол\w*"),
    ("брикс", r"брикс\w*"),
    ("плотность_поверхностная", r"поверхностн\w*\s+плотност\w*"),
    ("диаметр", r"диаметр\w*|калибр\w*"),
    ("толщина", r"толщин\w*"),
    ("ширина", r"ширин\w*"),
    ("длина", r"длин\w*"),
    ("высота", r"высот\w*"),
    ("вместимость", r"вместимост\w*|емкост\w*|объем\w*|нетто-объем\w*|упаковк\w*|нетто"),
    ("масса_полная", r"полн\w+\s+масс\w+|транспортного средства"),
    ("масса_упаковки", r"нетто-мас\w*|нетто|первичн\w*\s+упаковк\w*|упаковк\w*|рулонах массой"),
    ("мощность", r"мощност\w*"),
    ("напряжение", r"напряжени\w*"),
    ("пассажиров", r"для перевозки"),
    ("цена", r"цене|стоимост\w*"),
    ("линейная_плотность", r"дтекс|однониточн\w*"),
    ("масса", r"масс\w*|весом"),
]

OPERATORS = {
    "не более": "<=",
    "не менее": ">=",
    "более": ">",
    "менее": "<",
    "свыше": ">",
}

# длинные варианты идут первыми
UNITS = [
    "мас.%", "мас%", "об.%", "%",
    "г/м2", "см3", "дм3", "м3", "м2",
    "квт", "вт", "мпа", "бар",
    "дтекс", "мм", "см", "дм", "км", "мл", "кг",
    "лет", "года", "год", "человек", "доллара", "евро",
    "мг", "мл", "м", "г", "т", "л", "в",
]
UNIT_GROUP = "|".join(re.escape(u) for u in UNITS)
UNIT_END = r"(?![а-яa-z0-9])"

LENGTH_SCALE = {"мм": 1.0, "см": 10.0, "дм": 100.0, "м": 1000.0, "км": 1_000_000.0}

# класс единицы
UNIT_CLASS = {
    "%": "доля", "мас.%": "доля_массовая", "мас%": "доля_массовая",
    "об.%": "доля_объемная", "об%": "доля_объемная",
    "кг": "масса", "г": "масса", "мг": "масса", "т": "масса",
    "л": "объем", "мл": "объем", "м3": "объем", "см3": "объем", "дм3": "объем",
    "мм": "длина", "см": "длина", "дм": "длина", "м": "длина", "км": "длина",
    "м2": "площадь", "г/м2": "плотность_поверхностная",
    "квт": "мощность", "вт": "мощность", "в": "напряжение",
    "мпа": "давление", "бар": "давление", "дтекс": "линейная_плотность",
    "лет": "время", "года": "время", "год": "время",
    "человек": "количество", "доллара": "деньги", "евро": "деньги",
}

# безразмерная доля в декларации ("жирность 2,5%") сопоставима с любой конкретной долей
DOLYA_CLASSES = {"доля", "доля_массовая", "доля_объемная"}

# какие классы единиц допустимы для атрибута
ATTRIBUTE_CLASSES = {
    "влага_обезжиренная": DOLYA_CLASSES, "жир": DOLYA_CLASSES, "сахар": DOLYA_CLASSES,
    "сера": DOLYA_CLASSES, "спирт": DOLYA_CLASSES,
    "объем_цилиндров": {"объем"}, "вместимость": {"объем"},
    "возраст": {"время"},
    "диаметр": {"длина"}, "толщина": {"длина"}, "ширина": {"длина"},
    "длина": {"длина"}, "высота": {"длина"},
    "масса": {"масса"}, "масса_упаковки": {"масса"}, "масса_полная": {"масса"},
    "мощность": {"мощность"}, "напряжение": {"напряжение"},
    "плотность_поверхностная": {"плотность_поверхностная"},
    "линейная_плотность": {"линейная_плотность"},
    "пассажиров": {"количество"}, "цена": {"деньги"},
}

_CONSTRAINT = re.compile(
    r"(?P<op>не более|не менее|не превышающ\w+|превышающ\w+|более|менее|свыше)\s+"
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>" + UNIT_GROUP + r")?" + UNIT_END
)
_MEASURE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>" + UNIT_GROUP + r")" + UNIT_END)
_SECTION = re.compile(
    r"(?P<first>\d+(?:\.\d+)?)\s*x\s*(?P<second>\d+(?:\.\d+)?)\s*(?P<unit>" + UNIT_GROUP + r")" + UNIT_END
)
_CONTINUATION = re.compile(r"(?:^|[\s,])(?:но|а)\s+$")
_MANUFACTURE_YEAR = re.compile(r"год\w*\s+выпуска\s*[:-]?\s*(\d{4})|(\d{4})\s+года\s+выпуска")

# ввоз в рамках квоты идет по коду со ссылкой на дополнительное примечание, вне квоты - по общему
_QUOTA_INSIDE = re.compile(r"в рамках тарифной квоты|в счет тарифной квоты|в пределах тарифной квоты")
_QUOTA_OUTSIDE = re.compile(r"вне тарифной квоты|сверх тарифной квоты")
_QUOTA_REGULATION = re.compile(r"дополнительном примечании")
QUOTA_WEIGHT = 1.0

CONTEXT_BEFORE = 70
CONTEXT_AFTER = 30
SATISFIED_BONUS = 1.0
VIOLATED_PENALTY = 3.0

Measures = dict[str, list[tuple[float, str]]]
Constraint = tuple[str, str, float, str]


def _operator(text: str) -> str:
    if text.startswith("не превышающ"):
        return "<="
    if text.startswith("превышающ"):
        return ">"
    return OPERATORS[text]


def _allowed(attribute: str, unit: str) -> bool:
    """атрибут применим к единице, только если класс единицы для него разрешен"""
    classes = ATTRIBUTE_CLASSES.get(attribute)
    if classes is None:
        return True
    return UNIT_CLASS.get(unit, "") in classes


def _attribute_for(before: str, after: str, unit: str) -> str | None:
    """атрибут по ближайшему к числу ключевому слову, совместимому с единицей"""
    best, best_distance = None, None
    for name, pattern in ATTRIBUTE_PATTERNS:
        if not _allowed(name, unit):
            continue
        matches = list(re.finditer(pattern, before))
        distance = len(before) - matches[-1].end() if matches else None
        forward = re.search(pattern, after)
        if forward and (distance is None or forward.start() < distance):
            distance = forward.start()
        if distance is not None and (best_distance is None or distance < best_distance):
            best, best_distance = name, distance
    return best or unit or None


def _convert(value: float, unit: str, target: str) -> float | None:
    """приводим значение к единице порога; между разными классами не сравниваем"""
    if not unit or not target or unit == target:
        return value
    source_class, target_class = UNIT_CLASS.get(unit), UNIT_CLASS.get(target)
    if source_class is None or target_class is None:
        return None
    if source_class == "длина" and target_class == "длина":
        return value * LENGTH_SCALE[unit] / LENGTH_SCALE[target]
    # "жирность 2,5%" без уточнения сопоставима и с мас.%, и с об.%
    if source_class in DOLYA_CLASSES and target_class in DOLYA_CLASSES:
        if "доля" in (source_class, target_class) or source_class == target_class:
            return value
        return None
    return value if source_class == target_class else None


def parse_constraints(text: str) -> list[Constraint]:
    """пороги регуляции: (атрибут, оператор, значение, единица)"""
    text = normalize(text)
    constraints: list[Constraint] = []
    previous_attribute, previous_unit = None, ""

    for match in _CONSTRAINT.finditer(text):
        before = text[max(0, match.start() - CONTEXT_BEFORE) : match.start()]
        after = text[match.end() : match.end() + CONTEXT_AFTER]
        unit = match.group("unit") or ""

        # "более X, но не более Y" - второе условие про тот же атрибут
        if previous_attribute and _CONTINUATION.search(before):
            attribute, unit = previous_attribute, unit or previous_unit
        else:
            attribute = _attribute_for(before, after, unit)

        if attribute:
            constraints.append((attribute, _operator(match.group("op")), float(match.group("value")), unit))
            previous_attribute, previous_unit = attribute, unit

    return constraints


def parse_measures(text: str, reference_year: int | None = None) -> Measures:
    """измеримые атрибуты декларации: атрибут -> список (значение, единица)"""
    text = normalize(text)
    measures: Measures = {}

    def add(attribute: str, value: float, unit: str) -> None:
        measures.setdefault(attribute, []).append((value, unit))

    # регуляции оперируют возрастом ("прошло более 5 лет"), декларация - годом выпуска
    if reference_year is not None:
        for match in _MANUFACTURE_YEAR.finditer(text):
            year = int(match.group(1) or match.group(2))
            add("возраст", float(reference_year - year), "лет")

    consumed: list[tuple[int, int]] = []
    # "сечение 32 x 140 мм" - меньшая сторона это толщина, большая ширина
    for match in _SECTION.finditer(text):
        unit = match.group("unit")
        first, second = float(match.group("first")), float(match.group("second"))
        add("толщина", min(first, second), unit)
        add("ширина", max(first, second), unit)
        consumed.append((match.start(), match.end()))

    for match in _MEASURE.finditer(text):
        if any(start <= match.start() < end for start, end in consumed):
            continue
        before = text[max(0, match.start() - CONTEXT_BEFORE) : match.start()]
        after = text[match.end() : match.end() + CONTEXT_AFTER]
        attribute = _attribute_for(before, after, match.group("unit"))
        if attribute:
            add(attribute, float(match.group("value")), match.group("unit"))

    return measures


def _holds(value: float, operator: str, threshold: float) -> bool:
    if operator == "<=":
        return value <= threshold
    if operator == ">=":
        return value >= threshold
    if operator == "<":
        return value < threshold
    return value > threshold


def quota_score(declaration: str, regulation_description: str) -> float:
    """тарифная квота: ввоз в ее рамках идет по коду со ссылкой на дополнительное примечание"""
    declaration = normalize(declaration)
    if _QUOTA_OUTSIDE.search(declaration):
        wanted = False
    elif _QUOTA_INSIDE.search(declaration):
        wanted = True
    else:
        return 0.0

    has_reference = bool(_QUOTA_REGULATION.search(normalize(regulation_description)))
    return QUOTA_WEIGHT if has_reference == wanted else -QUOTA_WEIGHT


def constraint_score(measures: Measures, constraints: list[Constraint]) -> float:
    """бонус за выполненные пороги, штраф за нарушенные; неизвестный атрибут нейтрален"""
    score = 0.0
    for attribute, operator, threshold, unit in constraints:
        applicable = [
            converted
            for value, value_unit in measures.get(attribute, [])
            if (converted := _convert(value, value_unit, unit)) is not None
        ]
        if not applicable:
            continue
        if any(_holds(value, operator, threshold) for value in applicable):
            score += SATISFIED_BONUS
        else:
            score -= VIOLATED_PENALTY
    return score
