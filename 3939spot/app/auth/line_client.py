"""
LINE API クライアント

LINE Login API への HTTP 呼び出しをこのモジュールに集約することで、
テスト時に requests をモックしやすい構造にする。
"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

# LINE API エンドポイント
LINE_AUTHORIZE_URL = "https://access.line.me/oauth2/v2.1/authorize"
LINE_TOKEN_URL = "https://api.line.me/oauth2/v2.1/token"
LINE_PROFILE_URL = "https://api.line.me/v2/profile"


def build_authorize_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    scope: str = "profile openid",
) -> str:
    """LINE 認可エンドポイントへのリダイレクト URL を構築して返す。

    Args:
        client_id: LINE Channel ID。
        redirect_uri: コールバック URI。
        state: CSRF 防止トークン。
        scope: 要求するスコープ（デフォルト: 'profile openid'）。

    Returns:
        リダイレクト先の完全な URL 文字列。
    """
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
    }
    req = requests.Request("GET", LINE_AUTHORIZE_URL, params=params)
    prepared = req.prepare()
    return prepared.url  # type: ignore[return-value]


def fetch_access_token(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """LINE Token Endpoint からアクセストークンを取得する。

    Args:
        code: 認可コード（コールバックで受け取った `code` パラメータ）。
        client_id: LINE Channel ID。
        client_secret: LINE Channel Secret。
        redirect_uri: 認可リクエスト時に使用したリダイレクト URI。

    Returns:
        LINE Token Endpoint のレスポンス JSON 辞書。

    Raises:
        requests.HTTPError: LINE API がエラーレスポンスを返した場合。
    """
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    resp = requests.post(LINE_TOKEN_URL, data=data, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_profile(access_token: str) -> dict:
    """LINE Profile Endpoint からユーザープロフィールを取得する。

    Args:
        access_token: 取得済みのアクセストークン文字列。

    Returns:
        LINE Profile Endpoint のレスポンス JSON 辞書。
        主要フィールド: ``userId``, ``displayName``, ``pictureUrl``.

    Raises:
        requests.HTTPError: LINE API がエラーレスポンスを返した場合。
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(LINE_PROFILE_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()
