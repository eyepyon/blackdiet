# GCP環境・Terraformセットアップ手順

## 前提条件

- GCPアカウントとプロジェクトが作成済みであること
- `gcloud` CLI がインストール済みであること
- `terraform` (v1.5以上) がインストール済みであること
- GitHub リポジトリが作成済みであること

---

## 手順1: gcloud の初期設定

```bash
# ログイン
gcloud auth login

# プロジェクトを設定
gcloud config set project YOUR_PROJECT_ID

# アプリケーションデフォルト認証の設定
gcloud auth application-default login
```

---

## 手順2: 必要なAPIの有効化

```bash
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com \
  vpcaccess.googleapis.com \
  servicenetworking.googleapis.com
```

---

## 手順3: Terraformの初期設定

```bash
cd terraform

# terraform.tfvars を作成
cat > terraform.tfvars << 'EOF'
project_id = "YOUR_GCP_PROJECT_ID"
region     = "asia-northeast1"
EOF
```

初期化:

```bash
terraform init
```

---

## 手順4: Terraformで全リソースを作成

まず変更内容を確認:

```bash
terraform plan
```

問題なければ適用:

```bash
terraform apply
```

`yes` と入力して確定します。

作成されるリソース:

| リソース | 説明 |
|---|---|
| `google_artifact_registry_repository` | Dockerイメージ保管庫 |
| `google_storage_bucket` | 静的アセット配信用GCSバケット |
| `google_sql_database_instance` | Cloud SQL PostgreSQL 15 |
| `google_redis_instance` | Cloud Memorystore (Redis) |
| `google_vpc_network` | VPCネットワーク |
| `google_vpc_access_connector` | Serverless VPC Access（Cloud Run→Cloud SQL/Redis接続用） |
| `google_service_account` | Cloud Run実行用サービスアカウント |
| `google_project_iam_binding` | IAMバインディング |
| `google_cloud_run_service` | Cloud Runサービス |

---

## 手順5: Cloud SQL の初期設定

Terraformでインスタンス作成後、データベースとユーザーを作成します。

```bash
# Cloud SQL への接続（Cloud SQL Auth Proxy経由）
gcloud sql connect YOUR_INSTANCE_NAME --user=postgres

# psqlで以下を実行
CREATE DATABASE spot3939;
CREATE USER spot3939_user WITH PASSWORD 'your-strong-password';
GRANT ALL PRIVILEGES ON DATABASE spot3939 TO spot3939_user;
\q
```

---

## 手順6: GitHub Secretsの設定

GitHub Actions がGCPにデプロイするために、以下のSecretをリポジトリに設定します。

Settings → Secrets and variables → Actions → New repository secret

| Secret名 | 値 | 説明 |
|---|---|---|
| `GCP_PROJECT_ID` | `your-project-id` | GCPプロジェクトID |
| `GCP_SA_KEY` | サービスアカウントキーJSON | デプロイ用SAの認証情報 |
| `GAR_LOCATION` | `asia-northeast1` | Artifact Registryのリージョン |
| `GAR_REPOSITORY` | `3939spot` | Artifact Repositoryの名前 |

### デプロイ用サービスアカウントキーの作成

```bash
# サービスアカウントを作成
gcloud iam service-accounts create github-actions-sa \
  --display-name="GitHub Actions Deploy SA"

# 必要なロールを付与
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# JSONキーを生成
gcloud iam service-accounts keys create sa-key.json \
  --iam-account="github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com"

# JSONの内容をGitHub Secretsに貼り付け
cat sa-key.json
```

> **注意**: `sa-key.json` は取扱注意。使用後は削除してください。

---

## 手順7: 本番用 .env の内容を Cloud Run 環境変数に設定

Cloud Run はコンテナ起動時に環境変数を渡せます。Terraform の `google_cloud_run_service` リソースの `env` ブロック、またはGCP Consoleで設定します。

本番で必要な環境変数:

```
FLASK_ENV=production
SECRET_KEY=本番用の強力なランダム文字列
DATABASE_URL=postgresql+pg8000://user:pass@/dbname?unix_sock=/cloudsql/PROJECT:REGION:INSTANCE/.s.PGSQL.5432
REDIS_URL=redis://REDIS_IP:6379/0
LINE_CHANNEL_ID=...
LINE_CHANNEL_SECRET=...
LINE_REDIRECT_URI=https://3939.spot/auth/line/callback
LINE_MESSAGING_CHANNEL_SECRET=...
LINE_MESSAGING_CHANNEL_ACCESS_TOKEN=...
GOOGLE_MAPS_API_KEY=...
SENDGRID_API_KEY=...
GCP_PROJECT_ID=...
GCS_BUCKET_NAME=...
```

Secret Managerを使って機密情報を管理することを推奨します。

```bash
# シークレットを作成して値を設定
echo -n "本番用SECRET_KEY" | gcloud secrets create flask-secret-key --data-file=-

# Cloud Runサービスアカウントに読み取り権限を付与
gcloud secrets add-iam-policy-binding flask-secret-key \
  --member="serviceAccount:CLOUD_RUN_SA@PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 手順8: DBマイグレーションの実行（本番）

Cloud Run Jobs または Cloud Shell経由でマイグレーションを実行します。

```bash
# Cloud Shell または gcloud run jobs
gcloud run jobs create migrate-job \
  --image "REGION-docker.pkg.dev/PROJECT_ID/3939spot/3939spot:latest" \
  --region asia-northeast1 \
  --command "flask" \
  --args "db,upgrade" \
  --set-env-vars "DATABASE_URL=..."

gcloud run jobs execute migrate-job
```

---

## コスト目安

| リソース | 目安 |
|---|---|
| Cloud Run | リクエスト数に応じた従量課金。最小インスタンス0の場合アイドル時は無料 |
| Cloud SQL (db-f1-micro) | 約$10/月〜 |
| Cloud Memorystore (1GB) | 約$35/月〜 |
| Cloud Storage | 保存容量・転送量に応じた従量課金 |
| Artifact Registry | 保存容量に応じた従量課金 |
