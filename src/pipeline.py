from pathlib import Path

import numpy as np

from .attributes import constraint_score, parse_constraints, parse_measures, quota_score
from .dense import encode, select_device
from .io_utils import TOP_K, Declaration, Regulation, load_declarations, load_regulations
from .lexical import BM25
from .negation import contradiction_score, split_polarity
from .normalize import normalize, tokenize
from .rerank import score_pairs
from .tnved_tree import TnvedTree

DECLARATIONS_FILE = "declarations.jsonl"
REGULATIONS_FILE = "regulations.jsonl"
KNOWLEDGE_FILE = "tnved_knowledge.txt"

ENCODER_DIR = "bge-m3"
RERANKER_DIR = "bge-reranker-v2-m3"

RRF_K = 20
CANDIDATES = 30
FUSION_WEIGHT = 2.5
ATTRIBUTE_WEIGHT = 1.0
NEGATION_WEIGHT = 0.5


def declaration_text(declaration: Declaration) -> str:
    parts = [declaration.description, declaration.description_ext, declaration.permitting_docs]
    return normalize(" ".join(p for p in parts if p))


def regulation_text(regulation: Regulation) -> str:
    """документ для лексического и плотного поиска

    notes общие для всей группы и обрезаны на полуслове - в индекс не идут.
    раскрытые ссылки сюда тоже не идут: в мешке слов они размывают документ
    и на dev роняют P@1 с 0.406 до 0.344
    """
    parts = [regulation.description, regulation.explanation]
    return normalize(" ".join(p for p in parts if p))


def regulation_context(regulation: Regulation, tree: TnvedTree) -> str:
    """документ для cross-encoder: там ссылка читается в контексте фразы, а не как мешок слов"""
    text = regulation.description
    references = tree.referenced_headings(regulation.description)
    if references:
        text += " (" + "; ".join(references) + ")"
    return normalize(text + " " + regulation.explanation)


def load_data(data_dir: Path) -> tuple[list[Declaration], list[Regulation], TnvedTree]:
    declarations = load_declarations(data_dir / DECLARATIONS_FILE)
    regulations = load_regulations(data_dir / REGULATIONS_FILE)
    tree = TnvedTree.load(data_dir / KNOWLEDGE_FILE)
    return declarations, regulations, tree


def _rank_positions(scores: np.ndarray) -> np.ndarray:
    positions = np.empty(len(scores), dtype=np.float32)
    positions[np.argsort(-scores, kind="stable")] = np.arange(len(scores))
    return positions


def fuse(lexical: np.ndarray, dense: np.ndarray) -> np.ndarray:
    """reciprocal rank fusion: шкалы BM25 и косинуса несопоставимы, ранги - сопоставимы"""
    return 1.0 / (RRF_K + _rank_positions(lexical) + 1.0) + 1.0 / (
        RRF_K + _rank_positions(dense) + 1.0
    )


def rank(
    declarations: list[Declaration],
    regulations: list[Regulation],
    tree: TnvedTree,
    models_dir: Path,
) -> list[tuple[str, int, str, float]]:
    device = select_device()
    print(f"Устройство: {device}")

    queries = [declaration_text(d) for d in declarations]
    documents = [regulation_text(r) for r in regulations]

    bm25 = BM25([tokenize(doc) for doc in documents])
    lexical = np.stack([bm25.score(tokenize(q)) for q in queries])

    embeddings = encode(documents + queries, models_dir / ENCODER_DIR, device)
    doc_vectors, query_vectors = embeddings[: len(documents)], embeddings[len(documents) :]
    dense = query_vectors @ doc_vectors.T

    fused = np.stack([fuse(lexical[i], dense[i]) for i in range(len(declarations))])
    shortlist = np.argsort(-fused, axis=1)[:, :CANDIDATES]

    contexts = [regulation_context(r, tree) for r in regulations]
    pairs = [
        (queries[i], contexts[j]) for i in range(len(declarations)) for j in shortlist[i]
    ]
    reranked = score_pairs(pairs, models_dir / RERANKER_DIR, device).reshape(
        len(declarations), CANDIDATES
    )

    constraints = [parse_constraints(r.description) for r in regulations]

    prior = (CANDIDATES - np.arange(CANDIDATES, dtype=np.float32)) / CANDIDATES

    rows = []
    for i, declaration in enumerate(declarations):
        measures = parse_measures(queries[i], declaration.year)
        negated, positive = split_polarity(queries[i])
        attributes = np.array(
            [
                constraint_score(measures, constraints[j])
                + quota_score(queries[i], regulations[j].description)
                for j in shortlist[i]
            ],
            dtype=np.float32,
        )
        contradictions = np.array(
            [
                contradiction_score(negated, positive, regulations[j].description)
                for j in shortlist[i]
            ],
            dtype=np.float32,
        )
        combined = (
            reranked[i]
            + FUSION_WEIGHT * prior
            + ATTRIBUTE_WEIGHT * attributes
            + NEGATION_WEIGHT * contradictions
        )
        order = np.argsort(-combined, kind="stable")[:TOP_K]
        for position, local in enumerate(order, start=1):
            rows.append(
                (
                    declaration.declaration_id,
                    position,
                    regulations[shortlist[i][local]].regulation_id,
                    float(combined[local]),
                )
            )
    return rows
