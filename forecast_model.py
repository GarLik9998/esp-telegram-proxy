import pandas as pd
import numpy as np
import joblib
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split

# Загрузка CSV-файла (убедись, что он находится рядом)
df = pd.read_csv('weather_data.csv')

# Выбираем нужные параметры
df = df[['temp', 'humidity', 'clouds']].dropna()

# Признаки и целевая переменная
X = df[['humidity', 'clouds']]
y = df['temp']

# Разделение на обучающую и тестовую выборки
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Создание пайплайна полиномиальной регрессии степени 2
model = Pipeline([
    ('poly', PolynomialFeatures(degree=2)),
    ('linear', LinearRegression())
])

# Обучение модели
model.fit(X_train, y_train)

# Сохранение модели
joblib.dump(model, 'forecast_model.pkl')
print("✅ Модель успешно обучена и сохранена в 'forecast_model.pkl'")
