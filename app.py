import os
import requests
import logging
from flask import Flask, redirect, request, jsonify, session

app = Flask(__name__)

# Render 환경 변수에서 세션 비밀키 불러오기
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback-secret-key-please-change-in-render")

logging.basicConfig(level=logging.INFO)

# Client ID, Client Secret 모두 코드에서 완전 제거 (Render 환경 변수 필수)
CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "https://discord-oauth2-7e2n.onrender.com/oauth2")

DISCORD_AUTH_URL = "https://discord.com/oauth2/authorize"
DISCORD_API_URL = "https://discord-proxy.cls110623.workers.dev"

HEADERS = {
    "User-Agent": "DiscordBot (https://discord-oauth2-7e2n.onrender.com, 1.0.0)"
}


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
            <p><b>Token Type:</b> {token.get('token_type')}</p>
            <p><b>Expires In:</b> {token.get('expires_in')}초</p>
            <p><b>Scope:</b> {token.get('scope')}</p>
            <hr>
            <a href='/logout'><button style="padding:10px 15px; cursor:pointer;">로그아웃</button></a>
        </div>
        """
    return '<a href="/login"><button style="padding:10px 15px; cursor:pointer;">🚀 디스코드로 로그인</button></a>'


@app.route('/login')
def login():
    if not CLIENT_ID:
        return jsonify({
            "error": "서버 설정 오류",
            "message": "Render 환경 변수(DISCORD_CLIENT_ID)가 설정되지 않았습니다."
        }), 500

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

    if not CLIENT_ID or not CLIENT_SECRET:
        return jsonify({
            "error": "서버 설정 오류",
            "message": "Render 환경 변수(DISCORD_CLIENT_ID 또는 DISCORD_CLIENT_SECRET)가 누락되었습니다."
        }), 500

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
        # 1. 토큰 요청
        token_response = requests.post(token_url, data=payload, headers=headers, timeout=10)
        
        if token_response.status_code != 200:
            return jsonify({
                "error": "토큰 발급 실패",
                "status_code": token_response.status_code,
                "details": token_response.text
            }), token_response.status_code
            
        token_data = token_response.json()
        access_token = token_data.get('access_token')

        # 2. 유저 정보 요청
        user_url = f"{DISCORD_API_URL}/users/@me"
        user_headers = {**HEADERS, 'Authorization': f"Bearer {access_token}"}
        user_response = requests.get(user_url, headers=user_headers, timeout=10)
        
        if user_response.status_code != 200:
            return jsonify({"error": "유저 정보 조회 실패", "details": user_response.text}), user_response.status_code

        user_data = user_response.json()

        # 3. 세션 저장
        session['user'] = user_data
        session['token'] = token_data

        return redirect('/')

    except requests.exceptions.RequestException as e:
        return f"네트워크 오류 발생: {str(e)}", 500


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
