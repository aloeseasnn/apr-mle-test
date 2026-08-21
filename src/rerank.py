import gc
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MAX_LENGTH = 384
BATCH_SIZE = 8


def score_pairs(
    pairs: list[tuple[str, str]], model_dir: Path, device: str
) -> np.ndarray:
    """логиты cross-encoder для пар (декларация, регуляция)"""
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_dir),
        local_files_only=True,
        torch_dtype=torch.float16 if device != "cpu" else torch.float32,
    )
    model.eval().to(device)

    scores = np.zeros(len(pairs), dtype=np.float32)
    try:
        with torch.inference_mode():
            for start in range(0, len(pairs), BATCH_SIZE):
                batch = pairs[start : start + BATCH_SIZE]
                encoded = tokenizer(
                    [q for q, _ in batch],
                    [d for _, d in batch],
                    padding=True,
                    truncation=True,
                    max_length=MAX_LENGTH,
                    return_tensors="pt",
                ).to(device)
                logits = model(**encoded).logits.squeeze(-1).float()
                scores[start : start + len(batch)] = logits.cpu().numpy()
    finally:
        del model, tokenizer
        gc.collect()
        if device == "mps":
            torch.mps.empty_cache()
        elif device == "cuda":
            torch.cuda.empty_cache()

    return scores
