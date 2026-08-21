import re
from dataclasses import dataclass
from pathlib import Path

HIERARCHY_HEADER = "ИЕРАРХИЯ ТН ВЭД"
SECTION_HEADERS = ("ПРИМЕЧАНИЯ", "ПОЯСНЕНИЯ", "РАЗДЕЛ")

_NODE = re.compile(r"^(\s+)(\d{4,10})?\s*\| (.*)$")
_BRACKET = re.compile(r"\s*\[([^\]]+)\]\s*$")
_LEADING_DASHES = re.compile(r"^[\s\-–—]+")

# ссылки вида "товарной позиции 9205", "товарных позиций 8701 - 8705"
_REFERENCE = re.compile(r"(?:товарн\w+\s+позици\w+|позици\w+)\s+((?:\d{4}(?:\s*-\s*\d{4})?[\s,;]*(?:или|и)?\s*)+)")
_REF_CODES = re.compile(r"\d{4}(?:\s*-\s*\d{4})?")
_EXCLUSION = re.compile(r"кроме|за исключением|не включа|не поименован|отличн")

EXCLUSION_WINDOW = 60
MAX_REFERENCES = 4


@dataclass
class Node:
    code: str
    title: str
    depth: int


class TnvedTree:
    def __init__(self, nodes: dict[str, Node], headings: dict[str, str]) -> None:
        self.nodes = nodes
        self.headings = headings

    @classmethod
    def load(cls, path: Path) -> "TnvedTree":
        nodes: dict[str, Node] = {}
        headings: dict[str, str] = {}
        in_hierarchy = False

        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                stripped = line.strip()
                if stripped == HIERARCHY_HEADER:
                    in_hierarchy = True
                    continue
                if stripped.startswith(SECTION_HEADERS) and not line.startswith(" "):
                    in_hierarchy = False
                    continue
                if not in_hierarchy:
                    continue

                match = _NODE.match(line)
                if not match or not match.group(2):
                    continue

                indent, code, text = match.group(1), match.group(2), match.group(3)
                bracket = _BRACKET.search(text)
                title = bracket.group(1) if bracket else _BRACKET.sub("", text)
                title = _LEADING_DASHES.sub("", title).strip(" :;")

                nodes[code] = Node(code=code, title=title, depth=len(indent))
                if len(code) == 4:
                    headings[code] = title

        return cls(nodes, headings)

    def heading(self, code: str) -> str:
        return self.headings.get(code[:4], "")

    def path(self, code: str) -> str:
        """титулы всех предков кода: группа, товарная позиция, субпозиция"""
        titles = []
        for length in (4, 6, 8, 9, 10):
            if length >= len(code):
                break
            node = self.nodes.get(code[:length])
            if node and node.title not in titles:
                titles.append(node.title)
        return "; ".join(titles)

    def referenced_headings(self, text: str) -> list[str]:
        """титулы товарных позиций, на которые ссылается описание; исключающие ссылки пропускаем"""
        titles: list[str] = []
        for match in _REFERENCE.finditer(text):
            context = text[max(0, match.start() - EXCLUSION_WINDOW) : match.start()]
            if _EXCLUSION.search(context.lower()):
                continue
            for chunk in _REF_CODES.findall(match.group(1)):
                bounds = re.findall(r"\d{4}", chunk)
                start, end = int(bounds[0]), int(bounds[-1])
                for value in range(start, min(end, start + MAX_REFERENCES) + 1):
                    title = self.headings.get(f"{value:04d}")
                    if title and title not in titles:
                        titles.append(title)
        return titles[:MAX_REFERENCES]
