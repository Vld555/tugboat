from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
import asyncio
import logging
from datetime import datetime


logging.basicConfig(level=logging.INFO)


API_TOKEN = '7844462943:AAGUA5YJzwOYo0PJpt-9xU3lBSK2Qop7avc'

# Создание экземпляров бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ПРИМЕР!
questions = [
    "Вопрос 1: Как вас зовут?",
    "Вопрос 2: Сколько вам лет?",
    "Вопрос 3: Как вы узнали о нашем боте?"
]

# Определение состояний для FSM
class SurveyStates(StatesGroup):
    ANSWERING = State()

# сбор данных о пользователе
def get_user_info(message: Message):
    return {
        "date_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "username": message.from_user.username or "Нет username",
        "user_id": message.from_user.id,
        "first_name": message.from_user.first_name,
        "last_name": message.from_user.last_name or "Нет фамилии"
    }

@dp.message(Command("start"))
async def send_welcome(message: Message):
    user_info = get_user_info(message)
    logging.info(f"Новый пользователь: {user_info}")
    await message.reply("Привет! Я бот для проведения опросов. Чтобы начать опрос, введите /survey")

# Команда /survey — начало опроса
@dp.message(Command("survey"))
async def start_survey(message: Message, state: FSMContext):
    user_info = get_user_info(message)
    await state.set_state(SurveyStates.ANSWERING)
    await state.update_data(current_question=0, answers=[], user_info=user_info)
    await message.reply(questions[0])

# Обработка ответов на вопросы
@dp.message(SurveyStates.ANSWERING)
async def handle_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    current_question = data['current_question']
    answers = data['answers']
    user_info = data['user_info']

    answers.append(message.text)
    current_question += 1

    if current_question < len(questions):
        await state.update_data(current_question=current_question, answers=answers)
        await message.reply(questions[current_question])
    else:
        await message.reply("Спасибо за ответы! Опрос завершен.")
        survey_result = {
            "user_info": user_info,
            "answers": answers
        }
        logging.info(f"Результаты опроса: {survey_result}")
        await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())