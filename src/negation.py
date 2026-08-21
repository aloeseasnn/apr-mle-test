import re

from .lexical import stem
from .normalize import normalize

# "не является спецодеждой", "без футеровки" - отрицаемое стоит справа
_PREFIX = re.compile(
    r"\b(?:не|без|кроме|исключая)\s+(?:[а-я]+\s*){0,4}|"
    r"\bза исключением\s+(?:[а-я]+\s*){0,4}"
)
# "армирование отсутствует", "биодизель не содержит" - отрицаемое стоит слева
_SUFFIX = re.compile(
    r"(?:[а-я]+\s+){0,3}(?:отсутству\w+|не предусмотрен\w*|не имеет|не содержит|не разделенн\w*)"
    r"(?=\s*[;,.)]|\s*$)"
)
# слитное отрицание: "несеменной" отрицает "семенной"
_FUSED = re.compile(r"\bне([а-я]{4,})")

_WORD = re.compile(r"[а-яa-z]{3,}")
_STOPWORDS = {
    "для", "или", "при", "как", "что", "это", "они", "его", "все", "под", "над",
    "быть", "мас", "об", "шт", "кг", "прочие", "прочий", "прочая", "прочее",
    "иные", "иных", "других", "другом", "включая", "виде", "также", "содержит",
    "содержащие", "являются", "является", "имеет", "отсутствует",
}

CONTRADICTION_PENALTY = 1.0
MAX_CONTRADICTIONS = 3


def _stems(text: str) -> set[str]:
    return {stem(w) for w in _WORD.findall(text) if w not in _STOPWORDS}


def split_polarity(text: str) -> tuple[set[str], set[str]]:
    """основы слов внутри области отрицания и вне ее"""
    text = normalize(text)
    spans = [m.span() for m in _PREFIX.finditer(text)]
    spans += [m.span() for m in _SUFFIX.finditer(text)]

    negated = _stems(" ".join(text[start:end] for start, end in spans))
    negated |= {stem(m.group(1)) for m in _FUSED.finditer(text)}

    positive_text = text
    for start, end in sorted(spans, reverse=True):
        positive_text = positive_text[:start] + " " + positive_text[end:]
    positive = _stems(_FUSED.sub(" ", positive_text))

    return negated, positive


def contradiction_score(
    declaration_negated: set[str], declaration_positive: set[str], regulation_text: str
) -> float:
    """штраф за признак, который декларация отрицает, а регуляция утверждает"""
    regulation_negated, regulation_positive = split_polarity(regulation_text)
    asserted = regulation_positive - regulation_negated
    conflicts = (declaration_negated & asserted) - declaration_positive
    return -CONTRADICTION_PENALTY * min(len(conflicts), MAX_CONTRADICTIONS)
