# RaspberryPi WiFiルーター セットアップ手順

提携店に設置するキャプティブポータルデバイスの構築手順です。

## 概要

```
[ユーザーのスマートフォン]
        │ WiFi接続 (3939SPOT-Guest)
        ▼
[Raspberry Pi]
  wlan0 ← アクセスポイント（ゲスト向けSSID）
  eth0  → インターネット接続（有線LAN）
        │
        ▼
 dnsmasq (DHCP/DNS) → 全DNSを自身へ転送
        │
 nodogsplash → 未認証ユーザーをポータルへリダイレクト
        │
        ▼
 https://3939.spot/portal  ← Cloud Run上のFlaskアプリ
```

---

## 必要なハードウェア

- Raspberry Pi 4 Model B（推奨）または 3B+
- microSDカード 8GB以上（Class 10推奨）
- LANケーブル（eth0でインターネット接続する場合）
- USBアダプター（必要に応じて）

---

## 手順1: OSのインストール

1. [Raspberry Pi Imager](https://www.raspberrypi.com/software/) をダウンロード・インストール
2. OSとして **Raspberry Pi OS Lite (64-bit, Bookworm)** を選択
3. 「設定を編集する」でSSH・ユーザー名・WiFi等を事前設定
4. microSDカードに書き込み

---

## 手順2: 初期パッケージインストール

SSHで接続後、以下を実行します。

```bash
sudo apt-get update && sudo apt-get upgrade -y

# アクセスポイント関連
sudo apt-get install -y hostapd dnsmasq iptables-persistent

# nodogsplash (ソースからビルド)
sudo apt-get install -y git libmicrohttpd-dev build-essential
git clone https://github.com/nodogsplash/nodogsplash.git
cd nodogsplash
make
sudo make install
cd ..
```

hostapd を初期状態では無効化しておきます:

```bash
sudo systemctl unmask hostapd
sudo systemctl stop hostapd
```

---

## 手順3: ネットワークインターフェース設定

`/etc/dhcpcd.conf` を編集して `wlan0` に固定IPを設定:

```bash
sudo tee -a /etc/dhcpcd.conf << 'EOF'

interface wlan0
    static ip_address=192.168.50.1/24
    nohook wpa_supplicant
EOF
```

---

## 手順4: 設定ファイルの配置

リポジトリの `raspi/` ディレクトリにある設定ファイルをコピーします。

```bash
# リポジトリをクローン（または設定ファイルをSCPで転送）
git clone <リポジトリURL>
cd 3939spot

# hostapd 設定
sudo cp raspi/hostapd.conf /etc/hostapd/hostapd.conf

# dnsmasq 設定
sudo cp raspi/dnsmasq.conf /etc/dnsmasq.conf

# nodogsplash 設定
sudo mkdir -p /etc/nodogsplash
sudo cp raspi/nodogsplash.conf /etc/nodogsplash/nodogsplash.conf

# systemd ユニットファイル
sudo cp raspi/systemd/*.service /etc/systemd/system/
```

---

## 手順5: Spot UUIDの設定

管理画面で取得したこのRaspberryPiのスポットUUIDを設定します。

```bash
SPOT_UUID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"  # 管理画面で確認
sudo sed -i "s/RASPI_SPOT_UUID/${SPOT_UUID}/g" /etc/nodogsplash/nodogsplash.conf
```

---

## 手順6: iptablesの設定

```bash
sudo bash raspi/iptables-setup.sh

# 設定を永続化
sudo netfilter-persistent save
```

主要なルール:
- `wlan0` からの通信を `eth0` 経由でインターネットへNAT転送
- ゲストのHTTP(80)をnodogsplashのポート(2050)へリダイレクト
- eth0側からのインバウンドはSSHのみ許可

---

## 手順7: IPv4フォワーディングの有効化

```bash
# 一時的に有効化
sudo sysctl -w net.ipv4.ip_forward=1

# 永続化
echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf
```

---

## 手順8: サービスの有効化・起動

```bash
sudo systemctl daemon-reload
sudo systemctl enable hostapd dnsmasq nodogsplash
sudo systemctl start hostapd dnsmasq nodogsplash
```

各サービスの起動確認:

```bash
sudo systemctl status hostapd
sudo systemctl status dnsmasq
sudo systemctl status nodogsplash
```

すべて `active (running)` と表示されれば成功です。

---

## 手順9: セキュリティ設定

詳細は `raspi/security-setup.md` を参照してください。必須の設定項目:

**SSHパスワード認証を無効化（鍵認証のみに）**

```bash
# 管理PCで公開鍵を生成
ssh-keygen -t ed25519 -C "3939spot-raspi"

# 公開鍵をRaspberry Piに転送
ssh-copy-id -i ~/.ssh/id_ed25519.pub pi@<RASPI_IP>
```

`/etc/ssh/sshd_config` を編集:

```
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
```

```bash
sudo systemctl restart sshd
```

**不要サービスの無効化**

```bash
sudo systemctl disable bluetooth
sudo systemctl disable avahi-daemon
```

**デフォルトパスワードの変更**

```bash
sudo passwd pi
```

---

## 動作確認

1. スマートフォンでWiFi一覧を開く
2. `3939SPOT-Guest` (hostapd.confで設定したSSID) に接続する
3. ブラウザが自動的に開き `https://3939.spot/portal` にリダイレクトされる
4. LINEログイン → 交換券取得フローが正常に動作する

---

## 主要設定ファイル対応表

| 設定ファイル | 配置先 | 役割 |
|---|---|---|
| `raspi/hostapd.conf` | `/etc/hostapd/hostapd.conf` | アクセスポイント設定 (SSID等) |
| `raspi/dnsmasq.conf` | `/etc/dnsmasq.conf` | DHCP/DNS設定 |
| `raspi/nodogsplash.conf` | `/etc/nodogsplash/nodogsplash.conf` | キャプティブポータル設定 |
| `raspi/iptables-setup.sh` | 実行するだけ | NATルール設定スクリプト |
| `raspi/systemd/*.service` | `/etc/systemd/system/` | 自動起動設定 |
| `raspi/security-setup.md` | 参照用 | セキュリティ設定手順書 |

---

## トラブルシューティング

### WiFiアクセスポイントが表示されない

```bash
sudo journalctl -u hostapd -f
```

`wlan0` が既にクライアントモードで動いていると競合します。`/etc/dhcpcd.conf` の設定を確認してください。

### IPアドレスがもらえない

```bash
sudo journalctl -u dnsmasq -f
```

`wlan0` のIPアドレス (`192.168.50.1`) が設定されているか確認:

```bash
ip addr show wlan0
```

### キャプティブポータルが出ない

```bash
sudo journalctl -u nodogsplash -f
sudo ndsctl status
```

iptablesのルールを確認:

```bash
sudo iptables -t nat -L -n -v
```

### インターネットに繋がらない

```bash
# IPv4フォワーディングの確認
sysctl net.ipv4.ip_forward  # → 1 であること

# NATルールの確認
sudo iptables -t nat -L POSTROUTING -n -v
```
