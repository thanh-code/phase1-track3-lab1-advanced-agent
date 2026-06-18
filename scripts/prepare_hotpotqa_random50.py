from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from datasets import load_dataset


def normalize_difficulty(value: Any) -> str:
    level = str(value or "medium").lower()
    if level in {"easy", "medium", "hard"}:
        return level
    return "medium"


def context_to_chunks(context: dict[str, Any]) -> list[dict[str, str]]:
    titles = context.get("title", [])
    sentences = context.get("sentences", [])
    chunks: list[dict[str, str]] = []

    for title, sentence_list in zip(titles, sentences):
        if isinstance(sentence_list, str):
            text = sentence_list
        else:
            text = " ".join(str(sentence) for sentence in sentence_list)
        chunks.append({"title": str(title), "text": text.strip()})

    return [chunk for chunk in chunks if chunk["title"] and chunk["text"]]


def convert_example(row: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "qid": str(row.get("id") or row.get("_id") or f"hotpotqa_{index}"),
        "difficulty": normalize_difficulty(row.get("level")),
        "question": str(row["question"]),
        "gold_answer": str(row["answer"]),
        "context": context_to_chunks(row["context"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sample random HotpotQA examples and convert them to the lab QAExample schema."
    )
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="data/hotpotqa_random50.json")
    parser.add_argument("--split", default="validation")
    parser.add_argument("--config", default="distractor")
    args = parser.parse_args()

    dataset = load_dataset("hotpotqa/hotpot_qa", args.config, split=args.split)
    if args.n > len(dataset):
        raise ValueError(f"Requested {args.n} examples, but split only has {len(dataset)}.")

    sample = dataset.shuffle(seed=args.seed).select(range(args.n))
    converted = [convert_example(row, index) for index, row in enumerate(sample)]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(converted, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved {len(converted)} examples to {out_path}")


if __name__ == "__main__":
    main()
