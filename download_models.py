import argparse
from pathlib import Path

from huggingface_hub import snapshot_download

# ревизии зафиксированы: без них тег main поедет и результат перестанет воспроизводиться
MODELS = {
    "bge-m3": ("BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181"),
    "bge-reranker-v2-m3": ("BAAI/bge-reranker-v2-m3", "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"),
}

IGNORE = ["*.onnx", "*.onnx_data", "onnx/*", "*.h5", "*.msgpack", "*.ot", "openvino*/*"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="./models")
    args = parser.parse_args()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    for local_name, (repo_id, revision) in MODELS.items():
        target = out_root / local_name
        print(f"Скачивание {repo_id}@{revision[:8]} -> {target}")
        snapshot_download(
            repo_id=repo_id,
            revision=revision,
            local_dir=str(target),
            ignore_patterns=IGNORE,
        )
    print("Готово")


if __name__ == "__main__":
    main()
