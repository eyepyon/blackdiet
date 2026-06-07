# CI/CD・デプロイ手順

## デプロイの仕組み

`main` ブランチへのpushが自動的にデプロイをトリガーします。

```
git push origin main
      │
      ▼
GitHub Actions (.github/workflows/deploy.yml)
      │
      ├── 1. pytest実行（失敗でデプロイ中断）
      ├── 2. Docker build
      ├── 3. Artifact Registryへpush
      └── 4. Cloud Runへデプロイ
```

---

## GitHub Actions ワークフロー詳細

`.github/workflows/deploy.yml` の各ステップの説明です。

### ステップ1: テスト実行

```yaml
- name: Run tests
  run: pytest tests/
  env:
    FLASK_ENV: testing
    SECRET_KEY: ci-secret-key-for-testing
```

テストが1件でも失敗すると後続のデプロイステップは実行されません。

### ステップ2: GCP認証

```yaml
- name: Authenticate to Google Cloud
  uses: google-github-actions/auth@v2
  with:
    credentials_json: ${{ secrets.GCP_SA_KEY }}
```

GitHub Secretsに設定したサービスアカウントキーを使ってGCPに認証します。

### ステップ3: Dockerビルド・プッシュ

コミットのSHA (`github.sha`) をタグとして使用し、どのコミットからビルドされたイメージかを追跡できます。

```
asia-northeast1-docker.pkg.dev/PROJECT/3939spot/3939spot:abc1234
asia-northeast1-docker.pkg.dev/PROJECT/3939spot/3939spot:latest
```

### ステップ4: Cloud Runデプロイ

```bash
gcloud run deploy 3939spot \
  --image "IMAGE:SHA" \
  --region asia-northeast1 \
  --platform managed \
  --max-instances 1 \
  --allow-unauthenticated
```

`--allow-unauthenticated` はパブリックアクセスを許可する設定です（Webサービスなので必要）。

---

## 手動デプロイ（緊急時）

GitHub Actionsを使わずに手動でデプロイする手順です。

```bash
# GCPに認証
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Dockerビルド
docker build -t asia-northeast1-docker.pkg.dev/YOUR_PROJECT/3939spot/3939spot:manual .

# Artifact Registryにpush
gcloud auth configure-docker asia-northeast1-docker.pkg.dev
docker push asia-northeast1-docker.pkg.dev/YOUR_PROJECT/3939spot/3939spot:manual

# Cloud Runにデプロイ
gcloud run deploy 3939spot \
  --image "asia-northeast1-docker.pkg.dev/YOUR_PROJECT/3939spot/3939spot:manual" \
  --region asia-northeast1 \
  --platform managed \
  --allow-unauthenticated
```

---

## ロールバック

直前のバージョンに戻す場合:

```bash
# リビジョン一覧を確認
gcloud run revisions list --service 3939spot --region asia-northeast1

# 特定リビジョンにトラフィックを向ける
gcloud run services update-traffic 3939spot \
  --to-revisions 3939spot-00010-abc=100 \
  --region asia-northeast1
```

---

## デプロイ状況の確認

```bash
# Cloud Runサービスの状態確認
gcloud run services describe 3939spot --region asia-northeast1

# ログの確認
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=3939spot" \
  --limit 50 \
  --format "table(timestamp,textPayload)"
```

GCP Console → Cloud Run → 3939spot → ログ からも確認できます。

---

## デプロイ前チェックリスト

| 確認項目 | コマンド |
|---|---|
| テストが全件パス | `pytest` |
| .envに機密情報が入っていない | `git status` で .env が変更ファイルにないことを確認 |
| mainブランチに最新変更がマージ済み | `git log origin/main` |
| Cloud Runの環境変数が本番用に設定済み | GCP Console → Cloud Run → 環境変数 |
| DBマイグレーションが適用済み | `flask db current` |
