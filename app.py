import os, json, requests, joblib, numpy as np
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)
TOKEN = os.environ.get("TELEGRAM_API_KEY")
URL = f"https://api.telegram.org/bot{TOKEN}"
TEMP_FILE = "target_temp.txt"
current_temperature = 24

# Загрузка температуры при запуске
if os.path.exists(TEMP_FILE):
    try:
        with open(TEMP_FILE) as f:
            current_temperature = int(float(f.read().strip()))
    except: pass

# Клавиатуры
reply_keyboard = {
    "keyboard": [
        [{"text": "📡 Статус дома"}, {"text": "🌡 Установить температуру"}],
        [{"text": "🌦 Прогноз погоды"}, {"text": "🔌 Вкл/Выкл систему"}],
        [{"text": "🤖 Прогноз ИИ"}]
    ],
    "resize_keyboard": True
}
def get_temp_buttons(temp):
    return [
        [{"text": "➖", "callback_data": "temp-"}, {"text": "➕", "callback_data": "temp+"}],
        [{"text": "Сохранить", "callback_data": "temp_save"}]
    ]

# Telegram API
def send_message(cid, text, kb=None):
    payload = {"chat_id": cid, "text": text}
    if kb: payload["reply_markup"] = json.dumps(kb)
    requests.post(f"{URL}/sendMessage", json=payload)

def send_edit(cid, mid, text):  # для подтверждения сохранения
    requests.post(f"{URL}/editMessageText", json={"chat_id": cid, "message_id": mid, "text": text})

def send_edit_keyboard(cid, mid, text, btns):
    requests.post(f"{URL}/editMessageText", json={
        "chat_id": cid, "message_id": mid, "text": text,
        "reply_markup": {"inline_keyboard": btns}
    })

# Прогноз от модели
def forecast_ai():
    try:
        model = joblib.load("forecast_model.pkl")
        res = requests.get("https://api.openweathermap.org/data/2.5/weather?lat=41.2995&lon=69.2401&appid=4c5eb1d04065dfbf4d0f4cf2aad6623f&units=metric").json()
        hum, cloud = res["main"]["humidity"], res["clouds"]["all"]
        pred = model.predict(np.array([[hum, cloud]]))[0]
        return f"🤖 ИИ-прогноз:\n🌡 {round(pred,1)}°C\n💧 Влажность: {hum}%\n☁️ Облачность: {cloud}%"
    except Exception as e:
        return f"⚠️ Ошибка ИИ-прогноза: {e}"

# Webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    global current_temperature
    try:
        d = request.get_json()
        if "message" in d:
            cid = d["message"]["chat"]["id"]
            txt = d["message"].get("text", "")
        
            if txt.startswith("/start"):
                send_message(cid, "Привет! Я умный бот 🏡", reply_keyboard)
        
            elif txt == "📡 Статус дома":
                send_message(cid, get_status(), reply_keyboard)
        
            elif txt == "🌡 Установить температуру":
                send_inline_keyboard(cid, f"Установите температуру:\n[{current_temperature}°C]", get_temp_buttons(current_temperature))
        
            elif txt == "🌦 Прогноз погоды":
                send_message(cid, get_weather_forecast(), reply_keyboard)
        
            elif txt == "🔌 Вкл/Выкл систему":
                system_enabled = not system_enabled
                status = "включена" if system_enabled else "выключена"
                send_message(cid, f"Система {status}", reply_keyboard)
        
            elif txt == "🤖 Прогноз ИИ":
                send_message(cid, forecast_ai(), reply_keyboard)
        
            else:
                send_message(cid, "Команда не распознана.", reply_keyboard)


        elif "callback_query" in d:
            cid = d["callback_query"]["message"]["chat"]["id"]
            mid = d["callback_query"]["message"]["message_id"]
            val = d["callback_query"]["data"]

            if val == "temp+":
                current_temperature = min(36, current_temperature + 1)
                send_edit_keyboard(cid, mid, f"Установите температуру:\n[{current_temperature}°C]", get_temp_buttons(current_temperature))

            elif val == "temp-":
                current_temperature = max(16, current_temperature - 1)
                send_edit_keyboard(cid, mid, f"Установите температуру:\n[{current_temperature}°C]", get_temp_buttons(current_temperature))

            elif val == "temp_save":
                try:
                    with open(TEMP_FILE, "w") as f: f.write(str(current_temperature))
                    send_edit(cid, mid, f"✅ Температура установлена: {current_temperature}°C")
                except Exception as e:
                    send_edit(cid, mid, f"❌ Ошибка сохранения: {e}")

        return jsonify(ok=True)
    except Exception as e:
        print("❌ Webhook error:", e)
        return jsonify({"error": str(e)}), 500

# Для ESP
@app.route('/get_temp')
def get_temp():
    try:
        with open(TEMP_FILE) as f:
            return jsonify({"target": float(f.read().strip())})
    except:
        return jsonify({"target": 24})

@app.route('/')
def home(): return "✅ Telegram-бэкэнд запущен"

if __name__ == '__main__':
    app.run("0.0.0.0", 5000)
