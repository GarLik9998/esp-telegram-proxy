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

# --- Прогноз погоды с API ---
def get_weather_forecast():
    try:
        API_KEY = "4c5eb1d04065dfbf4d0f4cf2aad6623f"
        LAT = 41.2995
        LON = 69.2401

        current_url = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric&lang=ru"
        current = requests.get(current_url).json()
        temp_now = current["main"]["temp"]
        feels_like = current["main"]["feels_like"]
        humidity = current["main"]["humidity"]
        clouds_desc = current["weather"][0]["description"]

        now_block = (
            f"📍 Ташкент, сейчас: {round(temp_now)}°C (ощущается как {round(feels_like)}°C)\n"
            f"💧 Влажность: {humidity}% | ☁️ Облачность: {clouds_desc}"
        )

        forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric&lang=ru"
        res = requests.get(forecast_url).json()

        today = datetime.utcnow().date()
        tomorrow = today.replace(day=today.day + 1)

        today_points = ["09:00", "12:00", "15:00", "18:00", "21:00"]
        tomorrow_points = ["12:00", "15:00", "18:00"]

        forecast_today = []
        forecast_tomorrow = []

        for f in res["list"]:
            dt_txt = f["dt_txt"]
            date_part, time_part = dt_txt.split(" ")
            temp = round(f["main"]["temp"])
            time_short = time_part[:5]

            if date_part == str(today) and time_short in today_points:
                forecast_today.append(f"🕒 {time_short} — {temp}°C")
            elif date_part == str(tomorrow) and time_short in tomorrow_points:
                forecast_tomorrow.append(f"🕒 {time_short} — {temp}°C")

        day_block = "📅 Прогноз на сегодня:\n" + "\n".join(forecast_today)
        tomorrow_block = "📆 Прогноз на завтра:\n" + "\n".join(forecast_tomorrow)

        return f"{now_block}\n\n{day_block}\n\n{tomorrow_block}"

    except Exception as e:
        return f"⚠️ Не удалось получить данные прогноза: {e}"

# --- ИИ-прогноз ---
def forecast_ai():
    try:
        model = joblib.load("forecast_model.pkl")
        API_KEY = "4c5eb1d04065dfbf4d0f4cf2aad6623f"
        LAT, LON = 41.2995, 69.2401
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric"
        res = requests.get(url).json()
        humidity = res["main"]["humidity"]
        clouds = res["clouds"]["all"]
        temp_pred = model.predict(np.array([[humidity, clouds]]))[0]
        return f"🤖 ИИ-прогноз:\n🌡 Температура: {round(temp_pred, 1)}°C\n💧 Влажность: {humidity}%\n☁️ Облачность: {clouds}%"
    except Exception as e:
        return f"⚠️ Ошибка ИИ-прогноза: {e}"

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
