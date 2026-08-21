from collections import Counter

import numpy as np

K1 = 1.2
B = 0.75
MIN_STEM = 5
STEM_KEEP = 5


def stem(token: str) -> str:
    """грубый усекающий стеммер: русская морфология иначе разводит одинаковые слова"""
    if token.isdigit() or len(token) <= MIN_STEM:
        return token
    return token[:STEM_KEEP]


class BM25:
    def __init__(self, corpus: list[list[str]]) -> None:
        self.docs = [[stem(t) for t in doc] for doc in corpus]
        self.doc_len = np.array([len(doc) for doc in self.docs], dtype=np.float32)
        self.avg_len = float(self.doc_len.mean()) if len(self.docs) else 0.0

        self.vocab: dict[str, int] = {}
        for doc in self.docs:
            for term in doc:
                if term not in self.vocab:
                    self.vocab[term] = len(self.vocab)

        n_docs, n_terms = len(self.docs), len(self.vocab)
        self.tf = np.zeros((n_docs, n_terms), dtype=np.float32)
        for i, doc in enumerate(self.docs):
            for term, count in Counter(doc).items():
                self.tf[i, self.vocab[term]] = count

        df = (self.tf > 0).sum(axis=0)
        self.idf = np.log(1.0 + (n_docs - df + 0.5) / (df + 0.5)).astype(np.float32)

        norm = K1 * (1.0 - B + B * self.doc_len / max(self.avg_len, 1e-6))
        self.weights = self.tf * (K1 + 1.0) / (self.tf + norm[:, None])
        self.weights *= self.idf[None, :]

    def score(self, query: list[str]) -> np.ndarray:
        columns = [self.vocab[term] for term in (stem(t) for t in query) if term in self.vocab]
        if not columns:
            return np.zeros(len(self.docs), dtype=np.float32)
        return self.weights[:, columns].sum(axis=1)
