"""
mem_cell.py — مكوّن خلايا الذاكرة البصري (نسخة مُصلحة v2)
============================================================

الإصلاحات الإضافية في هذه النسخة:
  ✓ إصلاح تكرار خلية y عند undo — بحفظ snapshot قُبيل remove مباشرةً
  ✓ إصلاح القيمة الخاطئة عند undo — الـ snapshot يحمل القيمة الحالية
  ✓ إزالة _y_pos الثابت واستبداله بـ _y_snapshot ديناميكي
  ✓ كل إصلاحات النسخة الأولى محفوظة
"""

from __future__ import annotations
import random
from typing import Optional

import numpy as np
from manimlib import (
    Scene, VGroup, Rectangle, RoundedRectangle,
    Circle, CurvedArrow, Text, TAU, LEFT, RIGHT,
)

# ═══════════════════════════════════════════════════════
#  PALETTE
# ═══════════════════════════════════════════════════════
COL = dict(
    bg       = "#141728",
    bg_freed = "#3a0808",
    bg_heap  = "#0e3d22",
    border   = "#2e3566",
    ptr      = "#b06cf4",
    heap     = "#f49836",
    freed    = "#f05555",
    header   = "#0e1020",
    name_var  = "#38d9f5",
    name_ptr  = "#b06cf4",
    name_heap = "#f49836",
    val_var  = "#eef0fa",
    val_ptr  = "#f5c842",
    val_null = "#4a5070",
    val_edit = "#f5c842",
    addr     = "#4a5070",
    flash    = "#f5c842",
    dark     = "#252840",
    white    = "#eef0fa",
    grey     = "#8890b8",
)

FONT   = "Consolas"
CELL_W = 1.20
CELL_H = 1.00


# ═══════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════
def v3(x, y):
    return np.array([x, y, 0.], dtype=float)


def _lbl(s, sz=0.28, col=COL["white"]):
    return Text(s, color=col, font=FONT).scale(sz)


def _rm(scene, mob):
    if mob is not None:
        try:
            if mob in scene.mobjects:
                scene.remove(mob)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════
#  CELL GRID
# ═══════════════════════════════════════════════════════
class CellGrid:
    def __init__(self, scene: Scene,
                 vis_l: float, vis_r: float,
                 vis_t: float, vis_b: float,
                 cols: int = 3, rows: int = 4,
                 shuffle: bool = True,
                 pad_t: float = 0.46, pad_b: float = 0.10):
        self.scene = scene
        self.vis_l = vis_l;  self.vis_r = vis_r
        self.vis_t = vis_t;  self.vis_b = vis_b
        self.cols  = cols;   self.rows  = rows
        self.pad_t = pad_t;  self.pad_b = pad_b
        self.shuffle = shuffle
        self._build()

    def _build(self):
        l  = self.vis_l;  r  = self.vis_r
        t  = self.vis_t - self.pad_t
        b  = self.vis_b + self.pad_b
        cw = (r - l) / self.cols
        ch = (t - b) / self.rows
        self._pos  = [
            (l + cw * (c + 0.5), t - ch * (row + 0.5))
            for row in range(self.rows)
            for c   in range(self.cols)
        ]
        if self.shuffle:
            random.shuffle(self._pos)
        self._used = [False] * len(self._pos)

    def rebuild(self):
        self._build()

    def alloc(self) -> tuple[float, float]:
        free = [i for i, u in enumerate(self._used) if not u]
        if not free:
            return self._pos[0]
        i = random.choice(free)
        self._used[i] = True
        return self._pos[i]

    def alloc_at(self, cx: float, cy: float) -> tuple[float, float]:
        """
        حجز موضع محدد (أقرب نقطة في الشبكة) — يُستخدم عند undo.
        إذا كان الموضع محجوزاً بالفعل، يُعيده كما هو (الخلية القديمة أُزيلت).
        """
        best_i = 0
        best_d = float("inf")
        for i, (px, py) in enumerate(self._pos):
            d = abs(px - cx) + abs(py - cy)
            if d < best_d:
                best_d = d
                best_i = i
        self._used[best_i] = True
        return self._pos[best_i]

    def release(self, cx: float, cy: float):
        for i, (px, py) in enumerate(self._pos):
            if abs(px - cx) < 0.15 and abs(py - cy) < 0.15:
                self._used[i] = False
                return


# ═══════════════════════════════════════════════════════
#  MEM CELL
# ═══════════════════════════════════════════════════════
class MemCell:
    def __init__(self, scene: Scene,
                 name: str, addr: str, value: str,
                 cx: float, cy: float,
                 kind: str = "var",
                 w: float = CELL_W, h: float = CELL_H):
        self.scene  = scene
        self.name   = name
        self.addr   = addr
        self.value  = value
        self.cx, self.cy = cx, cy
        self.kind   = kind
        self.W, self.H   = w, h
        self.freed  = False
        self._vmob  = None
        self.bg     = None
        self.group  = None
        self._build()
        scene.add(self.group)

    def _build(self):
        brd = self._border_col()
        sw  = 2.2 if self.kind == "ptr" else 1.8

        self.bg = RoundedRectangle(corner_radius=0.10,
                                   width=self.W, height=self.H)
        self.bg.set_fill(COL["bg"], 1.0).set_stroke(brd, width=sw)
        self.bg.move_to(v3(self.cx, self.cy))

        stripe = RoundedRectangle(corner_radius=0.06,
                                  width=self.W - 0.04, height=0.24)
        stripe.set_fill(COL["header"], 1.0).set_stroke(brd, width=0.6)
        stripe.move_to(v3(self.cx, self.cy + self.H/2 - 0.13))

        nc = COL[f"name_{self.kind}"]
        nt = _lbl(self.name, 0.20, nc)
        nt.move_to(stripe.get_center())

        self._vmob = _lbl(self.value, 0.27, self._val_col())
        self._vmob.move_to(v3(self.cx, self.cy - 0.02))

        am = _lbl(self.addr, 0.15, COL["addr"])
        am.move_to(v3(self.cx, self.cy - self.H/2 + 0.10))

        self.group = VGroup(self.bg, stripe, nt, self._vmob, am)

    def _border_col(self):
        if self.freed:          return COL["freed"]
        if self.kind == "ptr":  return COL["ptr"]
        if self.kind == "heap": return COL["heap"]
        return COL["border"]

    def _val_col(self):
        if self.freed: return COL["freed"]
        if self.kind == "ptr": return COL["val_ptr"]
        return COL["val_var"]

    def set_value(self, v: str, col: str | None = None):
        self.value = v
        col = col or self._val_col()
        _rm(self.scene, self._vmob)
        try:
            self.group.remove(self._vmob)
        except Exception:
            pass
        self._vmob = _lbl(v, 0.27, col)
        self._vmob.move_to(v3(self.cx, self.cy - 0.02))
        self.group.add(self._vmob)
        self.scene.add(self._vmob)

    def flash(self, col: str = COL["flash"], duration: float = 0.07):
        orig = self._border_col()
        sw   = 2.2 if self.kind == "ptr" else 1.8
        self.bg.set_stroke(col, width=4.0)
        self.scene.update_frame(duration)
        self.bg.set_stroke(orig, width=sw)

    def mark_freed(self):
        self.freed = True
        self.bg.set_fill(COL["bg_freed"], 1.0)
        self.bg.set_stroke(COL["freed"], width=2.0)
        self.set_value("FREED", COL["freed"])

    def mark_allocated(self):
        self.freed = False
        self.bg.set_fill(COL["bg_heap"], 1.0)
        self.bg.set_stroke(COL["heap"], width=2.0)

    def null_ptr(self):
        self.bg.set_stroke(COL["border"], width=1.6)
        self.set_value("NULL", COL["val_null"])

    def restore(self, v: str):
        self.freed = False
        brd = self._border_col()
        self.bg.set_fill(COL["bg"], 1.0)
        self.bg.set_stroke(brd, width=2.2 if self.kind == "ptr" else 1.8)
        self.set_value(v, self._val_col())

    def move_to(self, cx: float, cy: float):
        self.group.shift(v3(cx - self.cx, cy - self.cy))
        self.cx, self.cy = cx, cy

    def remove(self):
        _rm(self.scene, self.group)

    def top(self): return v3(self.cx, self.cy + self.H/2)
    def bot(self): return v3(self.cx, self.cy - self.H/2)
    def lft(self): return v3(self.cx - self.W/2, self.cy)
    def rgt(self): return v3(self.cx + self.W/2, self.cy)
    def ctr(self): return v3(self.cx, self.cy - 0.02)

    def hit(self, pt) -> bool:
        return (abs(pt[0] - self.cx) < self.W/2 and
                abs(pt[1] - self.cy) < self.H/2)

    def hit_value(self, pt) -> bool:
        return (abs(pt[0] - self.cx)        < self.W/2 - 0.05 and
                abs(pt[1] - (self.cy-0.02)) < 0.22)


# ═══════════════════════════════════════════════════════
#  PTR ARROW
# ═══════════════════════════════════════════════════════
class PtrArrow:
    GAP = 0.06

    def __init__(self, scene: Scene, src: MemCell, dst: MemCell):
        self.scene = scene
        self.src   = src
        self.dst   = dst
        self.mob   = None
        self._draw()

    def _endpoints(self):
        sx, sy = self.src.cx, self.src.cy
        dx, dy = self.dst.cx, self.dst.cy
        g  = self.GAP
        SW, SH = self.src.W/2, self.src.H/2
        DW, DH = self.dst.W/2, self.dst.H/2
        ddx, ddy = dx - sx, dy - sy

        if abs(ddx) >= abs(ddy):
            if ddx >= 0:
                s = v3(sx+SW+g, sy);  e = v3(dx-DW-g, dy)
                a = TAU/12 if ddy > 0.3 else (-TAU/12 if ddy < -0.3 else 0.)
            else:
                s = v3(sx-SW-g, sy);  e = v3(dx+DW+g, dy)
                a = -TAU/12 if ddy > 0.3 else (TAU/12 if ddy < -0.3 else 0.)
        else:
            if ddy >= 0:
                s = v3(sx, sy+SH+g);  e = v3(dx, dy-DH-g)
                a = -TAU/10 if ddx > 0.3 else (TAU/10 if ddx < -0.3 else 0.)
            else:
                s = v3(sx, sy-SH-g);  e = v3(dx, dy+DH+g)
                a = TAU/10 if ddx > 0.3 else (-TAU/10 if ddx < -0.3 else 0.)

        if abs(ddx) < 0.1 and abs(ddy) < 0.1:
            s = v3(sx+SW+g, sy+SH*0.3)
            e = v3(dx+DW+g, dy-DH*0.3)
            a = -TAU/4

        return s, e, a

    def _draw(self):
        _rm(self.scene, self.mob)
        s, e, a = self._endpoints()
        self.mob = CurvedArrow(s, e,
                               color=COL["ptr"],
                               stroke_width=2.4,
                               angle=a)
        self.scene.add(self.mob)

    def refresh(self):
        self._draw()

    def set_color(self, col: str):
        if self.mob:
            self.mob.set_stroke(col, width=2.4)

    def remove(self):
        _rm(self.scene, self.mob)
        self.mob = None


# ═══════════════════════════════════════════════════════
#  MEM SYS
# ═══════════════════════════════════════════════════════
class MemSys:
    def __init__(self, scene: Scene, grid: CellGrid | None = None):
        self.scene    = scene
        self.grid     = grid
        self.cells:   dict[str, MemCell]  = {}
        self.arrows:  dict[str, PtrArrow] = {}

        self._drag_cell: MemCell | None = None
        self._drag_off   = [0.0, 0.0]

        self._edit_cell: MemCell | None = None
        self._edit_buf   = ""
        self._edit_box   = None
        self._edit_txt   = None

    def hook_text(self):
        pass

    def add(self, name: str, addr: str, value: str,
            kind: str = "var",
            cx: float | None = None, cy: float | None = None,
            target: str | None = None) -> MemCell:
        """إضافة خلية عبر الـ grid (الطريقة العادية)."""
        # منع التكرار: إزالة الخلية القديمة إن وجدت
        if name in self.cells:
            self.remove(name)

        if cx is None or cy is None:
            if self.grid is None:
                raise ValueError("أعطِ cx/cy أو مرّر CellGrid عند البناء")
            cx, cy = self.grid.alloc()
        else:
            # موضع محدد صريح — سجّله في الـ grid لتجنب التعارض
            if self.grid is not None:
                self.grid.alloc_at(cx, cy)
            # نُبقي cx/cy كما هما بالضبط بدون تعديل

        cell = MemCell(self.scene, name, addr, value, cx, cy, kind=kind)
        self.cells[name] = cell
        cell.flash()

        if kind == "ptr" and target and target in self.cells:
            self._make_arrow(name, target)
            if self.cells[target].kind == "heap":
                self.cells[target].mark_allocated()

        return cell

    def add_raw(self, name: str, addr: str, value: str,
                cx: float, cy: float,
                kind: str = "var") -> MemCell:
        """
        إضافة خلية في موضع حرفي دقيق — بدون تعديل الـ grid.
        تُستخدم حصراً في عمليات undo لاستعادة الخلية لمكانها الأصلي.
        """
        # تأكد من إزالة أي نسخة قديمة من المشهد أولاً
        if name in self.cells:
            old = self.cells.pop(name)
            # لا نُحرّر الموضع في الـ grid (alloc_at سجّله مسبقاً)
            for k in [k for k, a in list(self.arrows.items())
                      if a.src is old or a.dst is old]:
                self.arrows[k].remove()
                del self.arrows[k]
            old.remove()

        cell = MemCell(self.scene, name, addr, value, cx, cy, kind=kind)
        self.cells[name] = cell
        return cell

    def update(self, name: str, value: str,
               col: str | None = None, flash: bool = True):
        c = self.cells.get(name)
        if not c: return
        if flash: c.flash()
        c.set_value(value, col)
        if c.kind == "ptr":
            self._refresh_ptr_arrows(name, value)

    def free(self, name: str):
        c = self.cells.get(name)
        if not c: return
        c.mark_freed()
        for arr in self.arrows.values():
            if arr.dst is c:
                arr.set_color(COL["freed"])

    def null_ptr(self, name: str):
        c = self.cells.get(name)
        if not c: return
        for k in [k for k in self.arrows if k.startswith(name + "->")]:
            self.arrows[k].remove()
            del self.arrows[k]
        c.null_ptr()

    def add_arrow(self, src_name: str, dst_name: str):
        if src_name not in self.cells or dst_name not in self.cells:
            return
        self._make_arrow(src_name, dst_name)

    def remove(self, name: str):
        c = self.cells.pop(name, None)
        if not c: return
        if self.grid:
            self.grid.release(c.cx, c.cy)
        for k in [k for k, a in list(self.arrows.items())
                  if a.src is c or a.dst is c]:
            self.arrows[k].remove()
            del self.arrows[k]
        c.remove()

    def clear(self):
        for a in list(self.arrows.values()): a.remove()
        self.arrows.clear()
        for c in list(self.cells.values()): c.remove()
        self.cells.clear()
        self._cancel_edit()
        if self.grid: self.grid.rebuild()

    def move(self, name: str, cx: float, cy: float):
        c = self.cells.get(name)
        if not c: return
        c.move_to(cx, cy)
        self._refresh_arrows_for(name)

    def cell(self, name: str) -> MemCell | None:
        return self.cells.get(name)

    def snapshot(self, name: str) -> dict | None:
        """إرجاع نسخة من بيانات الخلية الحالية (للاستخدام قبل remove)"""
        c = self.cells.get(name)
        if not c:
            return None
        return {"cx": c.cx, "cy": c.cy, "value": c.value,
                "addr": c.addr, "kind": c.kind}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  معالجات التفاعل
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def handle_drag(self, pt) -> bool:
        if self._drag_cell is not None:
            pt = np.array(pt, dtype=float)
            if len(pt) == 2:
                pt = np.array([pt[0], pt[1], 0.], dtype=float)
            nx = pt[0] - self._drag_off[0]
            ny = pt[1] - self._drag_off[1]
            if abs(nx) < 9.0 and abs(ny) < 6.0:
                self._drag_cell.move_to(nx, ny)
                self._refresh_arrows_for(self._drag_cell.name)
            return True
        return False

    def handle_press(self, pt) -> bool:
        pt = np.array(pt, dtype=float)
        if len(pt) == 2:
            pt = np.array([pt[0], pt[1], 0.], dtype=float)

        if self._edit_cell is not None:
            if not self._edit_cell.hit(pt):
                self._commit_edit()
            return True

        for c in self.cells.values():
            if c.hit_value(pt):
                self._start_edit(c)
                return True

        for c in self.cells.values():
            if c.hit(pt):
                self._drag_cell = c
                self._drag_off  = [pt[0] - c.cx, pt[1] - c.cy]
                return True

        return False

    def handle_release(self):
        self._drag_cell = None

    def handle_text(self, ch: str) -> bool:
        if self._edit_cell is None: return False
        if ch.isprintable():
            self._edit_buf += ch
            self._draw_edit()
        return True

    def handle_key(self, sym) -> bool:
        import pyglet.window.key as K

        if self._edit_cell is None:
            return False

        if sym in (K.RETURN, K.NUM_ENTER):
            self._commit_edit()
        elif sym == K.ESCAPE:
            self._cancel_edit()
        elif sym == K.BACKSPACE:
            self._edit_buf = self._edit_buf[:-1]
            self._draw_edit()
        else:
            try:
                ch = chr(sym)
                if ch.isprintable():
                    self._edit_buf += ch
                    self._draw_edit()
            except (ValueError, OverflowError):
                pass

        return True

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  داخلي
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _make_arrow(self, src_name: str, dst_name: str):
        key = f"{src_name}->{dst_name}"
        if key in self.arrows: return
        s = self.cells.get(src_name)
        d = self.cells.get(dst_name)
        if s and d:
            self.arrows[key] = PtrArrow(self.scene, s, d)

    def _remove_arrows_from(self, src_name: str):
        for k in [k for k in list(self.arrows) if k.startswith(src_name + "->")]:
            self.arrows[k].remove()
            del self.arrows[k]

    def _refresh_arrows_for(self, name: str):
        for arr in self.arrows.values():
            if arr.src.name == name or arr.dst.name == name:
                arr.refresh()

    def _refresh_ptr_arrows(self, ptr_name: str, new_val: str):
        self._remove_arrows_from(ptr_name)
        val = new_val.strip().lower()
        if val in ("null", "0", ""):
            return
        for tgt_name, tgt in self.cells.items():
            if tgt.addr.lower() == val:
                self._make_arrow(ptr_name, tgt_name)
                break

    def _start_edit(self, cell: MemCell):
        self._cancel_edit()
        self._edit_cell = cell
        self._edit_buf  = ""
        self._draw_edit()

    def _draw_edit(self):
        _rm(self.scene, self._edit_box)
        _rm(self.scene, self._edit_txt)
        c = self._edit_cell
        if not c: return

        box = RoundedRectangle(corner_radius=0.06,
                               width=c.W - 0.14, height=0.30)
        box.set_fill("#0a0e22", 0.96)
        box.set_stroke(COL["val_edit"], width=1.6)
        box.move_to(c.ctr())

        txt = _lbl(self._edit_buf + "│", 0.26, COL["val_edit"])
        txt.move_to(c.ctr())

        self.scene.add(box, txt)
        self._edit_box = box
        self._edit_txt = txt

    def _commit_edit(self):
        _rm(self.scene, self._edit_box)
        _rm(self.scene, self._edit_txt)
        self._edit_box = self._edit_txt = None
        c   = self._edit_cell
        val = self._edit_buf.strip()
        self._edit_cell = None
        self._edit_buf  = ""
        if c and val:
            c.set_value(val)
            if c.kind == "ptr":
                self._refresh_ptr_arrows(c.name, val)

    def _cancel_edit(self):
        _rm(self.scene, self._edit_box)
        _rm(self.scene, self._edit_txt)
        self._edit_box = self._edit_txt = None
        self._edit_cell = None
        self._edit_buf  = ""


# ═══════════════════════════════════════════════════════
#  DEMO
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    """
    manimgl mem_cell.py MemCellDemo
    """

import pyglet.window.key as _K


class MemCellDemo(Scene):
    """
    مشهد تفاعلي.
        →   : خطوة للأمام
        ←   : رجوع خطوة (undo)
       سحب  : حرّك الخلية بالفأرة
    نقر قيمة: عدّل القيمة، اكتب، ENTER للتأكيد، ESC للإلغاء

    نظام الـ undo:
        قبل كل خطوة نحفظ snapshot كامل لحالة المشهد (كل الخلايا + كل الأسهم).
        عند undo نمسح المشهد ونعيد بناءه من الـ snapshot — بدون أي منطق خاص لكل خلية.
    """

    def construct(self):
        self.camera.background_color = "#0b0d18"

        self._grid = CellGrid(self,
                              vis_l=-6.0, vis_r=6.0,
                              vis_t=3.2,  vis_b=-3.0,
                              cols=4, rows=3,
                              shuffle=False)

        self._mem = MemSys(self, self._grid)
        mem = self._mem

        mem.add("x", "0xBFF0", "5",      kind="var")
        mem.add("y", "0xBFE8", "10",     kind="var")
        mem.add("p", "0xBFE0", "0xBFF0", kind="ptr", target="x")
        mem.add("q", "0xBFD8", "0xBFE8", kind="ptr", target="y")
        mem.add("h", "0x2000", "42",     kind="heap")
        mem.add_arrow("p", "h")

        hint = Text("drag=سحب  |  click=تعديل  |  \u2192=خطوة  |  \u2190=رجوع",
                    color="#4a5070", font="Consolas").scale(0.24)
        hint.move_to(np.array([0., -3.7, 0.]))
        self.add(hint)

        self._step_lbl = Text("0 / 5", color="#2a3060",
                              font="Consolas").scale(0.22)
        self._step_lbl.move_to(np.array([6.4, -3.7, 0.]))
        self.add(self._step_lbl)

        # قائمة خطوات — كل عنصر: (وصف, دالة_do)
        # لا يوجد undo يدوي — يتم عبر snapshot تلقائياً
        self._step_fns = [
            ("x = 99",    lambda: mem.update("x", "99")),
            ("y = 77",    lambda: mem.update("y", "77")),
            ("free(h)",   lambda: mem.free("h")),
            ("p = NULL",  lambda: mem.null_ptr("p")),
            ("remove(y)", lambda: mem.remove("y")),
        ]

        # stack من snapshots — كل عنصر يُحفظ قبل تنفيذ الخطوة المقابلة
        # history[i] = state قبل الخطوة i
        self._history: list[dict] = []

        self._si     = 0
        self._action = None
        self._update_lbl()

        while not self.is_window_closing():
            self.update_frame(1 / 60)
            a = self._action
            self._action = None

            if a == "next" and self._si < len(self._step_fns):
                # احفظ الحالة الحالية قبل التنفيذ
                self._history.append(self._capture())
                _, do = self._step_fns[self._si]
                do()
                self._si += 1
                self._update_lbl()

            elif a == "prev" and self._si > 0:
                self._si -= 1
                # استرجع الحالة المحفوظة قبل هذه الخطوة
                snap = self._history.pop()
                self._restore(snap)
                self._update_lbl()

    # ════════════════════════════════════════════════
    #  snapshot: احفظ حالة كل الخلايا والأسهم
    # ════════════════════════════════════════════════
    def _capture(self) -> dict:
        """
        يُعيد dict يصف الحالة الكاملة للمشهد:
          cells  : list[dict]  — بيانات كل خلية
          arrows : list[tuple] — (src_name, dst_name) لكل سهم
        """
        cells = []
        for name, c in self._mem.cells.items():
            cells.append({
                "name":  name,
                "addr":  c.addr,
                "value": c.value,
                "kind":  c.kind,
                "cx":    c.cx,
                "cy":    c.cy,
                "freed": c.freed,
            })
        arrows = [(k.split("->")[0], k.split("->")[1])
                  for k in self._mem.arrows]
        return {"cells": cells, "arrows": arrows}

    # ════════════════════════════════════════════════
    #  restore: امسح المشهد وأعد بناءه من snapshot
    # ════════════════════════════════════════════════
    def _restore(self, snap: dict):
        """
        امسح scene كلها نظيف ثم أعد بناء كل شيء من الـ snapshot.
        هذا يضمن عدم تراكم أي mobject قديم مهما كان نوعه.
        """
        mem = self._mem

        # ── 1. صفّر الـ dicts بدون محاولة مسح من scene ──
        mem.arrows.clear()
        mem.cells.clear()
        self._grid.rebuild()

        # ── 2. امسح كل الـ mobjects من scene دفعة واحدة ──
        self.mobjects.clear()          # أسرع وأضمن من remove() واحدة واحدة

        # ── 3. أعد رسم الـ UI الثابت ─────────────────
        hint = Text("drag=سحب  |  click=تعديل  |  →=خطوة  |  ←=رجوع",
                    color="#4a5070", font="Consolas").scale(0.24)
        hint.move_to(np.array([0., -3.7, 0.]))
        self.add(hint)
        # step_lbl سيُضاف في _update_lbl بعد return

        # ── 4. أعد بناء الخلايا ──────────────────────
        for cd in snap["cells"]:
            self._grid.alloc_at(cd["cx"], cd["cy"])
            cell = MemCell(self, cd["name"], cd["addr"], cd["value"],
                           cd["cx"], cd["cy"], kind=cd["kind"])
            mem.cells[cd["name"]] = cell
            if cd["freed"]:
                cell.mark_freed()

        # ── 5. أعد رسم الأسهم ────────────────────────
        for src_name, dst_name in snap["arrows"]:
            if src_name in mem.cells and dst_name in mem.cells:
                mem._make_arrow(src_name, dst_name)

    # ════════════════════════════════════════════════
    #  UI helpers
    # ════════════════════════════════════════════════
    def _update_lbl(self):
        _rm(self, self._step_lbl)
        self._step_lbl = Text(
            f"{self._si} / {len(self._step_fns)}",
            color="#2a3060", font="Consolas").scale(0.22)
        self._step_lbl.move_to(np.array([6.4, -3.7, 0.]))
        self.add(self._step_lbl)

    # ── أحداث التفاعل ────────────────────────────────
    def on_mouse_press(self, point, button, mods):
        self._mem.handle_press(point)

    def on_mouse_drag(self, point, d_point, buttons, modifiers):
        self._mem.handle_drag(point)

    def on_mouse_release(self, point, button, mods):
        self._mem.handle_release()

    def on_key_press(self, symbol, modifiers):
        if self._mem.handle_key(symbol):
            return
        if symbol == _K.RIGHT:
            self._action = "next"
        elif symbol == _K.LEFT:
            self._action = "prev"
        else:
            super().on_key_press(symbol, modifiers)