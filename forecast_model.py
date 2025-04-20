import requests
import pandas as pd
import joblib
from sklearn.linear_model import LinearRegression
from datetime import datetime

API_KEY = "4c5eb1d04065dfbf4d0f4cf2aad6623f"
LAT = 41.2995
LON = 69.2401

url = f"https://api.openweathermap.org/data/3.0/onecall?lat={LAT}&lon={LON}&exclude=hourly,minutely,alerts&units=metric&appid={API_KEY}"
response = requests.get(url)
data = response.json()

days = data["daily"]
df = pd.DataFrame([{
    "day": datetime.fromtimestamp(day["dt"]).strftime("%Y-%m-%d"),
    "temp": day["temp"]["day"],
    "humidity": day["humidity"],
    "clouds": day["clouds"]
} for day in days])

X = df[["humidity", "clouds"]]
y = df["temp"]

model = LinearRegression()
model.fit(X, y)

joblib.dump(model, "forecast_model.pkl")
print("✅ Модель сохранена как forecast_model.pkl")
