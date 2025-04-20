from flask import Flask, request
import requests
import os
import joblib
import numpy as np

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
THING_CHANNEL_ID = "2730833"
THING_READ_KEY = "28M9FBLCYTFZ2535"

MODEL_PATH = "forecast_model.pkl"
TEMP_FILE = "target_temp.txt"

# --- Команды ---
def get_status():
    url = f"https://api.thingspeak.com/channels/{THING_CHANNEL_ID}/feeds.json?api_key={THING_READ_KEY}&results=1"
    data = requests.get(url).json()
    if data["feeds"]:
        last = data["feeds"][-1]
        temp = last["field1"] or "-"
        hum = last["field2"] or "-"
        gas = last["field5"] or "-"
        return f"\ud83c\udfe0 Статус дома:\nТемпература: {temp}°C\nВлажность: {hum}%\nГаз: {gas}%"
    return "\u26a0\ufe0f Нет данных от системы."

def get_forecast_message():
    api_key = "4c5eb1d04065dfbf4d0f4cf2aad6623f"
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat=41.2995&lon=69.2401&appid={api_key}&units=metric&lang=ru"
    res = requests.get(url).json()
    if "list" in res:
        item = res["list"][1]
        temp = item["main"]["temp"]
        hum = item["main"]["humidity"]
        clouds = item["clouds"]["all"]
        desc = item["weather"][0]["description"]
        return f"\ud83c\udf27 Прогноз на ближайшие часы:\n\ud83c\udf21 Температура: {temp:.1f}°C\n\ud83d\udca7 Влажность: {hum}%\n\u2601\ufe0f Облачность: {clouds}%\n\ud83c\udf00 Описание: {desc}"
    return "\u26a0\ufe0f Не удалось получить прогноз."

def forecast_ai():
    try:
        model = joblib.load(MODEL_PATH)
        api_key = "4c5eb1d04065dfbf4d0f4cf2aad6623f"
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat=41.2995&lon=69.2401&appid={api_key}&units=metric"
        res = requests.get(url).json()
        forecast = res["list"][1]
        hum = forecast["main"]["humidity"]
        clouds = forecast["clouds"]["all"]
        pred = model.predict(np.array([[hum, clouds]]))[0]
        return f"\ud83e\udd16 ИИ-прогноз:\n\ud83c\udf21 Температура: {round(pred, 1)}°C\n\ud83d\udca7 Влажность: {hum}%\n\u2601\ufe0f Облачность: {clouds}%"
    except Exception as e:
        return f"\u26a0\ufe0f Ошибка прогноза ИИ: {e}"

def save_temperature(value):
    try:
        with open(TEMP_FILE, "w") as f:
            f.write(str(value))
        return True
    except:
        return False

# --- Telegram обработка ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.json

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text.startswith("/start"):
            send_buttons(chat_id)
        elif text.startswith("/status"):
            send_message(chat_id, get_status())
        elif text.startswith("/forecast"):
            send_message(chat_id, get_forecast_message())
        elif text.startswith("/forecast_ai"):
            send_message(chat_id, forecast_ai())
        elif text.startswith("/settemp"):
            send_temp_buttons(chat_id)
        else:
            send_message(chat_id, "\u2753 Неизвестная команда. Воспользуйтесь меню.")

    elif "callback_query" in data:
        query = data["callback_query"]
        chat_id = query["message"]["chat"]["id"]
        temp = query["data"]

        if temp.isdigit():
            if save_temperature(temp):
                send_message(chat_id, f"\u2705 Температура установлена: {temp}°C")
            else:
                send_message(chat_id, "\u26a0\ufe0f Ошибка при сохранении температуры.")

    return {"ok": True}

# --- Вспомогательные функции ---
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

def send_buttons(chat_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    keyboard = {
        "keyboard": [
            [
                {"text": "/status"}, {"text": "/forecast"}
            ],
            [
                {"text": "/forecast_ai"}, {"text": "/settemp"}
            ]
        ],
        "resize_keyboard": True
    }
    payload = {"chat_id": chat_id, "text": "Выберите действие:", "reply_markup": keyboard}
    requests.post(url, json=payload)

def send_temp_buttons(chat_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "18°C", "callback_data": "18"},
                {"text": "20°C", "callback_data": "20"},
                {"text": "22°C", "callback_data": "22"},
                {"text": "24°C", "callback_data": "24"}
            ]
        ]
    }
    payload = {"chat_id": chat_id, "text": "Выберите целевую температуру:", "reply_markup": keyboard}
    requests.post(url, json=payload)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

