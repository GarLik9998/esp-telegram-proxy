import os
import json
import requests
import joblib
import numpy as np
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- Переменные среды ---
TOKEN = os.environ.get("TELEGRAM_API_KEY")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
URL = f"https://api.telegram.org/bot{TOKEN}"

# --- Состояния ---
system_enabled = True
current_temperature = 24
forecast_days = 1

# --- Загрузка температуры из файла ---
TEMP_FILE = "target_temp.txt"
if os.path.exists(TEMP_FILE):
    with open(TEMP_FILE, "r") as f:
        try:
            current_temperature = int(float(f.read().strip()))
        except:
            pass

# --- Reply клавиатура ---
reply_keyboard = {
    "keyboard": [
        [{"text": "📡 Статус дома"}, {"text": "🌡 Установить температуру"}],
        [{"text": "🌦 Прогноз погоды"}, {"text": "🔌 Вкл/Выкл систему"}],
        [{"text": "🤖 Прогноз ИИ"}]
    ],
    "resize_keyboard": True
}

# --- Inline клавиатуры ---
def get_temp_buttons(temp):
    return [
        [{"text": "➖", "callback_data": "temp-"}, {"text": "➕", "callback_data": "temp+"}],
        [{"text": "Сохранить", "callback_data": "temp_save"}]
    ]

def get_forecast_buttons():
    return [
        [{"text": "➖", "callback_data": "f-"}, {"text": "➕", "callback_data": "f+"}]
    ]

# --- Telegram сообщения ---
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

# --- Получение статуса с ThingSpeak ---
def get_status():
    try:
        url = "https://api.thingspeak.com/channels/2730833/feeds/last.json?api_key=28M9FBLCYTFZ2535"
        res = requests.get(url).json()
        temp = res.get("field1", "н/д")
        hum = res.get("field2", "н/д")
        gas = res.get("field5", "н/д")
        return f"🏠 Статус дома:\n🌡 Температура: {temp}°C\n💧 Влажность: {hum}%\n🔥 Газ: {gas}%"
    except:
        return "⚠️ Не удалось получить статус с ThingSpeak"

# --- ИИ прогноз через OpenWeather + model.pkl ---
def forecast_ai():
    try:
        model = joblib.load("forecast_model.pkl")
        url = "https://api.openweathermap.org/data/3.0/onecall?lat=41.2995&lon=69.2401&exclude=hourly,minutely,alerts&units=metric&appid=4c5eb1d04065dfbf4d0f4cf2aad6623f"
        res = requests.get(url).json()
        tomorrow = res["daily"][1]
        humidity = tomorrow["humidity"]
        clouds = tomorrow["clouds"]
        prediction = model.predict(np.array([[humidity, clouds]]))[0]
        prediction = round(prediction, 1)
        return f"🤖 ИИ-прогноз на завтра:\n🌡 Температура: {prediction}°C\n💧 Влажность: {humidity}%\n☁️ Облачность: {clouds}%"
    except Exception as e:
        return f"⚠️ Ошибка прогноза ИИ: {e}"

# --- Реальный прогноз с API ---
def get_weather_forecast():
    try:
        url = "https://api.openweathermap.org/data/2.5/forecast?lat=41.2995&lon=69.2401&appid=4c5eb1d04065dfbf4d0f4cf2aad6623f&units=metric&lang=ru"
        res = requests.get(url).json()
        day = res["list"][4]
        temp = day["main"]["temp"]
        hum = day["main"]["humidity"]
        clouds = day["clouds"]["all"]
        desc = day["weather"][0]["description"]
        return f"📅 Прогноз на ближайшие часы:\n🌡 Температура: {temp}°C\n💧 Влажность: {hum}%\n☁️ Облачность: {clouds}%\n🌀 Описание: {desc}"
    except:
        return "⚠️ Не удалось получить данные прогноза"

# --- Telegram webhook ---
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    global current_temperature, forecast_days, system_enabled

    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text.startswith("/start"):
            send_message(chat_id, "Привет! Я умный бот для управления отоплением 🏡", reply_keyboard)
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
            with open(TEMP_FILE, "w") as f:
                f.write(str(current_temperature))
            send_edit(chat_id, message_id, f"✅ Температура установлена: {current_temperature}°C")
            return jsonify(ok=True)

        send_edit_keyboard(chat_id, message_id, f"Установите температуру:\n[{current_temperature}°C]", get_temp_buttons(current_temperature))

    return jsonify(ok=True)

# --- Отдача температуры для ESP ---
@app.route('/get_temp', methods=['GET'])
def get_temp():
    try:
        with open(TEMP_FILE, "r") as f:
            t = float(f.read().strip())
            return jsonify({"target": t})
    except:
        return jsonify({"target": 24})

# --- Запуск сервера ---
@app.route('/')
def index():
    return "Бот умного дома запущен ✅"

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
