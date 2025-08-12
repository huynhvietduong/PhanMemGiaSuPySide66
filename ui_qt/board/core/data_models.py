from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
from PySide6.QtGui import QImage

# Nét/hình vẽ trên lớp mực (ink); ảnh nằm lớp riêng.
@dataclass
class Stroke:
    t: str                                  # "line" | "rect" | "oval" | "poly"
    points: List[Tuple[float, float]] | None
    rgba: Tuple[int, int, int, int]
    width: int
    mode: str = "pen"                        # "pen" | "eraser"

@dataclass
class Img:
    qimage: QImage
    x: int
    y: int
    w: int
    h: int
