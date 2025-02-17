import dash
from dash import dcc, html
from flask import Flask, request, redirect, jsonify
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

# ✅ Добавляем `layout`, чтобы Dash не выдавал ошибку
app.layout = html.Div([
    html.H1("Dashboard", style={'textAlign': 'center'}),
    dcc.Graph(id='options-chart', style={'height': '600px'}),
])

# Функция проверки членства в Telegram-канале
def is_member(user_id):
    """ Проверяет, состоит ли пользователь в канале """
    url = f"https://api.telegram.org/bot{TOKEN}/getChatMember"
    response = requests.get(url, params={"chat_id": CHANNEL_ID, "user_id": user_id}).json()
    return response.get("ok") and response.get("result", {}).get("status") in ["member", "administrator", "creator"]

# Главная страница (авторизация через Telegram Web Apps API)
@server.route("/")
def index():
    return '''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Вход через Telegram</title>
            <script src="https://telegram.org/js/telegram-web-app.js"></script>
        </head>
        <body>
            <h1>Вход через Telegram</h1>
            <button id="login-btn" style="font-size: 20px; padding: 10px;">Войти через Telegram</button>

            <script>
                document.getElementById("login-btn").addEventListener("click", function() {
                    let tg = window.Telegram.WebApp;
                    tg.expand();
                    tg.MainButton.setText("Подтвердить вход");
                    tg.MainButton.show();
                    tg.onEvent("mainButtonClicked", function() {
                        let user = tg.initDataUnsafe.user;
                        if (user) {
                            window.location.href = "/verify?user_id=" + user.id + "&first_name=" + user.first_name;
                        }
                    });
                });
            </script>
        </body>
        </html>
    '''

# Проверка пользователя и вход в систему
@server.route("/verify")
def verify():
    user_id = request.args.get("user_id")

    if not user_id:
        return "Ошибка: Telegram не передал данные!", 400

    if not is_member(user_id):
        return "Доступ запрещён: вы не подписаны на канал!", 403

    # Генерируем токен (используется как параметр в URL)
    token = hashlib.sha256(f"{user_id}{TOKEN}".encode()).hexdigest()
    return redirect(f"/dashboard?token={token}&user_id={user_id}")

# Проверка членства (каждые 10 секунд)
@server.route("/check_access")
def check_access():
    user_id = request.args.get("user_id")

    if not user_id or not is_member(user_id):
        return jsonify({"status": "error", "message": "Вы больше не в канале"}), 403

    return jsonify({"status": "ok", "message": "Доступ разрешён"}), 200

# Dashboard (разлогинивает, если пользователь выходит из канала)
@server.route("/dashboard")
def dashboard():
    user_id = request.args.get("user_id")

    if not user_id or not is_member(user_id):
        return redirect("/")

    return f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard</title>
        <script>
            function checkAccess() {{
                fetch("/check_access?user_id={user_id}")
                    .then(response => response.json())
                    .then(data => {{
                        if (data.status !== "ok") {{
                            window.location.href = "/";
                        }}
                    }});
            }}
            setInterval(checkAccess, 10000);
        </script>
    </head>
    <body>
        <h1>Добро пожаловать, {user_id}!</h1>
        <p>Если вы покинете канал, доступ закроется автоматически.</p>
        <a href="/">Выйти</a>
    </body>
    </html>
    '''

# Запуск сервера
if __name__ == "__main__":
    server.run(host="0.0.0.0", port=8080)
