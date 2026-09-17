import os
import requests
import logging
from flask import Flask, redirect, request, jsonify, session

# ==========================================
# 1. 모든 방법으로 환경 변수 불러오기 (Multi-Strategy Loader)
# ==========================================

# [방법 1] python-dotenv 시도 (.env 파일이 있으면 우선 로드, 패키지 없어도 튕기지 않음)
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[ENV LOADER] .env 파일 감지 및 로드 완료")
except ImportError:
    print("[ENV LOADER] python-dotenv 모듈 없음 - 시스템 환경 변수로 진행")

def fetch_env(key_name, fallback_value=None):
    """
    모든 조회 방식을 순차적으로 시도하여 값을 찾아내는 감지 함수
    """
    # [방법 2] os.getenv() 시도
    val = os.getenv(key_name)
    if val:
        return val.strip()

    # [방법 3] os.environ 딕셔너리 직접 조회 시도
    val = os.environ.get(key_name)
    if val:
        return val.strip()

    # [방법 4] 대소문자 실수를 대비한 소문자 키 조회 시도 (e.g., discord_client_id)
    val = os.getenv(key_name.lower()) or os.environ.get(key_name.lower())
    if val:
        return val.strip()

    # [방법 5] 최후의 보루: 하드코딩된 백업값(fallback) 반환
    return fallback_value


# ==========================================
# 2. 설정값 만능 조회 적용
# ==========================================
app = Flask(__name__)
app.secret_key = fetch_env("FLASK_SECRET_KEY", "super-secret-key-fallback")

CLIENT_ID = fetch_env("DISCORD_CLIENT_ID", "1549778071404412988")
CLIENT_SECRET = fetch_env("DISCORD_CLIENT_SECRET", "5ahJy_7rUWhUOig9LTNd1tr-V8Oq_CWl")
REDIRECT_URI = fetch_env("DISCORD_REDIRECT_URI", "https://discord-oauth2-7e2n.onrender.com/oauth2")

DISCORD_AUTH_URL = "https://discord.com/oauth2/authorize"
DISCORD_API_URL = "https://discord-proxy.cls110623.workers.dev"

HEADERS = {
    "User-Agent": "DiscordBot (https://discord-oauth2-7e2n.onrender.com, 1.0.0)"
}

logging.basicConfig(level=logging.INFO)

# ==========================================
# 3. 라우트 정의
# ==========================================

@app.route('/')
def index():
    user = session.get('user')
    token = session.get('token')

    if user and token:
        access_token = token.get('access_token', '')
        masked_token = f"{access_token[:6]}...{access_token[-6:]}" if len(access_token) > 12 else "***"

        return f"""
        <div style="font-family: sans-serif; padding: 20px;">
            <h1>🎉 로그인 성공!</h1>
            <p><b>사용자:</b> {user.get('username')}#{user.get('discriminator', '0000')}</p>
            <p><b>이메일:</b> {user.get('email', '정보 없음')}</p>
            <hr>
            <h3>🔑 토큰 정보 (보안 마스킹)</h3>
            <p><b>Access Token:</b> <code style="background:#eee; padding:2px 6px;">{masked_token}</code></p>
            <p><b>Expires In:</b> {token.get('expires_in')}초</p>
            <hr>
            <a href='/logout'><button style="padding:10px 15px; cursor:pointer;">로그아웃</button></a>
        </div>
        """
    return '<a href="/login"><button style="padding:10px 15px; cursor:pointer;">🚀 디스코드로 로그인</button></a>'


@app.route('/login')
def login():
    if not CLIENT_ID:
        return jsonify({"error": "CLIENT_ID를 탐색하지 못했습니다."}), 500

    discord_login_url = (
        f"{DISCORD_AUTH_URL}"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20email"
    )
    return redirect(discord_login_url)


@app.route('/oauth2')
def oauth2_callback():
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return f"로그인 취소 또는 오류 발생: {error}", 400
    if not code:
        return "인증 코드가 없습니다.", 400

    token_url = f"{DISCORD_API_URL}/oauth2/token"
    
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    headers = {
        **HEADERS,
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        # 토큰 요청
        token_response = requests.post(token_url, data=payload, headers=headers, timeout=10)
        
        if token_response.status_code != 200:
            return jsonify({
                "error": "토큰 발급 실패",
                "status_code": token_response.status_code,
                "details": token_response.text
            }), token_response.status_code
            
        token_data = token_response.json()
        access_token = token_data.get('access_token')

        # 유저 정보 요청
        user_url = f"{DISCORD_API_URL}/users/@me"
        user_headers = {**HEADERS, 'Authorization': f"Bearer {access_token}"}
        user_response = requests.get(user_url, headers=user_headers, timeout=10)
        
        if user_response.status_code != 200:
            return jsonify({"error": "유저 정보 조회 실패", "details": user_response.text}), user_response.status_code

        # 세션 저장
        session['user'] = user_response.json()
        session['token'] = token_data

        return redirect('/')

    except requests.exceptions.RequestException as e:
        return f"네트워크 오류 발생: {str(e)}", 500


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


if __name__ == '__main__':
    port = int(fetch_env("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
