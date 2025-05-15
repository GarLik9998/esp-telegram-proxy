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

# --- Эндпоинт для платы ESP: возвращает целевую температуру и статус включения ---
@app.route("/get_temp")
def get_temp():
    return jsonify({
        "target": system_state["desired_temperature"],
        "enabled": system_state["enabled"]
    })

# --- Функции ---
@app.route("/update", methods=["POST"])
def update():
    data = request.json
    system_state["current_temperature"] = data.get("temperature")
    system_state["gas_level"] = data.get("gas")
    return "OK"

@app.route("/enable", methods=["POST"])
def enable():
    system_state["enabled"] = True
    system_state["valve_position"] = "closed"
    send_telegram("✅ Система включена. Клапан закрыт.")
    return "System enabled"

@app.route("/disable", methods=["POST"])
def disable():
    system_state["enabled"] = False
    system_state["valve_position"] = "closed"
    send_telegram("⚠️ Система отключена. Клапан закрыт. Газ продолжает проверяться.")
    return "System disabled"

@app.route("/control_valve", methods=["POST"])
def control_valve():
    if not system_state["enabled"]:
        return "System is disabled"
    current = system_state.get("current_temperature")
    desired = system_state.get("desired_temperature")
    if current is None:
        return "No temperature data"
    if current < desired:
        system_state["valve_position"] = "open"
    elif current > desired:
        system_state["valve_position"] = "closed"
    else:
        system_state["valve_position"] = "half"
    return f"Valve set to {system_state['valve_position']}"

@app.route("/error", methods=["POST"])
def report_error():
    data = request.json
    error_type = data.get("type")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    system_state["errors"].append({"type": error_type, "time": timestamp})

    if error_type == "temperature_sensor_fail":
        system_state["valve_position"] = "half"
        send_telegram("⚠️ Ошибка: датчик температуры. Клапан полуоткрыт.")
    elif error_type == "gas_sensor_fail":
        system_state["valve_position"] = "closed"
        system_state["enabled"] = False
        send_telegram("🚨 Ошибка: датчик газа. Клапан закрыт, система отключена.")
    elif error_type == "motor_fail":
        send_telegram("⚠️ Неисправность мотора клапана.")
    elif error_type == "overheat":
        system_state["valve_position"] = "closed"
        system_state["enabled"] = False
        send_telegram("🔥 Перегрев. Клапан закрыт, ожидание охлаждения.")
    elif error_type == "voltage_spike":
        system_state["valve_position"] = "closed"
        system_state["enabled"] = False
        send_telegram("⚡ Скачки напряжения. Клапан закрыт, система на паузе.")
    return "Error processed"

def get_forecast_text(day):
    try:
        from datetime import datetime

        API_KEY = "4c5eb1d04065dfbf4d0f4cf2aad6623f"
        lat, lon = 41.2995, 69.2401

        # Получаем текущую погоду
        current = requests.get(
            f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=ru"
        ).json()
        now_temp = current["main"]["temp"]
        now_hum = current["main"]["humidity"]
        now_desc = current["weather"][0]["description"]

        # Получаем прогноз на 5 дней
        forecast = requests.get(
            f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&cnt=40&lang=ru"
        ).json()

        # Сдвигаем на нужный день
        start = day * 8
        all_items = forecast["list"][start:start + 8]

        # Отфильтровываем блоки только на 09:00, 12:00, 15:00, 18:00
        wanted_times = ['09:00:00', '12:00:00', '15:00:00', '18:00:00']
        filtered = [item for item in all_items if item['dt_txt'].split(' ')[1] in wanted_times]

        # Сортируем по времени (datetime.time)
        items = sorted(filtered, key=lambda x: datetime.strptime(x['dt_txt'], "%Y-%m-%d %H:%M:%S").time())

        if not items:
            return "⚠️ Нет данных на выбранную дату."

        # Заголовок
        date_str = items[0]['dt_txt'].split(' ')[0]
        lines = [f"📅 Дата: {date_str}"]

        # Добавляем строку "сейчас"
        lines.append(f"🕒сейчас | 🌡 {now_temp}°C |💧 {now_hum}% | ☁️ {now_desc}")

        # Добавляем прогноз по часам
        for item in items:
            time_part = item['dt_txt'].split(' ')[1]
            temp = item['main']['temp']
            hum = item['main']['humidity']
            desc = item['weather'][0]['description']
            lines.append(f"🕒{time_part} | 🌡 {temp}°C |💧 {hum}% | ☁️ {desc}")

        return '\n'.join(lines)

    except Exception as e:
        return f"⚠️ Ошибка прогноза: {e}"

# --- Webhook ---
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    chat_id = data["message"]["chat"]["id"] if "message" in data else data["callback_query"]["message"]["chat"]["id"]
    if "message" in data:
        text = data["message"].get("text", "")
        if text == "📡 Статус дома":
            try:
                res = requests.get("https://api.thingspeak.com/channels/2730833/feeds/last.json?api_key=28M9FBLCYTFZ2535").json()
                msg = f"🏠 Статус дома:\n🌡 Температура: {res.get('field1')}°C\n💧 Влажность: {res.get('field2')}%\n🔥 Газ: {res.get('field5')}%"
            except:
                msg = "⚠️ Не удалось получить статус"
            send_telegram(msg)
        elif text == "🌡 Установить температуру":
            requests.post(f"{URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": f"Установите температуру:\n[{system_state['desired_temperature']}°C]",
                "reply_markup": get_temp_buttons(system_state['desired_temperature'])
            })
        elif text == "🔌 Вкл/Выкл систему":
            system_state["enabled"] = not system_state["enabled"]
            status = "включена" if system_state["enabled"] else "отключена"
            send_telegram(f"Система {status}.")
        elif text == "🌦 Прогноз погоды":
            system_state["forecast_day"] = 0
            forecast_text = get_forecast_text(0)
            requests.post(f"{URL}/sendMessage", json={"chat_id": chat_id, "text": forecast_text, "reply_markup": get_forecast_buttons()})
        elif text == "🤖 Прогноз ИИ":
            try:
                model = joblib.load("forecast_model.pkl")
                res = requests.get("https://api.openweathermap.org/data/2.5/weather?lat=41.2995&lon=69.2401&appid=4c5eb1d04065dfbf4d0f4cf2aad6623f&units=metric").json()
                hum, cloud = res["main"]["humidity"], res["clouds"]["all"]
                pred = model.predict(np.array([[hum, cloud]]))[0]
                send_telegram(f"🤖 ИИ-прогноз:\n🌡 Темп: {round(pred, 1)}°C\n💧 Влажность: {hum}%\n☁️ Облачность: {cloud}%")
            except:
                send_telegram("⚠️ Ошибка ИИ-прогноза.")

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
