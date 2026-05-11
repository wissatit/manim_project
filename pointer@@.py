"""C Pointer Visualizer — Teacher Mode  (v9-fix)
==========================================
Changes vs v9:
  - FIXED: Text overlapping in editor - proper space width calculation
  - FIXED: _make_row_seg now correctly accounts for text scale in width
"""
from typing import Optional
import pyglet
pyglet.options["shadow_window"] = False
pyglet.options["debug_gl"]      = False

import moderngl as _mgl
_orig_ctx = _mgl.create_standalone_context
def _egl(**kw):
    kw.pop("backend", None)
    return _orig_ctx(backend="egl", **kw)
_mgl.create_standalone_context = _egl

import re, random, time, json, os, subprocess
import numpy as np
import pyglet.window.key as K

from manimlib import (
    Scene, VGroup, VMobject,
    Rectangle, RoundedRectangle, Circle, Line,
    CurvedArrow, Text, TAU, LEFT, RIGHT,
)

# ───────────────────────────────────────────────────────────────
#  CONSTANTS & FONT
# ───────────────────────────────────────────────────────────────
FONT  = "Consolas"
SCALE = 0.27

CHAR_W = Text("a", font=FONT).scale(SCALE).get_width()
ROW_H  = Text("Mg", font=FONT).scale(SCALE).get_height() * 1.70
TAB_SZ = 4

FW, FH   = 14.222, 8.0
TOPBAR_H = 0.5

NOTE_JSON = "pointer.json"

ED_W_FIXED = 4.00
NOTE_W     = 3.20
LN_W       = 0.50
GUTTER     = 0.07

MIN_LINES_ED   = 8
MAX_LINES_ED   = 26
MIN_LINES_NOTE = 5
MAX_LINES_NOTE = 20
ED_HEADER_H    = 0.38
ED_PAD_BOT     = 0.14
NOTE_LINE_H    = 0.280

CURSOR_BLINK_PERIOD = 1.0
CURSOR_FADE_FRAC    = 0.25

# ───────────────────────────────────────────────────────────────
#  PALETTE
# ───────────────────────────────────────────────────────────────
BG       = "#0b0d18"
P_DARK   = "#0e1020"
P_MID    = "#111428"
P_ED     = "#1e1e2e"
P_MEM    = "#0d0f20"
P_NOTE   = "#0f1325"

BLUE     = "#4f8ef7";  BLUE_D   = "#1a3a8f"
RED      = "#f05555";  RED_D    = "#6e1515"
GREEN    = "#3dd68c";  GREEN_D  = "#0e3d22"
PURPLE   = "#b06cf4";  PURPLE_D = "#3a1560"
ORANGE   = "#f49836"
YELLOW   = "#f5c842"
CYAN     = "#38d9f5"
GREY     = "#4a5070";  GREY_L   = "#8890b8"
WHITE    = "#eef0fa"
DIM      = "#252840"

SAFE_BG  = "#141728";  SAFE_BRD = "#2e3566"
PTR_COL  = "#b06cf4"
HEAP_COL = "#f49836"
FREED_BG = "#3a0808"
ALLOC_BG = "#0e3d22"
CURLINE  = "#2d2d44"
SEL_COL  = "#3d3d5c"

S_KW   = "#ff79c6"
S_PP   = "#ff9580"
S_CM   = "#7c8ec0"
S_STR  = "#f1fa8c"
S_NUM  = "#bd93f9"
S_FN   = "#50fa7b"
S_OP   = "#ff6e6e"
S_TYPE = "#8be9fd"
S_VAR  = "#f8f8f2"
S_DEF  = "#f8f8f2"

C_KW = frozenset({
    "auto","break","case","continue","default","do",
    "else","extern","for","goto","if","inline",
    "register","restrict","return","sizeof","static",
    "switch","volatile","while",
    "NULL","malloc","calloc","realloc","free","printf","scanf","fprintf",
    "stderr","stdout","stdin","include","define","ifndef","ifdef","endif",
    "pragma","main",
})
C_TYPES = frozenset({
    "int","char","float","double","void","long","short",
    "unsigned","signed","struct","enum","union","typedef","const",
})

# ───────────────────────────────────────────────────────────────
#  LAYOUT MANAGER
# ───────────────────────────────────────────────────────────────
class Layout:
    def __init__(self, show_editor=True, show_note=True):
        self.show_editor = show_editor
        self.show_note   = show_note
        self._n_ed   = 16
        self._n_note = 1
        self._compute()

    def toggle_editor(self):
        self.show_editor = not self.show_editor
        self._compute()

    def toggle_note(self):
        self.show_note = not self.show_note
        self._compute()

    def update_line_counts(self, n_ed, n_note):
        old_ed_h   = getattr(self, "ed_h",   0)
        old_note_h = getattr(self, "note_h", 0)
        self._n_ed   = n_ed
        self._n_note = n_note
        self._compute()
        return (abs(self.ed_h   - old_ed_h)   > 0.001 or
                abs(self.note_h - old_note_h) > 0.001)

    def _compute(self):
        content_l = -FW / 2
        content_r =  FW / 2
        content_t =  FH / 2 - TOPBAR_H
        content_b = -FH / 2
        avail_h   = content_t - content_b

        cur_l = content_l

        if self.show_editor:
            vis_rows  = max(MIN_LINES_ED, min(self._n_ed, MAX_LINES_ED))
            raw_h     = ED_HEADER_H + vis_rows * ROW_H + ED_PAD_BOT
            self.ed_h = min(raw_h, avail_h)
            self.ed_y  = content_t - self.ed_h / 2
            self.ed_w  = ED_W_FIXED
            self.ed_l  = cur_l
            self.ed_r  = cur_l + ED_W_FIXED
            self.ed_x  = cur_l + ED_W_FIXED / 2
            cur_l      = self.ed_r
        else:
            self.ed_x = self.ed_w = self.ed_y = self.ed_h = 0
            self.ed_l = self.ed_r = content_l

        if self.show_note:
            vis_rows_n = max(MIN_LINES_NOTE, min(self._n_note, MAX_LINES_NOTE))
            raw_nh     = vis_rows_n * NOTE_LINE_H + ED_PAD_BOT
            self.note_h = min(raw_nh, avail_h)
            self.note_y = content_t - self.note_h / 2
            self.note_w = NOTE_W
            self.note_l = cur_l
            self.note_r = cur_l + NOTE_W
            self.note_x = cur_l + NOTE_W / 2
            cur_l       = self.note_r
        else:
            self.note_x = self.note_w = self.note_y = self.note_h = 0
            self.note_l = self.note_r = (
                self.ed_r if self.show_editor else content_l
            )

        vis_w      = content_r - cur_l
        self.vis_x = cur_l + vis_w / 2
        self.vis_w = vis_w
        self.vis_y = (content_t + content_b) / 2
        self.vis_h = avail_h
        self.vis_l = cur_l
        self.vis_r = content_r

        if self.show_editor:
            self.code_l   = self.ed_l + LN_W + GUTTER
            self.code_r   = self.ed_r - 0.05
            self.ln_cx    = self.ed_l + LN_W / 2
            self.ed_top_y = content_t - ED_HEADER_H - ROW_H * 0.5
        else:
            self.code_l = self.code_r = self.ln_cx = self.ed_top_y = 0

        self.mem_l = self.vis_l + 0.07
        self.mem_r = self.vis_r - 0.05
        self.mem_t = content_t
        self.mem_b = content_b


# ───────────────────────────────────────────────────────────────
#  EXTERNAL CLIPBOARD
# ───────────────────────────────────────────────────────────────
def _read_os_clipboard() -> str:
    try:
        r = subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                           capture_output=True, timeout=0.5)
        if r.returncode == 0:
            return r.stdout.decode("utf-8", errors="replace")
    except Exception:
        pass
    for cmd in (["xsel", "--clipboard", "--output"],
                ["xdotool", "getactivewindow", "type", "--clearmodifiers"]):
        try:
            r = subprocess.run(cmd[:2], capture_output=True, timeout=0.5)
            if r.returncode == 0:
                return r.stdout.decode("utf-8", errors="replace")
        except Exception:
            pass
    try:
        import tkinter as tk
        root = tk.Tk(); root.withdraw()
        data = root.clipboard_get()
        root.destroy()
        return data
    except Exception:
        pass
    try:
        r = subprocess.run(["wl-paste", "--no-newline"],
                           capture_output=True, timeout=0.5)
        if r.returncode == 0:
            return r.stdout.decode("utf-8", errors="replace")
    except Exception:
        pass
    return ""


def _write_os_clipboard(text: str):
    try:
        r = subprocess.run(["xclip", "-selection", "clipboard"],
                           input=text.encode("utf-8"), timeout=0.5)
        if r.returncode == 0:
            return
    except Exception:
        pass
    try:
        subprocess.run(["xsel", "--clipboard", "--input"],
                       input=text.encode("utf-8"), timeout=0.5)
        return
    except Exception:
        pass
    try:
        import tkinter as tk
        root = tk.Tk(); root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
    except Exception:
        pass
    try:
        subprocess.run(["wl-copy"],
                       input=text.encode("utf-8"), timeout=0.5)
    except Exception:
        pass


# ───────────────────────────────────────────────────────────────
#  HELPERS
# ───────────────────────────────────────────────────────────────
def v3(x, y):  return np.array([x, y, 0.], dtype=float)

def hit(mob, pt):
    try:
        bb = mob.get_bounding_box()
        return (bb[0][0] <= pt[0] <= bb[2][0] and
                bb[0][1] <= pt[1] <= bb[2][1])
    except Exception:
        return False

def rr(w, h, fill, stroke, radius=0.10, sw=1.5):
    r = RoundedRectangle(corner_radius=radius, width=w, height=h)
    r.set_fill(fill, 1.0).set_stroke(stroke, width=sw)
    return r

def lbl(s, sz=0.30, col=WHITE):
    return Text(s, color=col, font=FONT).scale(sz)

_tc: dict = {}

def ct(s, col, sz=SCALE):
    key = (s, col, round(sz, 4))
    if key not in _tc:
        _tc[key] = Text(s, color=col, font=FONT).scale(sz)
    return _tc[key]

def ct_copy(s, col, sz=SCALE):
    m = ct(s, col, sz)
    return m.copy() if m is not None else None


def tokenise(line):
    out = []
    if line.lstrip().startswith("#"):
        stripped = line.lstrip()
        leading  = line[:len(line)-len(stripped)]
        if leading:
            out.append((leading, S_DEF))
        out.append((stripped, S_PP))
        return out

    i, n = 0, len(line)
    while i < n:
        if line[i:i+2] == "//":
            out.append((line[i:], S_CM)); break
        if line[i:i+2] == "/*":
            j = line.find("*/", i+2); j = j+2 if j != -1 else n
            out.append((line[i:j], S_CM)); i = j; continue
        if line[i] == '"':
            j = i+1
            while j < n and line[j] != '"':
                if line[j] == '\\': j += 1
                j += 1
            out.append((line[i:j+1], S_STR)); i = j+1; continue
        if line[i] == "'":
            j = i+1
            while j < n and line[j] != "'":
                if line[j] == '\\': j += 1
                j += 1
            out.append((line[i:j+1], S_STR)); i = j+1; continue
        if line[i].isdigit():
            j = i+1
            while j < n and (line[j].isdigit() or line[j] in '.xXaAbBcCdDeEfFuUlL'):
                j += 1
            out.append((line[i:j], S_NUM)); i = j; continue
        if line[i].isalpha() or line[i] == '_':
            j = i
            while j < n and (line[j].isalnum() or line[j] == '_'): j += 1
            word = line[i:j]
            k2 = j
            while k2 < n and line[k2] == ' ': k2 += 1
            if line[k2:k2+1] == '(':
                col = S_FN
            elif word in C_TYPES:
                col = S_TYPE
            elif word in C_KW:
                col = S_KW
            else:
                col = S_VAR
            out.append((word, col)); i = j; continue
        if line[i] == ' ':
            j = i
            while j < n and line[j] == ' ': j += 1
            out.append((line[i:j], S_DEF)); i = j; continue
        out.append((line[i], S_OP)); i += 1
    return out


_width_cache: dict = {}

def text_width(s: str, sz: float) -> float:
    if not s:
        return 0.0
    return len(s) * CHAR_W * (sz / SCALE)

# ───────────────────────────────────────────────────────────────
#  RTL DETECTION
# ───────────────────────────────────────────────────────────────
_RTL_RANGES = [
    (0x0600, 0x06FF),   # Arabic
    (0x0750, 0x077F),   # Arabic Supplement
    (0x08A0, 0x08FF),   # Arabic Extended-A
    (0xFB50, 0xFDFF),   # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),   # Arabic Presentation Forms-B
    (0x0590, 0x05FF),   # Hebrew
    (0xFB00, 0xFB4F),   # Alphabetic Presentation Forms (Hebrew)
    (0x0700, 0x074F),   # Syriac
]

def _is_rtl_char(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _RTL_RANGES)

def _line_is_rtl(text: str) -> bool:
    for ch in text:
        if _is_rtl_char(ch):
            return True
        if ch.isalpha():
            return False
    return False


def load_notes():
    try:
        with open(NOTE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [str(x) for x in data]
            if isinstance(data, dict) and "lines" in data:
                return [str(x) for x in data["lines"]]
    except Exception:
        pass
    return [""]


def save_notes(lines):
    try:
        with open(NOTE_JSON, "w", encoding="utf-8") as f:
            json.dump({"lines": lines}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ───────────────────────────────────────────────────────────────
#  SELECTION
# ───────────────────────────────────────────────────────────────
class Sel:
    def __init__(self):
        self.r0 = self.c0 = self.r1 = self.c1 = 0
        self.active = False

    def set(self, r0, c0, r1, c1):
        self.r0=r0; self.c0=c0; self.r1=r1; self.c1=c1; self.active=True

    def clear(self): self.active = False

    def norm(self):
        if (self.r0, self.c0) <= (self.r1, self.c1):
            return self.r0, self.c0, self.r1, self.c1
        return self.r1, self.c1, self.r0, self.c0

    def text(self, lines):
        if not self.active: return ""
        r0, c0, r1, c1 = self.norm()
        if r0 == r1: return lines[r0][c0:c1]
        parts = [lines[r0][c0:]]
        for r in range(r0+1, r1): parts.append(lines[r])
        parts.append(lines[r1][:c1])
        return "\n".join(parts)


# ───────────────────────────────────────────────────────────────
#  WORD-WRAP HELPER
# ───────────────────────────────────────────────────────────────
def _wrap_line_words(text: str, max_cols: int) -> list:
    if not text:
        return [""]
    if len(text) <= max_cols:
        return [text]

    segs   = []
    start  = 0
    n      = len(text)

    while start < n:
        end = start + max_cols
        if end >= n:
            segs.append(text[start:])
            break

        bp = text.rfind(' ', start, end + 1)
        if bp > start:
            segs.append(text[start:bp + 1])
            start = bp + 1
        else:
            segs.append(text[start:end])
            start = end

    return segs if segs else [""]

# ───────────────────────────────────────────────────────────────
#  BASE TEXT PANEL
# ───────────────────────────────────────────────────────────────
class BasePanel:
    MAX_UNDO = 120

    def __init__(self, scene, lines, layout):
        self.scene   = scene
        self.lines   = list(lines) if lines else [""]
        self.layout  = layout
        self.row     = 0
        self.col     = 0
        self.focused = False
        self.sel     = Sel()
        self._wish   = 0
        self._undo:  list = []
        self._redo:  list = []
        self._clip   = ""
        self._scroll = 0

        self._rmobs: list = [None] * len(self.lines)
        self._smobs: list = []
        self._cmob:  Optional[VMobject] = None
        self._hlmob: VMobject | None    = None

        self._dirty: set  = set(range(len(self.lines)))
        self._dov         = True
        self._blink = True
        self._bt    = time.time()

        self._wrap_map: list = []
        self._disp_to_log: list = []
        self._disp_to_off: list = []
        self._recompute_wrap()

        self.on_change = None

    def _code_left(self)  -> float: raise NotImplementedError
    def _code_right(self) -> float: raise NotImplementedError
    def _row_h(self)      -> float: raise NotImplementedError
    def _text_scale(self) -> float: raise NotImplementedError
    def _top_y(self)      -> float: raise NotImplementedError
    def _panel_l(self)    -> float: raise NotImplementedError
    def _panel_r(self)    -> float: raise NotImplementedError
    def _panel_t(self)    -> float: raise NotImplementedError
    def _panel_b(self)    -> float: raise NotImplementedError

    def _max_cols(self) -> int:
        try:
            avail = self._code_right() - self._code_left() - 0.08
            cw = CHAR_W * (self._text_scale() / SCALE)
            return max(1, int(avail / cw))
        except (AttributeError, ZeroDivisionError):
            return 80

    def _split_line(self, text: str, max_cols: int) -> list:
        if not text:
            return [""]
        segs = []
        start = 0
        while start < len(text):
            segs.append(text[start:start + max_cols])
            start += max_cols
        return segs if segs else [""]

    def _recompute_wrap(self):
        mc = self._max_cols()
        self._wrap_map      = []
        self._disp_to_log   = []
        self._disp_to_off   = []
        for li, raw in enumerate(self.lines):
            segs = self._split_line(raw, mc)
            self._wrap_map.append(segs)
            off = 0
            for seg in segs:
                self._disp_to_log.append(li)
                self._disp_to_off.append(off)
                off += len(seg)
        self._dirty = set(range(len(self.lines)))
        self._dov   = True

    def _log_to_disp(self, logical_row: int, col: int):
        base = 0
        for li in range(logical_row):
            base += len(self._wrap_map[li])
        segs = self._wrap_map[logical_row] if logical_row < len(self._wrap_map) else [""]
        off = 0
        seg_idx = 0
        for k, seg in enumerate(segs):
            if off + len(seg) >= col:
                seg_idx = k
                break
            off += len(seg)
            seg_idx = k
        disp_row = base + seg_idx
        disp_col = col - off
        return disp_row, disp_col

    def _total_disp_rows(self) -> int:
        return sum(len(segs) for segs in self._wrap_map)

    def _visible_rows(self) -> int:
        raise NotImplementedError

    def _row_y(self, disp_row: int) -> float:
        return self._top_y() - (disp_row - self._scroll) * self._row_h()

    def _disp_row_count(self, logical_row: int) -> int:
        if logical_row < len(self._wrap_map):
            return len(self._wrap_map[logical_row])
        return 1

    def _ensure_visible(self):
        if not self._wrap_map:
            return
        n    = self._visible_rows()
        dr, _ = self._log_to_disp(self.row, self.col)
        changed = False
        if dr < self._scroll:
            self._scroll = dr; changed = True
        elif dr >= self._scroll + n:
            self._scroll = max(0, dr - n + 1); changed = True
        total = self._total_disp_rows()
        max_scroll = max(0, total - n)
        if self._scroll > max_scroll:
            self._scroll = max_scroll; changed = True
        if changed:
            self._dirty = set(range(len(self.lines)))
            self._dov   = True

    def _disp_row_visible(self, dr: int) -> bool:
        n = self._visible_rows()
        if not (self._scroll <= dr < self._scroll + n):
            return False
        y   = self._row_y(dr)
        bot = self._panel_b() + ED_PAD_BOT
        return y >= bot - self._row_h() * 0.5

    def _snap(self): return (list(self.lines), self.row, self.col)

    def _push_undo(self, snap=None):
        snap = snap or self._snap()
        if self._undo and self._undo[-1][0] == snap[0]: return
        self._undo.append(snap); self._redo.clear()
        if len(self._undo) > self.MAX_UNDO: self._undo.pop(0)

    def undo(self):
        if not self._undo: return
        self._redo.append(self._snap()); self._load(*self._undo.pop())

    def redo(self):
        if not self._redo: return
        self._undo.append(self._snap()); self._load(*self._redo.pop())

    def _load(self, lines, r, c):
        old = len(self.lines); self.lines = list(lines)
        self.row = max(0, min(r, max(0, len(self.lines)-1)))
        self.col = max(0, min(c, len(self.lines[self.row]) if self.lines else 0))
        self.sel.clear()
        self._recompute_wrap()
        self._mark_range(0, max(len(lines), old))
        self._ensure_visible()
        if self.on_change: self.on_change()

    def _mark(self, *rows):
        for r in rows:
            if 0 <= r < len(self.lines): self._dirty.add(r)
        self._dov = True
        if self.on_change: self.on_change()

    def _mark_range(self, a, b): self._mark(*range(a, b))

    def move_up(self, shift=False):
        if shift and not self.sel.active: self.sel.set(self.row, self.col, self.row, self.col)
        dr, dc = self._log_to_disp(self.row, self.col)
        if dr > 0:
            dr2   = dr - 1
            log2  = self._disp_to_log[dr2]
            off2  = self._disp_to_off[dr2]
            segs2 = self._wrap_map[log2]
            base2 = sum(len(self._wrap_map[l]) for l in range(log2))
            seg2  = dr2 - base2
            seg_len = len(segs2[seg2]) if seg2 < len(segs2) else 0
            col2  = min(self._wish - off2, seg_len)
            col2  = max(0, off2 + col2)
            col2  = min(col2, len(self.lines[log2]))
            self.row, self.col = log2, col2
        if shift: self.sel.r1=self.row; self.sel.c1=self.col
        else: self.sel.clear()
        self._ensure_visible(); self._dov = True; self._reset_blink()

    def move_down(self, shift=False):
        if shift and not self.sel.active: self.sel.set(self.row, self.col, self.row, self.col)
        dr, dc = self._log_to_disp(self.row, self.col)
        total  = self._total_disp_rows()
        if dr < total - 1:
            dr2   = dr + 1
            log2  = self._disp_to_log[dr2]
            off2  = self._disp_to_off[dr2]
            segs2 = self._wrap_map[log2]
            base2 = sum(len(self._wrap_map[l]) for l in range(log2))
            seg2  = dr2 - base2
            seg_len = len(segs2[seg2]) if seg2 < len(segs2) else 0
            col2  = min(self._wish - off2, seg_len)
            col2  = max(0, off2 + col2)
            col2  = min(col2, len(self.lines[log2]))
            self.row, self.col = log2, col2
        if shift: self.sel.r1=self.row; self.sel.c1=self.col
        else: self.sel.clear()
        self._ensure_visible(); self._dov = True; self._reset_blink()

    def move_left(self, shift=False):
        if not shift and self.sel.active:
            r0, c0, _, _ = self.sel.norm()
            self.row, self.col = r0, c0; self.sel.clear()
            self._wish=c0; self._ensure_visible(); self._dov=True; self._reset_blink(); return
        if shift and not self.sel.active: self.sel.set(self.row, self.col, self.row, self.col)
        if self.col > 0:
            self.col -= 1
        elif self.row > 0:
            self.row -= 1; self.col = len(self.lines[self.row])
        self._wish = self.col
        if shift: self.sel.r1=self.row; self.sel.c1=self.col
        self._ensure_visible(); self._dov = True; self._reset_blink()

    def move_right(self, shift=False):
        if not shift and self.sel.active:
            _, _, r1, c1 = self.sel.norm()
            self.row, self.col = r1, c1; self.sel.clear()
            self._wish=c1; self._ensure_visible(); self._dov=True; self._reset_blink(); return
        if shift and not self.sel.active: self.sel.set(self.row, self.col, self.row, self.col)
        ln = self.lines[self.row] if self.lines else ""
        if self.col < len(ln):
            self.col += 1
        elif self.row < len(self.lines)-1:
            self.row += 1; self.col = 0
        self._wish = self.col
        if shift: self.sel.r1=self.row; self.sel.c1=self.col
        self._ensure_visible(); self._dov = True; self._reset_blink()

    def home(self, shift=False):
        ln=self.lines[self.row] if self.lines else ""; ind=len(ln)-len(ln.lstrip())
        nc=0 if self.col==ind else ind
        if shift:
            if not self.sel.active: self.sel.set(self.row, self.col, self.row, self.col)
            self.sel.r1=self.row; self.sel.c1=nc
        else: self.sel.clear()
        self.col=nc; self._wish=nc; self._dov=True; self._reset_blink()

    def end(self, shift=False):
        nc=len(self.lines[self.row]) if self.lines else 0
        if shift:
            if not self.sel.active: self.sel.set(self.row, self.col, self.row, self.col)
            self.sel.r1=self.row; self.sel.c1=nc
        else: self.sel.clear()
        self.col=nc; self._wish=nc; self._dov=True; self._reset_blink()

    def select_all(self):
        if not self.lines: return
        self.sel.set(0, 0, len(self.lines)-1, len(self.lines[-1])); self._dov=True

    def click(self, px, py, extend=False):
        r, c = self._xy_to_rc(px, py)
        if extend:
            if not self.sel.active: self.sel.set(self.row, self.col, self.row, self.col)
            self.sel.r1=r; self.sel.c1=c
        else:
            self.sel.clear()
            self.row, self.col = r, c
        self._wish=c; self._dov=True; self._reset_blink()

    def select_word(self, px, py):
        r, c = self._xy_to_rc(px, py)
        ln = self.lines[r] if r < len(self.lines) else ""
        l = c
        while l > 0 and (ln[l-1].isalnum() or ln[l-1]=='_'): l -= 1
        rr2 = c
        while rr2 < len(ln) and (ln[rr2].isalnum() or ln[rr2]=='_'): rr2 += 1
        self.row, self.col = r, rr2
        self.sel.set(r, l, r, rr2); self._dov=True

    def _xy_to_rc(self, px, py):
        cl  = self._code_left()
        rh  = self._row_h()
        dy  = self._top_y() - py
        dr  = max(0, int(dy / rh)) + self._scroll
        total = self._total_disp_rows()
        dr  = min(dr, total - 1)
        if dr < len(self._disp_to_log):
            log  = self._disp_to_log[dr]
            off  = self._disp_to_off[dr]
        else:
            log  = len(self.lines) - 1
            off  = 0
        ln   = self.lines[log] if log < len(self.lines) else ""
        segs = self._wrap_map[log] if log < len(self._wrap_map) else [""]
        base = sum(len(self._wrap_map[l]) for l in range(log))
        seg_idx = dr - base
        seg_idx = max(0, min(seg_idx, len(segs) - 1))
        seg_text = segs[seg_idx] if seg_idx < len(segs) else ""
        dx   = max(0.0, px - cl)

        # ══ FIX: Calculate column using same token-based width as _make_row_seg ══
        c    = 0
        x_acc = 0.0
        tokens = tokenise(seg_text)
        tok_idx = 0
        char_count = 0

        for tok, col in tokens:
            if not tok:
                continue

            # Calculate token width same as _make_row_seg
            if not tok.strip():
                tok_w = len(tok) * CHAR_W
            else:
                m = ct_copy(tok, col)
                tok_w = m.get_width() if m else len(tok) * CHAR_W

            # Check if click is within this token
            if x_acc + tok_w > dx:
                # Click is inside this token - find exact character
                # For simplicity, assume uniform character width within token
                char_w = tok_w / len(tok) if tok else CHAR_W
                chars_in = int((dx - x_acc) / char_w) if char_w > 0 else 0
                c = char_count + max(0, min(chars_in, len(tok)))
                break

            x_acc += tok_w
            char_count += len(tok)
            c = char_count

        return log, min(off + c, len(ln))

    def _del_sel(self):
        if not self.sel.active: return False
        snap=self._snap(); r0,c0,r1,c1=self.sel.norm()
        if r0==r1:
            self.lines[r0]=self.lines[r0][:c0]+self.lines[r0][c1:]
        else:
            self.lines[r0]=self.lines[r0][:c0]+self.lines[r1][c1:]
            del self.lines[r0+1:r1+1]
        self.row,self.col=r0,c0; self.sel.clear()
        self._push_undo(snap)
        self._recompute_wrap()
        self._mark_range(r0, len(self.lines)+1)
        return True

    def insert(self, ch):
        snap=self._snap(); self._del_sel()
        ln=self.lines[self.row] if self.lines else ""
        self.lines[self.row]=ln[:self.col]+ch+ln[self.col:]
        self.col+=len(ch); self._wish=self.col
        self._push_undo(snap)
        self._recompute_wrap()
        self._mark(self.row)
        self._ensure_visible()
        self._reset_blink()

    def newline(self):
        snap=self._snap(); self._del_sel()
        ln=self.lines[self.row] if self.lines else ""; rest=ln[self.col:]
        self.lines[self.row]=ln[:self.col]
        ind=len(ln)-len(ln.lstrip())
        if ln.strip().endswith('{'): ind+=TAB_SZ
        self.lines.insert(self.row+1, " "*ind+rest)
        self.row+=1; self.col=ind; self._wish=ind
        self._push_undo(snap)
        self._recompute_wrap()
        self._mark_range(self.row-1, len(self.lines))
        self._ensure_visible()
        self._reset_blink()

    def backspace(self):
        snap=self._snap()
        if self._del_sel(): self._reset_blink(); return
        if self.col > 0:
            ln=self.lines[self.row]; pre=ln[:self.col]
            n=TAB_SZ if pre==' '*len(pre) and len(pre)%TAB_SZ==0 and pre else 1
            n=min(n, self.col)
            self.lines[self.row]=ln[:self.col-n]+ln[self.col:]
            self.col-=n; self._wish=self.col
            self._push_undo(snap)
            self._recompute_wrap()
            self._mark(self.row)
        elif self.row > 0:
            prev=self.lines[self.row-1]; curr=self.lines.pop(self.row)
            self.row-=1; self.col=len(prev)
            self.lines[self.row]=prev+curr
            self._push_undo(snap)
            self._recompute_wrap()
            self._mark_range(self.row, len(self.lines)+1)
        self._ensure_visible()
        self._reset_blink()

    def delete_fwd(self):
        snap=self._snap()
        if self._del_sel(): self._reset_blink(); return
        ln=self.lines[self.row] if self.lines else ""
        if self.col < len(ln):
            self.lines[self.row]=ln[:self.col]+ln[self.col+1:]
            self._push_undo(snap)
            self._recompute_wrap()
            self._mark(self.row)
        elif self.row < len(self.lines)-1:
            nxt=self.lines.pop(self.row+1)
            self.lines[self.row]+=nxt
            self._push_undo(snap)
            self._recompute_wrap()
            self._mark_range(self.row, len(self.lines)+1)
        self._reset_blink()

    def tab(self, shift=False):
        snap=self._snap(); r0=r1=self.row
        if self.sel.active: r0,_,r1,_=self.sel.norm()
        for r in range(r0, r1+1):
            if shift:
                n=0
                while n<TAB_SZ and n<len(self.lines[r]) and self.lines[r][n]==' ': n+=1
                self.lines[r]=self.lines[r][n:]
                if r==self.row: self.col=max(0, self.col-n)
            else:
                self.lines[r]=" "*TAB_SZ+self.lines[r]
                if r==self.row: self.col+=TAB_SZ
        self._wish=self.col; self._push_undo(snap)
        self._recompute_wrap()
        self._mark_range(r0, r1+1)
        self._reset_blink()

    def copy(self):
        text = self.sel.text(self.lines) if self.sel.active else (self.lines[self.row] if self.lines else "")
        self._clip = text
        _write_os_clipboard(text)

    def cut(self):
        snap=self._snap()
        if self.sel.active:
            self._clip=self.sel.text(self.lines)
            _write_os_clipboard(self._clip)
            self._del_sel()
            self._reset_blink(); return
        self._clip=self.lines[self.row] if self.lines else ""
        _write_os_clipboard(self._clip)
        if len(self.lines) > 1:
            self.lines.pop(self.row); self.row=min(self.row, len(self.lines)-1); self.col=0
        else:
            self.lines=[""]; self.lines[0]=""; self.col=0
        self._push_undo(snap)
        self._recompute_wrap()
        self._mark_range(self.row, len(self.lines)+1)
        self._ensure_visible()
        self._reset_blink()

    def paste(self):
        os_clip = _read_os_clipboard()
        if os_clip:
            self._clip = os_clip
        if not self._clip: return
        snap=self._snap(); self._del_sel()
        parts=self._clip.split('\n')
        if len(parts)==1: self.insert(parts[0]); return
        ln=self.lines[self.row] if self.lines else ""; rest=ln[self.col:]
        self.lines[self.row]=ln[:self.col]+parts[0]
        for i, p in enumerate(parts[1:], 1): self.lines.insert(self.row+i, p)
        last=self.row+len(parts)-1
        self.lines[last]+=rest
        self.row=last; self.col=len(parts[-1]); self._wish=self.col
        self._push_undo(snap)
        self._recompute_wrap()
        self._mark_range(self.row-len(parts), len(self.lines))
        self._ensure_visible()
        self._reset_blink()

    def _reset_blink(self):
        self._blink = True
        self._bt    = time.time()

    def _evict_mob(self, lst, idx):
        if idx < len(lst) and lst[idx] is not None:
            m = lst[idx]
            try:
                if m in self.scene.mobjects: self.scene.remove(m)
            except Exception: pass
            lst[idx] = None

    def _remove_mob(self, m):
        if m is not None:
            try:
                if m in self.scene.mobjects: self.scene.remove(m)
            except Exception: pass

    def _clear_overlay(self):
        for m in list(self._smobs):
            self._remove_mob(m)
        self._smobs.clear()
        self._remove_mob(self._cmob); self._cmob = None

    def set_focused(self, val):
        if self.focused != val:
            self.focused = val; self._dov = True
            if val: self._reset_blink()

    def full_redraw(self):
        n     = self._visible_rows()
        total = self._total_disp_rows()
        max_s = max(0, total - n)
        self._scroll = min(self._scroll, max_s)
        self._dirty  = set(range(len(self.lines)))
        self._dov    = True

    def cleanup(self):
        for i in range(len(self._rmobs)):
            self._evict_mob(self._rmobs, i)
        self._clear_overlay()
        self._remove_mob(self._hlmob); self._hlmob = None

    def in_panel(self, px, py):
        return (self._panel_l() <= px <= self._panel_r() and
                self._panel_b() <= py <= self._panel_t())

    def highlight_row(self, r):
        self._remove_mob(self._hlmob); self._hlmob = None
        if r is None or not (0 <= r < len(self.lines)): return
        dr, _ = self._log_to_disp(r, 0)
        if not self._disp_row_visible(dr): return
        cl = self._code_left(); cr = self._code_right()
        w  = cr - cl + GUTTER
        hl = Rectangle(width=w, height=self._row_h())
        hl.set_fill(GREEN_D, 0.42).set_stroke(GREEN, width=0.7)
        hl.move_to(v3(cl + w/2 - GUTTER/2, self._row_y(dr)))
        self.scene.add(hl); self._hlmob = hl

    def clear_highlight(self): self.highlight_row(None)


# ───────────────────────────────────────────────────────────────
#  EDITOR  (extends BasePanel)  —  FIXED VERSION
# ───────────────────────────────────────────────────────────────
class Editor(BasePanel):

    def __init__(self, scene, lines, layout):
        super().__init__(scene, lines, layout)
        self._nmobs: list = [None] * len(self.lines)

    def _code_left(self)  -> float: return self.layout.code_l
    def _code_right(self) -> float: return self.layout.code_r
    def _row_h(self)      -> float: return ROW_H
    def _text_scale(self) -> float: return SCALE
    def _top_y(self)      -> float: return self.layout.ed_top_y
    def _panel_l(self)    -> float: return self.layout.ed_l
    def _panel_r(self)    -> float: return self.layout.ed_r
    def _panel_t(self)    -> float: return self.layout.ed_y + self.layout.ed_h / 2
    def _panel_b(self)    -> float: return self.layout.ed_y - self.layout.ed_h / 2

    def _visible_rows(self) -> int:
        L = self.layout
        inner_h = max(ROW_H, L.ed_h - ED_HEADER_H - ED_PAD_BOT)
        return max(1, int(inner_h / ROW_H))

    def flush(self):
        if not self.layout.show_editor:
            return
        self._sync_lists()
        self._render_dirty_rows()
        if self._dov:
            self._render_overlay()
            self._dov = False
        now = time.time()
        if now - self._bt > 0.50:
            self._blink = not self._blink
            self._bt    = now
            self._render_cursor()

    def _sync_lists(self):
        n = len(self.lines)
        while len(self._rmobs) < n:
            self._rmobs.append(None); self._nmobs.append(None)
        while len(self._rmobs) > n:
            self._evict_mob(self._rmobs, len(self._rmobs)-1); self._rmobs.pop()
            self._evict_mob(self._nmobs, len(self._nmobs)-1); self._nmobs.pop()

    def _evict(self, i):
        self._evict_mob(self._rmobs, i)
        self._evict_mob(self._nmobs, i)

    def _render_dirty_rows(self):
        for i in range(len(self._rmobs)):
            dr, _ = self._log_to_disp(i, 0) if i < len(self.lines) else (999, 0)
            if not self._disp_row_visible(dr):
                self._evict(i)

        for i in sorted(self._dirty):
            if i >= len(self.lines): continue
            dr, _ = self._log_to_disp(i, 0)
            if not self._disp_row_visible(dr):
                self._evict(i); continue
            self._evict(i)
            nm = ct(str(i+1), GREY_L, SCALE * 0.78)
            if nm:
                n2 = nm.copy()
                n2.move_to(v3(self.layout.ln_cx, self._row_y(dr)))
                self.scene.add(n2); self._nmobs[i] = n2
            segs = self._wrap_map[i] if i < len(self._wrap_map) else [""]
            grp  = VGroup()
            for seg_idx, seg in enumerate(segs):
                drow = dr + seg_idx
                if not self._disp_row_visible(drow): continue
                y    = self._row_y(drow)
                row_mob = self._make_row_seg(seg, y)
                if row_mob: grp.add(row_mob)
            if len(grp): self.scene.add(grp)
            self._rmobs[i] = grp if len(grp) else None
        self._dirty.clear()

    # ══════════════════════════════════════════════════════════════
    #  FIX: Proper space width calculation in _make_row_seg
    # ══════════════════════════════════════════════════════════════
    def _make_row_seg(self, seg_text: str, y: float) -> Optional[VGroup]:
        if not seg_text: 
            return None
        tokens  = tokenise(seg_text)
        grp     = VGroup()
        x_cur   = self._code_left()
        clip_x  = self._code_right() - 0.04

        for tok, col in tokens:
            if not tok: 
                continue
            if x_cur >= clip_x: 
                break

            # For whitespace-only tokens, advance x by character width
            if not tok.strip():
                x_cur += len(tok) * CHAR_W
                continue

            m = ct_copy(tok, col)
            if m is None:
                x_cur += len(tok) * CHAR_W
                continue

            # Get ACTUAL width from the rendered text object (like v2)
            w = m.get_width()

            if x_cur + w > clip_x: 
                break
            m.move_to(v3(x_cur + w/2, y))
            grp.add(m)
            x_cur += w
        return grp if len(grp) else None

    def _render_overlay(self):
        self._clear_overlay()
        self._render_sel()
        self._render_cursor()

    def _render_sel(self):
        if not self.sel.active: return
        r0, c0, r1, c1 = self.sel.norm()
        L = self.layout
        for r in range(r0, r1+1):
            if r >= len(self.lines): break
            ln = self.lines[r]
            sc = c0 if r == r0 else 0
            ec = c1 if r == r1 else len(ln)
            if r < r1: ec = max(ec, len(ln)) + 1
            if sc >= ec: continue
            dr_start, _ = self._log_to_disp(r, sc)
            dr_end,   _ = self._log_to_disp(r, ec)
            for dr in range(dr_start, dr_end+1):
                if not self._disp_row_visible(dr): continue
                off  = self._disp_to_off[dr] if dr < len(self._disp_to_off) else 0
                log  = self._disp_to_log[dr] if dr < len(self._disp_to_log) else r
                segs = self._wrap_map[log] if log < len(self._wrap_map) else [""]
                base = sum(len(self._wrap_map[l]) for l in range(log))
                seg_idx = dr - base
                seg = segs[seg_idx] if seg_idx < len(segs) else ""
                seg_len = len(seg)
                dc0  = max(0, sc - off) if dr == dr_start else 0
                dc1  = min(seg_len, ec - off) if dr <= dr_end else seg_len
                if r < r1 and dr == dr_end: dc1 = seg_len
                if dc0 >= dc1 and dr < dr_end: dc1 = seg_len

                # ══ FIX: Use token-based width calculation (same as _make_row_seg) ══
                def _calc_seg_x(seg_text, up_to_col):
                    if not seg_text or up_to_col <= 0:
                        return 0.0
                    prefix = seg_text[:up_to_col]
                    tokens = tokenise(prefix)
                    x_acc = 0.0
                    for tok, col in tokens:
                        if not tok:
                            continue
                        if not tok.strip():
                            x_acc += len(tok) * CHAR_W
                        else:
                            m = ct_copy(tok, col)
                            x_acc += m.get_width() if m else len(tok) * CHAR_W
                    return x_acc

                x0 = L.code_l + _calc_seg_x(seg, dc0)
                x1 = min(L.code_l + _calc_seg_x(seg, dc1), L.code_r - 0.05)
                w  = max(x1 - x0, 0.02)
                rect = Rectangle(width=w, height=ROW_H*0.88)
                rect.set_fill(SEL_COL, 0.72).set_stroke(width=0)
                rect.move_to(v3(x0+w/2, self._row_y(dr)))
                self.scene.add(rect); self._smobs.append(rect)

    def _render_cursor(self):
        if self._cmob is not None:
            try:
                if self._cmob in self.scene.mobjects:
                    self.scene.remove(self._cmob)
            except Exception:
                pass
            self._cmob = None
        if not self.focused or not self._blink:
            return
        dr, dc = self._log_to_disp(self.row, self.col)
        if not self._disp_row_visible(dr):
            return
        log = self._disp_to_log[dr] if dr < len(self._disp_to_log) else self.row
        segs = self._wrap_map[log] if log < len(self._wrap_map) else [""]
        base = sum(len(self._wrap_map[l]) for l in range(log))
        seg_idx = dr - base
        seg = segs[seg_idx] if seg_idx < len(segs) else ""
        prefix = seg[:dc]

        # ══ FIX: Calculate cursor position using same method as _make_row_seg ══
        # Tokenise prefix and sum actual rendered widths (m.get_width())
        pw = 0.0
        if prefix:
            tokens = tokenise(prefix)
            for tok, col in tokens:
                if not tok.strip():
                    pw += len(tok) * CHAR_W  # spaces: fixed width
                else:
                    m = ct_copy(tok, col)
                    if m:
                        pw += m.get_width()  # actual rendered width
                    else:
                        pw += len(tok) * CHAR_W

        cur = Rectangle(width=0.015, height=ROW_H * 0.84)
        cur.set_fill(CYAN, 1.0).set_stroke(width=0)
        cur.move_to(v3(
            self.layout.code_l + pw,
            self._row_y(dr)
        ))
        self.scene.add(cur)
        self._cmob = cur

    def cleanup(self):
        super().cleanup()
        for i in range(len(self._nmobs)):
            self._evict_mob(self._nmobs, i)


# ───────────────────────────────────────────────────────────────
#  NOTE PANEL
# ───────────────────────────────────────────────────────────────
class NotePanel(BasePanel):
    PAD_L   = 0.14
    PAD_T   = 0.14

    def __init__(self, scene, layout, lines=None, on_change=None):
        raw = list(lines or load_notes())
        if not raw: raw = [""]
        self._note_scale = 0.200
        super().__init__(scene, raw, layout)
        self.on_change = on_change
        self._active   = False
        self._mobs: list = []
        self._render_full()

    def _split_line(self, text: str, max_cols: int) -> list:
        return _wrap_line_words(text, max_cols)

    def zoom(self, direction: int):
        self._note_scale = max(0.12, min(0.36, self._note_scale + direction * 0.025))
        self._recompute_wrap()
        self.full_redraw()
        self._render_full()

    def _code_left(self)  -> float: return self.layout.note_l + self.PAD_L
    def _code_right(self) -> float: return self.layout.note_r - 0.12
    def _row_h(self)      -> float: return NOTE_LINE_H
    def _text_scale(self) -> float: return self._note_scale

    def _top_y(self)      -> float:
        return self.layout.note_y + self.layout.note_h / 2 - self.PAD_T

    def _panel_l(self)    -> float: return self.layout.note_l
    def _panel_r(self)    -> float: return self.layout.note_r
    def _panel_t(self)    -> float: return self.layout.note_y + self.layout.note_h / 2
    def _panel_b(self)    -> float: return self.layout.note_y - self.layout.note_h / 2

    def _visible_rows(self) -> int:
        L = self.layout
        inner_h = max(self._row_h(), L.note_h - self.PAD_T - 0.10)
        return max(1, int(inner_h / self._row_h()))

    def _xy_to_rc(self, px, py):
        cl   = self._code_left()
        cr   = self._code_right()
        rh   = self._row_h()
        sc   = self._text_scale()
        dy   = self._top_y() - py
        dr   = max(0, int(dy / rh)) + self._scroll
        total = self._total_disp_rows()
        dr   = min(dr, total - 1)
        if dr < len(self._disp_to_log):
            log = self._disp_to_log[dr]
            off = self._disp_to_off[dr]
        else:
            log = len(self.lines) - 1
            off = 0
        ln   = self.lines[log] if log < len(self.lines) else ""
        segs = self._wrap_map[log] if log < len(self._wrap_map) else [""]
        base = sum(len(self._wrap_map[l]) for l in range(log))
        seg_idx = dr - base
        seg_idx = max(0, min(seg_idx, len(segs) - 1))
        seg_text = segs[seg_idx] if seg_idx < len(segs) else ""
        rtl = _line_is_rtl(seg_text.strip())
        if rtl:
            dx = max(0.0, cr - px)
        else:
            dx = max(0.0, px - cl)
        c = self._x_to_col(seg_text, dx, sc)
        return log, min(off + c, len(ln))

    def _fire_change(self):
        save_notes(self.lines)
        if self.on_change: self.on_change()

    def insert(self, ch):
        super().insert(ch); self._fire_change(); self._render_full()

    def newline(self):
        super().newline(); self._fire_change(); self._render_full()

    def backspace(self):
        super().backspace(); self._fire_change(); self._render_full()

    def delete_fwd(self):
        super().delete_fwd(); self._fire_change(); self._render_full()

    def tab(self, shift=False):
        super().tab(shift); self._fire_change(); self._render_full()

    def cut(self):
        super().cut(); self._fire_change(); self._render_full()

    def paste(self):
        super().paste(); self._fire_change(); self._render_full()

    def undo(self):
        super().undo(); self._fire_change(); self._render_full()

    def redo(self):
        super().redo(); self._fire_change(); self._render_full()

    def activate(self):
        self._active = True; self.set_focused(True)
        self._render_full()

    def deactivate(self):
        self._active = False; self.set_focused(False)
        save_notes(self.lines)
        self._render_full()

    def is_active(self): return self._active

    def click_at(self, px, py):
        r, c = self._xy_to_rc(px, py)
        self.sel.clear()
        self.row, self.col = r, c
        self._wish = c
        self.activate()

    def tick(self):
        if not self.layout.show_note: return
        if self._active:
            self._render_full()

    def full_redraw(self):
        super().full_redraw()
        self._render_full()

    def _clear_all(self):
        for m in self._mobs:
            try:
                if m in self.scene.mobjects: self.scene.remove(m)
            except Exception: pass
        self._mobs = []

    def _seg_anchor(self, seg: str, clip_l: float, clip_r: float, sc: float):
        rtl = _line_is_rtl(seg)
        if rtl:
            return clip_r, RIGHT, True
        return clip_l, LEFT, False

    def _col_to_x(self, seg: str, col_in_seg: int, sc: float,
                  clip_l: float, clip_r: float) -> float:
        rtl = _line_is_rtl(seg)
        if rtl:
            suffix = seg[col_in_seg:]
            sw = text_width(suffix, sc) if suffix else 0.0
            return max(clip_l, min(clip_r - sw, clip_r))
        else:
            pfx = seg[:col_in_seg]
            pw  = text_width(pfx, sc) if pfx else 0.0
            return min(clip_l + pw, clip_r - 0.02)

    def _x_to_col(self, seg: str, dx: float, sc: float) -> int:
        rtl = _line_is_rtl(seg)
        n = len(seg)
        if rtl:
            best = n
            for i in range(n + 1):
                suffix = seg[i:]
                w = text_width(suffix, sc) if suffix else 0.0
                if w > dx:
                    best = i
                    break
                best = i
            return best
        else:
            best = 0
            for i in range(n + 1):
                w = text_width(seg[:i], sc)
                if w > dx:
                    best = max(0, i - 1)
                    break
                best = i
            return best

    def _render_full(self):
        if not self.layout.show_note: return
        self._clear_all()
        L      = self.layout
        sc     = self._text_scale()
        n_vis  = self._visible_rows()
        lx     = self._code_left()
        rx     = self._code_right()

        for vi in range(n_vis):
            dr = vi + self._scroll
            if dr >= len(self._disp_to_log): break
            log = self._disp_to_log[dr]
            off = self._disp_to_off[dr]
            if log >= len(self.lines): break
            segs = self._wrap_map[log] if log < len(self._wrap_map) else [""]
            base = sum(len(self._wrap_map[l]) for l in range(log))
            seg_idx = dr - base
            seg = segs[seg_idx] if seg_idx < len(segs) else ""
            y    = self._row_y(dr)
            if y < self._panel_b() + 0.08: break

            col = WHITE if (self._active and log == self.row) else GREY_L
            display = seg if seg else " "
            rtl     = _line_is_rtl(display.strip())

            try:
                t = Text(display, color=col, font=FONT).scale(sc)
                tw = t.get_width()
                avail = rx - lx - 0.04
                if tw > avail:
                    lo2, hi2, best = 0, len(display), 0
                    while lo2 <= hi2:
                        mid = (lo2 + hi2) // 2
                        try:
                            cand = display[:mid] or " "
                            cw2  = Text(cand, color=col, font=FONT).scale(sc).get_width()
                        except Exception:
                            cw2 = 0
                        if cw2 <= avail:
                            best = mid; lo2 = mid + 1
                        else:
                            hi2 = mid - 1
                    display = display[:best]
                    try:
                        t = Text(display or " ", color=col, font=FONT).scale(sc)
                        tw = t.get_width()
                    except Exception:
                        continue
            except Exception:
                continue

            if rtl:
                t.move_to(v3(rx, y), aligned_edge=RIGHT)
            else:
                t.move_to(v3(lx, y), aligned_edge=LEFT)
            self.scene.add(t); self._mobs.append(t)

        if self._active:
            if self._blink:
                dr_c, dc_c = self._log_to_disp(self.row, self.col)
                if self._scroll <= dr_c < self._scroll + n_vis:
                    y_c  = self._row_y(dr_c)
                    if y_c >= self._panel_b() + 0.05:
                        log  = self._disp_to_log[dr_c] if dr_c < len(self._disp_to_log) else self.row
                        segs = self._wrap_map[log] if log < len(self._wrap_map) else [""]
                        base = sum(len(self._wrap_map[l]) for l in range(log))
                        seg_idx2 = dr_c - base
                        seg  = segs[seg_idx2] if seg_idx2 < len(segs) else ""
                        cx   = self._col_to_x(seg, dc_c, sc, lx, rx)
                        cur  = Rectangle(width=0.025, height=self._row_h()*0.80)
                        cur.set_fill(YELLOW, 1.0)
                        cur.set_stroke(width=0)
                        cur.move_to(v3(cx + 0.012, y_c))
                        self.scene.add(cur); self._mobs.append(cur)

        if self.sel.active:
            r0, c0, r1, c1 = self.sel.norm()
            for r in range(r0, r1+1):
                if r >= len(self.lines): break
                ln  = self.lines[r]
                sc_ = c0 if r == r0 else 0
                ec_ = c1 if r == r1 else len(ln)
                dr_s, _ = self._log_to_disp(r, sc_)
                dr_e, _ = self._log_to_disp(r, ec_)
                for dr in range(dr_s, dr_e+1):
                    if not (self._scroll <= dr < self._scroll + n_vis): continue
                    off  = self._disp_to_off[dr] if dr < len(self._disp_to_off) else 0
                    segs = self._wrap_map[r] if r < len(self._wrap_map) else [""]
                    base = sum(len(self._wrap_map[l]) for l in range(r))
                    si   = dr - base
                    si   = max(0, min(si, len(segs)-1))
                    seg  = segs[si] if si < len(segs) else ""
                    seg_len = len(seg)
                    dc0  = max(0, sc_ - off) if dr == dr_s else 0
                    dc1  = min(seg_len, ec_ - off) if dr <= dr_e else seg_len
                    if r < r1 and dr == dr_e: dc1 = seg_len
                    if dc0 >= dc1 and dr < dr_e: dc1 = seg_len
                    x0 = self._col_to_x(seg, dc0, sc, lx, rx)
                    x1 = self._col_to_x(seg, dc1, sc, lx, rx)
                    if x0 > x1: x0, x1 = x1, x0
                    w  = max(x1-x0, CHAR_W*0.3)
                    rect = Rectangle(width=w, height=self._row_h()*0.88)
                    rect.set_fill(SEL_COL, 0.72).set_stroke(width=0)
                    rect.move_to(v3(x0+w/2, self._row_y(dr)))
                    self.scene.add(rect); self._mobs.append(rect)

        total_dr = self._total_disp_rows()
        if total_dr > n_vis:
            for di in range(min(n_vis, 5)):
                frac  = (self._scroll + di * n_vis / 5) / max(1, total_dr)
                dot_y = self._top_y() - di * (L.note_h - self.PAD_T - 0.15) / 4
                dot   = Circle(radius=0.025)
                dot.set_fill(YELLOW if abs(di/4 - frac) < 0.15 else GREY, 1.0)
                dot.set_stroke(width=0)
                dot.move_to(v3(L.note_r - 0.08, dot_y))
                self.scene.add(dot); self._mobs.append(dot)

    _ZOOM_OUT_SYMS = {K.MINUS, K.UNDERSCORE, 45, 54, 95}

    def key(self, sym, mods):
        if not self._active: return
        ctrl  = bool(mods & K.MOD_CTRL)
        shift = bool(mods & K.MOD_SHIFT)

        if ctrl:
            if sym in (K.RETURN, K.NUM_ENTER):
                self.deactivate()
            elif sym == K.C:
                self.copy()
            elif sym == K.X:
                self.cut()
            elif sym == K.V:
                self.paste()
            elif sym == K.A:
                self.select_all(); self._render_full()
            elif sym == K.Z:
                self.undo()
            elif sym == K.Y:
                self.redo()
            elif sym == K.EQUAL:
                self.zoom(+1)
            elif sym in self._ZOOM_OUT_SYMS:
                self.zoom(-1)
            return

        if sym not in (K.LEFT, K.RIGHT, K.UP, K.DOWN, K.HOME, K.END,
                       K.BACKSPACE, K.DELETE, K.RETURN, K.NUM_ENTER, K.TAB):
            self.sel.clear()

        if   sym == K.ESCAPE:    self.deactivate()
        elif sym == K.RETURN:    self.newline()
        elif sym == K.BACKSPACE: self.backspace()
        elif sym == K.DELETE:    self.delete_fwd()
        elif sym == K.LEFT:      self.move_left(shift)
        elif sym == K.RIGHT:     self.move_right(shift)
        elif sym == K.UP:        self.move_up(shift)
        elif sym == K.DOWN:      self.move_down(shift)
        elif sym == K.HOME:      self.home(shift)
        elif sym == K.END:       self.end(shift)
        elif sym == K.TAB:       self.tab(shift)
        else:
            self._render_full()
            return
        self._render_full()

    def insert_text(self, ch):
        if not self._active or not ch or not ch.isprintable(): return
        self.insert(ch)

    def remove_all(self): self._clear_all()


# ───────────────────────────────────────────────────────────────
#  SAFE GRID  /  SAFE CELL  /  PTR ARROW  /  MEM SYS
# ───────────────────────────────────────────────────────────────
class SafeGrid:
    COLS = 3;  ROWS = 4

    def __init__(self, layout):
        self._layout = layout;  self._build()

    def _build(self):
        L = self._layout
        l = L.mem_l;  r = L.mem_r
        t = L.mem_t - 0.46;  b = L.mem_b + 0.10
        cw = (r-l)/self.COLS;  ch = (t-b)/self.ROWS
        self._pos = [
            (l + cw*(c+0.5), t - ch*(row+0.5))
            for row in range(self.ROWS) for c in range(self.COLS)
        ]
        random.shuffle(self._pos)
        self._used = [False] * len(self._pos)

    def rebuild(self):
        self._build();  self._used = [False] * len(self._pos)

    def alloc(self):
        free = [i for i, u in enumerate(self._used) if not u]
        if not free: return self._pos[0]
        i = random.choice(free);  self._used[i] = True
        return self._pos[i]

    def release(self, cx, cy):
        for i, (px, py) in enumerate(self._pos):
            if abs(px-cx) < 0.05 and abs(py-cy) < 0.05:
                self._used[i] = False;  return


class SafeCell:
    W = 1.20;  H = 1.00

    def __init__(self, scene, name, addr, value, cx, cy,
                 is_ptr=False, is_heap=False):
        self.scene=scene; self.name=name; self.addr=addr; self.value=value
        self.cx=cx; self.cy=cy
        self.is_ptr=is_ptr; self.is_heap=is_heap; self.freed=False
        self._build();  scene.add(self.group)

    def _build(self):
        brd = PTR_COL if self.is_ptr else (HEAP_COL if self.is_heap else SAFE_BRD)
        sw  = 2.2 if self.is_ptr else 1.8
        self.bg = RoundedRectangle(corner_radius=0.10, width=self.W, height=self.H)
        self.bg.set_fill(SAFE_BG, 1.0).set_stroke(brd, width=sw)
        self.bg.move_to(v3(self.cx, self.cy))

        stripe = RoundedRectangle(corner_radius=0.06, width=self.W-0.04, height=0.24)
        stripe.set_fill(P_DARK, 1.0).set_stroke(brd, width=0.6)
        stripe.move_to(v3(self.cx, self.cy+self.H/2-0.13))

        nc = PTR_COL if self.is_ptr else (HEAP_COL if self.is_heap else CYAN)
        nt = lbl(self.name, 0.20, nc);  nt.move_to(stripe.get_center())

        vc = YELLOW if self.is_ptr else WHITE
        self.vmob = lbl(self.value, 0.27, vc)
        self.vmob.move_to(v3(self.cx, self.cy-0.02))

        self.amob = lbl(self.addr, 0.15, GREY)
        self.amob.move_to(v3(self.cx, self.cy-self.H/2+0.10))

        self.group = VGroup(self.bg, stripe, nt, self.vmob, self.amob)

    def set_value(self, v, col=None):
        self.value = v;  col = col or (YELLOW if self.is_ptr else WHITE)
        if self.vmob is not None:
            try:
                if self.vmob in self.group.submobjects: self.group.remove(self.vmob)
            except Exception: pass
            try:
                if self.vmob in self.scene.mobjects: self.scene.remove(self.vmob)
            except Exception: pass
            self.vmob = None
        new_mob = lbl(v, 0.27, col)
        new_mob.move_to(v3(self.cx, self.cy-0.02))
        self.group.add(new_mob);  self.scene.add(new_mob);  self.vmob = new_mob

    def flash(self, col=YELLOW):
        orig = PTR_COL if self.is_ptr else SAFE_BRD
        self.bg.set_stroke(col, width=4.0)
        self.scene.update_frame(0.05)
        self.bg.set_stroke(orig, width=2.2 if self.is_ptr else 1.8)

    def mark_freed(self):
        self.freed = True
        self.bg.set_fill(FREED_BG, 1.0).set_stroke(RED, width=2.0)
        self.set_value("FREED", RED)

    def mark_allocated(self):
        self.freed = False
        self.bg.set_fill(ALLOC_BG, 1.0).set_stroke(GREEN, width=2.0)

    def restore(self, v):
        self.freed = False
        brd = PTR_COL if self.is_ptr else SAFE_BRD
        self.bg.set_fill(SAFE_BG, 1.0).set_stroke(brd, width=2.2 if self.is_ptr else 1.8)
        self.set_value(v, YELLOW if self.is_ptr else WHITE)

    def move_to(self, cx, cy):
        self.group.shift(v3(cx-self.cx, cy-self.cy));  self.cx, self.cy = cx, cy

    def top(self):  return v3(self.cx, self.cy+self.H/2)
    def bot(self):  return v3(self.cx, self.cy-self.H/2)
    def lft(self):  return v3(self.cx-self.W/2, self.cy)
    def rgt(self):  return v3(self.cx+self.W/2, self.cy)
    def vc(self):   return v3(self.cx, self.cy-0.02)

    def hit_val(self, pt):
        return (abs(pt[0]-self.cx) < self.W/2-0.04 and
                abs(pt[1]-(self.cy-0.02)) < 0.20)

    def remove(self): self.scene.remove(self.group)


class PtrArrow:
    GAP = 0.05

    def __init__(self, scene, src, dst, key):
        self.scene=scene;  self.src=src;  self.dst=dst;  self.key=key
        self.mob=None;  self._draw()

    def _ep(self):
        sx,sy=self.src.cx,self.src.cy;  dx,dy=self.dst.cx,self.dst.cy
        g=self.GAP;  SW,SH=self.src.W/2,self.src.H/2;  DW,DH=self.dst.W/2,self.dst.H/2
        ddx,ddy=dx-sx,dy-sy
        if abs(ddx) >= abs(ddy):
            if ddx>=0:
                s,e=v3(sx+SW+g,sy),v3(dx-DW-g,dy)
                a=TAU/12 if ddy>0.3 else (-TAU/12 if ddy<-0.3 else 0.)
            else:
                s,e=v3(sx-SW-g,sy),v3(dx+DW+g,dy)
                a=-TAU/12 if ddy>0.3 else (TAU/12 if ddy<-0.3 else 0.)
        else:
            if ddy>=0:
                s,e=v3(sx,sy+SH+g),v3(dx,dy-DH-g)
                a=-TAU/10 if ddx>0.3 else (TAU/10 if ddx<-0.3 else 0.)
            else:
                s,e=v3(sx,sy-SH-g),v3(dx,dy+DH+g)
                a=TAU/10 if ddx>0.3 else (-TAU/10 if ddx<-0.3 else 0.)
        if abs(ddx)<0.1 and abs(ddy)<0.1:
            s,e,a=v3(sx+SW+g,sy+SH*0.3),v3(dx+DW+g,dy-DH*0.3),-TAU/4
        return s, e, a

    def _draw(self):
        if self.mob and self.mob in self.scene.mobjects: self.scene.remove(self.mob)
        s,e,a = self._ep()
        self.mob = CurvedArrow(s, e, color=PTR_COL, stroke_width=2.4, angle=a)
        self.scene.add(self.mob)

    def refresh(self): self._draw()

    def remove(self):
        if self.mob and self.mob in self.scene.mobjects: self.scene.remove(self.mob)
        self.mob = None


class MemSys:
    def __init__(self, scene):
        self.scene  = scene
        self.safes:  dict = {}
        self.arrows: dict = {}

    def _addr_map(self):
        return {s.addr.lower(): n for n,s in self.safes.items()}

    def on_val_changed(self, name):
        s = self.safes.get(name)
        if not s or not s.is_ptr: return
        val = s.value.strip().lower()
        for key in [k for k in self.arrows if k.startswith(name+"->")]:
            self.arrows[key].remove();  del self.arrows[key]
        if val in ("null","0",""):
            s.bg.set_stroke(GREY, width=1.6);  return
        s.bg.set_stroke(PTR_COL, width=2.2)
        tgt = self._addr_map().get(val)
        if tgt and tgt != name and tgt in self.safes:
            key = f"{name}->{tgt}"
            arr = PtrArrow(self.scene, s, self.safes[tgt], key)
            self.arrows[key] = arr;  s.flash(PTR_COL)
            t2 = self.safes[tgt]
            if t2.is_heap and not t2.freed: t2.mark_allocated()

    def on_heap_freed(self, hname):
        h = self.safes.get(hname)
        if h: h.mark_freed()
        for arr in self.arrows.values():
            if arr.dst is h: arr.mob.set_stroke(RED, width=2.4)

    def add(self, name, addr, val, cx, cy, is_ptr=False, is_heap=False):
        s = SafeCell(self.scene, name, addr, val, cx, cy, is_ptr, is_heap)
        self.safes[name] = s
        if is_ptr: self.on_val_changed(name)
        return s

    def remove(self, name):
        s = self.safes.pop(name, None)
        if not s: return
        for k in [k for k,a in self.arrows.items() if a.src is s or a.dst is s]:
            self.arrows[k].remove();  del self.arrows[k]
        s.remove()

    def set_val(self, name, val, col=None):
        s = self.safes.get(name)
        if not s: return
        s.set_value(val, col);  self.on_val_changed(name)

    def clear(self):
        for a in list(self.arrows.values()): a.remove()
        self.arrows.clear()
        for s in list(self.safes.values()): s.remove()
        self.safes.clear()

    def refresh(self, name):
        for arr in self.arrows.values():
            if arr.src.name==name or arr.dst.name==name: arr.refresh()


# ───────────────────────────────────────────────────────────────
#  STEP CONTROLLER
# ───────────────────────────────────────────────────────────────
class StepCtrl:
    def __init__(self):
        self._q  = [];  self._s = []
        self._ed: Optional[Editor] = None

    def set_ed(self, ed):
        self._ed = ed

    def load(self, steps):
        self._q = steps;  self._s = []

    @property
    def pos(self):      return len(self._s)
    @property
    def total(self):    return len(self._q)
    @property
    def can_next(self): return len(self._s) < len(self._q)
    @property
    def can_prev(self): return len(self._s) > 0

    def next(self):
        if self.can_next:
            step = self._q[len(self._s)]
            step["do"]()
            self._s.append(step)

    def prev(self):
        if not self.can_prev: return
        self._s.pop()["undo"]()
        if self._ed:
            if self._s:
                row = self._s[-1].get("row")
                self._ed.highlight_row(row)
            else:
                self._ed.highlight_row(None)

    def reset(self):
        while self.can_prev: self.prev()


# ───────────────────────────────────────────────────────────────
#  STEP BUILDER
# ───────────────────────────────────────────────────────────────
def build_steps(ed: Editor, mem: MemSys, grid: SafeGrid):
    steps = []
    reg   = {}
    state = {"sa": 0xBFF0, "ha": 0x2000}

    steps.append({"do":   lambda: ed.highlight_row(None),
                  "undo": lambda: ed.highlight_row(None),
                  "row":  None})

    for li, raw in enumerate(ed.lines):
        line = raw.strip()
        if (not line or line.startswith(("//","/*","#")) or
                re.match(r'int\s+main\s*\(', line) or
                line in ('{','}') or re.match(r'return\s', line)):
            continue

        m = re.match(r'^int\s+([a-zA-Z_]\w*)\s*=\s*([^;*&]+);', line)
        if m and "malloc" not in line and "*" not in line.split("=")[0]:
            var, val = m.group(1), m.group(2).strip()
            addr = hex(state["sa"]);  state["sa"] -= 8
            def _mk(i=li, v=var, vl=val, a=addr):
                def do():
                    ed.highlight_row(i)
                    cx, cy = grid.alloc()
                    s = mem.add(v, a, vl, cx, cy);  s.flash()
                    reg[v] = {"addr": a}
                def undo():
                    if v in mem.safes: grid.release(mem.safes[v].cx, mem.safes[v].cy)
                    mem.remove(v);  reg.pop(v, None)
                return {"do": do, "undo": undo, "row": i}
            steps.append(_mk());  continue

        m = re.match(r'^int\s*\*\s*([a-zA-Z_]\w*)\s*=\s*&([a-zA-Z_]\w*)\s*;', line)
        if m:
            ptr, tgt = m.group(1), m.group(2)
            addr = hex(state["sa"]);  state["sa"] -= 8
            def _mk(i=li, p=ptr, tg=tgt, a=addr):
                def do():
                    ed.highlight_row(i)
                    ta = reg.get(tg, {}).get("addr", "?")
                    cx, cy = grid.alloc()
                    mem.add(p, a, ta, cx, cy, is_ptr=True)
                    reg[p] = {"addr": a, "target": tg}
                def undo():
                    if p in mem.safes: grid.release(mem.safes[p].cx, mem.safes[p].cy)
                    mem.remove(p);  reg.pop(p, None)
                return {"do": do, "undo": undo, "row": i}
            steps.append(_mk());  continue

        m = re.match(r'^\*([a-zA-Z_]\w*)\s*=\s*([^;]+);', line)
        if m:
            ptr, val = m.group(1), m.group(2).strip()
            def _mk(i=li, p=ptr, v=val):
                ov = [None]
                def do():
                    ed.highlight_row(i)
                    dest = reg.get(p, {}).get("target") or reg.get(p, {}).get("heap_target")
                    if dest and dest in mem.safes:
                        ov[0] = mem.safes[dest].value
                        mem.safes[dest].flash()
                        mem.set_val(dest, v)
                def undo():
                    dest = reg.get(p, {}).get("target") or reg.get(p, {}).get("heap_target")
                    if dest and dest in mem.safes and ov[0]:
                        mem.set_val(dest, ov[0])
                return {"do": do, "undo": undo, "row": i}
            steps.append(_mk());  continue

        m = re.match(r'(?:int\s*\*\s*)?([a-zA-Z_]\w*)\s*=\s*malloc\(', line)
        if m:
            ptr = m.group(1)
            ha  = hex(state["ha"]);  state["ha"] += 16
            sa  = hex(state["sa"]);  state["sa"] -= 8
            def _mk(i=li, p=ptr, h=ha, s2=sa):
                hk = f"{p}_heap"
                def do():
                    ed.highlight_row(i)
                    cx_h, cy_h = grid.alloc()
                    mem.add(hk, h, "?", cx_h, cy_h, is_heap=True)
                    cx_p, cy_p = grid.alloc()
                    mem.add(p, s2, h, cx_p, cy_p, is_ptr=True)
                    reg[p]  = {"addr": s2, "heap_target": hk}
                    reg[hk] = {"addr": h}
                def undo():
                    for n in [p, hk]:
                        if n in mem.safes: grid.release(mem.safes[n].cx, mem.safes[n].cy)
                        mem.remove(n);  reg.pop(n, None)
                return {"do": do, "undo": undo, "row": i}
            steps.append(_mk());  continue

        m = re.match(r'^free\(([a-zA-Z_]\w*)\)', line)
        if m:
            ptr = m.group(1)
            def _mk(i=li, p=ptr):
                ov = [None]
                def do():
                    ed.highlight_row(i)
                    hk = reg.get(p, {}).get("heap_target")
                    if hk and hk in mem.safes:
                        ov[0] = mem.safes[hk].value
                        mem.on_heap_freed(hk)
                def undo():
                    hk = reg.get(p, {}).get("heap_target")
                    if hk and hk in mem.safes and ov[0]:
                        mem.safes[hk].restore(ov[0])
                return {"do": do, "undo": undo, "row": i}
            steps.append(_mk());  continue

        m = re.match(r'^([a-zA-Z_]\w*)\s*=\s*NULL', line)
        if m:
            ptr = m.group(1)
            def _mk(i=li, p=ptr):
                ov = [None]
                def do():
                    ed.highlight_row(i)
                    if p in mem.safes:
                        ov[0] = mem.safes[p].value
                        mem.set_val(p, "NULL", GREY_L)
                        mem.safes[p].bg.set_stroke(GREY, width=1.6)
                def undo():
                    if p in mem.safes and ov[0]:
                        mem.set_val(p, ov[0], YELLOW)
                        mem.safes[p].bg.set_stroke(PTR_COL, width=2.2)
                return {"do": do, "undo": undo, "row": i}
            steps.append(_mk());  continue

    steps.append({"do": lambda: ed.highlight_row(None),
                  "undo": lambda: None, "row": None})
    return steps


DEFAULT_CODE = [
    "#include <stdio.h>",
    "#include <stdlib.h>",
    "",
    "int main() {",
    "    int  x = 5;",
    "    int *p = &x;",
    "    printf(\"%d\", *p);",
    "    *p = 99;",
    "",
    "    int *q = malloc(sizeof(int));",
    "    *q = 42;",
    "    free(q);",
    "    q = NULL;",
    "    return 0;",
    "}",
]


# ───────────────────────────────────────────────────────────────
#  HELP PANEL
# ───────────────────────────────────────────────────────────────
HELP_LINES = [
    ("══  Keyboard Shortcuts  ══", CYAN),
    ("", WHITE),
    ("── Navigation ──", YELLOW),
    ("→  /  ←          Next / Prev step", WHITE),
    ("Space            Auto-play toggle", GREEN),
    ("R                Reset all steps", WHITE),
    ("H                Toggle this help", ORANGE),
    ("", WHITE),
    ("── Editor ──", YELLOW),
    ("Ctrl + ↵         Compile code", WHITE),
    ("E                Toggle editor", WHITE),
    ("N                Toggle notes", WHITE),
    ("Ctrl + Z / Y     Undo / Redo", WHITE),
    ("Ctrl + C / X / V Copy/Cut/Paste", WHITE),
    ("Ctrl + A         Select all", WHITE),
    ("Tab / Shift+Tab  Indent / Unindent", WHITE),
    ("", WHITE),
    ("── Notes ──", YELLOW),
    ("Click            Activate / move cursor", WHITE),
    ("Ctrl + ↵         Finish editing", WHITE),
    ("Ctrl + C/X/V     Copy/Cut/Paste (OS clipboard)", WHITE),
    ("Ctrl + A         Select all", WHITE),
    ("Ctrl + Z / Y     Undo / Redo", WHITE),
    ("Ctrl + =         Zoom in", WHITE),
    ("Ctrl + -/Tiret6  Zoom out", WHITE),
    ("", WHITE),
    ("── Memory Cells ──", YELLOW),
    ("Drag             Move cells", WHITE),
    ("Click value      Edit value", WHITE),
    ("", WHITE),
    ("Press  H  to close", GREY_L),
]


# ───────────────────────────────────────────────────────────────
#  MAIN SCENE  (v9-fix)
# ───────────────────────────────────────────────────────────────
class PointerViz(Scene):

    def construct(self):
        self._hook_text()
        self.camera.background_color = BG

        self._layout   = Layout(show_editor=True, show_note=True)
        self._action   = None
        self._mods     = 0
        self._drag_safe  = None
        self._drag_off   = [0.0, 0.0]
        self._dbl_t      = 0.0

        self._vedit_safe = None
        self._vedit_buf  = ""
        self._vedit_mob  = None
        self._vedit_box  = None

        self._chrome_mobs: list = []
        self._show_help  = False
        self._help_mobs: list = []

        self._auto_play     = False
        self._auto_t        = 0.0
        self._auto_interval = 1.4

        self._show_teacher()

    def _hook_text(self):
        win = getattr(self, "window", None)
        if not win: return
        w = getattr(win, "_window", win)
        if hasattr(w, "push_handlers"):
            w.push_handlers(on_text=self._on_text)
        elif hasattr(w, "unicode_char_entered_func"):
            w.unicode_char_entered_func = self._on_text

    def _show_teacher(self):
        self.clear()
        self._drag_safe  = None
        self._vedit_safe = None;  self._vedit_buf = ""
        self._vedit_mob  = None;  self._vedit_box = None
        self._auto_play  = False

        L = self._layout
        self._mem  = MemSys(self)
        self._grid = SafeGrid(L)
        self._sc   = StepCtrl()

        self._ed = Editor(self, list(DEFAULT_CODE), L)
        self._sc.set_ed(self._ed)

        def _on_ed_change():
            n_note  = len(self._note.lines) if hasattr(self, '_note') else 1
            changed = self._layout.update_line_counts(len(self._ed.lines), n_note)
            if changed:
                self._rebuild_chrome()
                self._ed.full_redraw()
                if hasattr(self, '_note'):
                    self._note._recompute_wrap()
                    self._note.full_redraw()
        self._ed.on_change = _on_ed_change

        def _on_note_change():
            changed = self._layout.update_line_counts(
                len(self._ed.lines), len(self._note.lines))
            if changed:
                self._rebuild_chrome()
                self._ed.full_redraw()
                self._note._recompute_wrap()
                self._note.full_redraw()

        self._note = NotePanel(self, L, on_change=_on_note_change)

        self._layout.update_line_counts(len(self._ed.lines), len(self._note.lines))
        self._build_ui()
        self._ed.full_redraw()
        self._note.full_redraw()
        self._compile()

        while not self.is_window_closing():
            self._ed.flush()
            self._note.tick()

            if self._auto_play:
                now = time.time()
                if now - self._auto_t >= self._auto_interval:
                    self._auto_t = now
                    if self._sc.can_next:
                        self._vedit_commit()
                        self._sc.next()
                    else:
                        self._auto_play = False

            self.update_frame(1/60)
            a = self._action;  self._action = None
            if   a == "compile":      self._vedit_commit(); self._compile()
            elif a == "t_next":       self._vedit_commit(); self._sc.next()
            elif a == "t_prev":       self._vedit_commit(); self._sc.prev()
            elif a == "t_reset":      self._vedit_commit(); self._reset()
            elif a == "toggle_ed":    self._toggle_editor()
            elif a == "toggle_note":  self._toggle_note()
            elif a == "toggle_help":  self._toggle_help()
            elif a == "toggle_auto":
                self._auto_play = not self._auto_play
                self._auto_t    = time.time()

    def _toggle_editor(self):
        self._ed.cleanup()
        self._layout.toggle_editor()
        self._rebuild_chrome()
        if self._layout.show_editor:
            self._ed._recompute_wrap()
            self._ed.full_redraw()
        if hasattr(self, '_note'):
            self._note._recompute_wrap()
            self._note.full_redraw()
        self._grid.rebuild()

    def _toggle_note(self):
        if self._layout.show_note:
            save_notes(self._note.lines)
        self._note.remove_all()
        self._layout.toggle_note()
        self._rebuild_chrome()
        self._ed._recompute_wrap()
        self._ed.full_redraw()
        if self._layout.show_note:
            self._note._recompute_wrap()
            self._note.full_redraw()
        self._grid.rebuild()

    def _rebuild_chrome(self):
        for m in self._chrome_mobs:
            try:
                if m in self.mobjects: self.remove(m)
            except Exception: pass
        self._chrome_mobs = []
        self._build_ui()

    def _build_ui(self):
        L = self._layout

        def _t(mob):
            self.add(mob);  self._chrome_mobs.append(mob)

        TITLE_H = 0.52

        title = lbl("Pointers & Memory", 0.6, WHITE)
        title.set_opacity(1.0)
        title.move_to(v3(0, FH/2 - TITLE_H/2))
        _t(title)

        if L.show_editor:
            cp = RoundedRectangle(corner_radius=0.08, width=L.ed_w, height=L.ed_h)
            cp.set_fill(P_ED, 1.0).set_stroke("#1e2545", 1.4)
            cp.move_to(v3(L.ed_x, L.ed_y));  _t(cp)

            ehdr = Rectangle(width=L.ed_w, height=ED_HEADER_H)
            ehdr.set_fill("#07090f", 1.0).set_stroke("#1e2545", 0.6)
            ehdr.move_to(v3(L.ed_x, L.ed_y + L.ed_h/2 - ED_HEADER_H/2));  _t(ehdr)

            for i, col in enumerate(["#f05555","#f5c842","#3dd68c"]):
                d = Circle(radius=0.065)
                d.set_fill(col, 1.0).set_stroke(width=0)
                d.move_to(v3(L.ed_l+0.20+i*0.22, L.ed_y+L.ed_h/2-ED_HEADER_H/2));  _t(d)
            _t(lbl("main.c", 0.24, GREY_L)
               .move_to(v3(L.ed_l+1.10, L.ed_y+L.ed_h/2-ED_HEADER_H/2)))

            gutter_h = L.ed_h - ED_HEADER_H
            gutter = Rectangle(width=LN_W, height=gutter_h)
            gutter.set_fill("#060810", 0.95).set_stroke(DIM, 0.4)
            gutter.move_to(v3(L.ed_l+LN_W/2, L.ed_y - ED_HEADER_H/2));  _t(gutter)

            gdiv = Line(
                [L.ed_l+LN_W, L.ed_y+L.ed_h/2-ED_HEADER_H, 0],
                [L.ed_l+LN_W, L.ed_y-L.ed_h/2,              0])
            gdiv.set_stroke(DIM, 0.5);  _t(gdiv)

            total_dr = self._ed._total_disp_rows() if hasattr(self, '_ed') else len(DEFAULT_CODE)
            if total_dr > MAX_LINES_ED:
                n_vis  = self._ed._visible_rows() if hasattr(self, '_ed') else MAX_LINES_ED
                scroll = self._ed._scroll if hasattr(self, '_ed') else 0
                bar_h  = gutter_h * n_vis / max(1, total_dr)
                bar_y  = (L.ed_y + L.ed_h/2 - ED_HEADER_H -
                          gutter_h * (scroll / max(1, total_dr)) - bar_h/2)
                sbar = Rectangle(width=0.06, height=max(0.12, bar_h))
                sbar.set_fill(GREY, 0.6).set_stroke(width=0)
                sbar.move_to(v3(L.ed_r - 0.04, bar_y));  _t(sbar)

        if L.show_note:
            np_ = RoundedRectangle(corner_radius=0.08, width=L.note_w, height=L.note_h)
            np_.set_fill(P_NOTE, 1.0).set_stroke("#1e2545", 1.2)
            np_.move_to(v3(L.note_x, L.note_y));  _t(np_)

    def _toggle_help(self):
        self._show_help = not self._show_help
        if self._show_help: self._draw_help()
        else: self._hide_help()

    def _hide_help(self):
        for m in self._help_mobs:
            try:
                if m in self.mobjects: self.remove(m)
            except Exception: pass
        self._help_mobs = []

    def _draw_help(self):
        self._hide_help()
        panel_w = 5.80
        panel_h = min(len(HELP_LINES) * 0.295 + 0.40, FH - TOPBAR_H - 0.30)

        bg = RoundedRectangle(corner_radius=0.14, width=panel_w, height=panel_h)
        bg.set_fill("#080b18", 0.97).set_stroke(BLUE, width=1.8)
        bg.move_to(v3(0, 0))
        self.add(bg);  self._help_mobs.append(bg)

        y_start = panel_h / 2 - 0.26
        for i, (text, col) in enumerate(HELP_LINES):
            if not text: continue
            size = 0.26 if i == 0 else 0.22
            t = lbl(text, size, col)
            t.move_to(v3(-panel_w/2 + 0.25, y_start - i * 0.285), aligned_edge=LEFT)
            self.add(t);  self._help_mobs.append(t)

    def _compile(self):
        self._ed.set_focused(False)
        self._reset()
        steps = build_steps(self._ed, self._mem, self._grid)
        self._sc.load(steps)

    def _reset(self):
        self._sc.reset()
        self._mem.clear()
        self._grid.rebuild()
        self._ed.clear_highlight()
        self._ed._dov = True
        self._auto_play = False

    def _vedit_commit(self):
        for m in (self._vedit_mob, self._vedit_box):
            if m is not None:
                try:
                    if m in self.mobjects: self.remove(m)
                except Exception: pass
        self._vedit_mob = self._vedit_box = None
        if self._vedit_safe is not None:
            val = self._vedit_buf.strip()
            if val:
                self._vedit_safe.set_value(val)
                name = self._vedit_safe.name
                if name in self._mem.safes: self._mem.on_val_changed(name)
        self._vedit_safe = None;  self._vedit_buf = ""

    def _vedit_start(self, safe):
        self._vedit_commit();  self._vedit_safe = safe;  self._vedit_buf = ""
        self._vedit_draw()

    def _vedit_draw(self):
        for m in (self._vedit_mob, self._vedit_box):
            if m is not None:
                try:
                    if m in self.mobjects: self.remove(m)
                except Exception: pass
        s = self._vedit_safe
        if not s: return
        box = RoundedRectangle(corner_radius=0.06, width=s.W-0.14, height=0.30)
        box.set_fill("#0a0e22", 0.96).set_stroke(YELLOW, width=1.6)
        box.move_to(s.vc())
        txt = lbl(self._vedit_buf+"|", 0.26, YELLOW)
        txt.move_to(s.vc())
        self.add(box, txt)
        self._vedit_box = box;  self._vedit_mob = txt

    def _vedit_cancel(self):
        for m in (self._vedit_mob, self._vedit_box):
            if m is not None:
                try:
                    if m in self.mobjects: self.remove(m)
                except Exception: pass
        self._vedit_mob = self._vedit_box = None
        self._vedit_safe = None;  self._vedit_buf = ""

    # ─── MOUSE ─────────────────────────────────────────────────
    def on_mouse_press(self, point, button, mods):
        pt = point
        shift = bool(mods & K.MOD_SHIFT)

        if self._layout.show_note and self._note.in_panel(pt[0], pt[1]):
            self._ed.set_focused(False)
            if not shift:
                self._note.sel.clear()
            self._note.click_at(pt[0], pt[1])
            return

        if self._note.is_active():
            self._note.deactivate()

        if self._vedit_safe is not None:
            clicked_same = self._vedit_safe.hit_val(pt) or hit(self._vedit_safe.bg, pt)
            if not clicked_same: self._vedit_commit()
            else: return

        for s in self._mem.safes.values():
            if s.hit_val(pt):
                self._drag_safe = None;  self._ed.set_focused(False)
                self._vedit_start(s);  return
            if hit(s.bg, pt):
                self._drag_safe = s
                self._drag_off  = [pt[0]-s.cx, pt[1]-s.cy];  return

        if self._layout.show_editor and self._ed.in_panel(pt[0], pt[1]):
            now = time.time()
            dbl = (now - self._dbl_t) < 0.35;  self._dbl_t = now
            self._ed.set_focused(True)
            if dbl: self._ed.select_word(pt[0], pt[1])
            else:
                self._ed.click(pt[0], pt[1], extend=shift)
        else:
            self._ed.set_focused(False)
            if not shift:
                self._ed.sel.clear()
                self._ed._dov = True

    def on_mouse_drag(self, point, d_point, button, mods):
        if self._vedit_safe is not None: return
        if self._ed.focused and not self._drag_safe:
            self._ed.click(point[0], point[1], extend=True);  return
        if self._drag_safe:
            nx = point[0] - self._drag_off[0]
            ny = point[1] - self._drag_off[1]
            self._drag_safe.move_to(nx, ny)
            self._mem.refresh(self._drag_safe.name)

    def on_mouse_release(self, point, button, mods):
        self._drag_safe = None

    def on_mouse_motion(self, point, d_point): pass

    # ─── KEYBOARD ──────────────────────────────────────────────
    def on_key_press(self, symbol, modifiers):
        self._mods = modifiers
        ctrl  = bool(modifiers & K.MOD_CTRL)
        shift = bool(modifiers & K.MOD_SHIFT)

        if self._vedit_safe is not None:
            if symbol in (K.RETURN, K.NUM_ENTER): self._vedit_commit()
            elif symbol == K.ESCAPE:              self._vedit_cancel()
            elif symbol == K.BACKSPACE:
                self._vedit_buf = self._vedit_buf[:-1];  self._vedit_draw()
            return

        if self._note.is_active():
            if symbol == K.ESCAPE:
                self._note.deactivate();  return
            self._note.key(symbol, modifiers)
            return

        ed = self._ed
        if ed.focused:
            if ctrl:
                if   symbol == K.RETURN: self._action = "compile"
                elif symbol == K.Z:      ed.undo()
                elif symbol == K.Y:      ed.redo()
                elif symbol == K.A:      ed.select_all(); ed._dov = True
                elif symbol == K.C:      ed.copy()
                elif symbol == K.V:      ed.paste()
                elif symbol == K.X:      ed.cut()
            else:
                if   symbol == K.LEFT:   ed.move_left(shift)
                elif symbol == K.RIGHT:  ed.move_right(shift)
                elif symbol == K.UP:     ed.move_up(shift)
                elif symbol == K.DOWN:   ed.move_down(shift)
                elif symbol == K.HOME:   ed.home(shift)
                elif symbol == K.END:    ed.end(shift)
                elif symbol in (K.RETURN, K.NUM_ENTER): ed.newline()
                elif symbol == K.BACKSPACE: ed.backspace()
                elif symbol == K.DELETE:    ed.delete_fwd()
                elif symbol == K.TAB:       ed.tab(shift)
            return

        if   symbol == K.RIGHT: self._action = "t_next"
        elif symbol == K.LEFT:  self._action = "t_prev"
        elif symbol == K.R:     self._action = "t_reset"
        elif symbol == K.E:     self._action = "toggle_ed"
        elif symbol == K.N:     self._action = "toggle_note"
        elif symbol == K.H:     self._action = "toggle_help"
        elif symbol == K.SPACE: self._action = "toggle_auto"

    def _on_text(self, text):
        ctrl_chars = '\r\n\x08\x7f\x01\x03\x04\x06\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f'
        if text in ctrl_chars: return
        if self._vedit_safe is not None:
            self._vedit_buf += text;  self._vedit_draw();  return
        if self._note.is_active():
            self._note.insert_text(text);  return
        if self._ed.focused:
            self._ed.insert(text)
