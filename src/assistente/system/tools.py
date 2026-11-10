"""Módulo de ferramentas de automação e suporte do sistema operacional (T.I.).

Funções prontas para chamadas locais, pelo Gemini (Function Calling) ou via MCP.
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from typing import Any

import psutil


class SystemTools:
    @staticmethod
    def get_system_metrics() -> dict[str, Any]:
        """Retorna uso de CPU, Memória RAM, Disco e Uptime da máquina."""
        cpu_pct = psutil.cpu_percent(interval=0.2)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%d/%m/%Y %H:%M:%S")

        return {
            "cpu_percent": f"{cpu_pct}%",
            "ram_used_gb": f"{ram.used / (1024**3):.1f} GB",
            "ram_total_gb": f"{ram.total / (1024**3):.1f} GB",
            "ram_percent": f"{ram.percent}%",
            "disk_free_gb": f"{disk.free / (1024**3):.1f} GB",
            "boot_time": boot_time,
        }

    @staticmethod
    def open_application(app_name: str) -> dict[str, str]:
        """Abre aplicativos comuns ou comandos do sistema no Windows."""
        alias_map = {
            "terminal": "wt.exe",
            "powershell": "powershell.exe",
            "cmd": "cmd.exe",
            "vscode": "code",
            "calculadora": "calc.exe",
            "notepad": "notepad.exe",
            "bloco de notas": "notepad.exe",
            "gerenciador de tarefas": "taskmgr.exe",
            "taskmgr": "taskmgr.exe",
            "navegador": "start msedge",
        }
        target = alias_map.get(app_name.lower().strip(), app_name)
        try:
            if target.startswith("start "):
                os.system(target)
            else:
                subprocess.Popen(target, shell=True)
            return {"status": "success", "message": f"Iniciando {app_name}..."}
        except Exception as e:
            return {"status": "error", "message": f"Falha ao abrir {app_name}: {e}"}

    @staticmethod
    def lock_workstation() -> dict[str, str]:
        """Bloqueia a tela da estação de trabalho (Windows + L)."""
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return {"status": "success", "message": "Estação de trabalho bloqueada."}

