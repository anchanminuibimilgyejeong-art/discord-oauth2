import os
import requests
import threading
from flask import Flask, jsonify

app = Flask(__name__)

# Render Environment 탭의 DISCORD_WEBHOOK_URL을 읽어옵니다.
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "여기에_새로_생성한_웹후크_주소_입력")


def send_startup_webhook():
    """서버 실행 직후 즉시 1회 웹후크 전송"""
    if not WEBHOOK_URL or "여기에" in WEBHOOK_URL:
        print("[WEBHOOK ERROR] 올바른 DISCORD_WEBHOOK_URL을 설정해주세요.")
        return

    payload = {
        "content": "🚀 Render 서버 켜짐! 웹후크 정상 작동 중입니다."
    }
    
    try:
        res = requests.post(WEBHOOK_URL, json=payload, timeout=5)
        print(f"[WEBHOOK RESULT] Status: {res.status_code}, Response: {res.text}")
    except Exception as e:
        print(f"[WEBHOOK ERROR] {e}")


# 서버가 켜질 때 백그라운드에서 즉시 웹후크 전송 실행
threading.Thread(target=send_startup_webhook, daemon=True).start()


@app.route('/')
def index():
    return "<h2>✅ Render 서버가 정상 가동 중입니다.</h2><p>디스코드 채널로 메시지가 전송되었는지 확인하세요.</p>"


@app.route('/test')
def manual_test():
    """브라우저 접속으로 수동 테스트할 수 있는 경로"""
    try:
        res = requests.post(WEBHOOK_URL, json={"content": "🔔 /test 접속으로 보낸 수동 테스트 메시지!"}, timeout=5)
        return jsonify({"status_code": res.status_code, "response": res.text or "SUCCESS"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
