"""Geometria do desktop virtual (todos os monitores) para colisão do pet.

Trabalha com a lista de ``availableGeometry`` de cada tela (já exclui a barra
de tarefas). A área "sólida" é a UNIÃO desses retângulos — assim o pet circula
entre monitores lado a lado e não cai em "buracos" quando os monitores têm
alturas ou alinhamentos diferentes.
"""
from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication


def available_areas() -> list[QRect]:
    return [s.availableGeometry() for s in QGuiApplication.screens()]


def contains(areas: list[QRect], x: float, y: float) -> bool:
    """O ponto (x, y) está dentro de alguma área visível?"""
    xi, yi = int(x), int(y)
    return any(a.contains(xi, yi) for a in areas)


def floor_y(areas: list[QRect], cx: float, bottom: float, h: int) -> float | None:
    """Y (topo da janela) em que o pet "pousa" na coluna ``cx``.

    Escolhe o piso da área imediatamente abaixo do pet nessa coluna
    (suporta monitores empilhados). ``None`` = coluna fora de qualquer tela.
    """
    cands = [a for a in areas if a.left() <= cx <= a.right()]
    if not cands:
        return None
    below = [a for a in cands if a.bottom() >= bottom - 1]
    area = min(below, key=QRect.bottom) if below else max(cands, key=QRect.bottom)
    return area.bottom() + 1 - h


def clamp_into_desktop(areas: list[QRect], x: float, y: float, w: int, h: int) -> tuple[float, float]:
    """Se o centro do pet estiver fora de todas as telas, traz para a mais próxima."""
    cx, cy = x + w / 2, y + h / 2
    if contains(areas, cx, cy) or not areas:
        return x, y

    def dist(a: QRect) -> float:
        dx = max(a.left() - cx, 0, cx - a.right())
        dy = max(a.top() - cy, 0, cy - a.bottom())
        return dx * dx + dy * dy

    a = min(areas, key=dist)
    x = min(max(x, a.left()), a.right() + 1 - w)
    y = min(max(y, a.top()), a.bottom() + 1 - h)
    return x, y

