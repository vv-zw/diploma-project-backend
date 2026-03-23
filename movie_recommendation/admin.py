import uuid
from functools import wraps
from math import ceil

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from db.admin_repository import (
    admin_exists,
    create_admin_user,
    get_admin_by_username,
    update_admin_last_login,
)
from db.connection import get_db_connection, is_database_enabled
from recommendation.engine import generate_and_save_recommendations, init_or_repair_user_data


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
admin_api_bp = Blueprint("admin_api", __name__, url_prefix="/api/admin")
admin_tokens: dict[str, str] = {}


def _is_authenticated() -> bool:
    return bool(session.get("admin_authenticated"))


def admin_login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not _is_authenticated():
            return redirect(url_for("admin.login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped


def _issue_admin_token(username: str) -> str:
    token = uuid.uuid4().hex
    admin_tokens[token] = username
    return token


def _authenticate_admin_credentials(username: str, password: str) -> bool:
    normalized_username = str(username or "").strip()
    raw_password = str(password or "")
    if not normalized_username or not raw_password:
        return False

    admin_record = get_admin_by_username(normalized_username)
    if admin_record:
        if admin_record.get("status") != "active":
            return False
        if not check_password_hash(admin_record.get("password_hash", ""), raw_password):
            return False
        update_admin_last_login(normalized_username)
        return True

    return normalized_username == Config.ADMIN_USERNAME and raw_password == Config.ADMIN_PASSWORD


def _validate_admin_api_token() -> tuple[bool, str]:
    token = str(request.headers.get("X-Admin-Token", "")).strip()
    username = admin_tokens.get(token, "")
    return bool(username), username


def admin_api_login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        ok, username = _validate_admin_api_token()
        if not ok:
            return jsonify({"code": 401, "error": "admin_unauthorized"}), 401
        request.admin_username = username
        return view_func(*args, **kwargs)

    return wrapped


def _fetch_scalar(cur, query: str, params: dict | None = None, default: int = 0) -> int:
    cur.execute(query, params or {})
    row = cur.fetchone()
    if not row:
        return default
    try:
        return int(row[0] or 0)
    except (TypeError, ValueError):
        return default


def load_dashboard_stats() -> dict:
    user_data = init_or_repair_user_data()
    stats = {
        "database_enabled": is_database_enabled(),
        "movie_count": 0,
        "series_count": 0,
        "preference_count": sum(len(user_data.get("preferences", {}).get(content_type, []) or []) for content_type in ("movie", "series")),
        "watchlist_count": 0,
        "feedback_count": len(user_data.get("disliked_items", []) or []),
        "latest_movie_generated_time": "",
        "latest_series_generated_time": "",
    }

    if not is_database_enabled():
        return stats

    schema = Config.PGSCHEMA
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            stats["movie_count"] = _fetch_scalar(
                cur,
                f"SELECT COUNT(*) FROM {schema}.content_items WHERE content_type = %(content_type)s",
                {"content_type": "movie"},
            )
            stats["series_count"] = _fetch_scalar(
                cur,
                f"SELECT COUNT(*) FROM {schema}.content_items WHERE content_type = %(content_type)s",
                {"content_type": "series"},
            )
            stats["watchlist_count"] = _fetch_scalar(cur, f"SELECT COUNT(*) FROM {schema}.watchlist_items")
            stats["feedback_count"] = _fetch_scalar(cur, f"SELECT COUNT(*) FROM {schema}.negative_feedback")

            cur.execute(
                f"""
                SELECT content_type, MAX(generated_time)
                FROM {schema}.recommendation_snapshots
                GROUP BY content_type
                """
            )
            for content_type, generated_time in cur.fetchall():
                if content_type == "movie" and generated_time:
                    stats["latest_movie_generated_time"] = generated_time.strftime("%Y-%m-%d %H:%M:%S")
                elif content_type == "series" and generated_time:
                    stats["latest_series_generated_time"] = generated_time.strftime("%Y-%m-%d %H:%M:%S")

    return stats


def load_content_page(content_type: str, keyword: str, page: int, page_size: int = 20) -> dict:
    normalized_type = content_type if content_type in ("movie", "series") else ""
    keyword = (keyword or "").strip()

    result = {
        "items": [],
        "page": page,
        "page_size": page_size,
        "total": 0,
        "pages": 0,
        "content_type": normalized_type,
        "keyword": keyword,
    }

    if not is_database_enabled():
        return result

    schema = Config.PGSCHEMA
    where_clauses = []
    params: dict[str, object] = {}

    if normalized_type:
        where_clauses.append("content_type = %(content_type)s")
        params["content_type"] = normalized_type
    if keyword:
        where_clauses.append("(title ILIKE %(keyword)s OR COALESCE(original_title, '') ILIKE %(keyword)s)")
        params["keyword"] = f"%{keyword}%"

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {schema}.content_items {where_sql}", params)
            total = int(cur.fetchone()[0] or 0)
            pages = ceil(total / page_size) if total else 1
            page = max(1, min(page, pages))

            params["limit"] = page_size
            params["offset"] = (page - 1) * page_size
            cur.execute(
                f"""
                SELECT source_item_id, content_type, title, rating, year, genres, director, status, updated_at
                FROM {schema}.content_items
                {where_sql}
                ORDER BY updated_at DESC, id DESC
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                params,
            )
            rows = cur.fetchall()

    result.update(
        {
            "items": [
                {
                    "source_item_id": str(row[0] or ""),
                    "content_type": str(row[1] or ""),
                    "title": row[2] or "",
                    "rating": float(row[3] or 0),
                    "year": row[4] or "",
                    "genres": row[5] or "",
                    "director": row[6] or "",
                    "status": row[7] or "",
                    "updated_at": row[8].strftime("%Y-%m-%d %H:%M:%S") if row[8] else "",
                }
                for row in rows
            ],
            "page": page,
            "total": total,
            "pages": ceil(total / page_size) if total else 1,
        }
    )
    return result


def _load_behavior_trend(cur, schema: str, table_name: str, time_column: str, content_type: str = "") -> list[dict]:
    params: dict[str, object] = {}
    where_sql = ""
    if content_type in ("movie", "series"):
        where_sql = "WHERE content_type = %(content_type)s"
        params["content_type"] = content_type

    cur.execute(
        f"""
        SELECT TO_CHAR(DATE({time_column}), 'YYYY-MM-DD') AS day, COUNT(*)
        FROM {schema}.{table_name}
        {where_sql}
        GROUP BY DATE({time_column})
        ORDER BY DATE({time_column}) DESC
        LIMIT 7
        """,
        params,
    )
    rows = list(cur.fetchall())
    rows.reverse()
    return [{"label": row[0], "value": int(row[1] or 0)} for row in rows]


def _load_top_genres(cur, schema: str, table_name: str, content_type: str = "") -> list[dict]:
    params: dict[str, object] = {}
    where_sql = "WHERE COALESCE(genres, '') <> ''"
    if content_type in ("movie", "series"):
        where_sql += " AND content_type = %(content_type)s"
        params["content_type"] = content_type

    cur.execute(
        f"""
        SELECT TRIM(genre_item), COUNT(*)
        FROM (
            SELECT UNNEST(REGEXP_SPLIT_TO_ARRAY(REPLACE(COALESCE(genres, ''), '、', ','), '\\s*,\\s*')) AS genre_item
            FROM {schema}.{table_name}
            {where_sql}
        ) AS expanded
        WHERE TRIM(genre_item) <> ''
        GROUP BY TRIM(genre_item)
        ORDER BY COUNT(*) DESC, TRIM(genre_item) ASC
        LIMIT 5
        """,
        params,
    )
    return [{"label": row[0] or "未知", "value": int(row[1] or 0)} for row in cur.fetchall()]


def _load_top_titles(cur, schema: str, table_name: str, alias: str, time_column: str, content_type: str = "") -> list[dict]:
    params: dict[str, object] = {}
    where_sql = ""
    title_expr = "title"

    if table_name == "negative_feedback":
        title_expr = "COALESCE(ci.title, nf.content_id)"
        where_sql = f"""
        LEFT JOIN {schema}.content_items ci
            ON ci.source_item_id = nf.content_id
           AND ci.content_type = nf.content_type
        """

    content_filter = ""
    if content_type in ("movie", "series"):
        content_filter = f"WHERE {alias}.content_type = %(content_type)s"
        params["content_type"] = content_type

    cur.execute(
        f"""
        SELECT {title_expr} AS display_title, COUNT(*) AS total_count, MAX({alias}.{time_column}) AS latest_time
        FROM {schema}.{table_name} {alias}
        {where_sql}
        {content_filter}
        GROUP BY display_title
        ORDER BY total_count DESC, latest_time DESC
        LIMIT 5
        """,
        params,
    )
    return [
        {
            "title": row[0] or "未命名内容",
            "count": int(row[1] or 0),
        }
        for row in cur.fetchall()
    ]


def load_behavior_summary(tab: str = "overview") -> dict:
    normalized_tab = tab if tab in ("overview", "movie", "series") else "overview"
    content_type = "" if normalized_tab == "overview" else normalized_tab

    summary = {
        "tab": normalized_tab,
        "headline": "用户行为总览" if normalized_tab == "overview" else ("电影行为分析" if normalized_tab == "movie" else "剧集行为分析"),
        "summary_text": "",
        "cards": [],
        "trend": {
            "title": "最近 7 天行为趋势",
            "series": [],
        },
        "genre_distribution": [],
        "top_lists": {
            "preferences": [],
            "watchlist": [],
            "feedback": [],
        },
    }

    if not is_database_enabled():
        summary["summary_text"] = "数据库未启用，暂时无法生成行为分析。"
        return summary

    schema = Config.PGSCHEMA
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            params = {"content_type": content_type}
            type_where = "WHERE content_type = %(content_type)s" if content_type else ""

            preference_count = _fetch_scalar(cur, f"SELECT COUNT(*) FROM {schema}.user_preferences {type_where}", params if content_type else None)
            watchlist_count = _fetch_scalar(cur, f"SELECT COUNT(*) FROM {schema}.watchlist_items {type_where}", params if content_type else None)
            feedback_count = _fetch_scalar(cur, f"SELECT COUNT(*) FROM {schema}.negative_feedback {type_where}", params if content_type else None)

            if normalized_tab == "overview":
                movie_actions = _fetch_scalar(
                    cur,
                    f"""
                    SELECT
                        (SELECT COUNT(*) FROM {schema}.user_preferences WHERE content_type = 'movie') +
                        (SELECT COUNT(*) FROM {schema}.watchlist_items WHERE content_type = 'movie') +
                        (SELECT COUNT(*) FROM {schema}.negative_feedback WHERE content_type = 'movie')
                    """
                )
                series_actions = _fetch_scalar(
                    cur,
                    f"""
                    SELECT
                        (SELECT COUNT(*) FROM {schema}.user_preferences WHERE content_type = 'series') +
                        (SELECT COUNT(*) FROM {schema}.watchlist_items WHERE content_type = 'series') +
                        (SELECT COUNT(*) FROM {schema}.negative_feedback WHERE content_type = 'series')
                    """
                )
                summary["cards"] = [
                    {"label": "偏好记录", "value": preference_count, "accent": "warm"},
                    {"label": "待看记录", "value": watchlist_count, "accent": "ink"},
                    {"label": "负反馈", "value": feedback_count, "accent": "alert"},
                    {"label": "电影行为量", "value": movie_actions, "accent": "gold"},
                    {"label": "剧集行为量", "value": series_actions, "accent": "gold"},
                ]
                summary["summary_text"] = "这里汇总了当前全部用户行为，可以快速观察电影和剧集两条内容线的活跃程度。"
            else:
                summary["cards"] = [
                    {"label": "偏好记录", "value": preference_count, "accent": "warm"},
                    {"label": "待看记录", "value": watchlist_count, "accent": "ink"},
                    {"label": "负反馈", "value": feedback_count, "accent": "alert"},
                ]
                summary["summary_text"] = f"这里展示 {summary['headline']} 的趋势、类型分布和高频内容，方便继续细查。"

            summary["trend"]["series"] = [
                {
                    "label": "偏好",
                    "points": _load_behavior_trend(cur, schema, "user_preferences", "created_at", content_type),
                },
                {
                    "label": "待看",
                    "points": _load_behavior_trend(cur, schema, "watchlist_items", "added_at", content_type),
                },
                {
                    "label": "负反馈",
                    "points": _load_behavior_trend(cur, schema, "negative_feedback", "created_at", content_type),
                },
            ]
            summary["genre_distribution"] = _load_top_genres(cur, schema, "user_preferences", content_type)
            summary["top_lists"] = {
                "preferences": _load_top_titles(cur, schema, "user_preferences", "up", "created_at", content_type),
                "watchlist": _load_top_titles(cur, schema, "watchlist_items", "wi", "added_at", content_type),
                "feedback": _load_top_titles(cur, schema, "negative_feedback", "nf", "created_at", content_type),
            }

    return summary


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if _is_authenticated():
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = str(request.form.get("username", "")).strip()
        password = str(request.form.get("password", ""))
        if _authenticate_admin_credentials(username, password):
            session["admin_authenticated"] = True
            session["admin_username"] = username
            flash("登录成功。", "success")
            next_url = request.args.get("next") or url_for("admin.dashboard")
            return redirect(next_url)

        flash("账号或密码不正确。", "error")

    return render_template("admin/login.html")


@admin_bp.route("/logout", methods=["POST"])
@admin_login_required
def logout():
    session.pop("admin_authenticated", None)
    session.pop("admin_username", None)
    flash("已退出管理员后台。", "success")
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@admin_login_required
def dashboard():
    return render_template("admin/dashboard.html", stats=load_dashboard_stats())


@admin_bp.route("/content")
@admin_login_required
def content():
    content_type = str(request.args.get("type", "")).strip().lower()
    keyword = str(request.args.get("q", "")).strip()
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1

    listing = load_content_page(content_type, keyword, page)
    return render_template("admin/content.html", listing=listing)


@admin_bp.route("/refresh", methods=["POST"])
@admin_login_required
def refresh_recommendations():
    content_type = str(request.form.get("type", "")).strip().lower()
    targets = [content_type] if content_type in ("movie", "series") else ["movie", "series"]

    for target in targets:
        generate_and_save_recommendations(target)

    flash(f"已触发 {' / '.join(targets)} 推荐刷新。", "success")
    return redirect(url_for("admin.dashboard"))


@admin_api_bp.route("/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not _authenticate_admin_credentials(username, password):
        return jsonify({"code": 401, "error": "invalid_admin_credentials"}), 401

    token = _issue_admin_token(username)
    return jsonify({"code": 0, "token": token, "username": username})


@admin_api_bp.route("/bootstrap-status", methods=["GET"])
def api_bootstrap_status():
    return jsonify({
        "code": 0,
        "has_admin": admin_exists(),
        "database_enabled": is_database_enabled(),
    })


@admin_api_bp.route("/register", methods=["POST"])
def api_register():
    if admin_exists():
        return jsonify({"code": 403, "error": "admin_registration_closed"}), 403

    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    display_name = str(data.get("display_name", "")).strip()

    if not username:
        return jsonify({"code": 400, "error": "missing_username"}), 400
    if len(username) < 3:
        return jsonify({"code": 400, "error": "username_too_short"}), 400
    if not password:
        return jsonify({"code": 400, "error": "missing_password"}), 400
    if len(password) < 6:
        return jsonify({"code": 400, "error": "password_too_short"}), 400
    if get_admin_by_username(username):
        return jsonify({"code": 409, "error": "admin_username_exists"}), 409

    password_hash = generate_password_hash(password)
    if not create_admin_user(username, password_hash, display_name):
        return jsonify({"code": 500, "error": "admin_registration_failed"}), 500

    return jsonify({
        "code": 0,
        "message": "admin_register_success",
        "username": username,
    })


@admin_api_bp.route("/logout", methods=["POST"])
@admin_api_login_required
def api_logout():
    token = str(request.headers.get("X-Admin-Token", "")).strip()
    admin_tokens.pop(token, None)
    return jsonify({"code": 0, "message": "logout_success"})


@admin_api_bp.route("/dashboard", methods=["GET"])
@admin_api_login_required
def api_dashboard():
    return jsonify({"code": 0, "data": load_dashboard_stats()})


@admin_api_bp.route("/content", methods=["GET"])
@admin_api_login_required
def api_content():
    content_type = str(request.args.get("type", "")).strip().lower()
    keyword = str(request.args.get("q", "")).strip()
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1

    return jsonify({"code": 0, "data": load_content_page(content_type, keyword, page)})


@admin_api_bp.route("/behavior-summary", methods=["GET"])
@admin_api_login_required
def api_behavior_summary():
    tab = str(request.args.get("tab", "overview")).strip().lower()
    if tab not in ("overview", "movie", "series"):
        return jsonify({"code": 400, "error": "invalid_tab"}), 400
    return jsonify({"code": 0, "data": load_behavior_summary(tab)})


@admin_api_bp.route("/refresh", methods=["POST"])
@admin_api_login_required
def api_refresh():
    data = request.get_json(silent=True) or {}
    content_type = str(data.get("type", "")).strip().lower()
    targets = [content_type] if content_type in ("movie", "series") else ["movie", "series"]

    for target in targets:
        generate_and_save_recommendations(target)

    return jsonify({"code": 0, "message": "refresh_success", "targets": targets})
