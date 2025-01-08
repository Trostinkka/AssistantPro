import json
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import threading
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from collections import defaultdict

#токен бота
BOT_TOKEN = "7573763210:AAEK89qP4KLyuayM8c34g2O3HRAKHEA6KSM"
bot = telebot.TeleBot(BOT_TOKEN)

#API погоды
WEATHER_API_KEY = "874b5b685059bf9fc26a86d0be6d3cf6"
WEATHER_URL = "http://api.openweathermap.org/data/2.5/weather"

#хранилише данных 
tasks = defaultdict(list)
reminders = {}
expenses = defaultdict(list) #сумма -> категория -> дата 

#Инициализация расходов
expenses = {}

#файл для сохранения расходов
EXPENSES_FILE = 'expenses.json'
 
# == Главная клавиатура ==
def main_menu():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Погода", callback_data="weather"),
    )
    markup.row(
        InlineKeyboardButton("Напоминания", callback_data="reminder"),
        InlineKeyboardButton("Расходы", callback_data="expenses"),
    )
    markup.row(
        InlineKeyboardButton("Поддержка", callback_data="support")
    )
    return markup
 
# == Клавиатура для режима "Расходы" ==
def expenses_menu():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Добавить расход", callback_data="add_expense"),
        InlineKeyboardButton("Анализ (неделя)", callback_data="analyze_week"),
    )
    markup.row(
        InlineKeyboardButton("Анализ (месяц)", callback_data="analyze_month"),
        InlineKeyboardButton("Назад в главное меню", callback_data="main_menu")
    )
    return markup

# == Общая кнопка возврата ==
def back_to_main_menu():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("Назад в главное меню", callback_data="main_menu")) 
    return markup  

#Приведствие
@bot.message_handler(commands=['start'])
def start(message):
    load_expenses_from_file()
    bot.send_message(

        message.chat.id,
        "Привет! Я твой помощник. Выберите, что вы хотите сделать:",
        reply_markup=main_menu(),
    )

# === Обработка кнопок ===
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "weather":
        bot.send_message(call.message.chat.id, "Напиши название города, чтобы узнать погоду.", reply_markup=back_to_main_menu())
        bot.register_next_step_handler(call.message, get_weather)
    elif call.data == "reminder":
        bot.send_message(
            call.message.chat.id, 
            "Напиши текст напоминания и через сколько минут оно должно сработать (например, 'Встреча через 10').",
            reply_markup=back_to_main_menu()
        )
        bot.register_next_step_handler(call.message, set_reminder)
    elif call.data == "expenses":
        bot.send_message(call.message.chat.id, "Выбери действие с расходами:", reply_markup=expenses_menu())
    elif call.data == "add_expense":
        bot.send_message(call.message.chat.id, "Напиши все расходы через пробел (например, '100 еда 200 такси').", reply_markup=back_to_main_menu())
        bot.register_next_step_handler(call.message, save_expenses)
    elif call.data == "analyze_week":
        analyze_expenses(call.message, "week")
    elif call.data == "analyze_month":
        analyze_expenses(call.message, "month")
    elif call.data == "main_menu":
        bot.send_message(call.message.chat.id, "Выбери, что ты хочешь сделать:", reply_markup=main_menu())
    elif call.data == "support":
        bot.send_message(call.message.chat.id, "Для поддержки обращайся сюда: @trostinkka", reply_markup=main_menu())

# === Погода ===
def get_weather(message):
    city = message.text
    params = {"q": city, "appid": WEATHER_API_KEY, "units": "metric", "lang": "ru"}
    response = requests.get(WEATHER_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        weather_info = (f"Погода в {data['name']}:\n"
                        f"Температура: {data['main']['temp']}°C\n"
                        f"Ощущается как: {data['main']['feels_like']}°C\n"
                        f"Погодные условия: {data['weather'][0]['description']}")
        bot.send_message(message.chat.id, weather_info, reply_markup=main_menu())
    else:
        bot.send_message(message.chat.id, "Город не найден. Попробуй ещё раз.", reply_markup=main_menu())


# === Напоминания ===
def set_reminder(message):
    try:
        text, time = message.text.rsplit(' через ', 1)
        minutes = int(time)
        remind_time = datetime.now() + timedelta(minutes=minutes)
        reminders[(message.chat.id, text)] = remind_time
        bot.send_message(message.chat.id, f"Напоминание '{text}' установлено через {minutes} минут.", reply_markup=main_menu())
        threading.Timer(minutes * 60, send_reminder, args=(message.chat.id, text)).start()
    except ValueError:
        bot.send_message(message.chat.id, "Формат неправильный. Попробуй снова.", reply_markup=main_menu())

def send_reminder(chat_id, text):
    bot.send_message(chat_id, f"Напоминание: {text}", reply_markup=main_menu())

# === Расходы и анализ ===
def save_expenses(message):
    try:
        # Разделяем сообщение на слова, учитывая что расходы могут быть на одной или нескольких строках
        expenses_data = message.text.split()

        if len(expenses_data) % 2 != 0:
            # Если количество слов нечётное, значит ошибка ввода
            bot.send_message(message.chat.id, "Неправильный формат. Каждое число должно быть связано с категорией (например, '100 еда').", reply_markup=expenses_menu())
            return

        for i in range(0, len(expenses_data), 2):
            amount = float(expenses_data[i])  # Сначала идёт сумма
            category = expenses_data[i + 1]  # Потом категория
            date = datetime.now()  # Текущая дата для расхода
            expenses[message.chat.id].append((amount, category, date))  # Добавляем расход в список

        save_expenses_to_file()  # Сохраняем расходы в файл
        bot.send_message(message.chat.id, "Расходы добавлены.", reply_markup=expenses_menu())

    except ValueError:
        bot.send_message(message.chat.id, "Неправильный формат. Попробуй снова. Пример: '100 еда 200 такси'.", reply_markup=expenses_menu())

def analyze_expenses(message, period):
    user_expenses = expenses[message.chat.id]
    if not user_expenses:
        bot.send_message(message.chat.id, "У тебя пока нет расходов.", reply_markup=expenses_menu())
        return

# Определяем начало периода
    if period == "week":
        start_date = datetime.now() - timedelta(days=7)
        title = "Анализ расходов за неделю"
    elif period == "month":
        start_date = datetime.now() - timedelta(days=30)
        title = "Анализ расходов за месяц"
    
    # Фильтруем расходы
    filtered_expenses = [e for e in user_expenses if e[2] >= start_date]

    if not filtered_expenses:
        bot.send_message(message.chat.id, f"Расходов за выбранный период нет.", reply_markup=expenses_menu())
        return

# Группируем расходы по категориям
    categories = defaultdict(float)
    for amount, category, _ in filtered_expenses:
        categories[category] += amount

    total_expenses = sum(categories.values())
    response_message = f"Всего потрачено: {total_expenses} руб.\n"
    for category, amount in categories.items():
        response_message += f"{category.capitalize()}: {amount} руб.\n"

    bot.send_message(message.chat.id, response_message, reply_markup=expenses_menu())

# Функция сохранения расходов в файл
def save_expenses_to_file():
    # Преобразуем datetime в строку перед сохранением
    expenses_serializable = []
    for user_expenses in expenses.values():
        serializable_expenses = []
        for amount, category, date in user_expenses:
            # Преобразуем datetime в строку
            serializable_expenses.append((amount, category, date.strftime('%Y-%m-%d %H:%M:%S')))
        expenses_serializable.append(serializable_expenses)

    with open("expenses.json", "w", encoding="utf-8") as f:
        json.dump(expenses_serializable, f, ensure_ascii=False, indent=4)

# Функция загрузки расходов из файла
def load_expenses_from_file():
    global expenses  # Указываем, что работаем с глобальной переменной
    try:
        with open("expenses.json", "r", encoding="utf-8") as f:
            expenses_serializable = json.load(f)

        # Преобразуем строки обратно в datetime
        for user_expenses in expenses_serializable:
            for i, (amount, category, date_str) in enumerate(user_expenses):
                date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                user_expenses[i] = (amount, category, date)

        # Загрузим данные в глобальную переменную
        for idx, user_expenses in enumerate(expenses_serializable):
            expenses[idx] = user_expenses
    except FileNotFoundError:
        # Если файла нет, создаём пустой словарь для расходов
        expenses = {}


# Функция для работы с расходами
@bot.message_handler(func=lambda message: True)
def save_expenses(message):
    try:
        if message.chat.id not in expenses:
            expenses[message.chat.id] = []  # Если у пользователя ещё нет расходов, создаём пустой список расходов

        # Разделяем сообщение на слова
        expenses_data = message.text.split()

        if len(expenses_data) % 2 != 0:
            bot.send_message(message.chat.id, "Неправильный формат. Каждое число должно быть связано с категорией (например, '100 еда').")
            return

        for i in range(0, len(expenses_data), 2):
            amount = float(expenses_data[i])  # Сначала идёт сумма
            category = expenses_data[i + 1]  # Потом категория
            date = datetime.now()  # Текущая дата для расхода
            expenses[message.chat.id].append((amount, category, date))  # Добавляем расход в список

        save_expenses_to_file()  # Сохраняем расходы в файл
        bot.send_message(message.chat.id, "Расходы добавлены.")

    except ValueError:
        bot.send_message(message.chat.id, "Неправильный формат. Попробуй снова. Пример: '100 еда 200 такси'.")

# Запуск бота
bot.polling(none_stop=True)
