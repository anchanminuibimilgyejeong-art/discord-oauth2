import os
import requests
from flask import Flask, redirect, request, jsonify, session

app = Flask(__name__)
# 세션 관리를 위한 Secret Key (보안을 위해 환경 변수로 관리하거나 임의 문자열 사용)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super-secret-key-change-this")

# ==========================================
# 1. 설정 및 디스코드 OAuth2 정보
# ==========================================
CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "1549778071404412988")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "YOUR_CLIENT_SECRET_HERE")  # 본인 클라이언트 시크릿 입력
REDIRECT_URI = "https://discord-oauth2-7e2n.onrender.com/oauth2"  # Render 앱의 리다이렉트 URI

# 2. 주소 분리 (핵심 해결책!)
# - AUTH_URL: 브라우저가 직접 접속하는 동의 창 (공식 Discord URL 사용)
# - API_URL: Render 서버가 토큰/유저정보 요청을 보낼 통로 (Cloudflare Worker 프록시 사용)
DISCORD_AUTH_URL = "https://discord.com/oauth2/authorize"
DISCORD_API_URL = "https://discord-proxy.cls110623.workers.dev"

# 봇/요청 차단 방지용 User-Agent
HEADERS = {
    "User-Agent": "DiscordBot (https://discord-oauth2-7e2n.onrender.com, 1.0.0)"
}

# ==========================================
# 3. 라우트 정의
# ==========================================

@app.route('/')
def index():
    user = session.get('user')
    if user:
        return f"<h1>로그인 성공!</h1><p>안녕하세요, {user.get('username')}#{user.get('discriminator')}님!</p><a href='/logout'>로그아웃</a>"
    return '<a href="/login"><button>🚀 디스코드로 로그인</button></a>'


@app.route('/login')
def login():
    """사용자를 디스코드 공식 로그인/동의 페이지로 이동시킵니다."""
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
    """디스코드 동의 후 리다이렉트되는 콜백 백엔드 처리"""
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return f"로그인 취소 또는 오류 발생: {error}", 400
    if not code:
        return "인증 코드가 없습니다.", 400

    # ------------------------------------------
    # Step 1: Access Token 발급 요청 (Proxy 경유)
    # ------------------------------------------
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
        token_response = requests.post(token_url, data=payload, headers=headers, timeout=10)
        
        # 429 차단 및 기타 에러 예외 처리
        if token_response.status_code != 200:
            return jsonify({
                "error": "토큰 발급 실패",
                "status_code": token_response.status_code,
                "details": token_response.text
            }), token_response.status_code
            
        token_data = token_response.json()
        access_token = token_data.get('access_token')

    except requests.exceptions.RequestException as e:
        return f"토큰 요청 중 네트워크 오류 발생: {str(e)}", 500

    # ------------------------------------------
    # Step 2: 유저 정보 조회 요청 (Proxy 경유)
    # ------------------------------------------
    user_url = f"{DISCORD_API_URL}/users/@me"
    user_headers = {
        **HEADERS,
        'Authorization': f"Bearer {access_token}"
    }

    try:
        user_response = requests.get(user_url, headers=user_headers, timeout=10)
        
        if user_response.status_code != 200:
            return jsonify({
                "error": "유저 정보 조회 실패",
                "status_code": user_response.status_code,
                "details": user_response.text
            }), user_response.status_code

        user_data = user_response.json()
        session['user'] = user_data  # 세션에 저장
        
        return redirect('/')

    except requests.exceptions.RequestException as e:
        return f"유저 정보 요청 중 네트워크 오류 발생: {str(e)}", 500


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
