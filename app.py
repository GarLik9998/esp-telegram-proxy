import os
import json
import requests
import joblib
import numpy as np
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# --- Переменные среды ---
TOKEN = os.environ.get("TELEGRAM_API_KEY")
URL = f"https://api.telegram.org/bot{TOKEN}"

# --- Состояния ---
system_enabled = True
current_temperature = 24
TEMP_FILE = "target_temp.txt"

# --- Загрузка температуры из файла ---
if os.path.exists(TEMP_FILE):
    try:
        with open(TEMP_FILE, "r") as f:
            current_temperature = int(float(f.read().strip()))
    except:
        pass

# --- Клавиатура ---
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

# --- Telegram API ---
def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{URL}/sendMessage", json=payload)

def send_inline_keyboard(chat_id, text, buttons):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {"inline_keyboard": buttons}
    }
    requests.post(f"{URL}/sendMessage", json=payload)

def send_edit(chat_id, message_id, new_text):
    requests.post(f"{URL}/editMessageText", json={
        "chat_id": chat_id,
        "message_id": message_id,
        "text": new_text
    })

def send_edit_keyboard(chat_id, message_id, new_text, buttons):
    requests.post(f"{URL}/editMessageText", json={
        "chat_id": chat_id,
        "message_id": message_id,
        "text": new_text,
        "reply_markup": {"inline_keyboard": buttons}
    })

# --- Статус дома (ThingSpeak) ---
def get_status():
    try:
        res = requests.get("https://api.thingspeak.com/channels/2730833/feeds/last.json?api_key=28M9FBLCYTFZ2535").json()
        temp = res.get("field1", "н/д")
        hum = res.get("field2", "н/д")
        gas = res.get("field5", "н/д")
        return f"🏠 Статус дома:\n🌡 Температура: {temp}°C\n💧 Влажность: {hum}%\n🔥 Газ: {gas}%"
    except:
        return "⚠️ Не удалось получить статус"

# --- Прогноз с OpenWeather ---
def get_weather_forecast():
    try:
        API_KEY = "4c5eb1d04065dfbf4d0f4cf2aad6623f"
        LAT, LON = 41.2995, 69.2401

        current = requests.get(f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric&lang=ru").json()
        temp_now = current["main"]["temp"]
        feels_like = current["main"]["feels_like"]
        humidity = current["main"]["humidity"]
        clouds_desc = current["weather"][0]["description"]

        now_block = (
            f"📍 Сейчас в Ташкенте: {round(temp_now)}°C (ощущается как {round(feels_like)}°C)\n"
            f"💧 Влажность: {humidity}% | ☁️ Облачность: {clouds_desc}"
        )

        return now_block
    except Exception as e:
        return f"⚠️ Ошибка прогноза: {e}"

# --- ИИ-прогноз ---
def forecast_ai():
    try:
        model = joblib.load("forecast_model.pkl")
        res = requests.get("https://api.openweathermap.org/data/2.5/weather?lat=41.2995&lon=69.2401&appid=4c5eb1d04065dfbf4d0f4cf2aad6623f&units=metric").json()
        hum, cloud = res["main"]["humidity"], res["clouds"]["all"]
        pred = model.predict(np.array([[hum, cloud]]))[0]
        return f"🤖 ИИ-прогноз:\n🌡 Температура: {round(pred, 1)}°C\n💧 Влажность: {hum}%\n☁️ Облачность: {cloud}%"
    except Exception as e:
        return f"⚠️ Ошибка ИИ-прогноза: {e}"

# --- Webhook ---
@app.route('/webhook', methods=['POST'])
def webhook():
    global current_temperature, system_enabled
    try:
        data = request.get_json()
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "")
            if text.startswith("/start"):
                send_message(chat_id, "Привет! Я умный бот 🏡", reply_keyboard)
            elif text == "📡 Статус дома":
                send_message(chat_id, get_status(), reply_keyboard)
            elif text == "🌡 Установить температуру":
                send_inline_keyboard(chat_id, f"Установите температуру:\n[{current_temperature}°C]", get_temp_buttons(current_temperature))
            elif text == "🌦 Прогноз погоды":
                send_message(chat_id, get_weather_forecast(), reply_keyboard)
            elif text == "🤖 Прогноз ИИ":
                send_message(chat_id, forecast_ai(), reply_keyboard)
            elif text == "🔌 Вкл/Выкл систему":
                system_enabled = not system_enabled
                status = "включена" if system_enabled else "выключена"
                send_message(chat_id, f"Система {status}", reply_keyboard)

        elif "callback_query" in data:
            query = data["callback_query"]
            chat_id = query["message"]["chat"]["id"]
            message_id = query["message"]["message_id"]
            data_val = query["data"]

            if data_val == "temp+":
                current_temperature = min(36, current_temperature + 1)
            elif data_val == "temp-":
                current_temperature = max(16, current_temperature - 1)
            elif data_val == "temp_save":
                try:
                    with open(TEMP_FILE, "w") as f:
                        f.write(str(current_temperature))
                    send_edit(chat_id, message_id, f"✅ Температура установлена: {current_temperature}°C")
                except:
                    send_edit(chat_id, message_id, f"❌ Ошибка при сохранении температуры")
                return jsonify(ok=True)

            send_edit_keyboard(chat_id, message_id, f"Установите температуру:\n[{current_temperature}°C]", get_temp_buttons(current_temperature))

        return jsonify(ok=True)

    except Exception as e:
        print("❌ Webhook error:", e)
        return jsonify({"error": str(e)}), 500

# --- Для ESP ---
@app.route('/get_temp')
def get_temp():
    try:
        with open(TEMP_FILE) as f:
            return jsonify({"target": float(f.read().strip())})
    except:
        return jsonify({"target": 24})

@app.route('/')
def home():
    return "✅ Telegram-бот активен"

if __name__ == '__main__':
    app.run("0.0.0.0", 5000)
