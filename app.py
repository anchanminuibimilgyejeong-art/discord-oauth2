import os
import requests
import logging
from flask import Flask, redirect, request, jsonify, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super-secret-key-change-this")

# 로그 출력 설정
logging.basicConfig(level=logging.INFO)

CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "1549778071404412988")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "YOUR_CLIENT_SECRET_HERE")
REDIRECT_URI = "https://discord-oauth2-7e2n.onrender.com/oauth2"

DISCORD_AUTH_URL = "https://discord.com/oauth2/authorize"
DISCORD_API_URL = "https://discord-proxy.cls110623.workers.dev"

HEADERS = {
    "User-Agent": "DiscordBot (https://discord-oauth2-7e2n.onrender.com, 1.0.0)"
}


@app.route('/')
def index():
    user = session.get('user')
    if user:
        return f"<h1>로그인 성공!</h1><p>안녕하세요, {user.get('username')}님!</p><a href='/logout'>로그아웃</a>"
    return '<a href="/login"><button>🚀 디스코드로 로그인</button></a>'


@app.route('/login')
def login():
    discord_login_url = (
        f"{DISCORD_AUTH_URL}"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20email"
    )
    print(f"\n[DEBUG] 로그인 요청 시도 - CLIENT_ID: {CLIENT_ID}")
    return redirect(discord_login_url)


@app.route('/oauth2')
def oauth2_callback():
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        print(f"[DEBUG ERROR] 디스코드 인증 취소/오류: {error}")
        return f"로그인 취소 또는 오류 발생: {error}", 400
    if not code:
        print("[DEBUG ERROR] Auth Code가 전달되지 않음")
        return "인증 코드가 없습니다.", 400

    token_url = f"{DISCORD_API_URL}/oauth2/token"
    
    # 시크릿 키 문자열 검증용 디버그
    masked_secret = f"{CLIENT_SECRET[:4]}***{CLIENT_SECRET[-4:]}" if len(CLIENT_SECRET) > 8 else "TOO_SHORT_OR_EMPTY"
    
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

    # 디버그 로그 출력
    print("\n========= [DEBUG: OAUTH2 TOKEN REQUEST] =========")
    print(f"1. Target URL      : {token_url}")
    print(f"2. Client ID       : {CLIENT_ID}")
    print(f"3. Client Secret   : {masked_secret} (Length: {len(CLIENT_SECRET)})")
    print(f"4. Redirect URI    : {REDIRECT_URI}")
    print(f"5. Auth Code       : {code[:10]}...")
    print("=================================================\n")

    try:
        token_response = requests.post(token_url, data=payload, headers=headers, timeout=10)
        
        print("\n========= [DEBUG: DISCORD RESPONSE] =========")
        print(f"1. Status Code : {token_response.status_code}")
        print(f"2. Response Body: {token_response.text}")
        print("=============================================\n")

        if token_response.status_code != 200:
            return jsonify({
                "debug_info": {
                    "client_id_used": CLIENT_ID,
                    "secret_length": len(CLIENT_SECRET),
                    "redirect_uri_used": REDIRECT_URI,
                },
                "discord_error_raw": token_response.text,
                "status_code": token_response.status_code
            }), token_response.status_code
            
        token_data = token_response.json()
        access_token = token_data.get('access_token')

    except requests.exceptions.RequestException as e:
        print(f"[DEBUG EXCEPTION] Request Exception: {str(e)}")
        return f"토큰 요청 중 네트워크 오류 발생: {str(e)}", 500

    # 유저 정보 요청
    user_url = f"{DISCORD_API_URL}/users/@me"
    user_headers = {**HEADERS, 'Authorization': f"Bearer {access_token}"}

    try:
        user_response = requests.get(user_url, headers=user_headers, timeout=10)
        print(f"[DEBUG] /users/@me Status Code: {user_response.status_code}")
        
        if user_response.status_code != 200:
            return jsonify({"error": "유저 정보 조회 실패", "details": user_response.text}), user_response.status_code

        user_data = user_response.json()
        session['user'] = user_data
        return redirect('/')

    except requests.exceptions.RequestException as e:
        return f"유저 정보 요청 중 네트워크 오류 발생: {str(e)}", 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
