"""Módulo de integração com Telegram Bot para envio/recebimento de comandos remotos (Mobile)."""
from __future__ import annotations

import asyncio
import threading
import time
from typing import TYPE_CHECKING, Callable

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from assistente.ai.brain import AssistantBrain
from assistente.config import Settings
from assistente.network.routing import parse_target

if TYPE_CHECKING:
    from assistente.network.server import ThreadedHub


class TelegramBridge:
    def __init__(
        self,
        settings: Settings,
        brain: AssistantBrain,
        on_notify_desktop: Callable[[str], None] | None = None,
        hub: "ThreadedHub | None" = None,
    ) -> None:
        self.settings = settings
        self.brain = brain
        self.on_notify_desktop = on_notify_desktop
        self.hub = hub
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
        self._app.add_handler(CommandHandler("nodes", self._cmd_nodes))
        self._app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._on_message))

        self._app.run_polling(close_loop=False, stop_signals=None)

    def _is_authorized(self, update: Update) -> bool:
        # Com controle remoto de máquinas via internet, sem chat ID configurado ninguém é autorizado.
        if not self.settings.telegram_allowed_chat_id:
            return False
        user_id = str(update.effective_chat.id)
        return user_id == str(self.settings.telegram_allowed_chat_id)

    async def _deny(self, update: Update) -> None:
        await update.message.reply_text(
            "⛔ Acesso não autorizado. Use /start para ver seu Chat ID e configure TELEGRAM_ALLOWED_CHAT_ID."
        )

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        msg = (
            f"👋 Olá! Sou a Cecília, sua assistente.\n\n"
            f"Seu Chat ID é: {chat_id}\n\n"
            f"(adicione no .env como TELEGRAM_ALLOWED_CHAT_ID para segurança).\n\n"
            f"Você pode me enviar mensagens de texto ou comandos para controlar seu PC remotamente!"
        )
        await update.message.reply_text(msg)

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = (
            "🤖 *Comandos suportados:*\n"
            "- 'pause' ou 'play': Alterna música no PC\n"
            "- 'next' ou 'proxima': Próxima faixa\n"
            "- 'volume 40': Define volume para 40%\n"
            "- 'lembrete X min': Agenda lembrete\n"
            "- /nodes: Lista máquinas conectadas\n"
            "- '@notebook pause': Envia o comando para a máquina 'notebook'\n"
            "- Ou converse normalmente para tirar dúvidas de T.I.!"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return await self._deny(update)
        vol = self.brain.media.get_volume()
        muted = self.brain.media.is_muted()
        await update.message.reply_text(
            f"🖥️ {self.settings.node_id} Online\nVolume: {vol}% (Mudo: {muted})"
        )

    async def _cmd_nodes(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return await self._deny(update)
        lines = [f"🟢 *{self.settings.node_id}* (este Hub/local)"]
        if self.hub:
            now = time.time()
            for n in self.hub.nodes().values():
                lines.append(f"🟢 *{n.node_id}* — {n.hostname} (visto há {int(now - n.last_seen)}s)")
        else:
            lines.append("_Hub desativado (CECILIA_MODE=standalone)_")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return await self._deny(update)

        target, user_text = parse_target(update.message.text)
        if not user_text:
            await update.message.reply_text("Diga o comando após o nome da máquina. Ex: @notebook pause")
            return

        if target and target != self.settings.node_id:
            await update.message.reply_text(await self._dispatch_remote(target, user_text))
            return

        # Notifica visualmente o Pet no Desktop sobre a mensagem recebida
        if self.on_notify_desktop:
            self.on_notify_desktop(f"📱 Telegram: {user_text[:28]}...")

        # Processa através do Cérebro (Gemini / ferramentas do sistema) sem travar o loop do bot
        result = await asyncio.to_thread(self.brain.process_command, user_text)
        reply = result.get("message", "Comando processado.")
        await update.message.reply_text(reply)

    async def _dispatch_remote(self, target: str, text: str) -> str:
        from assistente.network.server import NodeNotFound

        if not self.hub:
            return "⚠️ Hub desativado. Inicie com CECILIA_MODE=hub para controlar outras máquinas."
        try:
            res = await self.hub.dispatch(target, "prompt", {"text": text}, timeout=60)
        except NodeNotFound:
            online = ", ".join(self.hub.nodes()) or "nenhum"
            return f"❌ Máquina '{target}' offline. Online: {online}"
        except (asyncio.TimeoutError, TimeoutError):
            return f"⏱️ '{target}' não respondeu a tempo."
        if not res.ok:
            return f"❌ [{target}] {res.payload.get('error', 'erro desconhecido')}"
        return f"[{target}] {res.payload.get('message', 'Comando processado.')}"
