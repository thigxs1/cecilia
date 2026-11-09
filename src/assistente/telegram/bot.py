"""Módulo de integração com Telegram Bot para envio/recebimento de comandos remotos (Mobile)."""
from __future__ import annotations

import asyncio
import threading
from typing import Callable

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from assistente.ai.brain import AssistantBrain
from assistente.config import Settings


class TelegramBridge:
    def __init__(
        self,
        settings: Settings,
        brain: AssistantBrain,
        on_notify_desktop: Callable[[str], None] | None = None,
    ) -> None:
        self.settings = settings
        self.brain = brain
        self.on_notify_desktop = on_notify_desktop
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._app = None

    def start(self) -> None:
        if not self.settings.telegram_bot_token:
            return

        self._thread = threading.Thread(target=self._run_bot, daemon=True)
        self._thread.start()

    def _run_bot(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self._app = ApplicationBuilder().token(self.settings.telegram_bot_token).build()

        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("help", self._cmd_help))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._on_message))

        self._app.run_polling(close_loop=False)

    def _is_authorized(self, update: Update) -> bool:
        if not self.settings.telegram_allowed_chat_id:
            return True  # se não configurado restrição, responde (sugere configurar no .env)
        user_id = str(update.effective_chat.id)
        return user_id == str(self.settings.telegram_allowed_chat_id)

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        msg = (
            f"👋 Olá! Sou seu Assistente/Jarvis.\n"
            f"Seu Chat ID é: `{chat_id}` (adicione no `.env` como TELEGRAM_ALLOWED_CHAT_ID para segurança).\n\n"
            f"Você pode me enviar mensagens de texto ou comandos para controlar seu PC remotamente!"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = (
            "🤖 *Comandos suportados:*\n"
            "- 'pause' ou 'play': Alterna música no PC\n"
            "- 'next' ou 'proxima': Próxima faixa\n"
            "- 'volume 40': Define volume para 40%\n"
            "- 'lembrete X min': Agenda lembrete\n"
            "- Ou converse normalmente para tirar dúvidas de T.I.!"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        vol = self.brain.media.get_volume()
        muted = self.brain.media.is_muted()
        await update.message.reply_text(f"🖥️ PC Online\nVolume: {vol}% (Mudo: {muted})")

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Acesso não autorizado.")
            return

        user_text = update.message.text
        # Notifica visualmente o Pet no Desktop sobre a mensagem recebida
        if self.on_notify_desktop:
            self.on_notify_desktop(f"📱 Telegram: {user_text[:28]}...")

        # Processa através do Cérebro (Gemini / ferramentas do sistema)
        result = self.brain.process_command(user_text)
        reply = result.get("message", "Comando processado.")
        await update.message.reply_text(reply)

