import os
import json
import requests
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

# --- Reply клавиатура ---
reply_keyboard = {
    "keyboard": [
        [{"text": "📡 Статус дома"}],
        [{"text": "🌡 Установить температуру"}],
        [{"text": "🌦 Прогноз погоды"}],
        [{"text": "🔌 Вкл/Выкл систему"}]
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

# --- Генерация текста ---
def get_temp_inline_text(temp):
    return f"Укажите температуру, которую хотите установить:\n\n[ {temp // 10} ][ {temp % 10} ]°C"

def get_status():
    return "🏠 Статус дома:\nТемпература: 24.0°C\nВлажность: 40%\nГаз: 0.0%"

def get_forecast_message(days):
    return f"📅 Прогноз на {days} день(дня):\n08:00 — 21.3°C 🌥\n12:00 — 24.1°C 🌞\n18:00 — 20.2°C 🌧\n00:00 — 18.3°C ☁️\n💧 Влажность: 63%\n🏭 Качество воздуха: умеренный"

# --- Telegram отправка ---
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

# --- Обработка webhook-запросов ---
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    global current_temperature, forecast_days, system_enabled

    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text.startswith("/start"):
            send_message(chat_id, "Привет! Я умный бот для управления домом 🏠\nВыбери действие ниже:", reply_keyboard)

        elif text.startswith("/status") or text == "📡 Статус дома":
            send_message(chat_id, get_status(), reply_keyboard)

        elif text.startswith("/settemp") or text == "🌡 Установить температуру":
            send_inline_keyboard(chat_id, get_temp_inline_text(current_temperature), get_temp_buttons(current_temperature))

        elif text.startswith("/forecast") or text == "🌦 Прогноз погоды":
            send_inline_keyboard(chat_id, get_forecast_message(forecast_days), get_forecast_buttons())

        elif text.startswith("/system") or text == "🔌 Вкл/Выкл систему":
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
            send_edit(chat_id, message_id, f"✅ Температура установлена на {current_temperature}°C")
            return jsonify(ok=True)

        elif data_val == "f+":
            forecast_days = min(3, forecast_days + 1)
        elif data_val == "f-":
            forecast_days = max(1, forecast_days - 1)

        if data_val.startswith("temp"):
            send_edit_keyboard(chat_id, message_id, get_temp_inline_text(current_temperature), get_temp_buttons(current_temperature))
        elif data_val.startswith("f"):
            send_edit_keyboard(chat_id, message_id, get_forecast_message(forecast_days), get_forecast_buttons())

    return jsonify(ok=True)

# --- Проверка работоспособности ---
@app.route('/', methods=['GET'])
def index():
    return "Бот запущен и работает."

if __name__ == '__main__':
    app.run(debug=True, port=5000)
