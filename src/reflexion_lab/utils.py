from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel

from .schemas import ContextChunk, QAExample, ReflectionEntry


def normalize_answer(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_difficulty(value: Any) -> str:
    level = str(value or "medium").lower()
    if level in {"easy", "medium", "hard"}:
        return level
    return "medium"


def hotpot_raw_to_qaexample(item: dict[str, Any], index: int = 0) -> QAExample:
    context = item.get("context", {})
    chunks: list[dict[str, str]] = []
    if isinstance(context, dict):
        titles = context.get("title", [])
        sentences = context.get("sentences", [])
        for title, sentence_list in zip(titles, sentences):
            text = sentence_list if isinstance(sentence_list, str) else " ".join(str(s) for s in sentence_list)
            chunks.append({"title": str(title), "text": text.strip()})
    elif isinstance(context, list):
        for row in context:
            if isinstance(row, dict):
                title = row.get("title", "")
                text = row.get("text", "")
            elif isinstance(row, (list, tuple)) and len(row) >= 2:
                title, sentences = row[0], row[1]
                text = sentences if isinstance(sentences, str) else " ".join(str(s) for s in sentences)
            else:
                continue
            chunks.append({"title": str(title), "text": str(text).strip()})

    return QAExample(
        qid=str(item.get("qid") or item.get("_id") or item.get("id") or f"gold_{index:04d}"),
        difficulty=normalize_difficulty(item.get("difficulty") or item.get("level")),
        question=str(item["question"]),
        gold_answer=str(item.get("gold_answer") or item.get("answer") or ""),
        context=[ContextChunk.model_validate(chunk) for chunk in chunks if chunk.get("title") and chunk.get("text")],
    )


def load_dataset(path: str | Path) -> list[QAExample]:
    return load_dataset_auto(path, dataset_format="qaexample")


def load_dataset_auto(path: str | Path, dataset_format: str = "auto") -> list[QAExample]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Dataset must be a JSON list: {path}")
    if not raw:
        return []

    first = raw[0]
    if not isinstance(first, dict):
        raise ValueError("Dataset items must be JSON objects.")

    detected = dataset_format
    if dataset_format == "auto":
        if "gold_answer" in first or (
            isinstance(first.get("context"), list)
            and first.get("context")
            and isinstance(first["context"][0], dict)
            and "text" in first["context"][0]
        ):
            detected = "qaexample"
        elif "answer" in first and isinstance(first.get("context"), dict):
            detected = "hotpotqa_raw"
        else:
            raise ValueError("Cannot detect dataset format. Use --dataset-format qaexample or hotpotqa_raw.")

    if detected == "qaexample":
        return [QAExample.model_validate(item) for item in raw]
    if detected == "hotpotqa_raw":
        return [hotpot_raw_to_qaexample(item, index) for index, item in enumerate(raw)]
    raise ValueError(f"Unsupported dataset format: {dataset_format}")


def save_jsonl(path: str | Path, records: Iterable[Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            if isinstance(record, BaseModel):
                f.write(record.model_dump_json() + "\n")
            else:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_json(path: str | Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def format_context(example: QAExample, max_chars: int = 12000) -> str:
    chunks: list[str] = []
    remaining = max_chars
    for index, chunk in enumerate(example.context, start=1):
        prefix = f"[{index}] {chunk.title}: "
        if remaining <= len(prefix):
            break
        text = chunk.text
        available = remaining - len(prefix)
        if len(text) > available:
            text = text[: max(0, available - 3)].rstrip() + "..."
        rendered = prefix + text
        chunks.append(rendered)
        remaining -= len(rendered) + 1
    return "\n".join(chunks)


def compact_reflection_memory(reflections: list[ReflectionEntry], max_items: int = 2) -> list[str]:
    memory: list[str] = []
    for reflection in reflections[-max_items:]:
        avoid = "; ".join(reflection.avoid)
        memory.append(
            f"Lesson: {reflection.lesson}; Strategy: {reflection.next_strategy}; Avoid: {avoid}"
        )
    return memory


def build_dataset_manifest(examples: list[QAExample], dataset_path: str | Path) -> dict:
    qids = [example.qid for example in examples]
    qid_counts = Counter(qids)
    context_counts = [len(example.context) for example in examples]
    question_lengths = [len(example.question) for example in examples]
    difficulty_counts = Counter(example.difficulty for example in examples)
    return {
        "dataset_path": str(dataset_path),
        "num_examples": len(examples),
        "qid_count": len(set(qids)),
        "duplicate_qids": sorted(qid for qid, count in qid_counts.items() if count > 1),
        "difficulty_counts": dict(sorted(difficulty_counts.items())),
        "avg_context_chunks": round(sum(context_counts) / len(context_counts), 2) if context_counts else 0,
        "min_context_chunks": min(context_counts) if context_counts else 0,
        "max_context_chunks": max(context_counts) if context_counts else 0,
        "avg_question_chars": round(sum(question_lengths) / len(question_lengths), 2) if question_lengths else 0,
        "has_empty_context": any(not example.context for example in examples),
        "has_gold_answers": all(bool(example.gold_answer) for example in examples),
        "schema_valid": True,
    }
