"""Cérebro IA (Gemini) do Assistente/Jarvis.

Interpreta comandos em linguagem natural (vindos do Telegram ou de prompts locais),
decide se executa ações no sistema (mídia, lembrete, apps) e gera respostas rápidas de T.I.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from google import genai
from google.genai import types

from assistente.config import Settings
from assistente.media.controller import MediaController
from assistente.system.tools import SystemTools
from assistente.tasks.scheduler import TaskScheduler


class AssistantBrain:
    def __init__(self, settings: Settings, media: MediaController, scheduler: TaskScheduler) -> None:
        self.settings = settings
        self.media = media
        self.scheduler = scheduler
        self.client: genai.Client | None = None
        if settings.gemini_api_key:
            try:
                self.client = genai.Client(api_key=settings.gemini_api_key)
            except Exception:
                self.client = None

    def process_command(self, user_prompt: str) -> dict[str, Any]:
        """Interpreta e executa um comando em linguagem natural."""
        # Se não houver chave de API configurada, utiliza parser heurístico local
        if not self.client:
            return self._fallback_local_command(user_prompt)

        system_instruction = (
            "Você é o Jarvis/Sexta-Feira, um assistente pessoal e de suporte de T.I. "
            "Você pode responder dúvidas técnicas, sugerir comandos e também disparar ações locais no PC. "
            "Se o usuário pedir para controlar som, música ou agendar lembrete, acione a ferramenta correspondente."
        )

        tools = [
            types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name="control_media",
                    description="Controla o player de mídia do Windows (play, pause, next, prev, stop)",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "action": types.Schema(type="STRING", enum=["play_pause", "next", "previous", "stop"])
                        },
                        required=["action"]
                    )
                ),
                types.FunctionDeclaration(
                    name="set_volume",
                    description="Define o volume do PC (0 a 100)",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "percent": types.Schema(type="INTEGER")
                        },
                        required=["percent"]
                    )
                ),
                types.FunctionDeclaration(
                    name="schedule_reminder",
                    description="Agenda um lembrete/alarme para daqui a X minutos ou horário específico",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "title": types.Schema(type="STRING"),
                            "minutes_from_now": types.Schema(type="INTEGER")
                        },
                        required=["title", "minutes_from_now"]
                    )
                ),
                types.FunctionDeclaration(
                    name="get_system_metrics",
                    description="Obtém uso atual de CPU, memória RAM, disco e uptime do PC",
                    parameters=types.Schema(type="OBJECT", properties={})
                ),
                types.FunctionDeclaration(
                    name="open_app",
                    description="Abre um aplicativo no computador (ex: terminal, vscode, calculadora, notepad)",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "app_name": types.Schema(type="STRING")
                        },
                        required=["app_name"]
                    )
                ),
                types.FunctionDeclaration(
                    name="lock_pc",
                    description="Bloqueia a tela do Windows por segurança",
                    parameters=types.Schema(type="OBJECT", properties={})
                )
            ])
        ]

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=tools,
                )
            )

            # Processa function call se o Gemini decidiu acionar ferramentas
            if response.function_calls:
                fc = response.function_calls[0]
                return self._execute_tool_call(fc.name, fc.args)

            return {"action": "reply", "message": response.text}

        except Exception as e:
            return {"action": "error", "message": f"Erro na IA: {e}"}

    def _execute_tool_call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "control_media":
            act = args.get("action", "play_pause")
            if act == "play_pause": self.media.play_pause()
            elif act == "next": self.media.next_track()
            elif act == "previous": self.media.previous_track()
            elif act == "stop": self.media.stop()
            return {"action": "media", "message": f"Mídia executada: {act}"}

        elif name == "set_volume":
            pct = int(args.get("percent", 50))
            self.media.set_volume(pct)
            return {"action": "volume", "message": f"Volume ajustado para {pct}%"}

        elif name == "schedule_reminder":
            title = args.get("title", "Lembrete")
            mins = int(args.get("minutes_from_now", 5))
            run_at = datetime.now() + timedelta(minutes=mins)
            self.scheduler.schedule_reminder(title, run_at)
            return {"action": "reminder", "message": f"Lembrete '{title}' agendado para daqui a {mins} min"}

        elif name == "get_system_metrics":
            m = SystemTools.get_system_metrics()
            msg = (
                f"📊 CPU: {m['cpu_percent']} | RAM: {m['ram_used_gb']}/{m['ram_total_gb']} ({m['ram_percent']}) | "
                f"Disco C Livre: {m['disk_free_gb']}"
            )
            return {"action": "metrics", "message": msg}

        elif name == "open_app":
            app = args.get("app_name", "")
            res = SystemTools.open_application(app)
            return {"action": "app", "message": res.get("message", f"Executado: {app}")}

        elif name == "lock_pc":
            SystemTools.lock_workstation()
            return {"action": "lock", "message": "PC Bloqueado com sucesso."}

        return {"action": "unknown", "message": "Ação não reconhecida."}

    def _fallback_local_command(self, text: str) -> dict[str, Any]:
        """Comandos diretos offline sem precisar do Gemini."""
        t = text.lower().strip()
        if "pause" in t or "play" in t:
            self.media.play_pause()
            return {"action": "media", "message": "Play/Pause acionado."}
        if "proxima" in t or "próxima" in t or "next" in t:
            self.media.next_track()
            return {"action": "media", "message": "Próxima faixa acionada."}
        if "voltar" in t or "anterior" in t or "prev" in t:
            self.media.previous_track()
            return {"action": "media", "message": "Faixa anterior acionada."}
        if "status" in t or "hardware" in t or "metricas" in t or "cpu" in t or "ram" in t:
            m = SystemTools.get_system_metrics()
            return {
                "action": "metrics",
                "message": f"📊 CPU: {m['cpu_percent']} | RAM: {m['ram_used_gb']}/{m['ram_total_gb']} ({m['ram_percent']}) | Disco C Livre: {m['disk_free_gb']}"
            }
        if "bloquear" in t or "lock" in t:
            SystemTools.lock_workstation()
            return {"action": "lock", "message": "PC Bloqueado com sucesso."}
        if "volume" in t:
            words = t.split()
            for w in words:
                if w.isdigit():
                    val = int(w)
                    self.media.set_volume(val)
                    return {"action": "volume", "message": f"Volume alterado para {val}%"}
        return {
            "action": "reply",
            "message": "Comando recebido. (Dica: Adicione GEMINI_API_KEY no .env para suporte avançado de IA)."
        }

