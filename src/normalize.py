import re
import unicodedata

# в regulations.jsonl надстрочные степени потеряны при выгрузке и заменены на "?"
MOJIBAKE = {
    "кг/м?": "кг/м3",
    "г/м?": "г/м2",
    "см?": "см3",
    "дм?": "дм3",
    "м?": "м2",
}

DASHES = "‐‑‒–—―−"

# приводим единицы к одной записи, чтобы пороги регуляций и атрибуты деклараций сравнивались
UNIT_ALIASES = {
    "куб. см": "см3",
    "куб.см": "см3",
    "куб. м": "м3",
    "куб.м": "м3",
    "кв. м": "м2",
    "кв.м": "м2",
    "cm3": "см3",
    "мас. %": "мас.%",
    "об. %": "об.%",
    "% мас": "мас.%",
    "% об": "об.%",
}

_DECIMAL_COMMA = re.compile(r"(?<=\d),(?=\d)")
_WHITESPACE = re.compile(r"\s+")
_TOKEN = re.compile(r"[а-яa-z]+(?:\.[а-яa-z]+)*(?:\.?%)?|\d+(?:\.\d+)?|%")


def normalize(text: str) -> str:
    """единая нормализация для деклараций и регуляций; NFKC заодно чинит надстрочные 2 и 3"""
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text).lower().replace("ё", "е")

    for src, dst in MOJIBAKE.items():
        text = text.replace(src, dst)
    for dash in DASHES:
        text = text.replace(dash, "-")
    text = text.replace("×", "x")
    for src, dst in UNIT_ALIASES.items():
        text = text.replace(src, dst)

    text = _DECIMAL_COMMA.sub(".", text)
    text = _WHITESPACE.sub(" ", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    """токены для лексического поиска: слова и числа"""
    return _TOKEN.findall(normalize(text))
