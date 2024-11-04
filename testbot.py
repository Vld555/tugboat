from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import asyncpg
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

API_TOKEN = '7844462943:AAGUA5YJzwOYo0PJpt-9xU3lBSK2Qop7avc'

# Параметры подключения к базе данных
user = 'postgres'
password = 'vlad'
host = 'localhost'
db_name = 'tourism'
port = 5432

# Создание экземпляров бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Определение состояний для FSM
class SurveyStates(StatesGroup):
    ANSWERING = State()

# Функция для получения данных о пользователе


# Функция для получения данных о пользователе
def get_user_info(message: Message):
    return {
        "date_time": datetime.now(),  # Возвращаем объект datetime напрямую
        "username": message.from_user.username or "Нет username",
        "user_id": message.from_user.id,
        "first_name": message.from_user.first_name,
        "last_name": message.from_user.last_name or "Нет фамилии"
    }


# Функция для подключения к базе данных и получения вопросов с опциями для выбора
async def get_questions():
    conn = await asyncpg.connect(
        user=user, password=password, host=host, database=db_name, port=port
    )
    try:
        # Загружаем вопросы из таблицы survey
        rows = await conn.fetch("SELECT id, name, type FROM survey ORDER BY id")
        questions = []
        
        for row in rows:
            question = {"id": row["id"], "name": row["name"], "type": row["type"]}
            
            # Если тип вопроса "choice", загружаем опции для кнопок из таблицы survey_options
            if question["type"] == "choice":
                options = await conn.fetch(
                    "SELECT option_text, option_value FROM survey_options WHERE survey_id = $1", row["id"]
                )
                question["options"] = [
                    {"text": option["option_text"], "value": option["option_value"]}
                    for option in options
                ]
                logging.info(f"Options for question {row['id']}: {question['options']}")
            
            questions.append(question)
            
        return questions
    finally:
        await conn.close()

# Создание клавиатуры для вопросов с вариантами ответов
def create_choice_keyboard(options):
    buttons = []
    for option in options:
        buttons.append(InlineKeyboardButton(text=option["text"], callback_data=option["value"]))
    
    # Группируем кнопки по две в ряд
    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons[i:i+2] for i in range(0, len(buttons), 2)])
    return keyboard

@dp.message(Command("start"))
async def send_welcome(message: Message):
    user_info = get_user_info(message)
    logging.info(f"Новый пользователь: {user_info}")
    await message.reply("Привет! Я бот для проведения опросов. Чтобы начать опрос, введите /survey")

# Команда /survey — начало опроса
@dp.message(Command("survey"))
async def start_survey(message: Message, state: FSMContext):
    user_info = get_user_info(message)
    questions = await get_questions()  # Загружаем вопросы из БД
    if not questions:
        await message.reply("Опросов не найдено.")
        return

    await state.set_state(SurveyStates.ANSWERING)
    await state.update_data(current_question=0, questions=questions, answers=[], user_info=user_info)
    await send_question(message, questions[0])

# Отправка вопроса в зависимости от типа (кнопки или текст)
async def send_question(message: Message, question):
    if question["type"] == "choice":
        # Если вопрос с вариантами ответа, создаем клавиатуру
        keyboard = create_choice_keyboard(question["options"])
        await message.reply(question["name"], reply_markup=keyboard)
    else:
        # Если вопрос текстовый, отправляем его с просьбой ввести ответ
        await message.reply(f"{question['name']}\n\nПожалуйста, введите ваш ответ:")

# Обработка ответа на текстовые вопросы
@dp.message(SurveyStates.ANSWERING)
async def handle_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    current_question = data['current_question']
    answers = data['answers']
    questions = data['questions']
    user_info = data['user_info']

    # Сохраняем ответ пользователя для текстового вопроса
    answers.append({"question_id": questions[current_question]["id"], "answer": message.text})
    await proceed_to_next_question(message, state, current_question, answers, questions, user_info)

# Обработка ответов на вопросы с вариантами
@dp.callback_query(SurveyStates.ANSWERING)
async def handle_choice_answer(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_question = data['current_question']
    answers = data['answers']
    questions = data['questions']
    user_info = data['user_info']

    # Сохраняем выбранный ответ пользователя (используем значение, переданное с кнопкой)
    answers.append({"question_id": questions[current_question]["id"], "answer": callback_query.data})
    await callback_query.answer()  # Закрываем уведомление от кнопки
    await proceed_to_next_question(callback_query.message, state, current_question, answers, questions, user_info)

# Функция для записи ответа в таблицу survey_responses
async def save_response(user_info, question_id, answer):
    conn = await asyncpg.connect(
        user=user, password=password, host=host, database=db_name, port=port
    )
    try:
        await conn.execute(
            """
            INSERT INTO survey_responses (user_id, username, first_name, last_name, date_time, question_id, answer)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            user_info["user_id"],
            user_info["username"],
            user_info["first_name"],
            user_info["last_name"],
            user_info["date_time"],
            question_id,
            answer
        )
    finally:
        await conn.close()

# Переход к следующему вопросу или завершение опроса
async def proceed_to_next_question(message, state, current_question, answers, questions, user_info):
    current_question += 1

    if current_question < len(questions):
        await state.update_data(current_question=current_question, answers=answers)
        await send_question(message, questions[current_question])
    else:
        await message.reply("Спасибо за ответы! Опрос завершен.")
        survey_result = {
            "user_info": user_info,
            "answers": answers
        }
        logging.info(f"Результаты опроса: {survey_result}")

        # Сохраняем все ответы в базе данных
        for answer in answers:
            await save_response(user_info, answer["question_id"], answer["answer"])

        await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
