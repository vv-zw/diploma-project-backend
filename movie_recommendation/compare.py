"""Offline evaluator aligned with the current recommender implementation.

Supported algorithms:
  - rule_only: rule content similarity + genre/quality/diversity
  - textcnn_rule: TextCNN + genre/quality/diversity
  - ncf_rule: NCF + rule content similarity + genre/quality/diversity
  - ncf_textcnn_rule: NCF + TextCNN + genre/quality/diversity
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

try:
    import tensorflow as tf
    from tensorflow.keras.callbacks import EarlyStopping
    from tensorflow.keras.layers import Concatenate, Dense, Dot, Dropout, Embedding, Flatten, Input
    from tensorflow.keras.models import Model
    from tensorflow.keras.optimizers import Adam

    TF_AVAILABLE = True
except Exception:
    TF_AVAILABLE = False

try:
    from TextCNN import TextCNN

    TEXTCNN_AVAILABLE = True
except Exception:
    TEXTCNN_AVAILABLE = False

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    PLOT_AVAILABLE = True
except Exception:
    PLOT_AVAILABLE = False


ALGORITHM_SPECS = {
    "rule_only": {"label": "Rule Only", "use_ncf": False, "use_textcnn": False},
    "textcnn_rule": {"label": "TextCNN + Rule", "use_ncf": False, "use_textcnn": True},
    "ncf_rule": {"label": "NCF + Rule", "use_ncf": True, "use_textcnn": False},
    "ncf_textcnn_rule": {"label": "NCF + TextCNN + Rule", "use_ncf": True, "use_textcnn": True},
}

FINAL_SCORE_WEIGHTS = {"ncf": 0.35, "textcnn": 0.30, "genre": 0.20, "quality": 0.10, "diversity": 0.05}
NEGATIVE_FEEDBACK_PENALTY = 0.3


@dataclass
class FoldMetrics:
    precision_at_k: float
    recall_at_k: float
    f1_at_k: float
    hit_rate_at_k: float
    ndcg_at_k: float
    map_at_k: float
    mrr_at_k: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate recommender algorithms used by the current project.")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--min-interactions", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20260313)
    parser.add_argument("--ncf-epochs", type=int, default=8)
    parser.add_argument("--ncf-embedding", type=int, default=32)
    parser.add_argument(
        "--algorithms",
        nargs="+",
        default=list(ALGORITHM_SPECS.keys()),
        choices=list(ALGORITHM_SPECS.keys()),
    )
    parser.add_argument("--output-dir", type=str, default="")
    return parser.parse_args()


def safe_load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_csv_with_fallback(path: Path) -> pd.DataFrame:
    for enc in ("utf-8", "gbk", "utf-8-sig"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    raise ValueError(f"Failed to read CSV: {path}")


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def parse_multi_value(raw: object) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]

    text = str(raw).strip()
    if not text:
        return []

    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text.replace("'", '"'))
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass

    text = text.replace("、", ",").replace("/", ",").replace("|", ",").replace(";", ",")
    return [part.strip() for part in text.split(",") if part.strip() and part.strip().lower() != "nan"]


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "id" not in out.columns:
        if "movie_id" in out.columns:
            out.rename(columns={"movie_id": "id"}, inplace=True)
        elif "drama_id" in out.columns:
            out.rename(columns={"drama_id": "id"}, inplace=True)
        else:
            out["id"] = range(len(out))

    for col in ("title", "genres", "director", "actors", "plot"):
        if col not in out.columns:
            out[col] = ""

    for col in ("rating", "year", "popularity"):
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    out["id"] = out["id"].astype(str)
    return out


def build_dataset_id_sets(movies_df: pd.DataFrame, series_df: pd.DataFrame) -> Dict[str, Set[str]]:
    return {"movie": set(movies_df["id"].astype(str)), "series": set(series_df["id"].astype(str))}


def infer_content_type(item: Dict, dataset_ids: Dict[str, Set[str]], default_type: str = "movie") -> str:
    explicit_type = str(item.get("content_type") or item.get("item_type") or item.get("type") or "").strip().lower()
    if explicit_type in ("movie", "series"):
        return explicit_type

    item_id = str(item.get("id") or item.get("item_id") or "").strip()
    if item_id in dataset_ids["movie"]:
        return "movie"
    if item_id in dataset_ids["series"]:
        return "series"
    return default_type


def normalize_preference_item(item: Dict, dataset_ids: Dict[str, Set[str]], default_type: str = "movie") -> Optional[Dict]:
    item_id = str(item.get("id", "")).strip()
    if not item_id:
        return None

    content_type = infer_content_type(item, dataset_ids=dataset_ids, default_type=default_type)
    return {
        "id": item_id,
        "title": str(item.get("title") or item.get("name") or "").strip(),
        "genres": parse_multi_value(item.get("genres", [])),
        "director": str(item.get("director", "")).strip(),
        "actors": parse_multi_value(item.get("actors", [])),
        "rating": safe_float(item.get("rating", 0)),
        "year": int(safe_float(item.get("year", 0))),
        "plot": str(item.get("plot", "")).strip(),
        "content_type": content_type,
    }


def normalize_preferences_payload(preferences: object, dataset_ids: Dict[str, Set[str]]) -> Dict[str, List[Dict]]:
    normalized = {"movie": [], "series": []}
    if isinstance(preferences, dict):
        for content_type in ("movie", "series"):
            for item in preferences.get(content_type, []) or []:
                if not isinstance(item, dict):
                    continue
                normalized_item = normalize_preference_item(item, dataset_ids, default_type=content_type)
                if normalized_item:
                    normalized[content_type].append(normalized_item)
        return normalized

    if isinstance(preferences, list):
        for item in preferences:
            if not isinstance(item, dict):
                continue
            normalized_item = normalize_preference_item(item, dataset_ids)
            if normalized_item:
                normalized[normalized_item["content_type"]].append(normalized_item)
    return normalized


def normalize_behavior_payload(behavior: object, dataset_ids: Dict[str, Set[str]]) -> Dict[str, List[Dict]]:
    normalized = {"movie": [], "series": []}
    if isinstance(behavior, dict):
        for content_type in ("movie", "series"):
            for event in behavior.get(content_type, []) or []:
                if not isinstance(event, dict):
                    continue
                event_copy = dict(event)
                event_copy["item_type"] = infer_content_type(event_copy, dataset_ids, default_type=content_type)
                normalized[event_copy["item_type"]].append(event_copy)
        return normalized

    if isinstance(behavior, list):
        for event in behavior:
            if not isinstance(event, dict):
                continue
            event_copy = dict(event)
            event_copy["item_type"] = infer_content_type({"item_id": event_copy.get("item_id", "")}, dataset_ids)
            normalized[event_copy["item_type"]].append(event_copy)
    return normalized


def get_disliked_ids_by_type(disliked_items: object, dataset_ids: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    disliked = {"movie": set(), "series": set()}
    if not isinstance(disliked_items, list):
        return disliked
    for item in disliked_items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or item.get("item_id") or "").strip()
        if not item_id:
            continue
        item_type = infer_content_type(item, dataset_ids)
        disliked[item_type].add(item_id)
    return disliked


def compute_preference_weights(preferences: Sequence[Dict]) -> Dict[str, Dict[str, float]]:
    weights: Dict[str, Dict[str, float]] = {"genres": {}, "directors": {}, "actors": {}}
    for pref in preferences:
        for genre in parse_multi_value(pref.get("genres", [])):
            weights["genres"][genre] = weights["genres"].get(genre, 0.0) + 1.0
        director = str(pref.get("director", "")).strip()
        if director and director.lower() != "nan":
            weights["directors"][director] = weights["directors"].get(director, 0.0) + 1.0
        for actor in parse_multi_value(pref.get("actors", []))[:3]:
            weights["actors"][actor] = weights["actors"].get(actor, 0.0) + 1.0
    return weights


def content_similarity(item: pd.Series, train_prefs: Sequence[Dict]) -> float:
    if not train_prefs:
        return 0.5

    item_genres = set(parse_multi_value(item.get("genres", "")))
    item_director = str(item.get("director", "")).strip()
    item_actors = set(parse_multi_value(item.get("actors", ""))[:3])
    score_sum = 0.0
    for pref in train_prefs:
        pref_genres = set(parse_multi_value(pref.get("genres", [])))
        pref_director = str(pref.get("director", "")).strip()
        pref_actors = set(parse_multi_value(pref.get("actors", []))[:3])
        genre_match = len(item_genres & pref_genres) / max(len(item_genres), len(pref_genres), 1)
        director_match = 1.0 if item_director and item_director == pref_director else 0.0
        actor_match = len(item_actors & pref_actors) / max(len(item_actors), len(pref_actors), 1)
        score_sum += (genre_match * 0.6) + (director_match * 0.2) + (actor_match * 0.2)
    return score_sum / max(len(train_prefs), 1)


def calculate_diversity_score(item: pd.Series) -> float:
    return min(len(set(parse_multi_value(item.get("genres", "")))) / 5.0, 1.0)


def build_item_text(record: object) -> str:
    getter = record.get
    fields = [
        str(getter("title", "")).strip(),
        ", ".join(parse_multi_value(getter("genres", []))),
        str(getter("director", "")).strip(),
        ", ".join(parse_multi_value(getter("actors", []))),
        str(getter("plot", "")).strip(),
    ]
    return " ".join(part for part in fields if part and part.lower() != "nan")


def normalize_score_map(score_map: Dict[str, float]) -> Dict[str, float]:
    if not score_map:
        return {}
    values = np.array(list(score_map.values()), dtype=float)
    min_value = float(values.min())
    max_value = float(values.max())
    if max_value - min_value < 1e-8:
        return {key: 1.0 for key in score_map}
    return {key: float((value - min_value) / (max_value - min_value)) for key, value in score_map.items()}


def cosine_score(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    denom = float(np.linalg.norm(vector_a) * np.linalg.norm(vector_b))
    if denom <= 1e-8:
        return 0.0
    raw = float(np.dot(vector_a, vector_b) / denom)
    return max(0.0, min(1.0, (raw + 1.0) / 2.0))


def build_textcnn_scores(items_df: pd.DataFrame, train_prefs: Sequence[Dict]) -> Optional[Dict[str, float]]:
    if not TEXTCNN_AVAILABLE or items_df.empty or not train_prefs:
        return None

    preference_texts = [build_item_text(pref) for pref in train_prefs]
    item_texts = [build_item_text(row) for _, row in items_df.iterrows()]
    training_texts = [text for text in dict.fromkeys(preference_texts + item_texts) if text]
    if not training_texts:
        return None

    try:
        encoder = TextCNN()
        encoder.fit(training_texts)
    except Exception:
        return None

    weighted_vectors: List[Tuple[np.ndarray, float]] = []
    for pref in train_prefs:
        text = build_item_text(pref)
        if not text:
            continue
        try:
            vector = encoder.extract_features(text)
        except Exception:
            continue
        weight = max(1.0, safe_float(pref.get("rating", 0), 0.0) / 5.0)
        weighted_vectors.append((np.asarray(vector, dtype=float), weight))

    if not weighted_vectors:
        return None

    total_weight = sum(weight for _, weight in weighted_vectors)
    user_vector = sum(vector * weight for vector, weight in weighted_vectors) / max(total_weight, 1e-8)

    raw_scores: Dict[str, float] = {}
    for _, row in items_df.iterrows():
        item_id = str(row.get("id", "")).strip()
        text = build_item_text(row)
        if not item_id or not text:
            continue
        try:
            item_vector = np.asarray(encoder.extract_features(text), dtype=float)
        except Exception:
            continue
        raw_scores[item_id] = cosine_score(user_vector, item_vector)

    return normalize_score_map(raw_scores) if raw_scores else None


def build_ncf_scores(
    items_df: pd.DataFrame,
    train_prefs: Sequence[Dict],
    train_behavior: Sequence[Dict],
    seed: int,
    epochs: int,
    embedding_size: int,
) -> Optional[Dict[str, float]]:
    if not TF_AVAILABLE or items_df.empty:
        return None

    item_ids = items_df["id"].astype(str).tolist()
    item2idx = {item_id: idx for idx, item_id in enumerate(item_ids)}
    id2item = {idx: item_id for item_id, idx in item2idx.items()}

    positive_indices: List[int] = []
    for pref in train_prefs:
        idx = item2idx.get(str(pref.get("id", "")))
        if idx is not None:
            positive_indices.append(idx)

    for behavior in train_behavior:
        if behavior.get("type") == "like":
            idx = item2idx.get(str(behavior.get("item_id", "")))
            if idx is not None:
                positive_indices.append(idx)

    if not positive_indices:
        return None

    all_indices = set(range(len(item_ids)))
    interacted = set(positive_indices)
    negative_candidates = list(all_indices - interacted)
    if not negative_candidates:
        return None

    rng = np.random.default_rng(seed)
    negative_size = min(len(positive_indices) * 2, len(negative_candidates))
    negative_indices = rng.choice(negative_candidates, size=negative_size, replace=False).tolist()

    user_input = np.zeros(len(positive_indices) + len(negative_indices), dtype=np.int32)
    item_input = np.array(positive_indices + negative_indices, dtype=np.int32)
    labels = np.array([1] * len(positive_indices) + [0] * len(negative_indices), dtype=np.float32)

    permutation = rng.permutation(len(labels))
    user_input = user_input[permutation]
    item_input = item_input[permutation]
    labels = labels[permutation]

    tf.random.set_seed(seed)
    np.random.seed(seed)
    random.seed(seed)

    user_tensor = Input(shape=(1,), name="user_input")
    item_tensor = Input(shape=(1,), name="item_input")

    user_embed_gmf = Embedding(1, embedding_size)(user_tensor)
    item_embed_gmf = Embedding(len(item2idx), embedding_size)(item_tensor)
    gmf_vector = Dot(axes=-1)([Flatten()(user_embed_gmf), Flatten()(item_embed_gmf)])

    user_embed_mlp = Embedding(1, embedding_size * 2)(user_tensor)
    item_embed_mlp = Embedding(len(item2idx), embedding_size * 2)(item_tensor)
    mlp_vector = Concatenate()([Flatten()(user_embed_mlp), Flatten()(item_embed_mlp)])
    mlp_vector = Dense(64, activation="relu")(mlp_vector)
    mlp_vector = Dropout(0.2)(mlp_vector)
    mlp_vector = Dense(32, activation="relu")(mlp_vector)

    merged = Concatenate()([gmf_vector, mlp_vector])
    output = Dense(1, activation="sigmoid", name="prediction")(merged)

    model = Model(inputs=[user_tensor, item_tensor], outputs=output)
    model.compile(optimizer=Adam(learning_rate=0.001), loss="binary_crossentropy", metrics=["accuracy"])

    fit_kwargs = {
        "epochs": epochs,
        "batch_size": 8,
        "verbose": 0,
        "callbacks": [EarlyStopping(patience=2, restore_best_weights=True)],
    }
    if len(labels) >= 10:
        fit_kwargs["validation_split"] = 0.2

    try:
        model.fit([user_input, item_input], labels, **fit_kwargs)
        all_item_idx = np.array(list(item2idx.values()), dtype=np.int32)
        all_user_idx = np.zeros(len(all_item_idx), dtype=np.int32)
        predictions = model.predict([all_user_idx, all_item_idx], verbose=0).flatten()
    except Exception:
        return None

    raw_scores = {id2item[idx]: float(score) for idx, score in zip(all_item_idx, predictions)}
    return normalize_score_map(raw_scores)


def score_item(
    item: pd.Series,
    train_prefs: Sequence[Dict],
    pref_weights: Dict[str, Dict[str, float]],
    disliked_ids: Set[str],
    algorithm: str,
    ncf_scores: Optional[Dict[str, float]],
    textcnn_scores: Optional[Dict[str, float]],
) -> float:
    spec = ALGORITHM_SPECS[algorithm]
    item_id = str(item.get("id", ""))
    weighted_score = 0.0
    active_weight = 0.0

    if spec["use_ncf"]:
        if not ncf_scores or item_id not in ncf_scores:
            return float("-inf")
        weighted_score += ncf_scores[item_id] * FINAL_SCORE_WEIGHTS["ncf"]
        active_weight += FINAL_SCORE_WEIGHTS["ncf"]

    if spec["use_textcnn"]:
        if not textcnn_scores or item_id not in textcnn_scores:
            return float("-inf")
        text_score = textcnn_scores[item_id]
    else:
        text_score = content_similarity(item, train_prefs)
    weighted_score += text_score * FINAL_SCORE_WEIGHTS["textcnn"]
    active_weight += FINAL_SCORE_WEIGHTS["textcnn"]

    genre_score = 0.0
    genres = parse_multi_value(item.get("genres", ""))
    for genre in genres:
        genre_score += pref_weights["genres"].get(genre, 0.0)
    if genres:
        genre_score = min(genre_score / len(genres), 1.0)
    weighted_score += genre_score * FINAL_SCORE_WEIGHTS["genre"]
    active_weight += FINAL_SCORE_WEIGHTS["genre"]

    rating_score = min(safe_float(item.get("rating", 0.0)) / 10.0, 1.0)
    year_val = int(safe_float(item.get("year", 0)))
    if year_val > 0:
        year_score = max(0.0, 1.0 - (datetime.now().year - year_val) / 20.0)
    else:
        year_score = 0.5
    quality_score = rating_score * 0.7 + year_score * 0.3
    weighted_score += quality_score * FINAL_SCORE_WEIGHTS["quality"]
    active_weight += FINAL_SCORE_WEIGHTS["quality"]

    weighted_score += calculate_diversity_score(item) * FINAL_SCORE_WEIGHTS["diversity"]
    active_weight += FINAL_SCORE_WEIGHTS["diversity"]

    score = weighted_score / max(active_weight, 1e-8)
    if item_id in disliked_ids:
        score *= NEGATIVE_FEEDBACK_PENALTY
    return float(score)


def rank_items(
    items_df: pd.DataFrame,
    train_prefs: Sequence[Dict],
    train_behavior: Sequence[Dict],
    train_item_ids: Set[str],
    disliked_ids: Set[str],
    algorithm: str,
    top_k: int,
    seed: int,
    ncf_epochs: int,
    ncf_embedding: int,
) -> Tuple[List[str], bool]:
    candidates = items_df[~items_df["id"].isin(train_item_ids)].copy()
    if candidates.empty:
        return [], False

    spec = ALGORITHM_SPECS[algorithm]
    ncf_scores = None
    textcnn_scores = None

    if spec["use_ncf"]:
        ncf_scores = build_ncf_scores(
            items_df=items_df,
            train_prefs=train_prefs,
            train_behavior=train_behavior,
            seed=seed,
            epochs=ncf_epochs,
            embedding_size=ncf_embedding,
        )
        if not ncf_scores:
            return [], False

    if spec["use_textcnn"]:
        textcnn_scores = build_textcnn_scores(items_df=items_df, train_prefs=train_prefs)
        if not textcnn_scores:
            return [], False

    pref_weights = compute_preference_weights(train_prefs)
    candidates["__score__"] = candidates.apply(
        lambda row: score_item(
            item=row,
            train_prefs=train_prefs,
            pref_weights=pref_weights,
            disliked_ids=disliked_ids,
            algorithm=algorithm,
            ncf_scores=ncf_scores,
            textcnn_scores=textcnn_scores,
        ),
        axis=1,
    )
    candidates = candidates[candidates["__score__"] != float("-inf")]
    if candidates.empty:
        return [], False

    ranked_ids = candidates.sort_values("__score__", ascending=False)["id"].astype(str).head(top_k).tolist()
    return ranked_ids, True


def calc_ranking_metrics(recommended: Sequence[str], relevant: Set[str], k: int) -> FoldMetrics:
    rec_k = list(recommended[:k])
    hit_positions = [idx + 1 for idx, item_id in enumerate(rec_k) if item_id in relevant]
    hit_count = len(hit_positions)

    precision = hit_count / float(k) if k > 0 else 0.0
    recall = hit_count / float(len(relevant)) if relevant else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    hit_rate = 1.0 if hit_count > 0 else 0.0
    mrr = (1.0 / hit_positions[0]) if hit_positions else 0.0

    dcg = sum(1.0 / math.log2(pos + 1) for pos in hit_positions)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(pos + 1) for pos in range(1, ideal_hits + 1))
    ndcg = (dcg / idcg) if idcg > 0 else 0.0

    running_hits = 0
    precision_sum = 0.0
    for rank, item_id in enumerate(rec_k, start=1):
        if item_id in relevant:
            running_hits += 1
            precision_sum += running_hits / rank
    ap = precision_sum / float(max(1, min(len(relevant), k)))

    return FoldMetrics(
        precision_at_k=precision,
        recall_at_k=recall,
        f1_at_k=f1,
        hit_rate_at_k=hit_rate,
        ndcg_at_k=ndcg,
        map_at_k=ap,
        mrr_at_k=mrr,
    )


def average_metrics(metrics: Sequence[FoldMetrics]) -> Dict[str, float]:
    if not metrics:
        return {
            "precision@k": 0.0,
            "recall@k": 0.0,
            "f1@k": 0.0,
            "hit_rate@k": 0.0,
            "ndcg@k": 0.0,
            "map@k": 0.0,
            "mrr@k": 0.0,
        }
    return {
        "precision@k": float(np.mean([m.precision_at_k for m in metrics])),
        "recall@k": float(np.mean([m.recall_at_k for m in metrics])),
        "f1@k": float(np.mean([m.f1_at_k for m in metrics])),
        "hit_rate@k": float(np.mean([m.hit_rate_at_k for m in metrics])),
        "ndcg@k": float(np.mean([m.ndcg_at_k for m in metrics])),
        "map@k": float(np.mean([m.map_at_k for m in metrics])),
        "mrr@k": float(np.mean([m.mrr_at_k for m in metrics])),
    }


def format_metrics_row(name: str, values: Dict[str, float], coverage: float, folds: int) -> str:
    return (
        f"{name:<18}  "
        f"{values['precision@k']:.4f}  "
        f"{values['recall@k']:.4f}  "
        f"{values['f1@k']:.4f}  "
        f"{values['hit_rate@k']:.4f}  "
        f"{values['ndcg@k']:.4f}  "
        f"{values['map@k']:.4f}  "
        f"{values['mrr@k']:.4f}  "
        f"{coverage:.4f}  "
        f"{folds}"
    )


def resolve_output_dir(root: Path, output_dir_arg: str) -> Path:
    if output_dir_arg.strip():
        output_dir = Path(output_dir_arg)
        if not output_dir.is_absolute():
            output_dir = root / output_dir
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = root / "reports" / f"recommender_comparison_{ts}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def to_markdown_table(rows: List[Dict[str, object]]) -> str:
    if not rows:
        return "No data.\n"

    cols = [
        "type",
        "algorithm",
        "precision@k",
        "recall@k",
        "f1@k",
        "hit_rate@k",
        "ndcg@k",
        "map@k",
        "mrr@k",
        "coverage@k",
        "folds",
    ]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines = [header, sep]
    for row in rows:
        values = []
        for col in cols:
            value = row.get(col, "")
            values.append(f"{value:.4f}" if isinstance(value, float) else str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def save_summary_bar_chart(summary_rows: List[Dict[str, object]], output_dir: Path) -> Optional[str]:
    if not PLOT_AVAILABLE or not summary_rows:
        return None

    metrics_keys = ["precision@k", "recall@k", "hit_rate@k", "ndcg@k"]
    metric_labels = ["Precision", "Recall", "HitRate", "NDCG"]
    algorithms = [row["algorithm"] for row in summary_rows]
    x = np.arange(len(metrics_keys))
    width = 0.8 / max(len(algorithms), 1)

    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    for idx, row in enumerate(summary_rows):
        offset = (idx - (len(algorithms) - 1) / 2) * width
        values = [row[key] for key in metrics_keys]
        bars = ax.bar(x + offset, values, width=width, label=row["algorithm"])
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{height:.3f}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(metric_labels)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Score")
    ax.set_title("Algorithm Comparison Summary")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()

    filename = "summary_metrics_bar.png"
    fig.savefig(output_dir / filename, dpi=180)
    plt.close(fig)
    return filename


def save_per_type_heatmap(per_type_rows: List[Dict[str, object]], output_dir: Path) -> Optional[str]:
    if not PLOT_AVAILABLE or not per_type_rows:
        return None

    metrics_keys = ["precision@k", "recall@k", "hit_rate@k", "ndcg@k"]
    metric_labels = ["Precision", "Recall", "HitRate", "NDCG"]
    row_labels = [f"{row['type']} | {row['algorithm']}" for row in per_type_rows]
    matrix = np.array([[float(row[key]) for key in metrics_keys] for row in per_type_rows], dtype=float)

    fig, ax = plt.subplots(figsize=(10, max(3.5, len(row_labels) * 0.55)))
    vmax = max(0.001, float(matrix.max()))
    im = ax.imshow(matrix, cmap="YlGnBu", aspect="auto", vmin=0.0, vmax=vmax)

    ax.set_xticks(np.arange(len(metric_labels)))
    ax.set_xticklabels(metric_labels)
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_yticklabels(row_labels)
    ax.set_title("Per-Type Metric Heatmap")

    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix[i, j]
            color = "white" if value > vmax * 0.6 else "black"
            ax.text(j, i, f"{value:.3f}", ha="center", va="center", color=color, fontsize=8)

    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    fig.tight_layout()

    filename = "per_type_metrics_heatmap.png"
    fig.savefig(output_dir / filename, dpi=180)
    plt.close(fig)
    return filename


def pct_change(base: float, new: float) -> str:
    if abs(base) < 1e-12:
        if abs(new) < 1e-12:
            return "0.00%"
        return "N/A"
    return f"{((new - base) / base) * 100:+.2f}%"


def write_key_results_file(
    output_dir: Path,
    args: argparse.Namespace,
    context: Dict[str, object],
    per_type_rows: List[Dict[str, object]],
    summary_rows: List[Dict[str, object]],
    chart_files: Dict[str, Optional[str]],
) -> None:
    algo_to_row = {row["algorithm"]: row for row in summary_rows}
    baseline_algo = None
    preferred_algo = None

    if "rule_only" in algo_to_row:
        baseline_algo = "rule_only"
    elif summary_rows:
        baseline_algo = summary_rows[0]["algorithm"]

    if "ncf_textcnn_rule" in algo_to_row:
        preferred_algo = "ncf_textcnn_rule"
    elif "ncf_rule" in algo_to_row:
        preferred_algo = "ncf_rule"
    elif len(summary_rows) > 1:
        preferred_algo = summary_rows[-1]["algorithm"]
    else:
        preferred_algo = baseline_algo

    available_types = sorted({row["type"] for row in per_type_rows})
    skipped_types = [name for name in ("movie", "series") if name not in available_types]

    lines: List[str] = []
    lines.append(f"# 性能指标关键结果（Top-K={args.top_k}, Trials={args.trials}）")
    lines.append("## 1. 评估范围")
    lines.append(f"- 数据时间: {context['generated_at']}")
    lines.append(f"- 评估算法: {', '.join(args.algorithms)}")
    lines.append(f"- 当前可评估类型: {', '.join(available_types) if available_types else '无'}")
    lines.append(f"- 被跳过类型: {', '.join(skipped_types) if skipped_types else '无'}")
    lines.append("")

    lines.append("## 2. 核心结论")
    if baseline_algo and preferred_algo and baseline_algo != preferred_algo:
        base = algo_to_row[baseline_algo]
        new = algo_to_row[preferred_algo]
        lines.append(
            f"- 在本次离线评估中，`{preferred_algo}` 相比 `{baseline_algo}` 的整体效果对比如下。"
        )
        lines.append(
            f"- `Precision@{args.top_k}`: {base['precision@k']:.4f} -> {new['precision@k']:.4f}（{pct_change(base['precision@k'], new['precision@k'])}）"
        )
        lines.append(
            f"- `HitRate@{args.top_k}`: {base['hit_rate@k']:.4f} -> {new['hit_rate@k']:.4f}（{pct_change(base['hit_rate@k'], new['hit_rate@k'])}）"
        )
        lines.append(
            f"- `NDCG@{args.top_k}`: {base['ndcg@k']:.4f} -> {new['ndcg@k']:.4f}（{pct_change(base['ndcg@k'], new['ndcg@k'])}）"
        )
        lines.append(
            f"- `Coverage@{args.top_k}`: {base['coverage@k']:.4f} -> {new['coverage@k']:.4f}（{pct_change(base['coverage@k'], new['coverage@k'])}）"
        )
    elif baseline_algo:
        only = algo_to_row[baseline_algo]
        lines.append(f"- 本次只评估了 `{baseline_algo}`。")
        lines.append(
            f"- `Precision@{args.top_k}`={only['precision@k']:.4f}，`HitRate@{args.top_k}`={only['hit_rate@k']:.4f}，`NDCG@{args.top_k}`={only['ndcg@k']:.4f}。"
        )
    else:
        lines.append("- 本次没有可用的汇总结果。")
    lines.append("")

    lines.append("## 3. 指标总览（Summary）")
    lines.append(to_markdown_table(summary_rows))

    if baseline_algo and preferred_algo and baseline_algo != preferred_algo:
        base = algo_to_row[baseline_algo]
        new = algo_to_row[preferred_algo]
        lines.append(f"## 4. 关键指标增益（{preferred_algo} 相对 {baseline_algo}）")
        lines.append("| 指标 | 绝对变化 | 相对变化 |")
        lines.append("| --- | ---: | ---: |")
        for metric in ("precision@k", "recall@k", "f1@k", "hit_rate@k", "ndcg@k", "map@k", "mrr@k", "coverage@k"):
            lines.append(
                f"| {metric.replace('@k', f'@{args.top_k}')} | "
                f"{new[metric] - base[metric]:+.4f} | {pct_change(base[metric], new[metric])} |"
            )
        lines.append("")

    lines.append("## 5. 图表说明")
    if chart_files.get("summary_bar"):
        lines.append(f"- 总览柱状图: [{chart_files['summary_bar']}]({(output_dir / chart_files['summary_bar']).as_posix()})")
    else:
        lines.append("- 总览柱状图: 当前环境未生成")
    if chart_files.get("per_type_heatmap"):
        lines.append(
            f"- 分类热力图: [{chart_files['per_type_heatmap']}]({(output_dir / chart_files['per_type_heatmap']).as_posix()})"
        )
    else:
        lines.append("- 分类热力图: 当前环境未生成")
    lines.append("")

    lines.append("## 6. 结果解读建议")
    lines.append("- `Precision@K` 和 `HitRate@K` 更适合看“推荐是否命中用户真实偏好”。")
    lines.append("- `NDCG@K`、`MAP@K`、`MRR@K` 更适合看“命中的排序位置是否靠前”。")
    lines.append("- `Coverage@K` 更适合看系统是否总是在重复推荐同一批内容。")
    lines.append("- 如果某个算法的 `folds=0`，通常表示当前环境缺少对应依赖，或训练在该轮次失败。")
    lines.append("")

    lines.append("## 7. 指标术语解释")
    lines.append(f"- `Precision@{args.top_k}`: 前 {args.top_k} 个推荐里命中的比例。")
    lines.append(f"- `Recall@{args.top_k}`: 测试集中真实喜欢项目被前 {args.top_k} 个推荐找回的比例。")
    lines.append(f"- `HitRate@{args.top_k}`: 前 {args.top_k} 个推荐里只要命中至少 1 个就记为成功。")
    lines.append(f"- `NDCG@{args.top_k}`: 同时考虑命中与命中位置的排序质量指标。")
    lines.append(f"- `MAP@{args.top_k}`: 多个命中项目在推荐列表中的平均精度。")
    lines.append(f"- `MRR@{args.top_k}`: 第一个命中项目出现得越靠前，值越高。")
    lines.append(f"- `Coverage@{args.top_k}`: 多次推荐中覆盖到的不同项目占候选集的比例。")
    lines.append("- `Folds`: 有效随机切分轮数。")
    lines.append("")

    (output_dir / "性能指标关键结果.md").write_text("\n".join(lines), encoding="utf-8")


def write_report_files(
    output_dir: Path,
    args: argparse.Namespace,
    context: Dict[str, object],
    per_type_rows: List[Dict[str, object]],
    summary_rows: List[Dict[str, object]],
    chart_files: Dict[str, Optional[str]],
) -> None:
    all_rows = summary_rows + per_type_rows
    pd.DataFrame(all_rows).to_csv(output_dir / "metrics.csv", index=False, encoding="utf-8-sig")

    with (output_dir / "metrics.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "run_config": {
                    "top_k": args.top_k,
                    "trials": args.trials,
                    "test_ratio": args.test_ratio,
                    "min_interactions": args.min_interactions,
                    "seed": args.seed,
                    "ncf_epochs": args.ncf_epochs,
                    "ncf_embedding": args.ncf_embedding,
                    "algorithms": args.algorithms,
                },
                "environment": context,
                "summary": summary_rows,
                "per_type": per_type_rows,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    md_lines = [
        "# Recommender Offline Comparison Report",
        "",
        f"- Generated at: {context['generated_at']}",
        f"- Top-K: {args.top_k}",
        f"- Trials: {args.trials}",
        f"- Test ratio: {args.test_ratio}",
        f"- Algorithms: {', '.join(args.algorithms)}",
        f"- TensorFlow available: {context['tensorflow_available']}",
        f"- TextCNN available: {context['textcnn_available']}",
        f"- Plot available: {context['plot_available']}",
        "",
        "## Data Overview",
        "",
        f"- Movie items: {context['movie_items']}",
        f"- Series items: {context['series_items']}",
        f"- Movie interactions: {context['movie_interactions']}",
        f"- Series interactions: {context['series_interactions']}",
        "",
        "## Summary",
        "",
        to_markdown_table(summary_rows),
    ]

    if chart_files.get("summary_bar"):
        md_lines.extend([f"![Summary Bar](./{chart_files['summary_bar']})", ""])

    md_lines.extend(["## Per Type", "", to_markdown_table(per_type_rows)])

    if chart_files.get("per_type_heatmap"):
        md_lines.extend([f"![Per-Type Heatmap](./{chart_files['per_type_heatmap']})", ""])

    md_lines.extend(
        [
            "## Notes",
            "",
            "- `ncf_textcnn_rule` matches the current production main path.",
            "- `ncf_rule` approximates the fallback when TextCNN is unavailable.",
            "- `textcnn_rule` approximates the fallback when NCF is unavailable.",
            "- `rule_only` approximates the last fallback based on rule content similarity.",
            "",
        ]
    )
    (output_dir / "report.md").write_text("\n".join(md_lines), encoding="utf-8")

    summary_df = pd.DataFrame(summary_rows)
    per_type_df = pd.DataFrame(per_type_rows)
    html = [
        "<html><head><meta charset='utf-8'><title>Recommender Offline Comparison</title>",
        "<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:1200px;margin:24px auto;padding:0 16px;line-height:1.5}",
        "table{border-collapse:collapse;width:100%;margin:12px 0}th,td{border:1px solid #ddd;padding:8px;text-align:left}",
        "th{background:#f6f8fa}img{max-width:100%;height:auto;border:1px solid #eee;padding:4px;background:#fff}",
        "code{background:#f3f4f6;padding:1px 4px;border-radius:4px}</style></head><body>",
        "<h1>Recommender Offline Comparison</h1>",
        f"<p>Generated at: {context['generated_at']}<br>Algorithms: {', '.join(args.algorithms)}</p>",
        "<h2>Summary</h2>",
        summary_df.to_html(index=False, float_format=lambda x: f"{x:.4f}"),
    ]
    if chart_files.get("summary_bar"):
        html.append(f"<p><img src='{chart_files['summary_bar']}' alt='summary bar'></p>")
    html.append("<h2>Per Type</h2>")
    html.append(per_type_df.to_html(index=False, float_format=lambda x: f"{x:.4f}"))
    if chart_files.get("per_type_heatmap"):
        html.append(f"<p><img src='{chart_files['per_type_heatmap']}' alt='per type heatmap'></p>")
    html.append("</body></html>")
    (output_dir / "report.html").write_text("".join(html), encoding="utf-8")


def evaluate_one_type(
    type_name: str,
    items_df: pd.DataFrame,
    prefs: Sequence[Dict],
    behavior: Sequence[Dict],
    disliked_ids: Set[str],
    args: argparse.Namespace,
) -> Dict[str, object]:
    print(f"\n=== Evaluating [{type_name}] ===")
    print(f"items={len(items_df)}, interactions={len(prefs)}, trials={args.trials}, top_k={args.top_k}")

    if len(prefs) < max(args.min_interactions, 2):
        print(f"skip: requires at least {max(args.min_interactions, 2)} interactions.")
        return {}

    metrics_store: Dict[str, List[FoldMetrics]] = defaultdict(list)
    unique_recommended: Dict[str, Set[str]] = defaultdict(set)
    attempts: Dict[str, int] = defaultdict(int)
    successes: Dict[str, int] = defaultdict(int)

    for trial in range(args.trials):
        trial_rng = random.Random(args.seed + trial + (0 if type_name == "movie" else 10000))
        test_size = max(1, int(round(len(prefs) * args.test_ratio)))
        if test_size >= len(prefs):
            test_size = len(prefs) - 1
        if test_size <= 0:
            continue

        test_indices = set(trial_rng.sample(range(len(prefs)), k=test_size))
        train_prefs = [p for idx, p in enumerate(prefs) if idx not in test_indices]
        test_prefs = [p for idx, p in enumerate(prefs) if idx in test_indices]
        train_ids = {str(p["id"]) for p in train_prefs}
        test_ids = {str(p["id"]) for p in test_prefs}
        train_behavior = [b for b in behavior if str(b.get("item_id", "")) in train_ids]

        for algorithm in args.algorithms:
            attempts[algorithm] += 1
            ranked_ids, ok = rank_items(
                items_df=items_df,
                train_prefs=train_prefs,
                train_behavior=train_behavior,
                train_item_ids=train_ids,
                disliked_ids=disliked_ids,
                algorithm=algorithm,
                top_k=args.top_k,
                seed=args.seed + trial,
                ncf_epochs=args.ncf_epochs,
                ncf_embedding=args.ncf_embedding,
            )
            if not ok or not ranked_ids:
                continue

            successes[algorithm] += 1
            metrics_store[algorithm].append(calc_ranking_metrics(ranked_ids, test_ids, args.top_k))
            unique_recommended[algorithm].update(ranked_ids)

    print(
        "algorithm            precision  recall     f1         hit_rate   ndcg       map        mrr        coverage   folds"
    )
    print("-" * 124)

    output_rows: Dict[str, object] = {}
    for algorithm in args.algorithms:
        averages = average_metrics(metrics_store[algorithm])
        coverage = len(unique_recommended[algorithm]) / float(max(1, len(items_df)))
        folds = len(metrics_store[algorithm])
        print(format_metrics_row(algorithm, averages, coverage, folds))
        output_rows[algorithm] = {
            "metrics": averages,
            "coverage@k": coverage,
            "folds": folds,
            "success_rate": successes[algorithm] / float(max(1, attempts[algorithm])),
        }
    return output_rows


def build_export_rows(
    all_results: Dict[str, Dict[str, Dict[str, object]]],
    algorithms: Sequence[str],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    per_type_rows: List[Dict[str, object]] = []
    summary_rows: List[Dict[str, object]] = []

    for type_name, type_result in all_results.items():
        for algorithm in algorithms:
            row = type_result.get(algorithm)
            if not row:
                continue
            per_type_rows.append(
                {
                    "scope": "per_type",
                    "type": type_name,
                    "algorithm": algorithm,
                    "precision@k": row["metrics"]["precision@k"],
                    "recall@k": row["metrics"]["recall@k"],
                    "f1@k": row["metrics"]["f1@k"],
                    "hit_rate@k": row["metrics"]["hit_rate@k"],
                    "ndcg@k": row["metrics"]["ndcg@k"],
                    "map@k": row["metrics"]["map@k"],
                    "mrr@k": row["metrics"]["mrr@k"],
                    "coverage@k": row["coverage@k"],
                    "folds": row["folds"],
                    "success_rate": row["success_rate"],
                }
            )

    for algorithm in algorithms:
        merged_metrics: List[FoldMetrics] = []
        coverage_values: List[float] = []
        success_rates: List[float] = []
        folds = 0
        for type_result in all_results.values():
            row = type_result.get(algorithm)
            if not row:
                continue
            folds += row["folds"]
            coverage_values.append(row["coverage@k"])
            success_rates.append(row["success_rate"])
            mean = row["metrics"]
            merged_metrics.extend(
                [
                    FoldMetrics(
                        precision_at_k=mean["precision@k"],
                        recall_at_k=mean["recall@k"],
                        f1_at_k=mean["f1@k"],
                        hit_rate_at_k=mean["hit_rate@k"],
                        ndcg_at_k=mean["ndcg@k"],
                        map_at_k=mean["map@k"],
                        mrr_at_k=mean["mrr@k"],
                    )
                ]
                * max(1, row["folds"])
            )

        summary_rows.append(
            {
                "scope": "summary",
                "type": "all",
                "algorithm": algorithm,
                **average_metrics(merged_metrics),
                "coverage@k": float(np.mean(coverage_values)) if coverage_values else 0.0,
                "folds": folds,
                "success_rate": float(np.mean(success_rates)) if success_rates else 0.0,
            }
        )

    return per_type_rows, summary_rows


def main() -> None:
    args = parse_args()
    if args.top_k <= 0:
        raise ValueError("--top-k must be > 0")
    if not (0 < args.test_ratio < 1):
        raise ValueError("--test-ratio must be in (0, 1)")

    root = Path(__file__).resolve().parents[1]
    output_dir = resolve_output_dir(root, args.output_dir)
    user_path = root / "data" / "user" / "user_data.json"
    movie_path = root / "data" / "datasets" / "douban_movies.csv"
    series_path = root / "data" / "datasets" / "douban_series.csv"

    movies_df = normalize_df(read_csv_with_fallback(movie_path))
    series_df = normalize_df(read_csv_with_fallback(series_path))
    dataset_ids = build_dataset_id_sets(movies_df, series_df)

    user_data = safe_load_json(user_path)
    preferences_by_type = normalize_preferences_payload(user_data.get("preferences", {}), dataset_ids)
    behavior_by_type = normalize_behavior_payload(user_data.get("behavior", {}), dataset_ids)
    disliked_by_type = get_disliked_ids_by_type(user_data.get("disliked_items", []), dataset_ids)

    print("=== Offline Recommender Comparison ===")
    print(f"tensorflow_available={TF_AVAILABLE}")
    print(f"textcnn_available={TEXTCNN_AVAILABLE}")
    print(f"plot_available={PLOT_AVAILABLE}")
    print(f"algorithms={args.algorithms}")
    print("metrics: Precision@K, Recall@K, F1@K, HitRate@K, NDCG@K, MAP@K, MRR@K, Coverage@K")
    print(f"report_output_dir={output_dir}")

    all_results: Dict[str, Dict[str, Dict[str, object]]] = {}
    for type_name, df in (("movie", movies_df), ("series", series_df)):
        result = evaluate_one_type(
            type_name=type_name,
            items_df=df,
            prefs=preferences_by_type[type_name],
            behavior=behavior_by_type[type_name],
            disliked_ids=disliked_by_type[type_name],
            args=args,
        )
        if result:
            all_results[type_name] = result

    if not all_results:
        print("\nNo evaluable data found. Add more user interactions and retry.")
        return

    per_type_rows, summary_rows = build_export_rows(all_results, args.algorithms)
    print("\n=== Summary ===")
    print("algorithm            precision  recall     f1         hit_rate   ndcg       map        mrr        coverage   folds")
    print("-" * 124)
    for row in summary_rows:
        metrics = {
            "precision@k": row["precision@k"],
            "recall@k": row["recall@k"],
            "f1@k": row["f1@k"],
            "hit_rate@k": row["hit_rate@k"],
            "ndcg@k": row["ndcg@k"],
            "map@k": row["map@k"],
            "mrr@k": row["mrr@k"],
        }
        print(format_metrics_row(row["algorithm"], metrics, row["coverage@k"], row["folds"]))

    chart_files = {
        "summary_bar": save_summary_bar_chart(summary_rows, output_dir),
        "per_type_heatmap": save_per_type_heatmap(per_type_rows, output_dir),
    }
    context = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tensorflow_available": TF_AVAILABLE,
        "textcnn_available": TEXTCNN_AVAILABLE,
        "plot_available": PLOT_AVAILABLE,
        "movie_items": len(movies_df),
        "series_items": len(series_df),
        "movie_interactions": len(preferences_by_type["movie"]),
        "series_interactions": len(preferences_by_type["series"]),
    }
    write_report_files(
        output_dir=output_dir,
        args=args,
        context=context,
        per_type_rows=per_type_rows,
        summary_rows=summary_rows,
        chart_files=chart_files,
    )
    write_key_results_file(
        output_dir=output_dir,
        args=args,
        context=context,
        per_type_rows=per_type_rows,
        summary_rows=summary_rows,
        chart_files=chart_files,
    )

    print("\nReport files generated:")
    print(f"- {output_dir / 'report.md'}")
    print(f"- {output_dir / 'report.html'}")
    print(f"- {output_dir / 'metrics.csv'}")
    print(f"- {output_dir / 'metrics.json'}")
    print(f"- {output_dir / '性能指标关键结果.md'}")
    if chart_files["summary_bar"]:
        print(f"- {output_dir / chart_files['summary_bar']}")
    if chart_files["per_type_heatmap"]:
        print(f"- {output_dir / chart_files['per_type_heatmap']}")


if __name__ == "__main__":
    main()
