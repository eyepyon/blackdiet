# Implementation Plan: 3939SPOT

## Overview

3939SPOTの実装計画です。無料WiFiスポットを活用してブラックサンダー交換券を配布するWebサービスを、FlaskベースのバックエンドとGCPインフラで構築します。プロジェクト基盤→データモデル→各サブシステム→フロントエンド→セキュリティ→CI/CD→RaspberryPiの順で実装します。

## Task Dependency Graph

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": ["1"],
      "description": "プロジェクト基盤セットアップ"
    },
    {
      "wave": 2,
      "tasks": ["2"],
      "description": "データモデルの実装（基盤に依存）"
    },
    {
      "wave": 3,
      "tasks": ["3", "5"],
      "description": "Auth_SystemとWiFi_Authの実装（モデルに依存）"
    },
    {
      "wave": 4,
      "tasks": ["4", "6"],
      "description": "Coupon_SystemとCaptive_Portalの実装（Auth・WiFi_Authに依存）"
    },
    {
      "wave": 5,
      "tasks": ["7", "8"],
      "description": "Map_SystemとNotification_Systemの実装"
    },
    {
      "wave": 6,
      "tasks": ["9", "11"],
      "description": "Admin DashboardとセキュリティLayerの実装"
    },
    {
      "wave": 7,
      "tasks": ["10", "12"],
      "description": "フロントエンドページとLINEbotリッチメニューの実装"
    },
    {
      "wave": 8,
      "tasks": ["13", "14"],
      "description": "統合テストとプロパティベーステストの実装"
    },
    {
      "wave": 9,
      "tasks": ["15", "16"],
      "description": "CI/CD・Terraformインフラ・RaspberryPi設定の実装"
    }
  ]
}
```

## Tasks

- [x] 1. プロジェクト基盤セットアップ
  - [x] 1.1 プロジェクト構成の作成（ディレクトリ構造・仮想環境・requirements.txt）
  - [x] 1.2 Flaskアプリファクトリ（`app/__init__.py`）の実装（Blueprints登録・設定管理・エラーハンドラー）
  - [x] 1.3 環境変数管理（`.env.example`・`python-dotenv`設定）
  - [x] 1.4 SQLAlchemy・Flask-Migrate初期設定とDB接続設定
  - [x] 1.5 Redisセッション（Flask-Session）の初期設定
  - [x] 1.6 `run.py`エントリーポイントの作成
  - [x] 1.7 Dockerfileの作成（`python:3.12-slim`ベース・`gunicorn`起動）
  - [x] 1.8 Docker Compose（ローカル開発用PostgreSQL・Redis）の作成

- [x] 2. データモデルの実装
  - [x] 2.1 `User`モデルの実装（`app/models/user.py`）
  - [x] 2.2 `Spot`モデルの実装（`app/models/spot.py`）
  - [x] 2.3 `Coupon`モデルの実装（`app/models/coupon.py`、`unique_daily_spot`制約含む）
  - [x] 2.4 `Session`モデルの実装（`app/models/session.py`）
  - [x] 2.5 `PartnerApplication`モデルの実装（`app/models/partner_application.py`）
  - [x] 2.6 `AdminUser`モデルの実装（`app/models/admin_user.py`）
  - [x] 2.7 `AdTruckLocation`モデルの実装（`app/models/ad_truck_location.py`）
  - [x] 2.8 初期マイグレーションファイルの生成（Flask-Migrate）

- [ ] 3. Auth_System（`app/auth/`）の実装
  - [x] 3.1 LINE Login APIを使ったOAuth 2.0認証フロー（`GET /auth/line/login`・`GET /auth/line/callback`）の実装
  - [-] 3.2 セッション発行・Redis保存（TTL 30日・最終アクセスでリセット）の実装
  - [~] 3.3 `@login_required`デコレーターの実装
  - [~] 3.4 `POST /auth/logout`・`GET /auth/me`エンドポイントの実装
  - [~] 3.5 LINE Messaging API Webhook（`POST /webhook/line`）の実装（follow/unfollow/blockイベント処理）
  - [~] 3.6 Auth_Systemの単体テスト（`tests/test_auth.py`）の作成

- [ ] 4. Coupon_System（`app/coupons/`）の実装
  - [~] 4.1 交換券発行ロジック（`issue_coupon`）の実装（JST日付・Redisによる重複チェック・DB保存）
  - [~] 4.2 `POST /api/coupons/issue`エンドポイントの実装
  - [~] 4.3 `GET /api/coupons/my`・`GET /api/coupons/<coupon_id>`エンドポイントの実装
  - [~] 4.4 交換券検証（`POST /api/coupons/<coupon_id>/verify`）の実装（有効期限・未使用確認）
  - [~] 4.5 交換券使用（`POST /api/coupons/<coupon_id>/redeem`）の実装（使用済み更新・使用日時・店舗ID記録）
  - [~] 4.6 Coupon_Systemの単体テスト（`tests/test_coupons.py`）の作成

- [ ] 5. WiFi_Auth（`app/wifi/`）の実装
  - [~] 5.1 パターンA（SSID/AP-MAC検証）ロジックの実装
  - [~] 5.2 パターンB（`X-RasPi-AP: 1`ヘッダー・`192.168.4.0/24`サブネット検証）ロジックの実装
  - [~] 5.3 `POST /api/wifi/verify`エンドポイントの実装
  - [~] 5.4 `GET /api/wifi/spots`エンドポイント（管理者向け）の実装
  - [~] 5.5 WiFi_Authの単体テスト（`tests/test_wifi_auth.py`）の作成

- [ ] 6. Captive_Portal（`app/portal/`）の実装
  - [~] 6.1 `GET /portal`キャプティブポータルランディングページ（Jinja2テンプレート）の実装
  - [~] 6.2 `GET /portal/redirect`認証後コンテンツページへのリダイレクト処理の実装
  - [~] 6.3 WiFi_Authとの連携（AP識別情報の検証）の実装

- [ ] 7. Map_System（`app/maps/`）の実装
  - [~] 7.1 `GET /api/spots`提携スポット一覧（lat/lng・keyword絞り込み対応）の実装
  - [~] 7.2 `GET /api/spots/<spot_id>`提携スポット詳細の実装
  - [~] 7.3 `POST /api/spots`・`PUT /api/spots/<spot_id>`・`DELETE /api/spots/<spot_id>`（管理者）の実装
  - [~] 7.4 Redisキャッシュ（`spots:cache`、TTL 5分）によるリアルタイム反映の実装
  - [~] 7.5 提携店マップページ（`/map`、Google Maps JavaScript API統合・Jinja2テンプレート）の実装

- [ ] 8. Notification_System（`app/notifications/`）の実装
  - [~] 8.1 `POST /api/admin/notifications/truck` ADトラック位置更新・通知配信の実装
  - [~] 8.2 ADトラック通知スロットリング（Redisカウンター、1ユーザー/1日最大3回）の実装
  - [~] 8.3 `POST /api/admin/notifications/blast`一斉メッセージ配信の実装
  - [~] 8.4 `POST /api/admin/notifications/new-spot`新規提携店通知の実装
  - [~] 8.5 有効期限3日前通知バッチ（Cloud Schedulerまたはcron）の実装
  - [~] 8.6 Notification_Systemの単体テスト（`tests/test_notifications.py`）の作成

- [ ] 9. Admin Dashboard（`app/admin/`）の実装
  - [~] 9.1 管理者MFA認証（`POST /admin/auth/login`・`POST /admin/auth/mfa/verify`）の実装（email+password+TOTP）
  - [~] 9.2 管理者ダッシュボード（`GET /admin`、交換券発行数・使用数・提携店数・ユーザー数表示）の実装
  - [~] 9.3 ADトラック管理（`GET /admin/trucks`・`PUT /admin/trucks/<truck_id>/location`）の実装
  - [~] 9.4 QRコード生成（`POST /admin/qr/generate`）の実装（ADトラック用・出荷トラック用・提携店用）
  - [~] 9.5 提携申し込み管理（`GET /admin/partners/applications`・`PUT /admin/partners/<app_id>/approve`・`DELETE /admin/partners/<spot_id>`）の実装
  - [~] 9.6 `@admin_required`デコレーター（多要素認証済みセッション確認）の実装

- [ ] 10. Jinja2 SSRフロントエンドページの実装
  - [~] 10.1 LP（`/`、サービス総合案内・レスポンシブデザイン）テンプレートの実装
  - [~] 10.2 交換券取得ページ（`/coupon/get?spot=<spot_id>`）テンプレートの実装
  - [~] 10.3 交換券一覧ページ（`/coupon/list`、保有・履歴一覧）テンプレートの実装
  - [~] 10.4 提携店募集ページ（`/partner`、提携申し込みフォーム含む）テンプレートの実装
  - [~] 10.5 WiFi接続限定コンテンツページ（`/exclusive`）テンプレートの実装

- [ ] 11. セキュリティ・不正防止の実装
  - [~] 11.1 IPレート制限（Redisカウンター、5分以内10回超でブロック・管理者通知）の実装
  - [~] 11.2 交換券QRコードのワンタイムトークン生成（`secrets.token_urlsafe(48)`）の実装
  - [~] 11.3 HTTPS強制リダイレクト（HTTP→HTTPS）の設定
  - [~] 11.4 セキュリティ関連の単体テストの作成

- [ ] 12. LINEbotリッチメニューの設定
  - [~] 12.1 LINEbotリッチメニュー（「イベント・ニュース」「提携店検索」「交換券・履歴」）の設定・Webhook処理の実装
  - [~] 12.2 各メニュー項目の応答ロジックの実装

- [ ] 13. 提携店WiFiチェックイン統合テストの作成
  - [~] 13.1 提携店WiFi接続→キャプティブポータル→LINE認証→交換券取得フロー全体の統合テストの作成

- [ ] 14. プロパティベーステストの実装
  - [~] 14.1 Property 1: 交換券の1日1スポット制限テスト（`tests/property/test_properties.py`）の実装
  - [~] 14.2 Property 2: 交換券有効期限30日テスト（`tests/property/test_properties.py`）の実装
  - [~] 14.3 Property 3: 交換券コードのワンタイム性・使用済み再利用防止テスト（`tests/property/test_properties.py`）の実装
  - [~] 14.4 Property 4: WiFi検証なしでは交換券取得不可テスト（`tests/property/test_properties.py`）の実装
  - [~] 14.5 Property 5: ADトラック通知1日上限（最大3回）テスト（`tests/property/test_properties.py`）の実装
  - [~] 14.6 Property 6: IPレート制限の普遍的適用テスト（`tests/property/test_properties.py`）の実装
  - [~] 14.7 Property 7: セッション有効期限管理テスト（`tests/property/test_properties.py`）の実装

- [ ] 15. CI/CDおよびTerraformインフラの実装
  - [~] 15.1 GitHub Actions ワークフロー（`.github/workflows/deploy.yml`、pytest→Dockerビルド→Artifact Registryプッシュ→Cloud Runデプロイ）の作成
  - [~] 15.2 Terraformコード（`terraform/`）の作成（Cloud Run・Cloud SQL・Redis・GCS・Artifact Registry・IAM・VPC）
  - [~] 15.3 `terraform/modules/`サブモジュール（cloud_run・cloud_sql・redis・storage・iam）の実装

- [ ] 16. RaspberryPi WiFiルーター設定の実装
  - [~] 16.1 hostapd設定ファイル（SSID・WPA2-PSK/AES・チャンネル）の作成
  - [~] 16.2 dnsmasq設定ファイル（DHCPレンジ192.168.4.2〜100・DNSリダイレクト）の作成
  - [~] 16.3 nodogsplash設定ファイル（splash-onlyモード・3939SPOT専用URLへリダイレクト）の作成
  - [~] 16.4 iptables NATルール（MASQUERADE・HTTP→nodogsplashポートPREROUTING）の設定スクリプト作成
  - [~] 16.5 wpa_supplicant設定ファイル（上流WiFi SSID・認証情報・自動再接続）の作成
  - [~] 16.6 systemdユニットファイル（hostapd・dnsmasq・nodogsplash自動起動）の作成
  - [~] 16.7 識別ヘッダー（`X-RasPi-AP: 1`・`X-RasPi-Spot-ID`）付与設定の実装
  - [~] 16.8 セキュリティ設定（パスワード変更・SSH公開鍵認証のみ・不要サービス無効化）の設定手順書作成

## Notes

- タスク14（PBT）はHypothesisフレームワークを使用し、`tests/property/test_properties.py`に実装する
- 各PBTは`@given`デコレーターと`@settings(max_examples=100)`を使用し、要件番号をdocstringに記載する
- ローカル開発はDocker Compose（PostgreSQL + Redis）で完結できる構成とする
- 本番デプロイはCloud Run + Cloud SQL + Cloud Memorystoreを使用する
- RaspberryPi関連タスク（16）はセットアップスクリプト・設定ファイル・手順書として成果物を作成する
- ADトラック通知・有効期限通知はCloud Scheduler（またはcronジョブ）で定期実行する
- 全APIエンドポイントはHTTPS強制とし、TLS 1.2以上を要件とする
