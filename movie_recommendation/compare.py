"""Offline evaluator for content-only vs NCF-hybrid recommendation quality.

Usage:
  python movie_recommendation/compare.py
  python movie_recommendation/compare.py --top-k 10 --trials 30 --test-ratio 0.3

Notes:
- Ground truth is built from historical user preferences in data/user/user_data.json.
- Evaluation uses repeated random train/test splits on user interactions.
- "accuracy" in top-K recommendation is typically represented by Precision@K and HitRate@K.
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
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

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
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    PLOT_AVAILABLE = True
except Exception:
    PLOT_AVAILABLE = False


DEFAULT_WEIGHTS = {
    "genre_preference": 0.7,
    "rating": 0.1,
    "popularity": 0.02,
    "release_year": 0.03,
    "similarity": 0.05,
    "user_preference": 0.1,
}


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
    parser = argparse.ArgumentParser(description="Compare content-only and NCF-hybrid metrics.")
    parser.add_argument("--top-k", type=int, default=20, help="Top-K cutoff for ranking metrics.")
    parser.add_argument("--trials", type=int, default=20, help="Number of random train/test splits.")
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.2,
        help="Fraction of interactions used as test in each trial.",
    )
    parser.add_argument(
        "--min-interactions",
        type=int,
        default=6,
        help="Minimum interactions required for a content type to be evaluated.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260309,
        help="Base random seed for reproducible splits.",
    )
    parser.add_argument(
        "--ncf-epochs",
        type=int,
        default=8,
        help="Training epochs for each NCF fold.",
    )
    parser.add_argument(
        "--ncf-embedding",
        type=int,
        default=32,
        help="NCF embedding dimension.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="",
        help="Output directory for report assets. Default: auto-create under reports/",
    )
    return parser.parse_args()


def safe_load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_csv_with_fallback(path: Path) -> pd.DataFrame:
    for enc in ("utf-8", "gbk"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    raise ValueError(f"Failed to read CSV: {path}")


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "id" not in out.columns:
        if "movie_id" in out.columns:
            out.rename(columns={"movie_id": "id"}, inplace=True)
        elif "drama_id" in out.columns:
            out.rename(columns={"drama_id": "id"}, inplace=True)
        else:
            out["id"] = range(len(out))
    for col in ("genres", "director", "actors", "title"):
        if col not in out.columns:
            out[col] = ""
    for col in ("rating", "year", "popularity"):
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    out["id"] = out["id"].astype(str)
    return out


def parse_multi_value(raw: object) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]

    text = str(raw).strip()
    if not text:
        return []

    # Handle stringified list like "['悬疑']".
    if text.startswith("[") and text.endswith("]"):
        try:
            # Literal parsing without eval safety risk.
            parsed = json.loads(text.replace("'", '"'))
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass

    text = text.replace("、", ",").replace("/", ",").replace("|", ",")
    return [part.strip() for part in text.split(",") if part.strip() and part.strip().lower() != "nan"]


def normalize_preferences(preferences: Iterable[Dict]) -> List[Dict]:
    normalized: List[Dict] = []
    for item in preferences:
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            continue
        normalized.append(
            {
                "id": item_id,
                "genres": parse_multi_value(item.get("genres", "")),
                "director": str(item.get("director", "")).strip(),
                "actors": parse_multi_value(item.get("actors", "")),
                "rating": safe_float(item.get("rating", 0)),
            }
        )
    return normalized


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


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


def diversity_score(item: pd.Series) -> float:
    return len(set(parse_multi_value(item.get("genres", "")))) / 5.0


def score_item(
    item: pd.Series,
    train_prefs: Sequence[Dict],
    pref_weights: Dict[str, Dict[str, float]],
    ncf_scores: Optional[Dict[str, float]],
    disliked_ids: Set[str],
    weights: Dict[str, float],
) -> float:
    item_id = str(item.get("id", ""))
    score = 0.0

    sim = content_similarity(item, train_prefs)
    if ncf_scores and item_id in ncf_scores:
        score += ncf_scores[item_id] * weights["similarity"]
    else:
        score += sim * weights["similarity"]

    genre_parts = parse_multi_value(item.get("genres", ""))
    genre_match = sum(pref_weights["genres"].get(g, 0.0) for g in genre_parts)
    if genre_parts:
        genre_match = min(genre_match / len(genre_parts), 1.0)
    score += genre_match * weights["genre_preference"]

    rating_score = min(safe_float(item.get("rating", 0.0)) / 10.0, 1.0)
    year_val = int(safe_float(item.get("year", 0)))
    if year_val > 0:
        year_score = max(0.0, 1.0 - (2026 - year_val) / 20.0)
    else:
        year_score = 0.5
    quality_score = (rating_score * 0.7) + (year_score * 0.3)
    score += quality_score * weights["rating"]

    score += sim * weights["user_preference"]
    score += diversity_score(item) * weights["popularity"]

    if item_id in disliked_ids:
        score *= 0.3
    return float(score)


def build_ncf_scores(
    items_df: pd.DataFrame,
    train_prefs: Sequence[Dict],
    train_behavior: Sequence[Dict],
    seed: int,
    epochs: int,
    embedding_size: int,
) -> Optional[Dict[str, float]]:
    if not TF_AVAILABLE:
        return None

    item_ids = items_df["id"].astype(str).tolist()
    item2idx = {item_id: idx for idx, item_id in enumerate(item_ids)}
    id2item = {idx: item_id for item_id, idx in item2idx.items()}
    all_indices = set(range(len(item_ids)))

    positive_indices: List[int] = []
    for pref in train_prefs:
        idx = item2idx.get(str(pref.get("id", "")))
        if idx is not None:
            rating = safe_float(pref.get("rating", 5), 5)
            if rating >= 5:
                positive_indices.append(idx)

    for behavior in train_behavior:
        if behavior.get("type") == "like":
            idx = item2idx.get(str(behavior.get("item_id", "")))
            if idx is not None:
                positive_indices.append(idx)

    if not positive_indices:
        return None

    interacted = set(positive_indices)
    negative_candidates = list(all_indices - interacted)
    if not negative_candidates:
        return None

    rng = np.random.default_rng(seed)
    neg_size = min(len(positive_indices) * 2, len(negative_candidates))
    negative_indices = rng.choice(negative_candidates, size=neg_size, replace=False).tolist()

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

    callbacks = [EarlyStopping(patience=2, restore_best_weights=True)]
    fit_kwargs = {"epochs": epochs, "batch_size": 8, "verbose": 0, "callbacks": callbacks}
    if len(labels) >= 10:
        fit_kwargs["validation_split"] = 0.2
    model.fit([user_input, item_input], labels, **fit_kwargs)

    all_item_idx = np.array(list(item2idx.values()), dtype=np.int32)
    all_user_idx = np.zeros(len(all_item_idx), dtype=np.int32)
    predictions = model.predict([all_user_idx, all_item_idx], verbose=0).flatten()
    return {id2item[idx]: float(score) for idx, score in zip(all_item_idx, predictions)}


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
    weights: Dict[str, float],
) -> Tuple[List[str], bool]:
    candidates = items_df[~items_df["id"].isin(train_item_ids)].copy()
    if candidates.empty:
        return [], False

    pref_weights = compute_preference_weights(train_prefs)
    ncf_scores = None
    ncf_ok = False
    if algorithm == "ncf_hybrid":
        ncf_scores = build_ncf_scores(
            items_df=items_df,
            train_prefs=train_prefs,
            train_behavior=train_behavior,
            seed=seed,
            epochs=ncf_epochs,
            embedding_size=ncf_embedding,
        )
        ncf_ok = ncf_scores is not None
        if not ncf_ok:
            return [], False

    candidates["__score__"] = candidates.apply(
        lambda row: score_item(row, train_prefs, pref_weights, ncf_scores, disliked_ids, weights),
        axis=1,
    )
    ranked_ids = candidates.sort_values("__score__", ascending=False)["id"].astype(str).head(top_k).tolist()
    return ranked_ids, (algorithm != "ncf_hybrid" or ncf_ok)


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
        f"{name:<14}  "
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


def split_preferences_by_type(
    preferences: Sequence[Dict],
    movie_ids: Set[str],
    series_ids: Set[str],
) -> Dict[str, List[Dict]]:
    result = {"movie": [], "series": []}
    for pref in preferences:
        pref_id = str(pref.get("id", ""))
        if pref_id in movie_ids:
            result["movie"].append(pref)
        elif pref_id in series_ids:
            result["series"].append(pref)
    return result


def filter_behavior_by_ids(behavior: Sequence[Dict], allowed_ids: Set[str]) -> List[Dict]:
    filtered = []
    for event in behavior:
        item_id = str(event.get("item_id", "")).strip()
        if item_id and item_id in allowed_ids:
            filtered.append(event)
    return filtered


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


def build_rows_for_export(
    all_results: Dict[str, Dict[str, Dict[str, object]]],
    summary_rows: Dict[str, Dict[str, object]],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    per_type_rows: List[Dict[str, object]] = []
    for type_name, type_result in all_results.items():
        for algo in ("content_only", "ncf_hybrid"):
            row = type_result.get(algo)
            if not row:
                continue
            per_type_rows.append(
                {
                    "scope": "per_type",
                    "type": type_name,
                    "algorithm": algo,
                    "precision@k": row["metrics"]["precision@k"],
                    "recall@k": row["metrics"]["recall@k"],
                    "f1@k": row["metrics"]["f1@k"],
                    "hit_rate@k": row["metrics"]["hit_rate@k"],
                    "ndcg@k": row["metrics"]["ndcg@k"],
                    "map@k": row["metrics"]["map@k"],
                    "mrr@k": row["metrics"]["mrr@k"],
                    "coverage@k": row["coverage@k"],
                    "folds": row["folds"],
                }
            )

    summary_export_rows: List[Dict[str, object]] = []
    for algo in ("content_only", "ncf_hybrid"):
        row = summary_rows.get(algo)
        if not row:
            continue
        summary_export_rows.append(
            {
                "scope": "summary",
                "type": "all",
                "algorithm": algo,
                "precision@k": row["metrics"]["precision@k"],
                "recall@k": row["metrics"]["recall@k"],
                "f1@k": row["metrics"]["f1@k"],
                "hit_rate@k": row["metrics"]["hit_rate@k"],
                "ndcg@k": row["metrics"]["ndcg@k"],
                "map@k": row["metrics"]["map@k"],
                "mrr@k": row["metrics"]["mrr@k"],
                "coverage@k": row["coverage@k"],
                "folds": row["folds"],
            }
        )
    return per_type_rows, summary_export_rows


def save_summary_bar_chart(summary_rows: Dict[str, Dict[str, object]], output_dir: Path) -> Optional[str]:
    if not PLOT_AVAILABLE:
        return None

    metrics_keys = ["precision@k", "recall@k", "hit_rate@k", "ndcg@k"]
    metric_labels = ["Precision", "Recall", "HitRate", "NDCG"]
    algorithms = [algo for algo in ("content_only", "ncf_hybrid") if algo in summary_rows]
    if not algorithms:
        return None

    x = np.arange(len(metrics_keys))
    width = 0.35 if len(algorithms) == 2 else 0.5

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for idx, algo in enumerate(algorithms):
        offset = (idx - (len(algorithms) - 1) / 2) * width
        values = [summary_rows[algo]["metrics"][key] for key in metrics_keys]
        bars = ax.bar(x + offset, values, width=width, label=algo)
        for bar in bars:
            h = bar.get_height()
            ax.annotate(
                f"{h:.3f}",
                xy=(bar.get_x() + bar.get_width() / 2, h),
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
    ax.set_title("Algorithm Comparison (Summary)")
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

    fig, ax = plt.subplots(figsize=(9.5, max(3.0, len(row_labels) * 0.65)))
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
        vals = []
        for col in cols:
            value = row.get(col, "")
            if isinstance(value, float):
                vals.append(f"{value:.4f}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


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
                },
                "environment": context,
                "summary": summary_rows,
                "per_type": per_type_rows,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    md_lines: List[str] = []
    md_lines.append("# 推荐算法对比报告")
    md_lines.append("")
    md_lines.append(f"- 生成时间: {context['generated_at']}")
    md_lines.append(f"- Top-K: {args.top_k}")
    md_lines.append(f"- Trials: {args.trials}")
    md_lines.append(f"- Test Ratio: {args.test_ratio}")
    md_lines.append(f"- TensorFlow 可用: {context['tensorflow_available']}")
    md_lines.append(f"- 图表可用: {context['plot_available']}")
    md_lines.append("")
    md_lines.append("## 数据概况")
    md_lines.append("")
    md_lines.append(f"- 电影候选数: {context['movie_items']}")
    md_lines.append(f"- 剧集候选数: {context['series_items']}")
    md_lines.append(f"- 电影交互数: {context['movie_interactions']}")
    md_lines.append(f"- 剧集交互数: {context['series_interactions']}")
    if context.get("skipped_types"):
        md_lines.append(f"- 跳过类型: {', '.join(context['skipped_types'])}")
    md_lines.append("")
    md_lines.append("## 总览指标（Summary）")
    md_lines.append("")
    md_lines.append(to_markdown_table(summary_rows))

    if chart_files.get("summary_bar"):
        md_lines.append("![Summary Bar](./" + chart_files["summary_bar"] + ")")
        md_lines.append("")

    md_lines.append("## 分类型指标（Per Type）")
    md_lines.append("")
    md_lines.append(to_markdown_table(per_type_rows))

    if chart_files.get("per_type_heatmap"):
        md_lines.append("![Per-Type Heatmap](./" + chart_files["per_type_heatmap"] + ")")
        md_lines.append("")

    md_lines.append("## 结论说明")
    md_lines.append("")
    md_lines.append("- 推荐系统中的“准确率”通常用 `Precision@K` 和 `HitRate@K` 表示。")
    md_lines.append("- 如果 `ncf_hybrid` 的 folds 很低，说明当前 NCF 训练在多次切分里失败率较高。")
    md_lines.append("- 当前报告属于离线评估，后续可结合在线 A/B 测试做业务验证。")
    md_lines.append("")

    report_md = output_dir / "report.md"
    report_md.write_text("\n".join(md_lines), encoding="utf-8")

    summary_df = pd.DataFrame(summary_rows)
    per_type_df = pd.DataFrame(per_type_rows)
    html = [
        "<html><head><meta charset='utf-8'><title>推荐算法对比报告</title>",
        "<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:1200px;margin:24px auto;padding:0 16px;line-height:1.5}",
        "table{border-collapse:collapse;width:100%;margin:12px 0}th,td{border:1px solid #ddd;padding:8px;text-align:left}",
        "th{background:#f6f8fa}img{max-width:100%;height:auto;border:1px solid #eee;padding:4px;background:#fff}",
        "code{background:#f3f4f6;padding:1px 4px;border-radius:4px}</style></head><body>",
        "<h1>推荐算法对比报告</h1>",
        f"<p>生成时间: {context['generated_at']}<br>Top-K: {args.top_k}<br>Trials: {args.trials}<br>Test Ratio: {args.test_ratio}</p>",
        "<h2>总览指标（Summary）</h2>",
        summary_df.to_html(index=False, float_format=lambda x: f"{x:.4f}"),
    ]
    if chart_files.get("summary_bar"):
        html.append(f"<p><img src='{chart_files['summary_bar']}' alt='summary bar'></p>")
    html.append("<h2>分类型指标（Per Type）</h2>")
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

    algorithms = ("content_only", "ncf_hybrid")
    metrics_store: Dict[str, List[FoldMetrics]] = defaultdict(list)
    unique_recommended: Dict[str, Set[str]] = defaultdict(set)
    ncf_success = 0
    ncf_attempt = 0

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

        for algo in algorithms:
            if algo == "ncf_hybrid":
                ncf_attempt += 1

            ranked_ids, ok = rank_items(
                items_df=items_df,
                train_prefs=train_prefs,
                train_behavior=train_behavior,
                train_item_ids=train_ids,
                disliked_ids=disliked_ids,
                algorithm=algo,
                top_k=args.top_k,
                seed=args.seed + trial,
                ncf_epochs=args.ncf_epochs,
                ncf_embedding=args.ncf_embedding,
                weights=DEFAULT_WEIGHTS,
            )

            if not ok:
                continue
            if algo == "ncf_hybrid":
                ncf_success += 1
            if not ranked_ids:
                continue

            fold_result = calc_ranking_metrics(ranked_ids, test_ids, args.top_k)
            metrics_store[algo].append(fold_result)
            unique_recommended[algo].update(ranked_ids)

    print(
        "algorithm       precision  recall     f1         hit_rate   ndcg       map        mrr        coverage   folds"
    )
    print("-" * 118)

    output_rows = {}
    for algo in algorithms:
        averages = average_metrics(metrics_store[algo])
        coverage = len(unique_recommended[algo]) / float(max(1, len(items_df)))
        folds = len(metrics_store[algo])
        print(format_metrics_row(algo, averages, coverage, folds))
        output_rows[algo] = {
            "metrics": averages,
            "coverage@k": coverage,
            "folds": folds,
        }

    if ncf_attempt > 0:
        print(f"ncf_train_success_rate={ncf_success}/{ncf_attempt} ({(ncf_success / ncf_attempt):.2%})")

    return output_rows


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

    user_data = safe_load_json(user_path)
    preferences = normalize_preferences(user_data.get("preferences", []))
    behavior = user_data.get("behavior", [])
    disliked_ids = {str(x.get("id")) for x in user_data.get("disliked_items", []) if str(x.get("id", "")).strip()}

    movies_df = normalize_df(read_csv_with_fallback(movie_path))
    series_df = normalize_df(read_csv_with_fallback(series_path))

    prefs_by_type = split_preferences_by_type(
        preferences=preferences,
        movie_ids=set(movies_df["id"].astype(str)),
        series_ids=set(series_df["id"].astype(str)),
    )

    behavior_by_type = {
        "movie": filter_behavior_by_ids(behavior, set(movies_df["id"].astype(str))),
        "series": filter_behavior_by_ids(behavior, set(series_df["id"].astype(str))),
    }

    print("=== Offline Recommender Comparison ===")
    print(f"tensorflow_available={TF_AVAILABLE}")
    print(f"plot_available={PLOT_AVAILABLE}")
    print(f"user_preferences_total={len(preferences)}")
    print(
        "metrics: Precision@K (accuracy proxy), Recall@K, F1@K, HitRate@K, NDCG@K, MAP@K, MRR@K, Coverage@K"
    )
    print(f"report_output_dir={output_dir}")

    all_results = {}
    skipped_types: List[str] = []
    for type_name, df in (("movie", movies_df), ("series", series_df)):
        result = evaluate_one_type(
            type_name=type_name,
            items_df=df,
            prefs=prefs_by_type[type_name],
            behavior=behavior_by_type[type_name],
            disliked_ids=disliked_ids,
            args=args,
        )
        if not result:
            skipped_types.append(type_name)
            continue
        all_results[type_name] = result

    if not all_results:
        print("\nNo evaluable data found. Add more user interactions in user_data.json and retry.")
        return

    print("\n=== Summary (macro over available types) ===")
    print(
        "algorithm       precision  recall     f1         hit_rate   ndcg       map        mrr        coverage   folds"
    )
    print("-" * 118)

    summary_rows: Dict[str, Dict[str, object]] = {}
    for algo in ("content_only", "ncf_hybrid"):
        merged_metrics: List[FoldMetrics] = []
        coverage_count = 0
        coverage_den = 0
        total_folds = 0
        for type_name, type_result in all_results.items():
            row = type_result.get(algo)
            if not row:
                continue
            total_folds += row["folds"]
            coverage_den += 1
            coverage_count += row["coverage@k"]
            # Approximate macro merge by repeating fold means as fold count.
            # We keep the detailed per-type rows as the primary source.
            per_type_mean = row["metrics"]
            merged_metrics.extend(
                [
                    FoldMetrics(
                        precision_at_k=per_type_mean["precision@k"],
                        recall_at_k=per_type_mean["recall@k"],
                        f1_at_k=per_type_mean["f1@k"],
                        hit_rate_at_k=per_type_mean["hit_rate@k"],
                        ndcg_at_k=per_type_mean["ndcg@k"],
                        map_at_k=per_type_mean["map@k"],
                        mrr_at_k=per_type_mean["mrr@k"],
                    )
                ]
                * max(1, row["folds"])
            )

        avg = average_metrics(merged_metrics)
        avg_coverage = (coverage_count / coverage_den) if coverage_den else 0.0
        print(format_metrics_row(algo, avg, avg_coverage, total_folds))
        summary_rows[algo] = {"metrics": avg, "coverage@k": avg_coverage, "folds": total_folds}

    print("\nInterpretation:")
    print("- Precision@K and HitRate@K are the most direct 'accuracy' views for top-K recommendation.")
    print("- If NCF rows have very few folds, TensorFlow/NCF training likely failed in many trials.")

    per_type_export_rows, summary_export_rows = build_rows_for_export(all_results, summary_rows)
    chart_files = {
        "summary_bar": save_summary_bar_chart(summary_rows, output_dir),
        "per_type_heatmap": save_per_type_heatmap(per_type_export_rows, output_dir),
    }
    context = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tensorflow_available": TF_AVAILABLE,
        "plot_available": PLOT_AVAILABLE,
        "movie_items": len(movies_df),
        "series_items": len(series_df),
        "movie_interactions": len(prefs_by_type["movie"]),
        "series_interactions": len(prefs_by_type["series"]),
        "skipped_types": skipped_types,
    }
    write_report_files(
        output_dir=output_dir,
        args=args,
        context=context,
        per_type_rows=per_type_export_rows,
        summary_rows=summary_export_rows,
        chart_files=chart_files,
    )
    print("\nReport files generated:")
    print(f"- {(output_dir / 'report.md')}")
    print(f"- {(output_dir / 'report.html')}")
    print(f"- {(output_dir / 'metrics.csv')}")
    print(f"- {(output_dir / 'metrics.json')}")
    if chart_files["summary_bar"]:
        print(f"- {(output_dir / chart_files['summary_bar'])}")
    if chart_files["per_type_heatmap"]:
        print(f"- {(output_dir / chart_files['per_type_heatmap'])}")


if __name__ == "__main__":
    main()
