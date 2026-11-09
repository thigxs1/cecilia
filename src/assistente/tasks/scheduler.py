"""Agendador de alarmes e lembretes com sons nativos do Windows."""
from __future__ import annotations

import winsound
from datetime import datetime
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from assistente.tasks.storage import TaskItem, TaskStorage


class TaskScheduler:
    def __init__(self, on_trigger: Callable[[TaskItem], None] | None = None) -> None:
        self.storage = TaskStorage()
        self.on_trigger = on_trigger
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self._load_pending_jobs()

    def _load_pending_jobs(self) -> None:
        pending = self.storage.list_pending()
        now = datetime.now()
        for item in pending:
            try:
                run_time = datetime.fromisoformat(item.remind_at)
                if run_time > now:
                    self._schedule_job(item, run_time)
            except Exception:
                pass

    def _schedule_job(self, item: TaskItem, run_time: datetime) -> None:
        job_id = f"task_{item.id}"
        self.scheduler.add_job(
            func=self._execute_trigger,
            trigger=DateTrigger(run_date=run_time),
            args=[item],
            id=job_id,
            replace_existing=True,
        )

    def _execute_trigger(self, item: TaskItem) -> None:
        # Toca sinal sonoro nativo do Windows (sem dependências pesadas de codec)
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

        self.storage.mark_done(item.id)

        if self.on_trigger:
            self.on_trigger(item)

    def schedule_reminder(self, title: str, remind_at: datetime) -> TaskItem:
        item = self.storage.add_task(title, remind_at)
        self._schedule_job(item, remind_at)
        return item

    def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)

