from flask import Flask, request, jsonify
import os
import json
import requests
import time
import joblib
import numpy as np

app = Flask(__name__)

# --- Telegram API ---
TOKEN = os.environ.get("TELEGRAM_API_KEY")
URL = f"https://api.telegram.org/bot{TOKEN}"
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

reply_keyboard = {
    "keyboard": [
        [{"text": "📡 Статус дома"}, {"text": "🌡 Установить температуру"}],
        [{"text": "🌦 Прогноз погоды"}, {"text": "🔌 Вкл/Выкл систему"}],
        [{"text": "🤖 Прогноз ИИ"}]
    ],
    "resize_keyboard": True
}

def send_telegram(text):
    if TOKEN and CHAT_ID:
        requests.post(f"{URL}/sendMessage", json={"chat_id": CHAT_ID, "text": text, "reply_markup": json.dumps(reply_keyboard)})

# --- Инлайн клавиатура для температуры ---
def get_temp_buttons(temp):
    return {
        "inline_keyboard": [
            [{"text": "➖", "callback_data": "temp-"}, {"text": "➕", "callback_data": "temp+"}],
            [{"text": "Сохранить", "callback_data": "temp_save"}]
        ]
    }

# --- Инлайн клавиатура для прогноза ---
def get_forecast_buttons():
    return {
        "inline_keyboard": [[
            {"text": "◀️", "callback_data": "forecast-"},
            {"text": "▶️", "callback_data": "forecast+"}
        ]]
    }

# --- Состояние системы ---
system_state = {
    "valve_position": "closed",
    "enabled": True,
    "desired_temperature": 24,
    "current_temperature": None,
    "gas_level": None,
    "errors": [],
    "forecast_day": 0
}

# --- Функция получения прогноза погоды ---
def get_forecast_text(day):
    try:
        API_KEY = "4c5eb1d04065dfbf4d0f4cf2aad6623f"
        lat, lon = 41.2995, 69.2401
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&cnt=40&lang=ru"
        res = requests.get(url).json()
        index = min(day * 8 + 4, len(res["list"]) - 1)
        forecast = res["list"][index]
        return f"📅 День {day}: {forecast['dt_txt']}\n🌡 {forecast['main']['temp']}°C\n💧 {forecast['main']['humidity']}%\n☁️ {forecast['weather'][0]['description']}"
    except:
        return "⚠️ Ошибка прогноза."

# --- Остальной код (без изменений, кроме webhook callback_query) ---

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    chat_id = data["message"]["chat"]["id"] if "message" in data else data["callback_query"]["message"]["chat"]["id"]
    if "message" in data:
        text = data["message"].get("text", "")
        if text == "🌦 Прогноз погоды":
            system_state["forecast_day"] = 0
            forecast_text = get_forecast_text(0)
            requests.post(f"{URL}/sendMessage", json={"chat_id": chat_id, "text": forecast_text, "reply_markup": get_forecast_buttons()})
        # остальной блок text == ... оставляем без изменений

    elif "callback_query" in data:
        msg = data["callback_query"]["message"]
        message_id = msg["message_id"]
        data_val = data["callback_query"]["data"]
        chat_id = msg["chat"]["id"]

        if data_val == "temp+":
            system_state["desired_temperature"] = min(36, system_state["desired_temperature"] + 1)
            requests.post(f"{URL}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": f"Установите температуру:\n[{system_state['desired_temperature']}°C]",
                "reply_markup": get_temp_buttons(system_state['desired_temperature'])
            })
        elif data_val == "temp-":
            system_state["desired_temperature"] = max(16, system_state["desired_temperature"] - 1)
            requests.post(f"{URL}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": f"Установите температуру:\n[{system_state['desired_temperature']}°C]",
                "reply_markup": get_temp_buttons(system_state['desired_temperature'])
            })
        elif data_val == "temp_save":
            send_telegram(f"✅ Температура установлена: {system_state['desired_temperature']}°C")
            return jsonify(ok=True)
        elif data_val == "forecast+":
            system_state["forecast_day"] = min(system_state["forecast_day"] + 1, 4)
            forecast_text = get_forecast_text(system_state["forecast_day"])
            requests.post(f"{URL}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": forecast_text,
                "reply_markup": get_forecast_buttons()
            })
        elif data_val == "forecast-":
            system_state["forecast_day"] = max(system_state["forecast_day"] - 1, 0)
            forecast_text = get_forecast_text(system_state["forecast_day"])
            requests.post(f"{URL}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": forecast_text,
                "reply_markup": get_forecast_buttons()
            })

    return jsonify(ok=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
