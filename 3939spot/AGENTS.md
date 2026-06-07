# AGENTS.md — AIエージェント向け実装ガイド

このファイルはKiro・Claude・Cursor等のAIエージェントがこのリポジトリでコードを書く際のコンテキストと規約を定義します。

---

## 最優先で確認すること

1. **Redisは使わない**: すでにRedis依存を排除済み。セッション・レート制限を再びRedisで実装してはいけない
2. **DBはSQLite**: `requirements.txt` に `psycopg2` や `pg8000` は含まれていない。PostgreSQL接続コードを書かない
3. **テストはインメモリSQLite**: `conftest.py` の `app` フィクスチャが `FLASK_ENV=testing` で `sqlite:///:memory:` を使用する

---

## アーキテクチャの核心

### アプリファクトリパターン

```python
# app/__init__.py
def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    # 設定ロード → 拡張初期化 → Blueprint登録 → エラーハンドラー登録
    return app
```

新しいBlueprintを追加するときは必ず `_register_blueprints(app)` 内に登録すること。

### 設定クラス

```python
class DevelopmentConfig(Config):  # FLASK_ENV=development
    SQLALCHEMY_DATABASE_URI = "sqlite:///dev.db"

class TestingConfig(Config):       # FLASK_ENV=testing
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

class ProductionConfig(Config):    # FLASK_ENV=production
    SQLALCHEMY_DATABASE_URI = "sqlite:////data/3939spot.db"  # Cloud Run永続ボリューム
```

### セッション管理

Flask標準の署名付きCookieセッションを使用。

```python
# ログイン時
session['user_id'] = str(user.id)
session.permanent = True  # PERMANENT_SESSION_LIFETIME (30日) を適用

# デコレーター
from app.utils.decorators import login_required

@app.route('/protected')
@login_required
def protected():
    ...
```

`flask_session` ディレクトリはローカル開発の遺物。本番では使わない。

### レート制限

Redisではなく `rate_limits` テーブル（SQLite）で実装。

```python
# app/utils/rate_limit.py
from app.utils.rate_limit import check_rate_limit

# before_requestフックで /api/coupons/issue に適用済み
# ルール: 同一IPから5分間に10回超 → 429
```

---

## Blueprint一覧と担当範囲

| Blueprint変数 | url_prefix | 担当 |
|---|---|---|
| `auth_bp` | `/auth` | LINE OAuth, セッション発行, /auth/me |
| `webhook_bp` | `/` | POST /webhook/line (follow/unfollow/message) |
| `coupons_api_bp` | `/api/coupons` | 交換券 CRUD API |
| `coupons_page_bp` | `/coupon` | 交換券取得・一覧ページ (Jinja2) |
| `wifi_bp` | `/api/wifi` | WiFi接続検証 |
| `maps_api_bp` | `/api` | GET/POST/PUT/DELETE /api/spots |
| `maps_page_bp` | `/map` | 提携店マップページ |
| `notifications_bp` | `/api/admin/notifications` | LINE通知配信 |
| `admin_bp` | `/admin` | 管理者ダッシュボード (MFA) |
| `portal_bp` | `/portal` | キャプティブポータル |

---

## モデル定義の規約

```python
# 全モデルはこのインポートパターンを使う
from app import db
from sqlalchemy import Column, String
from sqlalchemy.dialects.sqlite import TEXT  # SQLite固有の型が必要な場合のみ

class MyModel(db.Model):
    __tablename__ = "my_table"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # UUIDはSQLiteのTEXT型として保存（UUIDネイティブ型は使わない）
```

**SQLite固有の注意点**:
- `ARRAY` 型は使えない。JSON文字列またはカンマ区切りで代替する
- `TIMESTAMPTZ` ではなく `db.DateTime` を使う
- `gen_random_uuid()` は使えない。Pythonの `uuid.uuid4()` でデフォルト生成する

### 既存モデルの主要フィールド

**User**: `id, line_id(unique), display_name, home_area, is_active`
**Spot**: `id, name, spot_type(ad_truck/ship_truck/store/raspi), ssid, ap_mac, qr_token(unique), is_active`
**Coupon**: `id, user_id(FK), spot_id(FK), coupon_code(unique), issued_at, expires_at, status(active/used/expired)`
**AdminUser**: `id, email(unique), password_hash, otp_secret`

---

## 交換券発行ロジック（重要）

`app/coupons/service.py` の `issue_coupon()` を必ず経由すること。直接DBに書かない。

```python
from app.coupons.service import issue_coupon

result = issue_coupon(user_id=user.id, spot_id=spot.id)
# result: {"status": "issued", "coupon": {...}}
#      or {"status": "already_issued", "message": "..."}
```

**1日1スポット制限のチェック**: JST日付 + user_id + spot_id の組み合わせで `coupons` テーブルを検索。
**有効期限**: `issued_at + timedelta(days=30)` （JST基準）。

---

## WiFi認証の2パターン

### パターンA: SSID/AP-MAC検証（提携店WiFi）

```python
# POSTボディの ssid, ap_mac を spots テーブルと照合
spot = Spot.query.filter_by(ssid=ssid, ap_mac=ap_mac, is_active=True).first()
```

### パターンB: RaspberryPi経由（カスタムHTTPヘッダー）

```python
# nodogsplashが付与するヘッダーで判定
raspi_flag = request.headers.get("X-RasPi-AP")
spot_id    = request.headers.get("X-RasPi-Spot-ID")
# 送信元サブネット 192.168.50.0/24 も識別に使用可能
```

---

## テストの書き方

```python
# tests/conftest.py のフィクスチャを使う
def test_something(client, app):
    with app.app_context():
        # DBアクセスはここで
        ...
    response = client.get('/some/path')
    assert response.status_code == 200
```

**ログイン状態のシミュレーション**:

```python
with client.session_transaction() as sess:
    sess['user_id'] = str(user.id)
```

**Hypothesisプロパティテスト**:

```python
from hypothesis import given, settings
from hypothesis import strategies as st

@given(user_id=st.uuids(), spot_id=st.uuids())
@settings(max_examples=100)
def test_property_coupon_limit(app, user_id, spot_id):
    """Feature: 3939spot, Property 1: 交換券の1日1スポット制限"""
    with app.app_context():
        ...
```

---

## デプロイ関連

### Dockerfile

```dockerfile
FROM python:3.12-slim
# non-rootユーザー(appuser)で実行
# gunicorn --workers 2 --threads 4 --timeout 120 run:app
```

### GitHub Actions フロー

```
push to main
  → pytest tests/  (失敗でデプロイ中断)
  → docker build & push to Artifact Registry
  → gcloud run deploy 3939spot
```

### Cloud Run 環境変数（本番で必須）

```
FLASK_ENV=production
SECRET_KEY=<強いランダム文字列>
DATABASE_URL=sqlite:////data/3939spot.db   ← 永続ボリュームのパス
LINE_CHANNEL_ID, LINE_CHANNEL_SECRET, LINE_REDIRECT_URI
LINE_MESSAGING_CHANNEL_SECRET, LINE_MESSAGING_CHANNEL_ACCESS_TOKEN
GOOGLE_MAPS_API_KEY
GCP_PROJECT_ID, GCS_BUCKET_NAME
```

---

## RaspberryPi構成（参照のみ）

コードを変更しないでください。設定ファイルは `raspi/` にあります。

```
raspi/
├── hostapd.conf         SSIDブロードキャスト設定 (wlan0, オープンネットワーク)
├── dnsmasq.conf         DHCP: 192.168.50.10-200, DNS全転送でキャプティブポータル検知
├── nodogsplash.conf     splash-onlyモード → 3939.spot/portal へリダイレクト
├── iptables-setup.sh    NAT MASQUERADE + HTTP(80)→port 2050 PREROUTING
├── wpa_supplicant.conf  上流WiFi接続設定
└── systemd/             自動起動ユニットファイル
```

---

## やってはいけないこと

| NG | 理由 |
|---|---|
| `import redis` を追加する | Redis依存を排除済み。セッションはCookieで処理 |
| `psycopg2` や `pg8000` を使う | SQLiteのみ使用。PostgreSQLドライバ不要 |
| `flask_session` を設定する | 標準Cookieセッションに移行済み |
| `db.session.add()` を `commit()` せずに終わる | トランザクションが宙ぶらりんになる |
| `ARRAY` 型をモデルに使う | SQLiteは非対応。JSON文字列で代替 |
| `.env` をGitにコミットする | `.gitignore` で除外されているが厳守 |
| テストでProductionConfigを使う | 必ず `FLASK_ENV=testing` (インメモリDB) を使う |
| Blueprintを `app/__init__.py` 外で `register_blueprint` する | 管理が煩雑になる |

---

## よくある実装パターン

### 新しいAPIエンドポイントを追加する

1. `app/<module>/routes.py` に `@bp.route(...)` を追加
2. 認証が必要なら `@login_required` デコレーターを付ける
3. JSONレスポンスは `jsonify({...})` で返す（日本語メッセージOK）
4. `tests/test_<module>.py` に対応するテストを追加

### 新しいモデルを追加する

1. `app/models/<model_name>.py` を作成
2. `app/models/__init__.py` でインポートを追加
3. `flask db migrate -m "add <model_name>"` でマイグレーションを生成
4. `flask db upgrade` で適用

### LINE通知を送信する

```python
from app.notifications.routes import send_line_push

send_line_push(
    line_id="Uxxxx",
    message="通知メッセージ"
)
```
