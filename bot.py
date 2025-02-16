from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Твой токен бота из BotFather
TOKEN = "your_telegram_bot_token"

# Адрес твоего сайта, куда бот будет перенаправлять пользователей
SITE_URL = "https://your-render-url.com/login"  # Замени на URL твоего сайта

def start(update: Update, context: CallbackContext):
    """Обрабатывает команду /start и перенаправляет пользователя на сайт для входа"""
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name

    # Формируем ссылку для входа
    login_url = f"{SITE_URL}?id={user_id}&first_name={first_name}"
    
    # Отправляем пользователю сообщение с ссылкой
    update.message.reply_text(f"Привет, {first_name}! Для входа на сайт нажми на ссылку: {login_url}")

def main():
    """Запускает бота"""
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    # Добавляем обработчик команды /start
    dp.add_handler(CommandHandler("start", start))

    # Запускаем бота
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
