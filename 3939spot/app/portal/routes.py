"""
Captive_Portal routes
- GET /portal           キャプティブポータルランディング（Jinja2 template）
- GET /portal/redirect  認証後コンテンツページへリダイレクト
"""

from flask import redirect, render_template, request, url_for

from app.portal import portal_bp
from app.utils.session import is_logged_in


def _get_spot_id() -> str | None:
    """クエリパラメータ → リファラ → X-RasPi-AP の順で spot_id を解決する。"""
    # 明示的なクエリパラメータが最優先
    spot_id = request.args.get("spot_id")
    if spot_id:
        return spot_id

    # X-RasPi-AP ヘッダーがある場合は "raspi" を疑似 spot_id として返す
    if request.headers.get("X-RasPi-AP") == "1":
        return "raspi"

    # リファラからの判定（例: ?spot_id=xxx を含む URL から来た場合）
    referrer = request.referrer or ""
    if "spot_id=" in referrer:
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = parse_qs(urlparse(referrer).query)
            vals = parsed.get("spot_id", [])
            if vals:
                return vals[0]
        except Exception:
            pass

    return None


@portal_bp.route("")
def portal_landing():
    """キャプティブポータルランディングページ。

    X-RasPi-AP ヘッダー / リファラ / クエリパラメータから spot_id を取得し
    テンプレートに渡す。
    """
    spot_id = _get_spot_id()
    return render_template("portal/landing.html", spot_id=spot_id)


@portal_bp.route("/redirect")
def portal_redirect():
    """認証後コンテンツページへリダイレクト。

    ログイン済み → /coupon/get
    未ログイン  → /auth/line/login?next=/coupon/get
    spot_id があればそれぞれに引き渡す。
    """
    spot_id = _get_spot_id()
    next_url = "/coupon/get"
    if spot_id:
        next_url = f"/coupon/get?spot_id={spot_id}"

    if is_logged_in():
        return redirect(next_url)

    return redirect(f"/auth/line/login?next={next_url}")
