from flask import Flask, request
import requests
import os
from flask import jsonify

app = Flask(__name__)

TELEGRAM_API_KEY = os.environ.get("TELEGRAM_API_KEY")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

@app.route('/')
def home():
    return "Hello, this is the home page!"

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }
    response = requests.post(url, data=payload)
    return response.json()

@app.route('/update_data', methods=['POST'])
def update_data():
    data = request.get_json()

    temperature = data.get('temperature')
    humidity = data.get('humidity')
    gas_level = data.get('gas_level')

    message = f"🌡 Температура: {temperature}°C\n💧 Влажность: {humidity}%\n🔥 Газ: {gas_level:.2f}%"
    send_telegram_message(message)

    if gas_level > 70:
        send_telegram_message("🚨 Внимание! Обнаружена утечка газа! Проверьте систему.")

    #return "Данные получены и отправлены в Telegram!"
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
