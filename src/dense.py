import gc
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

MAX_LENGTH = 512
BATCH_SIZE = 8


def select_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def encode(texts: list[str], model_dir: Path, device: str | None = None) -> np.ndarray:
    """эмбеддинги с L2-нормировкой"""
    device = device or select_device()
    model_kwargs = {"torch_dtype": torch.float16} if device != "cpu" else {}
    model = SentenceTransformer(
        str(model_dir), device=device, local_files_only=True, model_kwargs=model_kwargs
    )
    model.max_seq_length = MAX_LENGTH

    try:
        embeddings = model.encode(
            texts,
            batch_size=BATCH_SIZE,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
    finally:
        del model
        gc.collect()
        if device == "mps":
            torch.mps.empty_cache()
        elif device == "cuda":
            torch.cuda.empty_cache()

    return embeddings.astype(np.float32)
