# -*- coding: utf-8 -*-
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, Update
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Состояния FSM для авторизации
class AuthStates(StatesGroup):
    waiting_for_password = State()
    authorized = State() # Это состояние мы будем использовать как маркер, но фактически храним флаг в data

class AuthMiddleware(BaseMiddleware):
    def __init__(self, password: str):
        self.password = password
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:

        # Мы работаем только с сообщениями для простоты
        if not isinstance(event, Message):
            return await handler(event, data)

        message: Message = event
        state: FSMContext = data.get("state")

        if not state:
             # Если стейта нет (странно, но бывает), пропускаем или блочим
             # Лучше пропустить, если что-то не так с настройкой, но безопаснее блочить.
             return await handler(event, data)

        current_state = await state.get_state()
        state_data = await state.get_data()

        is_authorized = state_data.get("is_authorized", False)

        # Если пользователь уже авторизован, пропускаем
        if is_authorized:
            return await handler(event, data)

        # Если мы ждем пароль
        if current_state == AuthStates.waiting_for_password:
            if message.text == self.password:
                await state.update_data(is_authorized=True)
                await state.set_state(None) # Сбрасываем стейт, чтобы не мешать другим хендлерам
                await message.answer("✅ Доступ разрешен. Добро пожаловать!")
                # Мы не вызываем handler для сообщения с паролем, чтобы оно не улетело в бота как команда
                return
            else:
                await message.answer("❌ Неверный пароль. Попробуйте еще раз.")
                return

        # Если пользователь не авторизован и не вводит пароль - просим пароль
        # Устанавливаем состояние ожидания пароля
        await state.set_state(AuthStates.waiting_for_password)
        await message.answer("🔒 Бот защищен паролем. Пожалуйста, введите пароль для доступа:")
        return
