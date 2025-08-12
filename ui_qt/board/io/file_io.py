from __future__ import annotations
import json, base64
from typing import List, Dict, Tuple
from PySide6 import QtCore, QtGui
from PySide6.QtGui import QImage
from ui_qt.board.core.data_models import Stroke, Img

def to_dict(pages: List[Dict[str, list]], meta: Dict[str, str]) -> dict:
    data = {"version": 2, "meta": dict(meta or {}), "pages": []}
    for p in pages:
        strokes = [{"type": s.t, "points": s.points, "rgba": list(s.rgba),
                    "width": s.width, "mode": s.mode} for s in p["strokes"]]
        images = {}
        for idx, im in enumerate(p["images"]):
            buf = QtCore.QBuffer(); buf.open(QtCore.QIODevice.WriteOnly)
            im.qimage.save(buf, "PNG")
            images[str(idx)] = {"x": im.x, "y": im.y, "w": im.w, "h": im.h,
                                "fmt": "png", "b64": base64.b64encode(bytes(buf.data())).decode("ascii")}
        data["pages"].append({"strokes": strokes, "images": images})
    return data

def from_dict(data: dict) -> List[Dict[str, list]]:
    pages: List[Dict[str, list]] = []
    for page in data.get("pages", []):
        strokes: List[Stroke] = []
        for s in page.get("strokes", []):
            strokes.append(Stroke(
                t=s.get("type","line"),
                points=[tuple(pt) for pt in s.get("points", [])],
                rgba=tuple(s.get("rgba", [0,0,0,255])),
                width=int(s.get("width", 3)),
                mode=s.get("mode", "pen"),
            ))
        images: List[Img] = []
        imgs = page.get("images", {})
        if isinstance(imgs, dict):
            items = sorted(imgs.items(), key=lambda x:int(x[0]))
            for _, im in items:
                b = base64.b64decode(im.get("b64",""))
                qimg = QImage.fromData(b, "PNG")
                images.append(Img(qimage=qimg,
                                  x=int(im.get("x",0)), y=int(im.get("y",0)),
                                  w=int(im.get("w", qimg.width())),
                                  h=int(im.get("h", qimg.height()))))
        pages.append({"strokes": strokes, "images": images})
    return pages

def save_json(path: str, pages: List[Dict[str, list]], meta: Dict[str, str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_dict(pages, meta), f, ensure_ascii=False, indent=2)

def load_json(path: str) -> Tuple[List[Dict[str, list]], Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    pages = from_dict(data)
    meta = data.get("meta", {})
    return pages, meta
