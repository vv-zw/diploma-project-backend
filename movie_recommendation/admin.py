import uuid
from functools import wraps
from math import ceil

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from config import Config
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


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if _is_authenticated():
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = str(request.form.get("username", "")).strip()
        password = str(request.form.get("password", ""))
        if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
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
    if username != Config.ADMIN_USERNAME or password != Config.ADMIN_PASSWORD:
        return jsonify({"code": 401, "error": "invalid_admin_credentials"}), 401

    token = _issue_admin_token(username)
    return jsonify({"code": 0, "token": token, "username": username})


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


@admin_api_bp.route("/refresh", methods=["POST"])
@admin_api_login_required
def api_refresh():
    data = request.get_json(silent=True) or {}
    content_type = str(data.get("type", "")).strip().lower()
    targets = [content_type] if content_type in ("movie", "series") else ["movie", "series"]

    for target in targets:
        generate_and_save_recommendations(target)

    return jsonify({"code": 0, "message": "refresh_success", "targets": targets})
