
import telebot
import requests
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
import schedule
import threading
import time
from datetime import datetime, timedelta
import hashlib

TOKEN = 'ВАШ_ТОКЕН_ЗДЕСЬ'
bot = telebot.TeleBot(TOKEN)

user_groups = {}
last_file_hash = None

def get_schedule_excel_url():
    url = "https://pnk59.ru/raspisanie-zanyatij/"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    for link in soup.find_all('a'):
        href = link.get('href')
        if href and href.endswith('.xlsx'):
            return href
    return None

def extract_schedule(group_name, day_filter=None):
    file_url = get_schedule_excel_url()
    if not file_url:
        return "Файл с расписанием не найден."

    response = requests.get(file_url)
    excel_data = BytesIO(response.content)

    try:
        df = pd.read_excel(excel_data, sheet_name=None)
        result = ""
        for sheet, data in df.items():
            for i, row in data.iterrows():
                row_str = " ".join(str(cell) for cell in row if pd.notna(cell))
                if group_name.upper() in row_str.upper():
                    if day_filter:
                        if day_filter.lower() in row_str.lower():
                            result += row_str + "\n"
                    else:
                        result += row_str + "\n"
        return result if result else "Группа найдена, но пар на этот день нет."
    except Exception as e:
        return f"Ошибка при обработке файла: {e}"

def get_tomorrow_day_name():
    tomorrow = datetime.now() + timedelta(days=1)
    return tomorrow.strftime('%A')

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.reply_to(message, "Привет! Я бот с расписанием Пермского нефтяного колледжа.\nНапиши /group ТВОЯ_ГРУППА, чтобы установить свою группу.\nПример: /group ТЭ-21")

@bot.message_handler(commands=['group'])
def set_group(message):
    try:
        _, group_name = message.text.split(maxsplit=1)
        user_groups[message.chat.id] = group_name.strip()
        bot.reply_to(message, f"Группа установлена: {group_name}")
    except:
        bot.reply_to(message, "Напиши команду так: /group ТВОЯ_ГРУППА")

@bot.message_handler(commands=['schedule'])
def send_schedule(message):
    user_id = message.chat.id
    if user_id not in user_groups:
        bot.reply_to(message, "Сначала установи свою группу командой /group ТВОЯ_ГРУППА")
        return
    group = user_groups[user_id]
    schedule_text = extract_schedule(group)
    bot.send_message(user_id, schedule_text)

def daily_schedule_job():
    for user_id, group in user_groups.items():
        day = get_tomorrow_day_name()
        schedule_text = extract_schedule(group, day_filter=day)
        bot.send_message(user_id, f"Расписание на {day} для группы {group}:\n\n{schedule_text}")

def check_for_updates():
    global last_file_hash
    file_url = get_schedule_excel_url()
    if not file_url:
        return
    response = requests.get(file_url)
    file_data = response.content
    current_hash = hashlib.md5(file_data).hexdigest()
    if last_file_hash and current_hash != last_file_hash:
        for user_id in user_groups:
            bot.send_message(user_id, "Внимание! Расписание на сайте колледжа обновилось.")
    last_file_hash = current_hash

def scheduler_loop():
    schedule.every().day.at("19:00").do(daily_schedule_job)
    schedule.every(3).hours.do(check_for_updates)
    while True:
        schedule.run_pending()
        time.sleep(60)

threading.Thread(target=scheduler_loop, daemon=True).start()
bot.polling()
