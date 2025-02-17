import yfinance as yf
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, request, redirect, url_for, jsonify
import hashlib
import hmac
import requests

# Настройки Telegram API
TOKEN = "8068526221:AAF2pw4c00-tWobTC-GJ6TtSE_sLLRKt8_U"
CHANNEL_ID = "@Trade_Channel"  # Замените на ваш канал

# Создаём Flask сервер
server = Flask(__name__)

# Создаём Dash-приложение
app = dash.Dash(__name__, suppress_callback_exceptions=True, server=server, routes_pathname_prefix='/dashboard/')


# Функция для проверки подписи Telegram
def check_telegram_auth(auth_data):
    """ Проверка подписи Telegram """
    check_string = "\n".join([f"{k}={v}" for k, v in sorted(auth_data.items()) if k != "hash"])
    secret_key = hmac.new(TOKEN.encode(), digestmod=hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return expected_hash == auth_data["hash"]


# Функция проверки членства в Telegram-канале
def is_member(user_id):
    """ Проверяет, состоит ли пользователь в канале """
    url = f"https://api.telegram.org/bot{TOKEN}/getChatMember"
    response = requests.get(url, params={"chat_id": CHANNEL_ID, "user_id": user_id}).json()
    return response.get("ok") and response.get("result", {}).get("status") in ["member", "administrator", "creator"]


# Маршрут для авторизации через Telegram
@server.route("/verify")
def verify():
    auth_data = request.args.to_dict()

    if not auth_data or "id" not in auth_data:
        return "Ошибка: Telegram не передал данные!", 400

    if not check_telegram_auth(auth_data):
        return "Ошибка авторизации Telegram", 403

    user_id = int(auth_data.get("id", 0))

    if not is_member(user_id):
        return "Доступ запрещён: вы не подписаны на канал!", 403

    # Генерируем временный токен доступа
    token = hashlib.sha256(f"{user_id}{TOKEN}".encode()).hexdigest()
    return redirect(f"/dashboard?token={token}&user_id={user_id}")


# Маршрут для проверки доступа
@server.route("/check_access")
def check_access():
    user_id = request.args.get("user_id")
    token = request.args.get("token")

    if not user_id or not token:
        return jsonify({"status": "error", "message": "Нет токена"}), 403

    if not is_member(user_id):
        return jsonify({"status": "error", "message": "Вы больше не в канале"}), 403

    return jsonify({"status": "ok", "message": "Доступ разрешён"}), 200


# Лейаут Dash-приложения
app.layout = html.Div([
    html.H1("Max Power Dashboard", style={'textAlign': 'center'}),

    html.Div([
        html.Label("Введите тикер актива:"),
        dcc.Input(id='ticker-input', type='text', value='SPX', className='dash-input'),
    ], className='dash-container'),

    dcc.Graph(id='options-chart', style={'height': '900px'}, config={'displayModeBar': False}),

    html.Script("""
        function checkAccess() {
            let urlParams = new URLSearchParams(window.location.search);
            let user_id = urlParams.get('user_id');
            let token = urlParams.get('token');

            fetch(`/check_access?user_id=${user_id}&token=${token}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status !== "ok") {
                        window.location.href = "/";
                    }
                });
        }

        setInterval(checkAccess, 10000);
    """, type="text/javascript"),
])


# Главная страница (авторизация)
@server.route("/")
def index():
    return '''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Вход через Telegram</title>
            <script async src="https://telegram.org/js/telegram-widget.js?22"></script>
        </head>
        <body>
            <h1>Вход через Telegram</h1>
            <div id="telegram-login-container"></div>
            <script>
                document.addEventListener("DOMContentLoaded", function() {
                    let container = document.getElementById('telegram-login-container');
                    container.innerHTML = '<script async src="https://telegram.org/js/telegram-widget.js?22" '
                        + 'data-telegram-login="Ttcttc_bot" '  // Здесь правильный юзернейм бота
                        + 'data-size="large" '
                        + 'data-auth-url="https://maxpower-t7lp.onrender.com/verify" '
                        + 'data-request-access="write"><\\/script>';
                });
            </script>
        </body>
        </html>
    '''




# Запуск сервера
if __name__ == "__main__":
    server.run(host="0.0.0.0", port=8080)
