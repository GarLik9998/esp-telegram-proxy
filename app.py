if "message" in data:
        text = data["message"].get("text", "")
        if text.startswith("/start"):
            send_message(data["message"]["chat"]["id"], "Привет! Я умный бот для управления домом 🏠
Выбери действие ниже:", reply_keyboard)

        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        # Поддержка команд с / из BotFather
        if text.startswith("/status") or text == "📡 Статус дома":
            send_message(chat_id, get_status(), reply_keyboard)

        elif text.startswith("/settemp") or text == "🌡 Установить температуру":
            temp_text = get_temp_inline_text(current_temperature)
            send_inline_keyboard(chat_id, temp_text, get_temp_buttons(current_temperature))

        elif text.startswith("/forecast") or text == "🌦 Прогноз погоды":
            forecast = get_forecast_message(forecast_days)
            send_inline_keyboard(chat_id, forecast, get_forecast_buttons())

        elif text.startswith("/system") or text == "🔌 Вкл/Выкл систему":
            system_enabled = not system_enabled
            status = "включена" if system_enabled else "выключена"
            send_message(chat_id, f"Система {status}", reply_keyboard)

    elif "callback_query" in data:
        query = data["callback_query"]
        chat_id = query["message"]["chat"]["id"]
        message_id = query["message"]["message_id"]
        data_val = query["data"]

        if data_val.startswith("temp+"):
            current_temperature = min(36, current_temperature + 1)
        elif data_val.startswith("temp-"):
            current_temperature = max(16, current_temperature - 1)
        elif data_val == "temp_save":
            send_edit(chat_id, message_id, f"✅ Температура установлена на {current_temperature}°C")
            return "ok"

        elif data_val == "f+":
            forecast_days = min(3, forecast_days + 1)
        elif data_val == "f-":
            forecast_days = max(1, forecast_days - 1)

        # Обновление inline-сообщения
        if data_val.startswith("temp"):
            send_edit_keyboard(chat_id, message_id, get_temp_inline_text(current_temperature), get_temp_buttons(current_temperature))
        elif data_val.startswith("f"):
            send_edit_keyboard(chat_id, message_id, get_forecast_message(forecast_days), get_forecast_buttons())

    return jsonify(ok=True)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }
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

def get_temp_inline_text(temp):
    return f"Укажите температуру, которую хотите установить:\n\n[ {temp // 10} ][ {temp % 10} ]°C"

def get_temp_buttons(temp):
    return [
        [{"text": "➖", "callback_data": "temp-"}, {"text": "➕", "callback_data": "temp+"}],
        [{"text": "Сохранить", "callback_data": "temp_save"}]
    ]

def get_forecast_buttons():
    return [
        [{"text": "➖", "callback_data": "f-"}, {"text": "➕", "callback_data": "f+"}]
    ]

def get_status():
    return "🏠 Статус дома:\nТемпература: 24.0°C\nВлажность: 40%\nГаз: 0.0%"

def get_forecast_message(days):
    # Заглушка. Позже заменим реальными данными от ИИ/API.
    return f"📅 Прогноз на {days} день(дня):\n08:00 — 21.3°C 🌥\n12:00 — 24.1°C 🌞\n18:00 — 20.2°C 🌧\n00:00 — 18.3°C ☁️\n💧 Влажность: 63%\n🏭 Качество воздуха: умеренный"

if __name__ == '__main__':
    app.run(debug=True, port=5000)
