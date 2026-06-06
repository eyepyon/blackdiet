#!/bin/bash
# ============================================================
# iptables-setup.sh — 3939SPOT キャプティブポータル iptables 設定
# 16.4: iptables ルール設定スクリプト
#
# 使用方法:
#   sudo bash raspi/iptables-setup.sh
#
# ネットワーク構成:
#   eth0  : インターネット側（WAN）
#   wlan0 : ゲスト Wi-Fi 側（LAN, 192.168.50.0/24）
#   GW    : 192.168.50.1（Raspberry Pi）
# ============================================================

set -euo pipefail

IFACE_WAN="eth0"
IFACE_LAN="wlan0"
GATEWAY_IP="192.168.50.1"
SUBNET="192.168.50.0/24"
NDS_PORT="2050"   # nodogsplash ゲートウェイポート

echo "[INFO] iptables ルールを設定中..."

# ── 既存ルールをフラッシュ ────────────────────────────────────
iptables -F
iptables -t nat -F
iptables -t mangle -F
iptables -X

# ── デフォルトポリシー ────────────────────────────────────────
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# ── INPUT チェーン ────────────────────────────────────────────
# ループバック
iptables -A INPUT -i lo -j ACCEPT

# 確立済みセッション
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# SSH（管理用）
iptables -A INPUT -i "${IFACE_WAN}" -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -i "${IFACE_LAN}" -p tcp --dport 22 -j ACCEPT

# DHCP（ゲスト側）
iptables -A INPUT -i "${IFACE_LAN}" -p udp --dport 67:68 -j ACCEPT

# DNS（ゲスト側）
iptables -A INPUT -i "${IFACE_LAN}" -p udp --dport 53 -j ACCEPT
iptables -A INPUT -i "${IFACE_LAN}" -p tcp --dport 53 -j ACCEPT

# nodogsplash ゲートウェイポート
iptables -A INPUT -i "${IFACE_LAN}" -p tcp --dport "${NDS_PORT}" -j ACCEPT

# HTTP/HTTPS（キャプティブポータル検出用のリダイレクト先含む）
iptables -A INPUT -i "${IFACE_LAN}" -p tcp --dport 80  -j ACCEPT
iptables -A INPUT -i "${IFACE_LAN}" -p tcp --dport 443 -j ACCEPT

# ICMP（ping）
iptables -A INPUT -p icmp --icmp-type echo-request -j ACCEPT

# ── FORWARD チェーン ──────────────────────────────────────────
# 確立済みセッション
iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT

# ゲスト → インターネット（nodogsplash が認証済みマークを付けた通信のみ）
# nodogsplash が独自チェーンでコントロールするため、ここでは全転送を許可し
# nodogsplash 側で制御する
iptables -A FORWARD -i "${IFACE_LAN}" -o "${IFACE_WAN}" -j ACCEPT
iptables -A FORWARD -i "${IFACE_WAN}" -o "${IFACE_LAN}" -j ACCEPT

# ── NAT（マスカレード） ───────────────────────────────────────
# ゲストのプライベート IP をインターネット側でマスカレード
iptables -t nat -A POSTROUTING -o "${IFACE_WAN}" -s "${SUBNET}" -j MASQUERADE

# ── キャプティブポータル用 HTTP リダイレクト ──────────────────
# 未認証ゲストの HTTP(80) を nodogsplash ゲートウェイポートへリダイレクト
iptables -t nat -A PREROUTING -i "${IFACE_LAN}" -p tcp --dport 80 \
    -j REDIRECT --to-port "${NDS_PORT}"

# ── IP フォワーディング有効化 ─────────────────────────────────
echo 1 > /proc/sys/net/ipv4/ip_forward

# 永続化（/etc/sysctl.conf）
if ! grep -q "^net.ipv4.ip_forward=1" /etc/sysctl.conf; then
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
fi

echo "[INFO] iptables 設定完了"
echo "[INFO] ルールを確認するには: sudo iptables -L -n -v && sudo iptables -t nat -L -n -v"
echo "[INFO] 設定を永続化するには: sudo netfilter-persistent save"
