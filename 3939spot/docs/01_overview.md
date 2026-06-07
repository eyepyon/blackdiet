# サービス概要

## 3939SPOTとは

3939SPOTは、無料WiFiスポットを活用してブラックサンダー（チョコレート菓子）の交換券を配布し、販促活動を促進するWebサービスです。

URL: **https://3939.spot/**

---

## 交換券取得チャネル

ユーザーは以下3つのチャネルから交換券を取得できます。

```
[ADトラック発見] → QRコード読み取り → LINEログイン → 交換券取得
[出荷トラック発見] → QRコード読み取り → LINEログイン → 交換券取得
[提携店来店] → WiFi接続 → キャプティブポータル → LINEログイン → 交換券取得
```

### チャネル詳細

| チャネル | 方法 | 特徴 |
|---|---|---|
| ADトラック | QRコードスキャン | 日本各地を巡回する広告トラックに掲示 |
| 出荷トラック | QRコードスキャン | 走行中のトラックを見かけたら即参加 |
| 提携店WiFi | WiFi接続 → キャプティブポータル | 来店するだけで自動的に交換券取得フローへ |

**ルール: 同じスポット（QR/WiFiスポット）で1日1枚まで。有効期限は取得日から30日。**

---

## システム構成

```
ユーザー (スマートフォン)
    │
    ├── HTTPS
    │
┌───▼────────────────────────────────────┐
│  GCP Cloud Run                         │
│  Flask アプリ (Python 3.12)            │
│  ├── auth      LINEログイン・セッション │
│  ├── coupons   交換券発行・管理         │
│  ├── wifi      WiFi接続検証             │
│  ├── maps      提携店マップ             │
│  ├── portal    キャプティブポータル     │
│  ├── notifications LINEプッシュ通知    │
│  └── admin     管理者ダッシュボード     │
└────────────────────────────────────────┘
    │
    ├── Cloud SQL (PostgreSQL 15)    … 主データストア
    ├── Cloud Memorystore (Redis)    … セッション・キャッシュ
    ├── Cloud Storage                … 静的アセット
    └── Artifact Registry            … Dockerイメージ

外部サービス:
    ├── LINE Login API     … OAuth 2.0 認証
    ├── LINE Messaging API … プッシュ通知・Webhook
    └── Google Maps API    … 提携店マップ表示
```

### RaspberryPi WiFiルーター

提携店に設置するキャプティブポータルデバイスです。

```
Raspberry Pi (Raspberry Pi OS Lite)
  ├── hostapd    … アクセスポイント（ゲスト向けSSID）
  ├── dnsmasq    … DHCP/DNS（全DNSをローカルへ転送）
  ├── nodogsplash … キャプティブポータル（3939SPOTへリダイレクト）
  └── iptables   … NATルーティング
```

---

## 技術スタック

| レイヤー | 技術 |
|---|---|
| バックエンド | Python 3.12 + Flask 3.x |
| テンプレート | Jinja2 (SSR) |
| ORM | SQLAlchemy 2.x + Flask-Migrate |
| 仮想環境 | venv |
| 環境変数 | python-dotenv (.env) |
| 主DB | Cloud SQL for PostgreSQL 15 |
| キャッシュ/セッション | Redis (Cloud Memorystore) |
| コンテナ | Docker + Artifact Registry |
| デプロイ | GCP Cloud Run |
| 静的ファイル | Google Cloud Storage |
| CI/CD | GitHub Actions |
| IaC | Terraform |

---

## リポジトリ構成

```
3939spot/
├── app/                  Flaskアプリケーション本体
│   ├── __init__.py       アプリファクトリ (create_app)
│   ├── auth/             Auth_System Blueprint
│   ├── coupons/          Coupon_System Blueprint
│   ├── wifi/             WiFi_Auth Blueprint
│   ├── maps/             Map_System Blueprint
│   ├── notifications/    Notification_System Blueprint
│   ├── admin/            Admin Dashboard Blueprint
│   ├── portal/           Captive_Portal Blueprint
│   ├── models/           SQLAlchemyモデル
│   ├── templates/        Jinja2テンプレート
│   ├── static/           静的ファイル (GCSへアップロード)
│   └── utils/            共通ユーティリティ
├── tests/                pytestテスト
│   └── property/         Hypothesisプロパティベーステスト
├── terraform/            Terraformコード (GCPリソース管理)
├── raspi/                RaspberryPi設定ファイル・手順書
│   └── systemd/          systemdユニットファイル
├── docs/                 ← このディレクトリ
├── .github/workflows/    GitHub Actions CI/CDワークフロー
├── Dockerfile
├── docker-compose.yml    ローカル開発用
├── requirements.txt
├── .env.example
└── run.py
```
