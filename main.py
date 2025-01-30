import telebot
from PIL import Image
import io
from telebot import types
import os
from dotenv import load_dotenv
import time

# Загружаем токен бота из переменных окружения
load_dotenv()
TOKEN = os.getenv('TOKEN')
bot = telebot.TeleBot(TOKEN)

# Удаляем Webhook и ждем 1 секунду перед запуском бота
bot.remove_webhook()
time.sleep(1)

# Хранение состояний пользователей (выбранный режим и изображение)
user_states = {}


def image_to_ascii(image_stream, ascii_chars, new_width=40):
    """
    Преобразует изображение в ASCII-арт, используя заданный набор символов.

    :param image_stream: Поток изображения.
    :param ascii_chars: Набор символов для ASCII-арта.
    :param new_width: Новая ширина изображения в символах.
    :return: Строка с ASCII-артом.
    """
    image = Image.open(image_stream).convert('L')
    width, height = image.size
    aspect_ratio = height / float(width)
    new_height = int(aspect_ratio * new_width * 0.55)
    img_resized = image.resize((new_width, new_height))

    img_str = pixels_to_ascii(img_resized, ascii_chars)
    img_width = img_resized.width

    max_characters = 4000 - (new_width + 1)
    max_rows = max_characters // (new_width + 1)

    ascii_art = ""
    for i in range(0, min(max_rows * img_width, len(img_str)), img_width):
        ascii_art += img_str[i:i + img_width] + "\n"

    return ascii_art


def pixels_to_ascii(image, ascii_chars):
    """
    Преобразует пиксели изображения в ASCII-символы.

    :param image: Изображение в градациях серого.
    :param ascii_chars: Набор символов для ASCII-арта.
    :return: Строка ASCII-изображения.
    """
    pixels = image.getdata()
    characters = "".join(ascii_chars[pixel * len(ascii_chars) // 256] for pixel in pixels)
    return characters


def pixelate_image(image, pixel_size):
    """
    Создает эффект пикселизации изображения.

    :param image: Оригинальное изображение.
    :param pixel_size: Размер пикселя (чем больше, тем сильнее эффект).
    :return: Пикселизированное изображение.
    """
    image = image.resize(
        (image.size[0] // pixel_size, image.size[1] // pixel_size),
        Image.NEAREST
    )
    image = image.resize(
        (image.size[0] * pixel_size, image.size[1] * pixel_size),
        Image.NEAREST
    )
    return image


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Обрабатывает команды /start и /help, отправляя пользователю приветственное сообщение."""
    bot.reply_to(message, "Send me an image, and I'll provide options for you!")


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """Принимает изображение от пользователя и предлагает выбрать режим обработки."""
    bot.reply_to(message, "I got your photo! Choose an option:", reply_markup=get_options_keyboard())
    user_states[message.chat.id] = {'photo': message.photo[-1].file_id}


def get_options_keyboard():
    """Создает клавиатуру с вариантами обработки изображения (пикселизация или ASCII-арт)."""
    keyboard = types.InlineKeyboardMarkup()
    pixelate_btn = types.InlineKeyboardButton("Pixelate", callback_data="pixelate")
    ascii_btn = types.InlineKeyboardButton("ASCII Art", callback_data="ascii")
    keyboard.add(pixelate_btn, ascii_btn)
    return keyboard


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    """Обрабатывает нажатия на кнопки выбора режима."""
    chat_id = call.message.chat.id
    if chat_id not in user_states:
        user_states[chat_id] = {}

    if call.data == "pixelate":
        bot.answer_callback_query(call.id, "Pixelating your image...")
        pixelate_and_send(call.message)
    elif call.data == "ascii":
        bot.answer_callback_query(call.id, "Send me a set of characters to use for ASCII art.")
        user_states[chat_id]['awaiting_chars'] = True


@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('awaiting_chars'))
def receive_custom_chars(message):
    """Принимает набор символов от пользователя для генерации ASCII-арта."""
    custom_chars = message.text.strip()
    if len(custom_chars) < 2:
        bot.reply_to(message, "Please provide at least two characters for ASCII art.")
        return

    user_states[message.chat.id]['ascii_chars'] = custom_chars
    user_states[message.chat.id]['awaiting_chars'] = False
    bot.reply_to(message, "Great! Now converting your image to ASCII art...")
    ascii_and_send(message)


def ascii_and_send(message):
    """Обрабатывает изображение и отправляет ASCII-арт пользователю."""
    chat_id = message.chat.id
    photo_id = user_states.get(chat_id, {}).get('photo')
    ascii_chars = user_states.get(chat_id, {}).get('ascii_chars', '@%#*+=-:. ')

    if not photo_id:
        bot.send_message(chat_id, "Error: No image found. Please send an image again.")
        return

    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)
    image_stream = io.BytesIO(downloaded_file)

    ascii_art = image_to_ascii(image_stream, ascii_chars)
    bot.send_message(chat_id, f"<pre>{ascii_art}</pre>", parse_mode="HTML")


def pixelate_and_send(message):
    """Обрабатывает изображение и отправляет пикселизированное изображение пользователю."""
    chat_id = message.chat.id
    photo_id = user_states.get(chat_id, {}).get('photo')

    if not photo_id:
        bot.send_message(chat_id, "Error: No image found. Please send an image again.")
        return

    file_info = bot.get_file(photo_id)
    downloaded_file = bot.download_file(file_info.file_path)
    image_stream = io.BytesIO(downloaded_file)
    image = Image.open(image_stream)
    pixelated = pixelate_image(image, 20)

    output_stream = io.BytesIO()
    pixelated.save(output_stream, format="JPEG")
    output_stream.seek(0)
    bot.send_photo(chat_id, output_stream)


# Запуск бота
bot.polling(none_stop=True)
