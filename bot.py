from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import sqlite3
import re  # Для перевірки формату дати та часу

# Константи для станів
SELECT_DATE, SELECT_TIME, CONFIRM, CANCEL_BOOKING, CHANGE_BOOKING = range(5)

# Підключення до бази даних
def connect_db():
    return sqlite3.connect('bookings.db')

# Створення таблиці, якщо її немає
def create_table():
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                date TEXT,
                time TEXT
            )
        ''')
        conn.commit()

# Додавання нового запису
def add_booking(username, date, time):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO bookings (username, date, time) VALUES (?, ?, ?)', (username, date, time))
        conn.commit()
        return cursor.lastrowid  # Повертаємо ID нового запису

# Отримання записів користувача
def get_user_bookings(username):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM bookings WHERE username = ?', (username,))
        return cursor.fetchall()

# Скасування запису
def cancel_booking(booking_id):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
        conn.commit()

# Оновлення запису
def update_booking(booking_id, new_date, new_time):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE bookings SET date = ?, time = ? WHERE id = ?', (new_date, new_time, booking_id))
        conn.commit()

# Перевірка, чи час зайнятий
def is_time_booked(date, time):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM bookings WHERE date = ? AND time = ?', (date, time))
        return cursor.fetchone() is not None

# Перевірка формату дати (YYYY-MM-DD) та часу (HH:MM)
def is_valid_date(date):
    return re.match(r'^\d{4}-\d{2}-\d{2}$', date) is not None

def is_valid_time(time):
    return re.match(r'^\d{2}:\d{2}$', time) is not None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт! Я твій бот для запису. "
        "Використай /book, щоб записатися на прийом.\n"
        "Використай /help, щоб побачити доступні команди."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Доступні команди:\n"
        "/start - почати взаємодію з ботом\n"
        "/book - забронювати запис\n"
        "/view - переглянути свої записи\n"
        "/change - змінити існуючий запис\n"
        "/cancel - скасувати запис\n"
    )

async def view_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username or "Анонім"
    bookings = get_user_bookings(username)

    if not bookings:
        await update.message.reply_text("У вас немає записів.")
        return

    response = "Ваші записи:\n"
    for booking in bookings:
        response += f"ID: {booking[0]}, Дата: {booking[2]}, Час: {booking[3]}\n"

    await update.message.reply_text(response)

async def book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть дату для запису (формат: YYYY-MM-DD):")
    return SELECT_DATE

async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = update.message.text
    if not is_valid_date(date):
        await update.message.reply_text("Неправильний формат дати. Будь ласка, введіть дату в форматі YYYY-MM-DD.")
        return SELECT_DATE  # Повторити запит дати
    context.user_data['date'] = date
    await update.message.reply_text("Введіть час для запису (формат: HH:MM):")
    return SELECT_TIME

async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time = update.message.text
    date = context.user_data['date']
    username = update.effective_user.username or "Анонім"

    if not is_valid_time(time):
        await update.message.reply_text("Неправильний формат часу. Будь ласка, введіть час в форматі HH:MM.")
        return SELECT_TIME  # Повторити запит часу

    if is_time_booked(date, time):
        await update.message.reply_text("Цей час вже зайнятий. Спробуйте інший.")
        return SELECT_TIME
    else:
        booking_id = add_booking(username, date, time)
        await update.message.reply_text(f"Запис успішно створено на {date} о {time}. Ваш ID запису: {booking_id}.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть ID запису, який ви хочете скасувати:")
    return CANCEL_BOOKING

async def cancel_booking_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        booking_id = int(update.message.text)
        cancel_booking(booking_id)
        await update.message.reply_text("Запис скасовано.")
    except ValueError:
        await update.message.reply_text("Будь ласка, введіть коректний ID запису.")
    return ConversationHandler.END

async def change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть ID запису, який ви хочете змінити:")
    return CHANGE_BOOKING

async def change_booking_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        booking_id = int(update.message.text)
        username = update.effective_user.username or "Анонім"

        # Перевірка, чи існує запис
        bookings = get_user_bookings(username)
        booking = next((b for b in bookings if b[0] == booking_id), None)
        if not booking:
            await update.message.reply_text("Запис з таким ID не знайдено.")
            return ConversationHandler.END

        # Запит нових дати та часу
        context.user_data['booking_id'] = booking_id
        await update.message.reply_text("Введіть нову дату для запису (формат: YYYY-MM-DD):")
        return SELECT_DATE  # Переходимо до вибору нової дати

    except ValueError:
        await update.message.reply_text("Будь ласка, введіть коректний ID запису.")
        return ConversationHandler.END

async def change_select_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_date = update.message.text
    if not is_valid_date(new_date):
        await update.message.reply_text("Неправильний формат дати. Будь ласка, введіть дату в форматі YYYY-MM-DD.")
        return SELECT_DATE  # Повторити запит дати
    context.user_data['new_date'] = new_date
    await update.message.reply_text("Введіть новий час для запису (формат: HH:MM):")
    return SELECT_TIME

async def change_select_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_time = update.message.text
    new_date = context.user_data['new_date']
    booking_id = context.user_data['booking_id']

    # Перевірка, чи новий час вже зайнятий
    if not is_valid_time(new_time):
        await update.message.reply_text("Неправильний формат часу. Будь ласка, введіть час в форматі HH:MM.")
        return SELECT_TIME  # Повторити запит часу

    if is_time_booked(new_date, new_time):
        await update.message.reply_text("Цей новий час вже зайнятий. Оберіть інший.")
        return SELECT_TIME
    else:
        update_booking(booking_id, new_date, new_time)
        await update.message.reply_text(f"Запис змінено на {new_date} о {new_time}.")
        return ConversationHandler.END

def main():
    create_table()

    app = ApplicationBuilder().token("your_token_here").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("view", view_bookings))

    # Обробник для бронювання
    book_handler = ConversationHandler(
        entry_points=[CommandHandler("book", book)],
        states={
            SELECT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_date)],
            SELECT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_time)],
        },
        fallbacks=[],
    )

    # Обробник для скасування запису
    cancel_handler = ConversationHandler(
        entry_points=[CommandHandler("cancel", cancel)],
        states={
            CANCEL_BOOKING: [MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_booking_handler)],
        },
        fallbacks=[],
    )

    # Обробник для зміни запису
    change_handler = ConversationHandler(
        entry_points=[CommandHandler("change", change)],
        states={
            CHANGE_BOOKING: [MessageHandler(filters.TEXT & ~filters.COMMAND, change_booking_handler)],
            SELECT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, change_select_date)],
            SELECT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, change_select_time)],
        },
        fallbacks=[],
    )

    app.add_handler(book_handler)
    app.add_handler(cancel_handler)
    app.add_handler(change_handler)

    app.run_polling()

if __name__ == "__main__":
    main()