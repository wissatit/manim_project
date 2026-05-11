from manimlib import *
import pyglet.window.key as K
import time, copy, json, os

# ═══════════════════════════════════════════════ PALETTE ═════
BG_COLOR   = "#0d0f1a"
NODE_FILL  = "#12122a"
NEXT_FILL  = "#0a0a1e"
ARROW_COL  = "#4a9eff"
GRAY_COLOR = "#44475a"
SEL_COLOR  = "#f39c12"
FOUND_COL  = "#27ae60"
VISIT_COL  = "#e67e22"
ADDR_COLOR = "#7ec8e3"
DRAG_COL   = "#f1c40f"

PAD_BG      = "#070d18"
PAD_STROKE  = "#1e4a7f"
PAD_TEXT    = "#c8dff5"
PAD_SEL_BG  = "#1a3a5f"
PAD_LINE_NR = "#2a3a4a"
BTN_FONT_UP = "#0d5a8f"
BTN_FONT_DN = "#1a3a5f"
TOG_COL     = "#2563eb"

BTN_ADD_H = "#1b5e8f";  BTN_ADD_T = "#0d6b53"
BTN_DEL   = "#8e2318";  BTN_SCH   = "#512b7a"
BTN_TRV   = "#7d560e";  BTN_REV   = "#09513e"
BTN_RST   = "#5c1c14"

ARR_COL    = "#e74c3c"
ARR_NEW    = "#f39c12"
ARR_SHIFT  = "#c0392b"
LL_COL     = FOUND_COL
LL_NEW     = "#f39c12"
LL_PTR     = ARROW_COL

HELP_BG    = "#0a0f1e"
HELP_STROKE = "#1e3a5f"
HELP_TEXT  = "#c8dff5"
HELP_TITLE = "#4a9eff"
HELP_KEY   = "#f39c12"

FAKE_ADDRS   = [f"0x{(0xA10 + i*0x14):03X}" for i in range(30)]
SCATTERED    = ["0xF20", "0x3A0", "0xB14", "0x720", "0xC88",
                "0x2F0", "0x8D4", "0x5A8", "0xE1C", "0x430"]
DEFAULT_LIST = [12, 7, 35, 4, 19]
S2_DEFAULT   = [12, 7, 35]
S5_ARR_DEF   = [10, 20, 30, 40, 50]
S5_LL_DEF    = [10, 20, 30, 40, 50]
N_SCENES     = 6

# ══════════════════════════════════════════════ LAYOUT ═══════
_PAD_CX_VIS = -4.80
_PAD_CX_HID = -10.50
_PAD_CY     =  0.10
_PAD_W      =  3.00
_PAD_H      =  7.20
_SLIDE_FRAMES = 14


# ═══════════════════════════════════════════ KEY → CHAR ══════
_SHIFT_MAP = {
    ord('`'): '~',  ord('1'): '!',  ord('2'): '@',  ord('3'): '#',
    ord('4'): '$',  ord('5'): '%',  ord('6'): '^',  ord('7'): '&',
    ord('8'): '*',  ord('9'): '(',  ord('0'): ')',  ord('-'): '_',
    ord('='): '+',  ord('['): '{',  ord(']'): '}',  ord('\\'): '|',
    ord(';'): ':',  ord("'"): '"',  ord(','): '<',  ord('.'): '>',
    ord('/'): '?',
}

def _sym_to_char(symbol: int, modifiers: int) -> str:
    shift = bool(modifiers & K.MOD_SHIFT)
    ctrl  = bool(modifiers & K.MOD_CTRL)
    if ctrl:
        return ""
    if K.A <= symbol <= K.Z:
        ch = chr(symbol)
        return ch.upper() if shift else ch
    if 32 <= symbol <= 126:
        ch = chr(symbol)
        if shift:
            return _SHIFT_MAP.get(symbol, ch.upper())
        return ch
    if symbol == K.SPACE:
        return ' '
    return ""


def _get_clipboard() -> str:
    try:
        import ctypes
        CF_UNICODETEXT = 13
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        if u32.OpenClipboard(None):
            try:
                h = u32.GetClipboardData(CF_UNICODETEXT)
                if h:
                    ptr = k32.GlobalLock(h)
                    if ptr:
                        try:
                            text = ctypes.wstring_at(ptr)
                        finally:
                            k32.GlobalUnlock(h)
                        if text:
                            return text
            finally:
                u32.CloseClipboard()
    except Exception:
        pass
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        if text:
            return text
    except Exception:
        pass
    return _PS.clip


def _tog_pos():
    header_y = _PAD_CY + _PAD_H / 2 + 0.07
    if _PS.visible:
        x = _PAD_CX_VIS - _PAD_W / 2 + 0.19
    else:
        x = -6.50
    return x, header_y

def _cx():  return  1.60 if _PS.visible else 0.00
def _cl():  return -3.10 if _PS.visible else -6.80
def _cw():  return 10.00 if _PS.visible else 13.60

MAX_ROW_VIS  = 4
MAX_ROW_FULL = 6

# ═══════════════════════════════════════════ PERSISTENCE ═════
_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ll_notes.json")

def _load_saved_notes():
    try:
        with open(_SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        notes = data.get("notes", [[""] for _ in range(N_SCENES)])
        while len(notes) < N_SCENES:
            notes.append([""])
        return notes[:N_SCENES]
    except Exception:
        return [[""] for _ in range(N_SCENES)]

def _save_notes(scene_lines):
    try:
        with open(_SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump({"notes": scene_lines}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

class _PadState:
    scene_lines : list = _load_saved_notes()
    visible      = False
    undo_stk    : list = [[] for _ in range(N_SCENES)]
    redo_stk    : list = [[] for _ in range(N_SCENES)]
    clip         = ""
    cur_scene    = 0

_PS = _PadState()


# ══════════════════════════════════════════════ NOTEPAD ════
class Notepad:
    SCALE_BASE  = 0.220
    LINE_H_BASE = 0.310
    CHAR_W_EST  = 0.130
    PAD_LEFT    = 0.14
    PAD_RIGHT   = 0.12
    PAD_TOP     = 0.28

    def __init__(self, scene, cx, cy, scene_idx=0):
        self._scene     = scene
        self._cx        = cx
        self._cy        = cy
        self._scene_idx = scene_idx
        self._scale     = self.SCALE_BASE
        self._line_h    = self.LINE_H_BASE
        self._raw       = _PS.scene_lines[scene_idx]
        self._cur_l     = min(len(self._raw)-1, 0)
        self._cur_c     = 0
        self._sel_anch  = None
        self._active    = False
        self._mobs      : list = []
        self._fmobs     : list = []
        self._vis_line_widths: dict = {}
        self._last_render_t = 0.0
        self._render_dirty  = True
        self._build_frame()
        self._render(force=True)

    def _build_frame(self):
        bw = _PAD_W + 0.40
        bh = _PAD_H + 0.50
        self._bg = Rectangle(width=bw, height=bh)
        self._bg.set_fill(PAD_BG, 0.97).set_stroke(PAD_STROKE, 1.8)
        self._bg.move_to(np.array([self._cx, self._cy, 0]))

        header = Rectangle(width=bw, height=0.36)
        header.set_fill("#0a1525", 1).set_stroke(PAD_STROKE, 1.0)
        header.move_to(np.array([self._cx, self._cy + _PAD_H/2 + 0.07, 0]))
        self._header = header

        self._btn_plus  = self._mk_icon_btn("[A+]", self._cx + _PAD_W/2 - 0.30,
                                            self._cy + _PAD_H/2 + 0.07, BTN_FONT_UP)
        self._btn_minus = self._mk_icon_btn("[A-]", self._cx + _PAD_W/2 - 0.78,
                                            self._cy + _PAD_H/2 + 0.07, BTN_FONT_DN)

        self._stat_mob = Text("READ", color=GRAY_COLOR).scale(0.17)
        self._stat_mob.move_to(np.array([self._cx + 0.20, self._cy + _PAD_H/2 + 0.07, 0]))

        self._rule = Line(
            np.array([self._cx - bw/2 + 0.08, self._cy + _PAD_H/2 - 0.12, 0]),
            np.array([self._cx + bw/2 - 0.08, self._cy + _PAD_H/2 - 0.12, 0])
        ).set_stroke(PAD_STROKE, 0.8, opacity=0.50)

        for m in [self._bg, self._header,
                  self._btn_plus[0], self._btn_plus[1],
                  self._btn_minus[0], self._btn_minus[1],
                  self._stat_mob, self._rule]:
            self._scene.add(m)
            self._fmobs.append(m)

    def _mk_icon_btn(self, txt, x, y, color):
        bg = RoundedRectangle(corner_radius=0.05, width=0.44, height=0.24)
        bg.set_fill(color, 0.85).set_stroke(WHITE, 0.5)
        bg.move_to(np.array([x, y, 0]))
        t = Text(txt, color=WHITE).scale(0.15)
        t.move_to(np.array([x, y, 0]))
        return bg, t

    def all_mobs(self): return self._fmobs + self._mobs

    def _text_left_x(self):
        return self._cx - _PAD_W/2 + self.PAD_LEFT

    def _text_right_x(self):
        return self._cx + _PAD_W/2 - self.PAD_RIGHT

    def _text_area_width(self):
        return self._text_right_x() - self._text_left_x()

    def _max_chars_per_line(self):
        cw = self.CHAR_W_EST * (self._scale / self.SCALE_BASE)
        return max(8, int(self._text_area_width() / cw))

    def _top_y(self):
        return self._cy + _PAD_H/2 - self.PAD_TOP

    def _wrap_line(self, raw_line):
        if not raw_line:
            return [""]
        max_width = self._text_area_width()
        words = raw_line.split(" ")
        lines = []
        current = ""
        for w in words:
            test = current + (" " if current else "") + w
            try:
                t = Text(test).scale(self._scale)
                w_width = t.get_width()
            except:
                w_width = len(test) * self.CHAR_W_EST * (self._scale / self.SCALE_BASE)
            if w_width <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)
        return lines

    def _build_display(self):
        vis_lines  = []
        cur_vis    = (0, 0)
        sel_start = sel_end = None
        if self._has_sel():
            sl, sc, el, ec = self._norm_sel()
            sel_start = (sl, sc)
            sel_end   = (el, ec)
        sel_regions = []

        for li, raw in enumerate(self._raw):
            if not raw:
                vis_idx = len(vis_lines)
                if li == self._cur_l:
                    cur_vis = (vis_idx, 0)
                if sel_start and sel_end:
                    sl, sc = sel_start; el, ec = sel_end
                    if sl <= li <= el:
                        sel_regions.append((vis_idx, 0, 0))
                vis_lines.append("")
                continue

            chunks = self._wrap_line(raw) if raw else [""]
            if not chunks: chunks = [""]
            base_offset = 0
            for chunk in chunks:
                vis_idx = len(vis_lines)
                chunk_end = base_offset + len(chunk)
                if li == self._cur_l:
                    local_c = self._cur_c - base_offset
                    if 0 <= local_c <= len(chunk):
                        cur_vis = (vis_idx, local_c)
                if sel_start and sel_end:
                    sl, sc = sel_start; el, ec = sel_end
                    if sl <= li <= el:
                        cs = 0; ce = len(chunk)
                        if li == sl: cs = max(0, sc - base_offset)
                        if li == el: ce = min(len(chunk), ec - base_offset)
                        if cs < ce or (li > sl and li < el):
                            sel_regions.append((vis_idx, cs, ce))
                vis_lines.append(chunk)
                base_offset = chunk_end

        return vis_lines, cur_vis, sel_regions

    def _render(self, force=False):
        now = time.time()
        if not force and not self._render_dirty:
            if now - self._last_render_t < 0.016:
                return
        self._render_dirty = False
        self._last_render_t = now

        for m in self._mobs: self._scene.remove(m)
        self._mobs = []
        self._vis_line_widths = {}

        vis_lines, (cvl, cvc), sel_regions = self._build_display()
        top   = self._top_y()
        max_v = max(1, int((_PAD_H - 0.30) / self._line_h))
        lx0   = self._text_left_x()
        rox   = self._text_right_x()

        sel_set = {r[0]: (r[1], r[2]) for r in sel_regions}

        for vi, line in enumerate(vis_lines):
            if vi >= max_v: break
            y = top - vi * self._line_h
            if y < self._cy - _PAD_H/2 + 0.14: break

            if line:
                try:
                    _meas = Text(line, color=WHITE).scale(self._scale)
                    line_w = _meas.get_width()
                except Exception:
                    line_w = len(line) * self.CHAR_W_EST * (self._scale / self.SCALE_BASE)
            else:
                line_w = 0.0
            self._vis_line_widths[vi] = line_w

            if vi in sel_set:
                cs, ce = sel_set[vi]
                if line and line_w > 0:
                    n = len(line)
                    s_x = lx0 + (cs / n) * line_w
                    e_x = lx0 + (max(ce, cs + 1) / n) * line_w
                else:
                    ch_w = self.CHAR_W_EST * (self._scale / self.SCALE_BASE)
                    s_x  = lx0 + cs * ch_w
                    e_x  = lx0 + max(ce, cs + 1) * ch_w
                e_x   = min(e_x, rox)
                sel_w = max(e_x - s_x, 0.02)
                sel_bg = Rectangle(width=sel_w, height=self._line_h * 0.88)
                sel_bg.set_fill(PAD_SEL_BG, 0.85).set_stroke(width=0)
                sel_bg.move_to(np.array([s_x + sel_w / 2, y, 0]))
                self._scene.add(sel_bg)
                self._mobs.append(sel_bg)

            display = line if line else " "
            col = "#e0f0ff" if (self._active and vi == cvl) else PAD_TEXT

            try:
                t = Text(display, color=col).scale(self._scale)
            except Exception:
                t = Text(" ", color=col).scale(self._scale)

            t.move_to(np.array([lx0, y, 0]), aligned_edge=LEFT)
            self._scene.add(t)
            self._mobs.append(t)

            if self._active and vi == cvl:
                if line and cvc > 0:
                    prefix = line[:cvc]
                    try:
                        t_prefix = Text(prefix).scale(self._scale)
                        t_prefix.move_to(np.array([lx0, y, 0]), aligned_edge=LEFT)
                        prefix_w = t_prefix.get_right()[0] - lx0
                    except:
                        prefix_w = len(prefix) * self.CHAR_W_EST * (self._scale / self.SCALE_BASE)
                else:
                    prefix_w = 0
                cur_x = lx0 + prefix_w
                cur_x = min(cur_x, rox - 0.01)
                half_h = self._line_h * 0.40
                cur_line = Line(
                    np.array([cur_x, y - half_h, 0]),
                    np.array([cur_x, y + half_h, 0])
                ).set_stroke(YELLOW, 1.8)
                self._scene.add(cur_line)
                self._mobs.append(cur_line)

        _PS.scene_lines[self._scene_idx] = self._raw
        _save_notes(_PS.scene_lines)

    def click_at(self, point):
        top  = self._top_y()
        lx0  = self._text_left_x()
        dy   = top - point[1]
        vi   = max(0, int(dy / self._line_h))
        vis_lines, _, _ = self._build_display()
        vi = min(vi, len(vis_lines) - 1)
        if vi < 0: vi = 0
        line = vis_lines[vi] if vi < len(vis_lines) else ""
        dx   = max(0.0, point[0] - lx0)

        if line:
            best_i = 0
            best_diff = float('inf')
            for i in range(len(line) + 1):
                prefix = line[:i]
                if prefix:
                    try:
                        t = Text(prefix).scale(self._scale)
                        t.move_to(np.array([lx0, 0, 0]), aligned_edge=LEFT)
                        w = t.get_right()[0] - lx0
                    except:
                        w = len(prefix) * self.CHAR_W_EST * (self._scale / self.SCALE_BASE)
                else:
                    w = 0
                diff = abs(w - dx)
                if diff < best_diff:
                    best_diff = diff
                    best_i = i
            vc = best_i
        else:
            vc = 0

        vis_count = 0
        for li, raw in enumerate(self._raw):
            if not raw:
                if vis_count == vi:
                    self._cur_l = li; self._cur_c = 0; return
                vis_count += 1
                continue
            chunks = self._wrap_line(raw) if raw else [""]
            if not chunks: chunks = [""]
            base_off = 0
            for chunk in chunks:
                if vis_count == vi:
                    self._cur_l = li
                    self._cur_c = base_off + vc
                    return
                vis_count += 1
                base_off += len(chunk)
        self._cur_l = len(self._raw) - 1
        self._cur_c = len(self._raw[-1])

    def _set_status(self, txt, color):
        self._scene.remove(self._stat_mob)
        if self._stat_mob in self._fmobs:
            self._fmobs.remove(self._stat_mob)
        self._stat_mob = Text(txt, color=color).scale(0.17)
        self._stat_mob.move_to(np.array([self._cx + 0.20, self._cy + _PAD_H/2 + 0.07, 0]))
        self._scene.add(self._stat_mob)
        self._fmobs.append(self._stat_mob)

    def activate(self):
        self._active = True
        self._set_status("EDIT", FOUND_COL)
        self._render(force=True)

    def deactivate(self):
        self._active = False
        self._sel_anch = None
        self._set_status("READ", GRAY_COLOR)
        self._render(force=True)

    def is_active(self): return self._active

    def hit(self, p):
        bb = self._bg.get_bounding_box()
        return (bb[0][0] <= p[0] <= bb[2][0] and bb[0][1] <= p[1] <= bb[2][1])

    def _hit_mob(self, mob, p, pad=0.08):
        bb = mob.get_bounding_box()
        return (bb[0][0]-pad <= p[0] <= bb[2][0]+pad and
                bb[0][1]-pad <= p[1] <= bb[2][1]+pad)

    def hit_plus(self, p):  return self._hit_mob(self._btn_plus[0],  p)
    def hit_minus(self, p): return self._hit_mob(self._btn_minus[0], p)

    def font_up(self):
        self._scale  = min(0.38, self._scale + 0.020)
        self._line_h = self._scale * 1.42
        self._render(force=True)

    def font_down(self):
        self._scale  = max(0.13, self._scale - 0.020)
        self._line_h = self._scale * 1.42
        self._render(force=True)

    def _save_undo(self):
        s = self._scene_idx
        _PS.undo_stk[s].append((copy.deepcopy(self._raw), self._cur_l, self._cur_c))
        if len(_PS.undo_stk[s]) > 120: _PS.undo_stk[s].pop(0)
        _PS.redo_stk[s].clear()

    def _undo(self):
        s = self._scene_idx
        if _PS.undo_stk[s]:
            _PS.redo_stk[s].append((copy.deepcopy(self._raw), self._cur_l, self._cur_c))
            saved, cl, cc = _PS.undo_stk[s].pop()
            self._raw[:] = saved
            self._cur_l, self._cur_c = cl, cc
            self._sel_anch = None
            self._render_dirty = True
            self._render(force=True)

    def _redo(self):
        s = self._scene_idx
        if _PS.redo_stk[s]:
            _PS.undo_stk[s].append((copy.deepcopy(self._raw), self._cur_l, self._cur_c))
            saved, cl, cc = _PS.redo_stk[s].pop()
            self._raw[:] = saved
            self._cur_l, self._cur_c = cl, cc
            self._sel_anch = None
            self._render_dirty = True
            self._render(force=True)

    def _has_sel(self):
        if self._sel_anch is None: return False
        return self._sel_anch != (self._cur_l, self._cur_c)

    def _norm_sel(self):
        al, ac = self._sel_anch
        cl, cc = self._cur_l, self._cur_c
        if (al, ac) > (cl, cc): al, ac, cl, cc = cl, cc, al, ac
        return al, ac, cl, cc

    def _get_sel_text(self):
        if not self._has_sel(): return ""
        sl, sc, cl, cc = self._norm_sel()
        if sl == cl: return self._raw[sl][sc:cc]
        parts = [self._raw[sl][sc:]]
        for li in range(sl+1, cl): parts.append(self._raw[li])
        parts.append(self._raw[cl][:cc])
        return "".join(parts)

    def _delete_sel(self):
        if not self._has_sel(): return
        sl, sc, cl, cc = self._norm_sel()
        if sl == cl:
            l = self._raw[sl]
            self._raw[sl] = l[:sc] + l[cc:]
        else:
            self._raw[sl:cl+1] = [self._raw[sl][:sc] + self._raw[cl][cc:]]
        self._cur_l, self._cur_c = sl, sc
        self._sel_anch = None

    def insert_text(self, ch):
        if not self._active: return
        if not ch or not ch.isprintable(): return
        self._save_undo()
        if self._has_sel(): self._delete_sel()
        l = self._raw[self._cur_l]
        self._raw[self._cur_l] = l[:self._cur_c] + ch + l[self._cur_c:]
        self._cur_c += 1
        self._sel_anch = None
        self._render_dirty = True
        self._render(force=True)

    def paste_text(self, text):
        if not self._active: return
        self._save_undo()
        if self._has_sel(): self._delete_sel()
        ins = text.replace("", "").replace("", "")    
        parts = ins.split("")
        l = self._raw[self._cur_l]
        if len(parts) == 1:
            self._raw[self._cur_l] = l[:self._cur_c] + parts[0] + l[self._cur_c:]
            self._cur_c += len(parts[0])
        else:
            rest = l[self._cur_c:]
            self._raw[self._cur_l] = l[:self._cur_c] + parts[0]
            for pi, p in enumerate(parts[1:], 1):
                self._raw.insert(self._cur_l + pi,
                                 p if pi < len(parts)-1 else p + rest)
            self._cur_l += len(parts) - 1
            self._cur_c  = len(parts[-1])
        self._sel_anch = None
        self._render_dirty = True
        self._render(force=True)

    def key(self, sym, mods):
        if not self._active: return
        ctrl  = bool(mods & K.MOD_CTRL)
        shift = bool(mods & K.MOD_SHIFT)

        if ctrl:
            if sym == K.A:
                self._sel_anch = (0, 0)
                self._cur_l = len(self._raw) - 1
                self._cur_c = len(self._raw[-1])
                self._render_dirty = True; self._render(); return
            if sym == K.C:
                _PS.clip = self._get_sel_text() if self._has_sel() \
                           else self._raw[self._cur_l]
                try:
                    import pyglet
                    pyglet.app.clipboard.set_text(_PS.clip)
                except Exception:
                    pass
                return
            if sym == K.X:
                self._save_undo()
                if self._has_sel():
                    _PS.clip = self._get_sel_text(); self._delete_sel()
                else:
                    _PS.clip = self._raw[self._cur_l]
                    if len(self._raw) > 1:
                        self._raw.pop(self._cur_l)
                        self._cur_l = max(0, self._cur_l - 1)
                    else:
                        self._raw[0] = ""
                    self._cur_c = len(self._raw[self._cur_l])
                self._sel_anch = None
                self._render_dirty = True; self._render(force=True); return
            if sym == K.V:
                self.paste_text(_get_clipboard()); return
            if sym == K.Z: self._undo(); return
            if sym in (K.Y, K.R): self._redo(); return
            return

        def begin_sel():
            if shift and self._sel_anch is None:
                self._sel_anch = (self._cur_l, self._cur_c)
            elif not shift:
                self._sel_anch = None

        if sym == K.RETURN:
            self._save_undo()
            if self._has_sel(): self._delete_sel()
            l = self._raw[self._cur_l]
            self._raw[self._cur_l] = l[:self._cur_c]
            self._raw.insert(self._cur_l + 1, l[self._cur_c:])
            self._cur_l += 1; self._cur_c = 0
            self._sel_anch = None
            self._render_dirty = True; self._render(force=True)
        elif sym == K.BACKSPACE:
            self._save_undo()
            if self._has_sel(): self._delete_sel()
            elif self._cur_c > 0:
                l = self._raw[self._cur_l]
                self._raw[self._cur_l] = l[:self._cur_c-1] + l[self._cur_c:]
                self._cur_c -= 1
            elif self._cur_l > 0:
                prev = self._raw[self._cur_l-1]
                self._cur_c = len(prev)
                self._raw[self._cur_l-1] = prev + self._raw[self._cur_l]
                self._raw.pop(self._cur_l); self._cur_l -= 1
            self._sel_anch = None
            self._render_dirty = True; self._render(force=True)
        elif sym == K.DELETE:
            self._save_undo()
            if self._has_sel(): self._delete_sel()
            else:
                l = self._raw[self._cur_l]
                if self._cur_c < len(l):
                    self._raw[self._cur_l] = l[:self._cur_c] + l[self._cur_c+1:]
                elif self._cur_l < len(self._raw) - 1:
                    self._raw[self._cur_l] = l + self._raw[self._cur_l+1]
                    self._raw.pop(self._cur_l + 1)
            self._sel_anch = None
            self._render_dirty = True; self._render(force=True)
        elif sym == K.LEFT:
            begin_sel()
            if self._cur_c > 0: self._cur_c -= 1
            elif self._cur_l > 0:
                self._cur_l -= 1; self._cur_c = len(self._raw[self._cur_l])
            self._render_dirty = True; self._render()
        elif sym == K.RIGHT:
            begin_sel()
            if self._cur_c < len(self._raw[self._cur_l]): self._cur_c += 1
            elif self._cur_l < len(self._raw) - 1: self._cur_l += 1; self._cur_c = 0
            self._render_dirty = True; self._render()
        elif sym == K.UP:
            begin_sel()
            if self._cur_l > 0:
                self._cur_l -= 1
                self._cur_c = min(self._cur_c, len(self._raw[self._cur_l]))
            self._render_dirty = True; self._render()
        elif sym == K.DOWN:
            begin_sel()
            if self._cur_l < len(self._raw) - 1:
                self._cur_l += 1
                self._cur_c = min(self._cur_c, len(self._raw[self._cur_l]))
            self._render_dirty = True; self._render()
        elif sym == K.HOME:
            begin_sel(); self._cur_c = 0
            self._render_dirty = True; self._render()
        elif sym == K.END:
            begin_sel(); self._cur_c = len(self._raw[self._cur_l])
            self._render_dirty = True; self._render()

    def remove_all(self, scene):
        _PS.scene_lines[self._scene_idx] = self._raw
        _save_notes(_PS.scene_lines)
        for m in self._mobs:  scene.remove(m)
        for m in self._fmobs: scene.remove(m)
        self._mobs = []; self._fmobs = []


# ═════════════════════════════════════════════ DYNAMIC ARROW ═
class DynamicArrow:
    """
    سهم ديناميكي مرن يرتبط بنقطة بداية ونهاية ويتحدث تلقائياً
    عند تحريك أي من العقدتين. يستخدم manimlib updater للتحديث الفعلي.
    """
    def __init__(self, scene, get_start, get_end, color=ARROW_COL, 
                 stroke_width=6, buff=0.05, tip_ratio=0.35, curved=False):
        self._scene = scene
        self._get_start = get_start
        self._get_end = get_end
        self._color = color
        self._stroke_width = stroke_width
        self._buff = buff
        self._tip_ratio = tip_ratio
        self._curved = curved
        self._arrow = None
        self._tracked = []
        self._updater_added = False
        self._update()
        # Add updater to the arrow itself for true dynamic binding
        if self._arrow and not self._updater_added:
            self._arrow.add_updater(lambda mob: self._update_arrow_shape())
            self._updater_added = True

    def _update(self):
        start = self._get_start()
        end = self._get_end()
        if self._arrow:
            try:
                self._scene.remove(self._arrow)
            except:
                pass
        direction = end - start
        norm = np.linalg.norm(direction)
        if norm > 0.001:
            direction = direction / norm
            start_pt = start + direction * self._buff
            end_pt = end - direction * (self._buff + 0.15)
            if np.linalg.norm(end_pt - start_pt) > 0.1:
                if self._curved:
                    # Calculate curve angle based on relative positions
                    ddx = end[0] - start[0]
                    ddy = end[1] - start[1]
                    if abs(ddx) >= abs(ddy):
                        angle = TAU/12 if ddy > 0.3 else (-TAU/12 if ddy < -0.3 else 0.)
                    else:
                        angle = -TAU/10 if ddx > 0.3 else (TAU/10 if ddx < -0.3 else 0.)
                    self._arrow = CurvedArrow(
                        start_pt, end_pt,
                        color=self._color,
                        stroke_width=self._stroke_width,
                        angle=angle
                    )
                else:
                    self._arrow = Arrow(
                        start_pt, end_pt, buff=0,
                        stroke_width=self._stroke_width, 
                        color=self._color,
                        max_tip_length_to_length_ratio=self._tip_ratio
                    )
                self._scene.add(self._arrow)
                if self._arrow not in self._tracked:
                    self._tracked.append(self._arrow)
                # Re-add updater after recreation
                if not self._updater_added:
                    self._arrow.add_updater(lambda mob: self._update_arrow_shape())
                    self._updater_added = True

    def _update_arrow_shape(self):
        """Updater function that continuously updates arrow endpoints"""
        if self._arrow is None:
            return
        start = self._get_start()
        end = self._get_end()
        direction = end - start
        norm = np.linalg.norm(direction)
        if norm > 0.001:
            direction = direction / norm
            start_pt = start + direction * self._buff
            end_pt = end - direction * (self._buff + 0.15)
            if hasattr(self._arrow, 'put_start_and_end_on'):
                self._arrow.put_start_and_end_on(start_pt, end_pt)
            elif hasattr(self._arrow, 'set_points_by_ends'):
                self._arrow.set_points_by_ends(start_pt, end_pt)

    def refresh(self):
        self._update()

    def remove(self):
        if self._arrow:
            try:
                self._arrow.clear_updaters()
                self._scene.remove(self._arrow)
            except:
                pass
            self._arrow = None
        self._updater_added = False

    def get_mobs(self):
        return self._tracked


# ══════════════════════════════════════════════ HELP WINDOW ══
class HelpWindow:
    """
    نافذة مساعدة تظهر/تختفي عند الضغط على H
    تعرض جميع اختصارات لوحة المفاتيح
    """
    def __init__(self, scene):
        self._scene = scene
        self._visible = False
        self._mobs = []
        self._bg = None
        self._build()

    def _build(self):
        # Main background
        w, h = 5.20, 6.80
        self._bg = RoundedRectangle(corner_radius=0.12, width=w, height=h)
        self._bg.set_fill(HELP_BG, 0.96).set_stroke(HELP_STROKE, 2.0)
        self._bg.move_to(np.array([0, 0, 0]))

        # Title
        title = Text("Keyboard Shortcuts", color=HELP_TITLE, weight=BOLD).scale(0.32)
        title.move_to(np.array([0, h/2 - 0.38, 0]))

        # Separator line
        sep = Line(
            np.array([-w/2 + 0.20, h/2 - 0.62, 0]),
            np.array([w/2 - 0.20, h/2 - 0.62, 0])
        ).set_stroke(HELP_STROKE, 0.8)

        # Shortcut definitions
        shortcuts = [
            ("H", "Toggle this Help window"),
            ("N", "Show / Hide Notepad"),
            ("→", "Next scene"),
            ("←", "Previous scene"),
            ("Space", "Step through traversal"),
            ("", ""),
            ("Scene 3 - Operations:", ""),
            (" Ctrl+H", "Add Head"),
            ("  Ctrl+T", "Add Tail"),
            ("  M", "Add Middle (after selected)"),
            ("  D", "Delete selected node"),
            ("  Ctrl+S", "Search value"),
            ("  X", "Reset list"),
            ("", ""),
            ("Scene 4 - Traverse/Reverse:", ""),
            ("  T", "Traverse list"),
            ("  R", "Reverse list"),
            ("  X", "Reset list"),
            ("", ""),
            ("Scene 5 - Array vs LL:", ""),
            ("  I", "Access by index"),
            ("  Ctrl+H", "Insert at head"),
            ("  D", "Delete selected"),
            ("  Ctrl+S", "Search value"),
            ("  X", "Reset both"),
            ("", ""),
            ("Notepad (when active):", ""),
            ("  Ctrl+A", "Select all"),
            ("  Ctrl+C", "Copy"),
            ("  Ctrl+X", "Cut"),
            ("  Ctrl+V", "Paste"),
            ("  Ctrl+Z", "Undo"),
            ("  Ctrl+Y", "Redo"),
        ]

        y_start = h/2 - 0.88
        line_h = 0.26
        all_mobs = [self._bg, title, sep]

        for i, (key, desc) in enumerate(shortcuts):
            y = y_start - i * line_h
            if y < -h/2 + 0.20:
                break
            if not key and not desc:
                continue
            if desc == "" and key.endswith(":"):
                # Section header
                t = Text(key, color=HELP_TITLE, weight=BOLD).scale(0.20)
                t.move_to(np.array([0, y, 0]))
                all_mobs.append(t)
            else:
                key_t = Text(key, color=HELP_KEY, weight=BOLD).scale(0.19)
                key_t.move_to(np.array([-w/2 + 0.90, y, 0]), aligned_edge=LEFT)
                desc_t = Text(desc, color=HELP_TEXT).scale(0.19)
                desc_t.move_to(np.array([-w/2 + 1.70, y, 0]), aligned_edge=LEFT)
                all_mobs.append(key_t)
                all_mobs.append(desc_t)

        self._mobs = all_mobs
        # Don't add to scene yet - wait for toggle

    def toggle(self):
        if self._visible:
            self.hide()
        else:
            self.show()

    def show(self):
        if not self._visible:
            for m in self._mobs:
                self._scene.add(m)
            self._visible = True

    def hide(self):
        if self._visible:
            for m in self._mobs:
                try:
                    self._scene.remove(m)
                except:
                    pass
            self._visible = False

    def is_visible(self):
        return self._visible

    def hit(self, p):
        if not self._visible or self._bg is None:
            return False
        bb = self._bg.get_bounding_box()
        return (bb[0][0] <= p[0] <= bb[2][0] and bb[0][1] <= p[1] <= bb[2][1])

    def remove_all(self):
        self.hide()
        self._mobs = []


# ══════════════════════════════════════════════ SCENE ═══════
class LinkedList(Scene):

    def construct(self):
        self._scene_idx   = 0
        self._data        = DEFAULT_LIST.copy()
        self._ram_data    = S2_DEFAULT.copy()
        self._arr_data    = S5_ARR_DEF.copy()
        self._ll_data     = S5_LL_DEF.copy()

        self._nodes       = []
        self._tracked     = []
        self._node_ids    = set()
        self._ram_rows    = []
        self._ram_tmobs   = []
        self._arr_boxes   = []
        self._ll_s5       = []
        self._ram_drag    = False
        self._selected    = None
        self._box_bg      = None
        self._box_mode    = None
        self._box_idx     = None
        self._buf         = ""
        self._action      = None
        self._pending_val = None
        self._drag_idx    = None
        self._last_clicks = {}
        self._traversing  = False
        self._btns        = []
        self._notepad     = None
        self._tog_mob     = None
        self._help_window = None

        # Dynamic arrows storage
        self._dynamic_arrows = []
        self._dynamic_ptrs = {}

        self._bg = Rectangle(width=22, height=14)
        self._bg.set_fill(BG_COLOR, 1).set_stroke(width=0)
        self.add(self._bg)

        try:
            win = self.renderer.window
            self.update_frame(1/self.camera.fps)
            sc  = win.display.get_default_screen()
            win.set_location((sc.width - win.width)//2, (sc.height - win.height)//2)
        except Exception:
            pass

        self._load_scene(0)
        self._main_loop()

    def _t(self, *mobs):
        for m in mobs:
            self.add(m)
            self._tracked.append(m)

    def _clear_all(self):
        # Clean up dynamic arrows first
        for da in self._dynamic_arrows:
            da.remove()
        self._dynamic_arrows = []
        self._dynamic_ptrs = {}

        for m in self._tracked: 
            try:
                self.remove(m)
            except:
                pass
        self._tracked   = []
        self._nodes     = []
        self._btns      = []
        self._node_ids  = set()
        self._ram_rows  = []
        self._ram_tmobs = []
        self._arr_boxes = []
        self._ll_s5     = []
        self._ram_drag  = False

    def _main_loop(self):
        while not self.is_window_closing():
            self._action = None
            while self._action is None and not self.is_window_closing():
                self.update_frame(1/self.camera.fps)
                # Update dynamic arrows every frame
                for da in self._dynamic_arrows:
                    da.refresh()
            a = self._action
            if   a == "scene_next": self._switch_scene(1)
            elif a == "scene_prev": self._switch_scene(-1)
            elif a == "toggle_pad": self._do_toggle_pad()
            elif a == "toggle_help": 
                if self._help_window is None:
                    self._help_window = HelpWindow(self)
                self._help_window.toggle()
            elif a == "add_head":   self._op_add_head()
            elif a == "add_tail":   self._op_add_tail()
            elif a == "add_mid":    self._op_add_mid()
            elif a == "delete":     self._op_delete()
            elif a == "delete_key": self._op_delete_key()
            elif a == "search":     self._op_search()
            elif a == "traverse":   self._op_traverse()
            elif a == "reverse":    self._op_reverse()
            elif a == "reset":      self._op_reset()
            elif a == "s2_add":     self._s2_op_add()
            elif a == "s2_delete":  self._s2_op_delete()
            elif a == "s5_access":  self._s5_do_access()
            elif a == "s5_insert":  self._s5_do_insert()
            elif a == "s5_delete":  self._s5_do_delete()
            elif a == "s5_search":  self._s5_do_search()
            elif a == "s5_reset":
                self._arr_data = S5_ARR_DEF.copy()
                self._ll_data  = S5_LL_DEF.copy()
                self._load_scene(5)

    def _switch_scene(self, d):
        ni = self._scene_idx + d
        if 0 <= ni < N_SCENES: self._load_scene(ni)

    def _load_scene(self, idx):
        self._scene_idx = idx; _PS.cur_scene = idx
        if idx == 0: _PS.visible = False

        if self._notepad: self._notepad.remove_all(self); self._notepad = None
        if self._tog_mob: self.remove(self._tog_mob);     self._tog_mob = None
        if self._help_window: self._help_window.remove_all(); self._help_window = None
        if self._box_bg is not None: self._close_box()
        self._clear_all()
        self._selected    = None
        self._drag_idx    = None
        self._traversing  = False
        self._last_clicks = {}

        builders = [self._build_s0, self._build_s1, self._build_s2,
                    self._build_s3, self._build_s4, self._build_s5]
        builders[idx]()
        self._draw_dots()
        if idx != 0: self._draw_tog()

        # Show keyboard shortcuts hint
        if idx in [3, 4, 5]:
            self._draw_shortcuts_hint()

    def _draw_shortcuts_hint(self):
        """عرض اختصارات لوحة المفاتيح"""
        hints = [
            "[A] Add Head  [S] Add Tail  [D] Delete  [F] Search",
            "[T] Traverse  [R] Reverse  [N] Notepad  [->] Next  [<-] Prev"
        ]
        hint_text = " | ".join(hints)
        hint = Text(hint_text, color="#3a5577").scale(0.14)
        hint.move_to(np.array([_cx(), -3.40, 0]))
        self._t(hint)

    def _draw_dots(self):
        dots = []
        for i in range(N_SCENES):
            c = Circle(radius=0.07)
            c.set_fill(ARROW_COL if i == self._scene_idx else "#1e2d3a", 1)
            c.set_stroke(width=0)
            dots.append(c)
        bar = VGroup(*dots).arrange(RIGHT, buff=0.18)
        bar.move_to(np.array([_cx(), -3.80, 0]))
        self._t(bar)

    def _draw_tog(self):
        """زر التبديل أصبح غير ضروري لأن N يفتح/يغلق الـNotepad مباشرة"""
        # تم إزالة زر التبديل - الاختصار N كافٍ
        pass

    def _hit_tog(self, p):
        return False

    def _do_toggle_pad(self):
        if _PS.visible:
            mobs = self._notepad.all_mobs() if self._notepad else []
            dx   = (_PAD_CX_HID - _PAD_CX_VIS) / _SLIDE_FRAMES
            for _ in range(_SLIDE_FRAMES):
                for m in mobs: m.shift(np.array([dx, 0, 0]))
                self.update_frame(1/60)
            _PS.visible = False
        else:
            tmp  = Notepad(self, _PAD_CX_HID, _PAD_CY, self._scene_idx)
            mobs = tmp.all_mobs()
            dx   = (_PAD_CX_VIS - _PAD_CX_HID) / _SLIDE_FRAMES
            for _ in range(_SLIDE_FRAMES):
                for m in mobs: m.shift(np.array([dx, 0, 0]))
                self.update_frame(1/60)
            tmp.remove_all(self)
            _PS.visible = True
        self._load_scene(self._scene_idx)

    def _build_notepad(self):
        if _PS.visible:
            self._notepad = Notepad(self, _PAD_CX_VIS, _PAD_CY, self._scene_idx)

    def _hit(self, mob, p):
        bb = mob.get_bounding_box()
        return (bb[0][0] <= p[0] <= bb[2][0] and bb[0][1] <= p[1] <= bb[2][1])

    def _open_box(self, pos, prompt):
        self._buf = ""
        self._box_bg = Rectangle(width=1.70, height=0.52)
        self._box_bg.set_fill("#111133", 0.97).set_stroke(YELLOW, 2.0)
        self._box_bg.move_to(pos)
        self._box_prompt = Text(prompt, color=GRAY_COLOR).scale(0.20)
        self._box_prompt.next_to(self._box_bg, UP, buff=0.05)
        self._box_cursor = Text("_", color=YELLOW).scale(0.54)
        self._box_cursor.move_to(self._box_bg.get_center())
        self.add(self._box_bg, self._box_prompt, self._box_cursor)

    def _close_box(self):
        if self._box_bg is not None:
            self.remove(self._box_bg, self._box_prompt, self._box_cursor)
            self._box_bg = None

    def _refresh_box(self):
        self.remove(self._box_cursor)
        self._box_cursor = Text((self._buf or "") + "_", color=YELLOW).scale(0.54)
        self._box_cursor.move_to(self._box_bg.get_center())
        self.add(self._box_cursor)


    def _build_list(self, data, base_y=-0.5, row_gap=2.6, override_cx=None):
        if self._node_ids:
            survivors = []
            for m in self._tracked:
                if id(m) in self._node_ids: 
                    try:
                        self.remove(m)
                    except:
                        pass
                else: survivors.append(m)
            self._tracked = survivors
        self._node_ids = set()
        self._nodes    = []

        # Clear old dynamic arrows
        for da in self._dynamic_arrows:
            da.remove()
        self._dynamic_arrows = []

        cx      = override_cx if override_cx is not None else _cx()
        max_row = MAX_ROW_VIS if _PS.visible else MAX_ROW_FULL
        n       = len(data)
        rows    = [data[s:s+max_row] for s in range(0, n, max_row)]

        flat_idx = 0
        for ri, row in enumerate(rows):
            m_cnt  = len(row)
            sp     = min(3.00, _cw() / max(m_cnt, 1))
            dw     = min(1.20, sp * 0.46)
            nw     = min(0.55, sp * 0.20)
            h      = 1.10
            row_y  = base_y - ri * row_gap

            for ci, val in enumerate(row):
                node_mid_x = cx + ci*sp - sp*(m_cnt-1)/2.0
                dsq_cx = node_mid_x - nw / 2
                nsq_cx = node_mid_x + dw / 2

                i = flat_idx
                is_last_in_row   = (ci == m_cnt - 1)
                is_absolute_last = (flat_idx == n - 1)

                dsq = Rectangle(width=dw, height=h)
                dsq.set_fill(NODE_FILL, 1).set_stroke(WHITE, 2.2)
                dsq.move_to(np.array([dsq_cx, row_y, 0]))

                nsq = Rectangle(width=nw, height=h)
                nsq.set_fill(NEXT_FILL, 1).set_stroke(GRAY_COLOR, 1.2)
                nsq.move_to(np.array([nsq_cx, row_y, 0]))

                total_w = dw + nw
                frame = RoundedRectangle(corner_radius=0.08,
                                         width=total_w + 0.10, height=h + 0.10)
                frame.set_fill(opacity=0).set_stroke(ARROW_COL, 0.7, opacity=0.40)
                frame.move_to(np.array([node_mid_x, row_y, 0]))

                sep = Line(
                    np.array([dsq_cx - dw/2 + 0.06, row_y - 0.06, 0]),
                    np.array([dsq_cx + dw/2 - 0.06, row_y - 0.06, 0])
                ).set_stroke(GRAY_COLOR, 0.7, opacity=0.40)

                vt = Text(str(val), color=WHITE, weight=BOLD).scale(0.70)
                vt.move_to(np.array([dsq_cx, row_y + h*0.26, 0]))

                at = Text(FAKE_ADDRS[i], color=ADDR_COLOR).scale(0.20)
                at.move_to(np.array([dsq_cx, row_y - h*0.26, 0]))

                lbd = Text("data", color="#3a5577").scale(0.14)
                lbd.move_to(np.array([dsq_cx, row_y + h*0.48, 0]))
                lba = Text("addr", color="#3a5577").scale(0.14)
                lba.move_to(np.array([dsq_cx, row_y - h*0.08, 0]))

                il = Text(str(i), color="#3a4a5a").scale(0.22)
                il.move_to(np.array([dsq_cx, row_y - h/2 - 0.24, 0]))

                mobs = [frame, dsq, nsq, sep, vt, at, lbd, lba, il]

                if is_absolute_last:
                    null_t = Text("null", color="#3a5a6a").scale(0.18)
                    null_t.move_to(nsq.get_center())
                    mobs.append(null_t)
                elif is_last_in_row:
                    next_addr = FAKE_ADDRS[i + 1]
                    pt = Text(next_addr, color=ARROW_COL).scale(0.15)
                    pt.move_to(nsq.get_center())
                    mobs.append(pt)
                    cont_lbl = Text("↓", color=ARROW_COL).scale(0.24)
                    cont_lbl.next_to(nsq, DOWN, buff=0.06)
                    mobs.append(cont_lbl)
                else:
                    pt = Text(FAKE_ADDRS[i+1], color=ARROW_COL).scale(0.15)
                    pt.move_to(nsq.get_center())
                    mobs.append(pt)

                    # Dynamic arrow connecting to next node with LIVE tracking
                    # The arrow will read current positions from mobjects every frame
                    next_node_mid_x = cx + (ci+1)*sp - sp*(m_cnt-1)/2.0
                    next_dsq_cx = next_node_mid_x - nw / 2

                    # Create closures that capture mobject references for live tracking
                    def make_start(nsq_obj=nsq, nsq_cx=nsq_cx, row_y=row_y, nw=nw):
                        # Get live position from the next_sq mobject
                        try:
                            center = nsq_obj.get_center()
                            return np.array([center[0] + nw/2 + 0.05, center[1], 0])
                        except:
                            return np.array([nsq_cx + nw/2 + 0.05, row_y, 0])

                    def make_end(next_dsq_cx=next_dsq_cx, row_y=row_y, dw=dw):
                        # Will be updated after next node is created
                        return np.array([next_dsq_cx - dw/2, row_y, 0])

                    da = DynamicArrow(self, make_start, make_end, 
                                     color=ARROW_COL, stroke_width=6, 
                                     buff=0.02, tip_ratio=0.35, curved=True)
                    self._dynamic_arrows.append(da)
                    # Store for linking with next node's data square
                    if not hasattr(self, '_pending_arrows'):
                        self._pending_arrows = []
                    self._pending_arrows.append({
                        'arrow': da,
                        'from_idx': i,
                        'to_idx': i + 1,
                        'make_end_func': make_end
                    })

                for m in mobs:
                    self.add(m)
                    self._tracked.append(m)
                    self._node_ids.add(id(m))

                self._nodes.append({
                    "val": val, "data_sq": dsq, "next_sq": nsq, "frame": frame,
                    "val_txt": vt, "addr_txt": at, "idx_lbl": il, "mobs": mobs,
                    "row_y": row_y, "dsq_cx": dsq_cx, "nsq_cx": nsq_cx,
                    "dw": dw, "nw": nw, "h": h
                })
                flat_idx += 1

        # Link pending arrows to actual node objects for live tracking
        if hasattr(self, '_pending_arrows'):
            for pa in self._pending_arrows:
                to_idx = pa['to_idx']
                if to_idx < len(self._nodes):
                    target_dsq = self._nodes[to_idx]['data_sq']
                    target_dw = self._nodes[to_idx]['dw']
                    # Update the make_end function to use live object
                    def make_end_live(dsq_obj=target_dsq, dw=target_dw):
                        try:
                            center = dsq_obj.get_center()
                            return np.array([center[0] - dw/2, center[1], 0])
                        except:
                            return np.array([dsq_obj.get_center()[0] - dw/2, dsq_obj.get_center()[1], 0])
                    pa['arrow']._get_end = make_end_live
            self._pending_arrows = []

    def _ptr(self, ni, label, color):
        if ni >= len(self._nodes): return None
        nd  = self._nodes[ni]
        tip = nd["data_sq"].get_center() + UP*0.66
        lbl = Text(label, color=color).scale(0.26)
        lbl.move_to(tip + UP*0.20)
        arr = Arrow(lbl.get_bottom()+DOWN*0.04, tip, buff=0,
                    stroke_width=3.5, color=color,
                    max_tip_length_to_length_ratio=0.32)
        g = VGroup(lbl, arr); self.add(g); return g

    def _rptr(self, *ptrs):
        for p in ptrs:
            if p: self.remove(p)

    def _move_node(self, i, delta):
        for m in self._nodes[i]["mobs"]: m.shift(delta)
        # Dynamic arrows update automatically via updaters

    def _sel(self, i):
        self._desel(); self._selected = i
        self._nodes[i]["data_sq"].set_stroke(SEL_COLOR, 3.5)

    def _desel(self):
        if self._selected is not None and self._selected < len(self._nodes):
            self._nodes[self._selected]["data_sq"].set_stroke(WHITE, 2.2)
        self._selected = None

    def _edit_val(self, i, val):
        nd = self._nodes[i]
        nd["data_sq"].set_stroke(WHITE, 2.2)
        self.remove(nd["val_txt"])
        nt = Text(str(val), color=WHITE, weight=BOLD).scale(0.70)
        nt.move_to(nd["data_sq"].get_center()+UP*0.26)
        idx_m = nd["mobs"].index(nd["val_txt"])
        nd["mobs"][idx_m] = nt
        nd["val_txt"] = nt; nd["val"] = val
        self._data[i] = val
        self.add(nt); self._tracked.append(nt); self._node_ids.add(id(nt))


    # ═══════════════════════════════════════════════ SCENES ══

    def _build_s0(self):
        title = Text("Linked List", weight=BOLD, color=ARROW_COL).scale(1.40)
        title.move_to(np.array([0.00, 0.40, 0]))
        self._t(title)

    def _build_s1(self):
        self._build_notepad()
        cx = _cx()
        title = Text("Node Anatomy", weight=BOLD, color=ARROW_COL).scale(0.68)
        title.move_to(np.array([cx, 3.50, 0])); self._t(title)

        DW = 2.60; NW = 1.60; H = 2.20
        N1_MID_X = cx - 2.40
        N1Y      = 0.30
        self._s1_NY = N1Y

        n1_dsq_cx = N1_MID_X - NW/2
        n1_nsq_cx = N1_MID_X + DW/2
        self._s1_N1_DSQCX = n1_dsq_cx

        outer1 = RoundedRectangle(corner_radius=0.16, width=DW+NW+0.20, height=H+0.10)
        outer1.set_fill("#07071c", 0.95).set_stroke(ARROW_COL, 1.8)
        outer1.move_to(np.array([N1_MID_X, N1Y, 0]))

        db1 = Rectangle(width=DW, height=H)
        db1.set_fill("#14142e", 1).set_stroke(WHITE, 1.8)
        db1.move_to(np.array([n1_dsq_cx, N1Y, 0]))

        nb1 = Rectangle(width=NW, height=H)
        nb1.set_fill("#0a0a1e", 1).set_stroke(GRAY_COLOR, 1.1)
        nb1.move_to(np.array([n1_nsq_cx, N1Y, 0]))

        sep1 = Line(
            np.array([n1_dsq_cx - DW/2 + 0.05, N1Y + 0.20, 0]),
            np.array([n1_dsq_cx + DW/2 - 0.05, N1Y + 0.20, 0])
        ).set_stroke(GRAY_COLOR, 0.6, opacity=0.32)

        self._s1_v1 = Text("42", color=WHITE, weight=BOLD).scale(1.04)
        self._s1_v1.move_to(np.array([n1_dsq_cx, N1Y + 0.72, 0]))

        self._s1_a1 = Text(FAKE_ADDRS[0], color=ADDR_COLOR).scale(0.50)
        self._s1_a1.move_to(np.array([n1_dsq_cx, N1Y - 0.32, 0]))

        lbd1 = Text("data",    color="#3a5577").scale(0.24).move_to(np.array([n1_dsq_cx, N1Y + 1.00, 0]))
        lba1 = Text("address", color="#3a5577").scale(0.24).move_to(np.array([n1_dsq_cx, N1Y + 0.20, 0]))
        lbn1 = Text("next",    color="#3a5577").scale(0.24).move_to(np.array([n1_nsq_cx, N1Y + 0.84, 0]))
        lbp1 = Text("(ptr)",   color=GRAY_COLOR).scale(0.20).move_to(np.array([n1_nsq_cx, N1Y - 0.48, 0]))

        self._s1_nv1 = Text(FAKE_ADDRS[1], color=ARROW_COL).scale(0.40)
        self._s1_nv1.move_to(np.array([n1_nsq_cx, N1Y + 0.10, 0]))

        self._s1_db1 = db1; self._s1_nb1 = nb1
        self._s1_n1_nsq_cx = n1_nsq_cx

        self._t(outer1, db1, sep1, self._s1_v1, self._s1_a1,
                lbd1, lba1, nb1, lbn1, lbp1, self._s1_nv1)

        N2_MID_X = cx + 2.60
        N2Y      = N1Y
        DW2 = 2.00; NW2 = 1.10
        n2_dsq_cx = N2_MID_X - NW2/2
        n2_nsq_cx = N2_MID_X + DW2/2

        n1_frame_right = N1_MID_X + (DW + NW) / 2 + 0.14
        n2_frame_left  = N2_MID_X - (DW2 + NW2) / 2 - 0.14

        link_start = np.array([n1_frame_right + 0.08, N1Y, 0])
        link_end   = np.array([n2_frame_left  - 0.08, N2Y, 0])
        link = Arrow(link_start, link_end, buff=0, stroke_width=6.0,
                     color=ARROW_COL, max_tip_length_to_length_ratio=0.30)
        self._t(link)

        outer2 = RoundedRectangle(corner_radius=0.16, width=DW2+NW2+0.20, height=H+0.10)
        outer2.set_fill("#07071c", 0.95).set_stroke(FOUND_COL, 1.6)
        outer2.move_to(np.array([N2_MID_X, N2Y, 0]))

        db2 = Rectangle(width=DW2, height=H)
        db2.set_fill("#14142e", 1).set_stroke(WHITE, 1.8)
        db2.move_to(np.array([n2_dsq_cx, N2Y, 0]))

        nb2 = Rectangle(width=NW2, height=H)
        nb2.set_fill("#0a0a1e", 1).set_stroke(GRAY_COLOR, 1.1)
        nb2.move_to(np.array([n2_nsq_cx, N2Y, 0]))

        sep2 = Line(
            np.array([n2_dsq_cx - DW2/2 + 0.05, N2Y + 0.20, 0]),
            np.array([n2_dsq_cx + DW2/2 - 0.05, N2Y + 0.20, 0])
        ).set_stroke(GRAY_COLOR, 0.6, opacity=0.32)

        self._s1_v2 = Text("17", color=WHITE, weight=BOLD).scale(1.04)
        self._s1_v2.move_to(np.array([n2_dsq_cx, N2Y + 0.72, 0]))

        self._s1_a2 = Text(FAKE_ADDRS[1], color=ADDR_COLOR).scale(0.50)
        self._s1_a2.move_to(np.array([n2_dsq_cx, N2Y - 0.32, 0]))

        lbd2 = Text("data",    color="#3a5577").scale(0.24).move_to(np.array([n2_dsq_cx, N2Y + 1.00, 0]))
        lba2 = Text("address", color="#3a5577").scale(0.24).move_to(np.array([n2_dsq_cx, N2Y + 0.20, 0]))
        lbn2 = Text("next",    color="#3a5577").scale(0.24).move_to(np.array([n2_nsq_cx, N2Y + 0.60, 0]))
        nl2  = Text("null",    color="#3a5a6a").scale(0.24).move_to(np.array([n2_nsq_cx, N2Y, 0]))

        self._s1_db2 = db2; self._s1_nb2 = nb2
        self._s1_N2_DSQCX = n2_dsq_cx
        self._s1_DW2 = DW2; self._s1_NW2 = NW2

        self._t(outer2, db2, sep2, self._s1_v2, self._s1_a2,
                lbd2, lba2, nb2, lbn2, nl2)

        mb = SurroundingRectangle(VGroup(self._s1_nv1, self._s1_a2), buff=0.10)
        mb.set_stroke(YELLOW, 1.6)
        ml = Text("Same address — that's the link!", color=YELLOW).scale(0.24)
        ml.next_to(mb, DOWN, buff=0.08)
        self._t(mb, ml)
        self._s1_last_t = 0.0

    def _s1_update_link_addr(self, new_addr):
        self.remove(self._s1_nv1)
        self._s1_nv1 = Text(new_addr, color=ARROW_COL).scale(0.40)
        self._s1_nv1.move_to(np.array([self._s1_n1_nsq_cx, self._s1_NY + 0.10, 0]))
        self.add(self._s1_nv1); self._tracked.append(self._s1_nv1)

    def _ms1(self, pt):
        now  = time.time()
        db1, nb1 = self._s1_db1, self._s1_nb1
        db2, nb2 = self._s1_db2, self._s1_nb2
        NY = self._s1_NY
        n1_dsq_cx = self._s1_N1_DSQCX
        n2_dsq_cx = self._s1_N2_DSQCX

        def rst():
            db1.set_stroke(WHITE, 1.8); nb1.set_stroke(GRAY_COLOR, 1.1)
            db2.set_stroke(WHITE, 1.8); nb2.set_stroke(GRAY_COLOR, 1.1)

        if self._hit(db1, pt):
            if pt[1] > NY + 0.20:
                if now - self._s1_last_t < 0.45:
                    self._open_box(np.array([n1_dsq_cx, NY + 0.72, 0]), "Edit value")
                    self._box_mode = "s1_v1"
                else: rst(); db1.set_stroke(YELLOW, 3.0)
                self._s1_last_t = now
            else: rst(); db1.set_stroke(ADDR_COLOR, 3.0)
            return
        if self._hit(nb1, pt): rst(); nb1.set_stroke(ARROW_COL, 3.0); return
        if self._hit(db2, pt):
            if pt[1] > NY + 0.20:
                if now - self._s1_last_t < 0.45:
                    self._open_box(np.array([n2_dsq_cx, NY + 0.72, 0]), "Edit value")
                    self._box_mode = "s1_v2"
                else: rst(); db2.set_stroke(YELLOW, 3.0)
                self._s1_last_t = now
            else:
                if now - self._s1_last_t < 0.45:
                    self._open_box(np.array([n2_dsq_cx, NY - 0.32, 0]), "New address")
                    self._box_mode = "s1_a2"
                else: rst(); db2.set_stroke(ADDR_COLOR, 3.0)
                self._s1_last_t = now
            return
        if self._hit(nb2, pt): rst(); nb2.set_stroke(GRAY_COLOR, 2.2); return
        rst()

    def _build_s2(self):
        self._build_notepad()
        cx = _cx(); cl = _cl(); cw = _cw()

        title = Text("Memory Model", weight=BOLD, color=ARROW_COL).scale(0.68)
        title.move_to(np.array([cx, 3.50, 0])); self._t(title)

        ll_lbl = Text("Linked List", color=FOUND_COL, weight=BOLD).scale(0.34)
        ll_lbl.move_to(np.array([cx, 2.62, 0])); self._t(ll_lbl)

        self._build_list(self._ram_data, base_y=1.80, override_cx=cx)

        SEP_Y = 0.72
        self._s2_SEP_Y = SEP_Y
        div = Line(np.array([cl + 0.10, SEP_Y, 0]), np.array([cl + cw - 0.10, SEP_Y, 0]))
        div.set_stroke(ARROW_COL, 1.2, opacity=0.55); self._t(div)

        HDR_Y = -0.65
        RH    = 0.46
        TW    = min(5.40, cw * 0.60)

        n           = len(self._ram_data)
        outer_top   = HDR_Y + RH / 2 + 0.26
        outer_bot   = HDR_Y - RH / 2 - n * RH - 0.10
        outer_cy    = (outer_top + outer_bot) / 2
        outer_h     = outer_top - outer_bot

        self._ram_outer = Rectangle(width=TW + 0.30, height=outer_h)
        self._ram_outer.set_fill("#07071a", 0.90).set_stroke(PAD_STROKE, 1.4)
        self._ram_outer.move_to(np.array([cx, outer_cy, 0]))

        ram_tag = Text(" (RAM)", color=ADDR_COLOR, weight=BOLD).scale(0.22)
        ram_tag.move_to(np.array([cx, outer_top + 0.14, 0]))

        hbg = Rectangle(width=TW, height=RH - 0.04)
        hbg.set_fill("#0d1030", 1).set_stroke(GRAY_COLOR, 0.7)
        hbg.move_to(np.array([cx, HDR_Y, 0]))

        col_x = [cx - TW*0.32, cx - TW*0.06, cx + TW*0.22]
        h1 = Text("Address", color=GRAY_COLOR).scale(0.19).move_to(np.array([col_x[0], HDR_Y, 0]))
        h2 = Text("Data",    color=GRAY_COLOR).scale(0.19).move_to(np.array([col_x[1], HDR_Y, 0]))
        h3 = Text("Next ->",  color=GRAY_COLOR).scale(0.19).move_to(np.array([col_x[2], HDR_Y, 0]))

        self._ram_tmobs = [self._ram_outer, ram_tag, hbg, h1, h2, h3]
        for m in self._ram_tmobs: self._t(m)

        self._ram_col_x = col_x
        self._ram_HDR_Y = HDR_Y
        self._ram_RH    = RH
        self._ram_TW    = TW
        self._ram_cx    = cx
        self._ram_rows  = []
        self._s2_lc     = {}
        self._ram_drag  = False

        self._s2_rebuild_rows()

        BY2 = -2.80
        self._bg_s2_add = self._btn("+ Node", BTN_ADD_H, np.array([cx - 0.85, BY2, 0]), w=1.40)
        self._bg_s2_del = self._btn("- Node", BTN_DEL,   np.array([cx + 0.85, BY2, 0]), w=1.40)

    def _btn(self, label, color, centre, w=1.46):
        bg = RoundedRectangle(corner_radius=0.10, width=w, height=0.44)
        bg.set_fill(color, 0.92).set_stroke(WHITE, 0.7)
        bg.move_to(centre)
        tx = Text(label, color=WHITE).scale(0.30).move_to(centre)
        self._t(bg, tx)
        self._btns += [bg, tx]
        return bg

    def _s2_rebuild_rows(self):
        for row in self._ram_rows:
            for m in row.values():
                try: self.remove(m); self._tracked.remove(m)
                except Exception: pass
        self._ram_rows = []

        n     = len(self._ram_data)
        col_x = self._ram_col_x
        HDR_Y = self._ram_HDR_Y
        RH    = self._ram_RH
        TW    = self._ram_TW
        cx    = self._ram_cx

        outer_top = HDR_Y + RH / 2 + 0.26
        outer_bot = HDR_Y - RH / 2 - n * RH - 0.10
        outer_cy  = (outer_top + outer_bot) / 2
        outer_h   = outer_top - outer_bot
        self._ram_outer.set_height(outer_h)
        self._ram_outer.move_to(np.array([cx, outer_cy, 0]))

        for ri in range(n):
            ry  = HDR_Y - (ri + 1) * RH
            rbg = Rectangle(width=TW, height=RH - 0.05)
            rbg.set_fill("#090918", 1).set_stroke(GRAY_COLOR, 0.38)
            rbg.move_to(np.array([cx, ry, 0]))

            ta = Text(FAKE_ADDRS[ri], color=ADDR_COLOR).scale(0.19)
            ta.move_to(np.array([col_x[0], ry, 0]))

            td = Text(str(self._ram_data[ri]), color=WHITE).scale(0.19)
            td.move_to(np.array([col_x[1], ry, 0]))

            nxt = FAKE_ADDRS[ri + 1] if ri + 1 < n else "null"
            nc  = ARROW_COL if nxt != "null" else "#3a7a6a"
            tn  = Text(nxt, color=nc).scale(0.19)
            tn.move_to(np.array([col_x[2], ry, 0]))

            for m in [rbg, ta, td, tn]:
                self._t(m)
                self._ram_tmobs.append(m)
            self._ram_rows.append({"bg": rbg, "ta": ta, "td": td, "tn": tn})

    def _s2_op_add(self):
        box_y = getattr(self, "_s2_SEP_Y", 0.72) - 0.42
        self._open_box(np.array([_cx(), box_y, 0]), "New value")
        self._box_mode = "s2_add"

    def _s2_op_delete(self):
        if self._selected is None: return
        idx = self._selected; self._desel()
        self.play(self._nodes[idx]["data_sq"].animate.set_fill("#9e1e18", 0.90), run_time=0.18)
        self.play(FadeOut(VGroup(*self._nodes[idx]["mobs"])), run_time=0.24)
        self._ram_data.pop(idx)
        self._build_list(self._ram_data, base_y=1.80, override_cx=_cx())
        self._s2_rebuild_rows()

    def _s2_hl(self, idx):
        if self._scene_idx != 2: return
        for row in self._ram_rows:
            row["bg"].set_fill("#090918", 1)
            row["ta"].set_color(ADDR_COLOR)
            row["td"].set_color(WHITE)
        for nd in self._nodes:
            nd["data_sq"].set_stroke(WHITE, 2.2)
        if idx is None: return
        if idx < len(self._ram_rows):
            self._ram_rows[idx]["bg"].set_fill("#0e2040", 1)
            self._ram_rows[idx]["ta"].set_color(YELLOW)
            self._ram_rows[idx]["td"].set_color(YELLOW)
        if idx < len(self._nodes):
            self._nodes[idx]["data_sq"].set_stroke(YELLOW, 3.0)

    def _s2_update_ram(self):
        if self._scene_idx != 2: return
        for ri, row in enumerate(self._ram_rows):
            if ri < len(self._nodes):
                self.remove(row["td"])
                nt = Text(str(self._nodes[ri]["val"]), color=WHITE).scale(0.19)
                nt.move_to(row["td"].get_center())
                row["td"] = nt
                self.add(nt); self._tracked.append(nt)
                self._ram_tmobs.append(nt)

    def _ms2(self, pt):
        if self._scene_idx != 2: return
        if self._hit(self._bg_s2_add, pt): self._action = "s2_add"; return
        if self._hit(self._bg_s2_del, pt): self._action = "s2_delete"; return
        if self._hit(self._ram_outer, pt):
            self._ram_drag = True
            for ri, row in enumerate(self._ram_rows):
                if self._hit(row["bg"], pt):
                    self._s2_hl(ri); return
            return
        for i, nd in enumerate(self._nodes):
            if self._hit(nd["data_sq"], pt):
                now  = time.time()
                last = self._s2_lc.get(i, 0)
                if now - last < 0.46:
                    self._open_box(nd["data_sq"].get_center() + UP*0.26, "Value")
                    self._box_mode = "cell"; self._box_idx = i
                else:
                    self._drag_idx = i
                    nd["data_sq"].set_stroke(DRAG_COL, 3.0)
                    self._s2_hl(i)
                    if self._selected == i: self._desel()
                    else: self._sel(i)
                self._s2_lc[i] = now; return
        self._s2_hl(None); self._desel()


    def _build_s3(self):
        self._build_notepad()
        cx = _cx()
        title = Text("Operations", weight=BOLD, color=ARROW_COL).scale(0.68)
        title.move_to(np.array([cx, 3.50, 0])); self._t(title)

        # Build list without buttons - use keyboard shortcuts instead
        self._build_list(self._data, base_y=1.00)

        # Show operation hints
        # hint = Text("[A] Add Head  [S] Add Tail  [M] Add Mid  [D] Delete  [F] Search  [X] Reset", 
        #            color="#3a5577").scale(0.18)
        # hint.move_to(np.array([cx, 2.72, 0]))
        # self._t(hint)

    def _ms3(self, pt):
        # Mouse selection only - no buttons
        for i, nd in enumerate(self._nodes):
            if self._hit(nd["data_sq"], pt):
                now  = time.time(); last = self._last_clicks.get(i, 0)
                if now - last < 0.46:
                    self._desel(); nd["data_sq"].set_stroke(YELLOW, 3.5)
                    self._open_box(nd["data_sq"].get_center(), f"Edit [{i}]")
                    self._box_mode = "cell"; self._box_idx = i
                else:
                    if self._selected == i: self._desel()
                    else: self._sel(i)
                    self._drag_idx = i; nd["data_sq"].set_stroke(DRAG_COL, 3.0)
                self._last_clicks[i] = now; return
        self._desel()

    def _build_s4(self):
        self._build_notepad()
        cx = _cx()
        title = Text("Traverse / Reverse", weight=BOLD, color=ARROW_COL).scale(0.68)
        title.move_to(np.array([cx, 3.50, 0])); self._t(title)

        self._build_list(self._data, base_y=1.00)

        # Show operation hints
        # hint = Text("[T] Traverse  [R] Reverse  [X] Reset  [Click] Edit Node", 
        #            color="#3a5577").scale(0.18)
        # hint.move_to(np.array([cx, 2.72, 0]))
        # self._t(hint)

    def _ms4(self, pt):
        for i, nd in enumerate(self._nodes):
            if self._hit(nd["data_sq"], pt):
                now = time.time(); last = self._last_clicks.get(i, 0)
                if now - last < 0.46:
                    self._desel(); nd["data_sq"].set_stroke(YELLOW, 3.5)
                    self._open_box(nd["data_sq"].get_center(), f"Edit [{i}]")
                    self._box_mode = "cell"; self._box_idx = i
                else:
                    self._drag_idx = i; nd["data_sq"].set_stroke(DRAG_COL, 3.0)
                self._last_clicks[i] = now; return

    def _build_s5(self):
        self._build_notepad()
        cx = _cx(); cl = _cl(); cw = _cw()
        TITLE_Y = 3.60
        title = Text("Array  vs  Linked List", weight=BOLD, color=ARROW_COL).scale(0.68)
        title.move_to(np.array([cx, TITLE_Y, 0])); self._t(title)

        arr_vals = self._arr_data
        ll_vals  = self._ll_data
        N  = len(arr_vals)

        avail = cw * 0.86
        SP = avail / max(N, 1)
        BW = min(SP * 0.56, 1.10)
        NW = min(BW * 0.36, 0.40)

        AY    = 1.30
        DIV_Y = 0.10
        LY    = -1.10
        LABEL_OFFSET = 0.84

        al = Text("Array", color=ARR_COL, weight=BOLD).scale(0.44)
        al.move_to(np.array([cl + 1.00, AY + LABEL_OFFSET, 0])); self._t(al)

        self._arr_boxes = []
        for i, v in enumerate(arr_vals):
            bx_cx = cx + i*SP - SP*(N-1)/2.0

            # CONTIGUOUS array - boxes touching each other with no gaps
            # Use exact width to eliminate spacing
            bx = Rectangle(width=BW, height=BW * 0.80)
            bx.set_fill("#1a1a2e", 1).set_stroke(WHITE, 1.8)
            bx.move_to(np.array([bx_cx, AY, 0]))

            val_scale = min(0.50, BW * 0.38)
            tv = Text(str(v), color=WHITE, weight=BOLD).scale(val_scale)
            tv.move_to(np.array([bx_cx, AY, 0]))

            ta = Text(f"[{i}]", color=ADDR_COLOR).scale(0.24)
            ta.move_to(np.array([bx_cx, AY - BW*0.80/2 - 0.26, 0]))

            addr_t = Text(FAKE_ADDRS[i], color="#888").scale(0.18)
            addr_t.move_to(np.array([bx_cx, AY + BW*0.80/2 + 0.20, 0]))

            self._t(bx, tv, ta, addr_t)
            self._arr_boxes.append({
                "bx": bx, "tv": tv, "ta": ta, "addr": addr_t,
                "val": v, "cx": bx_cx, "cy": AY,
                "bw": BW, "bh": BW * 0.80,
            })

        div = Line(np.array([cl+0.10, DIV_Y, 0]), np.array([cl+cw-0.10, DIV_Y, 0]))
        div.set_stroke(GRAY_COLOR, 0.6, opacity=0.20); self._t(div)

        ll_lbl = Text("Linked List", color=LL_COL, weight=BOLD).scale(0.44)
        ll_lbl.move_to(np.array([cl + 1.10, LY + LABEL_OFFSET, 0])); self._t(ll_lbl)

        self._ll_s5 = []
        for i, v in enumerate(ll_vals):
            nx_cx = cx + i*SP - SP*(N-1)/2.0

            dbx = Rectangle(width=BW, height=BW * 0.80)
            dbx.set_fill(NODE_FILL, 1).set_stroke(WHITE, 1.8)
            dbx.move_to(np.array([nx_cx, LY, 0]))

            nbx = Rectangle(width=NW, height=BW * 0.80)
            nbx.set_fill(NEXT_FILL, 1).set_stroke(GRAY_COLOR, 0.9)
            nbx.move_to(np.array([nx_cx + BW/2 + NW/2, LY, 0]))

            frame_cx = nx_cx + NW / 2
            frame = RoundedRectangle(corner_radius=0.06, width=BW+NW+0.06, height=BW*0.80+0.06)
            frame.set_fill(opacity=0).set_stroke(ARROW_COL, 0.5, opacity=0.30)
            frame.move_to(np.array([frame_cx, LY, 0]))

            val_scale = min(0.46, BW * 0.36)
            tv = Text(str(v), color=WHITE, weight=BOLD).scale(val_scale)
            tv.move_to(np.array([nx_cx, LY, 0]))

            sc_addr = SCATTERED[i % len(SCATTERED)] if i < len(ll_vals) else FAKE_ADDRS[i + 10]
            ta = Text(f"@{sc_addr}", color=FOUND_COL).scale(0.18)
            ta.move_to(np.array([nx_cx, LY + BW*0.80/2 + 0.20, 0]))

            self._t(frame, dbx, tv, ta, nbx)

            if i < len(ll_vals) - 1:
                next_cx = cx + (i+1)*SP - SP*(N-1)/2.0
                ar = Arrow(
                    np.array([nx_cx + BW/2 + NW + 0.08, LY, 0]),
                    np.array([next_cx - BW/2 - 0.06, LY, 0]),
                    buff=0, stroke_width=5.0, color=ARROW_COL,
                    max_tip_length_to_length_ratio=0.36)
                self._t(ar)
            else:
                nl = Text("null", color="#3a5a6a").scale(0.20)
                nl.move_to(nbx.get_center()); self._t(nl)

            self._ll_s5.append({
                "dbx": dbx, "tv": tv, "ta": ta,
                "val": v, "cx": nx_cx, "cy": LY,
                "nbx": nbx, "frame": frame,
                "bw": BW, "bh": BW * 0.80,
            })

        # Keyboard shortcuts hint
        # hint = Text("[I] Access  [H] Insert Head  [D] Delete  [F] Search  [X] Reset  [Click] Edit", 
        #            color="#3a5577").scale(0.16)
        # hint.move_to(np.array([cx, 2.70, 0]))
        # self._t(hint)

        self._s5_AY = AY; self._s5_LY = LY
        self._s5_BW = BW; self._s5_NW = NW; self._s5_SP = SP
        self._arr_cx = cx; self._ll_cx = cx
        self._s5_lc_arr = {}; self._s5_lc_ll = {}
        self._s5_sel_idx = None

    def _ms5(self, pt):
        for i, ab in enumerate(self._arr_boxes):
            if self._hit(ab["bx"], pt):
                for a in self._arr_boxes:
                    a["bx"].set_stroke(WHITE, 1.8)
                ab["bx"].set_stroke(YELLOW, 3.0)
                self._s5_sel_idx = i
                now = time.time()
                if now - self._s5_lc_arr.get(i, 0) < 0.46:
                    self._open_box(np.array([ab["cx"], ab["cy"], 0]), "Value")
                    self._box_mode = "s5_arr"; self._box_idx = i
                self._s5_lc_arr[i] = now; return

        for i, ln in enumerate(self._ll_s5):
            if self._hit(ln["dbx"], pt):
                for l2 in self._ll_s5:
                    l2["dbx"].set_stroke(WHITE, 1.8)
                ln["dbx"].set_stroke(YELLOW, 3.0)
                now = time.time()
                if now - self._s5_lc_ll.get(i, 0) < 0.46:
                    self._open_box(np.array([ln["cx"], ln["cy"], 0]), "Value")
                    self._box_mode = "s5_ll"; self._box_idx = i
                self._s5_lc_ll[i] = now; return


    # ═══════════════════════════════════════════ OPERATIONS ══
    def _op_add_head(self):
        self.wait(0.20)
        self._build_list(self._data, base_y=1.00)
        self.play(self._nodes[0]["data_sq"].animate.set_fill(FOUND_COL, 0.70), run_time=0.22)
        self.play(self._nodes[0]["data_sq"].animate.set_fill(NODE_FILL, 1),    run_time=0.18)

    def _op_add_tail(self):
        n_old = len(self._data) - 1; self.wait(0.22); cp = None
        for i in range(n_old):
            self._rptr(cp); cp = self._ptr(i, "curr", ARROW_COL)
            self.play(self._nodes[i]["data_sq"].animate.set_fill(VISIT_COL, 0.40), run_time=0.16)
            self.wait(0.16)
        self._rptr(cp)
        for i in range(n_old): self._nodes[i]["data_sq"].set_fill(NODE_FILL, opacity=1)
        self._build_list(self._data, base_y=1.00)
        self.play(self._nodes[-1]["data_sq"].animate.set_fill(FOUND_COL, 0.72), run_time=0.22)
        self.play(self._nodes[-1]["data_sq"].animate.set_fill(NODE_FILL, 1),    run_time=0.18)

    def _op_add_mid(self):
        """إضافة عنصر في منتصف القائمة مع رسوم متحركة تفاعلية خطوة بخطوة"""
        if self._selected is None:
            self._op_add_tail()
            return

        idx = self._selected
        val = self._pending_val
        if val is None: return

        # Step 1: Animate traversal to the insertion position
        cp = None
        for i in range(idx + 1):
            self._rptr(cp)
            cp = self._ptr(i, "curr", ARROW_COL)
            self.play(self._nodes[i]["data_sq"].animate.set_fill(VISIT_COL, 0.50), run_time=0.18)
            self.wait(0.15)

        # Step 2: Highlight insertion point
        self.play(self._nodes[idx]["data_sq"].animate.set_fill(FOUND_COL, 0.80), run_time=0.20)
        self.wait(0.20)

        # Step 3: Show "creating new node" animation
        self._rptr(cp)

        # Create a temporary visual indicator for the new node being created
        new_node_visual = Text(f"NEW NODE: {val}", color=LL_NEW).scale(0.30)
        new_node_visual.move_to(np.array([_cx(), 2.50, 0]))
        self._t(new_node_visual)
        self.play(new_node_visual.animate.set_color(FOUND_COL), run_time=0.30)
        self.wait(0.20)
        self.remove(new_node_visual)
        self._tracked.remove(new_node_visual)

        # Step 4: Rebuild list with new node
        self._build_list(self._data, base_y=1.00)

        # Step 5: Highlight the newly inserted node and show pointer reconnection
        new_idx = idx + 1
        if new_idx < len(self._nodes):
            # Flash the new node
            self.play(self._nodes[new_idx]["data_sq"].animate.set_fill(LL_NEW, 0.85), run_time=0.25)
            self.wait(0.15)

            # Show pointer reconnection visualization
            if new_idx > 0 and new_idx < len(self._nodes) - 1:
                # Show arrows being "relinked"
                reconnect_text = Text("Pointers relinked!", color=ARROW_COL).scale(0.24)
                reconnect_text.move_to(np.array([_cx(), -2.20, 0]))
                self._t(reconnect_text)
                self.wait(0.30)
                self.remove(reconnect_text)
                self._tracked.remove(reconnect_text)

            self.play(self._nodes[new_idx]["data_sq"].animate.set_fill(NODE_FILL, 1), run_time=0.18)

        self._desel()

    def _op_delete(self):
        """حذف العقدة المحددة مع رسوم متحركة توضيحية"""
        if self._selected is None: return
        idx = self._selected
        self._desel()

        # Show deletion animation
        self.play(self._nodes[idx]["data_sq"].animate.set_fill("#9e1e18", 0.90), run_time=0.18)

        # If middle node, show "skipping" visualization
        if 0 < idx < len(self._nodes) - 1:
            skip_text = Text("Pointer skip: prev -> next", color=ARROW_COL).scale(0.24)
            skip_text.move_to(np.array([_cx(), -2.20, 0]))
            self._t(skip_text)
            self.wait(0.30)
            self.remove(skip_text)
            self._tracked.remove(skip_text)

        self.play(FadeOut(VGroup(*self._nodes[idx]["mobs"])), run_time=0.24)
        self._data.pop(idx)
        self._build_list(self._data, base_y=1.00)

    def _op_delete_key(self):
        """حذف العقدة المحددة باستخدام مفتاح Delete من لوحة المفاتيح"""
        if self._selected is not None:
            self._op_delete()

    def _op_search(self):
        """بحث تفاعلي يظهر انتقال المؤشر Node by Node"""
        val = self._pending_val
        found = -1
        cp = None

        for i, nd in enumerate(self._nodes):
            self._rptr(cp)
            cp = self._ptr(i, "curr", ARROW_COL)

            # Highlight current node being checked
            self.play(nd["data_sq"].animate.set_fill(VISIT_COL, 0.55), run_time=0.16)
            self.wait(0.26)

            if nd["val"] == val:
                found = i
                # Found! Highlight with success color
                self.play(self._nodes[found]["data_sq"].animate.set_fill(FOUND_COL, 0.85), run_time=0.20)

                # Show found indicator
                found_text = Text(f"Found at index {found}!", color=FOUND_COL).scale(0.26)
                found_text.move_to(np.array([_cx(), -2.20, 0]))
                self._t(found_text)
                self.wait(0.50)
                self.remove(found_text)
                self._tracked.remove(found_text)
                break
            else:
                # Not found, reset color
                self.play(nd["data_sq"].animate.set_fill(NODE_FILL, 1), run_time=0.10)

        self._rptr(cp)

        if found < 0:
            # Not found in entire list
            not_found_text = Text(f"Value {val} not found", color=GRAY_COLOR).scale(0.26)
            not_found_text.move_to(np.array([_cx(), -2.20, 0]))
            self._t(not_found_text)
            self.wait(0.50)
            self.remove(not_found_text)
            self._tracked.remove(not_found_text)

        self.wait(0.65)
        self._build_list(self._data, base_y=1.00)

    def _op_traverse(self):
        self.wait(0.20)
        self._traversing = True
        cp = None

        for i, nd in enumerate(self._nodes):
            self._rptr(cp)
            cp = self._ptr(i, "curr", ARROW_COL)

            self.play(nd["val_txt"].animate.set_color(YELLOW),
                      nd["addr_txt"].animate.set_color(YELLOW),
                      nd["data_sq"].animate.set_fill(VISIT_COL, 0.44), run_time=0.20)

            self._action = None
            while not self.is_window_closing():
                self.update_frame(1/self.camera.fps)
                if self._action == "space":
                    break
                if self._action in ("scene_next", "scene_prev"):
                    self._rptr(cp)
                    self._traversing = False
                    d = 1 if self._action == "scene_next" else -1
                    self._action = None
                    self._switch_scene(d)
                    return

            self.play(nd["val_txt"].animate.set_color(WHITE),
                      nd["addr_txt"].animate.set_color(ADDR_COLOR),
                      nd["data_sq"].animate.set_fill(FOUND_COL, 0.24), run_time=0.14)

        self._rptr(cp)
        self.wait(0.45)
        self._build_list(self._data, base_y=1.00)
        self._traversing = False

    def _op_reverse(self):
        if len(self._data) < 2: return
        self.wait(0.28)
        n = len(self._data)
        pp = cp = np_ = None

        for i in range(n):
            self._rptr(pp, cp, np_)
            if i > 0:   pp  = self._ptr(i-1, "prev", "#e74c3c")
            cp  = self._ptr(i, "curr", ARROW_COL)
            if i < n-1: np_ = self._ptr(i+1, "nxt",  "#9b59b6")

            self.play(self._nodes[i]["data_sq"].animate.set_fill(VISIT_COL, 0.50), run_time=0.16)
            self.wait(0.30)
            self.play(self._nodes[i]["data_sq"].animate.set_fill(FOUND_COL, 0.24), run_time=0.10)

        self._rptr(pp, cp, np_)
        self._data.reverse()
        self._build_list(self._data, base_y=1.00)
        self.wait(0.45)

    def _op_reset(self):
        self._desel()
        self._data = DEFAULT_LIST.copy()
        self._build_list(self._data, base_y=1.00)


    def _s5_do_access(self):
        ti = self._pending_val
        if ti is None or not (0 <= ti < len(self._arr_boxes)): self._load_scene(5); return
        BW  = self._s5_BW; AY  = self._s5_AY; LY  = self._s5_LY

        for a in self._arr_boxes: a["bx"].set_stroke(WHITE, 1.8)
        ab = self._arr_boxes[ti]
        ab["bx"].set_stroke(FOUND_COL, 3.5)
        pa = Arrow(
            np.array([ab["cx"], AY - BW*0.80/2 - 0.52, 0]),
            np.array([ab["cx"], AY - BW*0.80/2 - 0.06, 0]),
            buff=0, stroke_width=4.0, color=FOUND_COL,
            max_tip_length_to_length_ratio=0.36)
        la = Text("O(1)", color=FOUND_COL, weight=BOLD).scale(0.34)
        la.move_to(np.array([ab["cx"], AY - BW*0.80/2 - 0.76, 0]))
        self._t(pa, la); self.wait(0.40)

        cp = None
        for i, ln in enumerate(self._ll_s5):
            if cp: self.remove(cp)
            cp = Arrow(
                np.array([ln["cx"], LY - BW*0.80/2 - 0.46, 0]),
                np.array([ln["cx"], LY - BW*0.80/2 - 0.06, 0]),
                buff=0, stroke_width=4.0, color=VISIT_COL,
                max_tip_length_to_length_ratio=0.36)
            self._t(cp)
            self.play(ln["dbx"].animate.set_fill(VISIT_COL, 0.45), run_time=0.20)
            self.wait(0.22)
            if i == ti:
                self.play(ln["dbx"].animate.set_fill(FOUND_COL, 0.60), run_time=0.20)
                ll2 = Text(f"O(n)  ({ti+1} steps)", color=VISIT_COL, weight=BOLD).scale(0.26)
                ll2.move_to(np.array([self._ll_cx, LY - BW*0.80/2 - 0.76, 0]))
                self._t(ll2); break
            self.play(ln["dbx"].animate.set_fill(NODE_FILL, 1), run_time=0.10)

        self.wait(1.00); self._load_scene(5)

    def _s5_do_insert(self):
        val = self._pending_val
        if val is None: self._load_scene(5); return
        N  = len(self._arr_boxes)
        SP = self._s5_SP; BW = self._s5_BW; NW = self._s5_NW
        AY = self._s5_AY; LY = self._s5_LY
        if N == 0: self._load_scene(5); return

        for i in range(N-1, 0, -1):
            self.play(self._arr_boxes[i]["bx"].animate.set_fill(ARR_SHIFT, 0.70), run_time=0.09)
        self._arr_data.insert(0, val)
        la = Text("O(n)  shift all", color=ARR_COL, weight=BOLD).scale(0.28)
        la.move_to(np.array([self._arr_cx, AY - BW*0.80 - 0.58, 0]))
        self._t(la); self.wait(0.40)

        if self._ll_s5:
            old_head = self._ll_s5[0]
            new_cx = old_head["cx"]
            new_cy = LY + 1.10

            new_dbx = Rectangle(width=BW, height=BW*0.80)
            new_dbx.set_fill(LL_NEW, 0.85).set_stroke(LL_NEW, 2.5)
            new_dbx.move_to(np.array([new_cx, new_cy, 0]))

            val_scale = min(0.46, BW * 0.36)
            new_tv = Text(str(val), color=WHITE, weight=BOLD).scale(val_scale)
            new_tv.move_to(np.array([new_cx, new_cy, 0]))

            new_nbx = Rectangle(width=NW, height=BW*0.80)
            new_nbx.set_fill(NEXT_FILL, 1).set_stroke(LL_NEW, 1.5)
            new_nbx.move_to(np.array([new_cx + BW/2 + NW/2, new_cy, 0]))

            new_sc_addr = SCATTERED[min(len(self._ll_data), len(SCATTERED)-1)]
            new_addr = Text(f"@{new_sc_addr}", color=LL_COL).scale(0.18)
            new_addr.move_to(np.array([new_cx, new_cy + BW*0.80/2 + 0.20, 0]))

            self.play(FadeIn(VGroup(new_dbx, new_tv, new_nbx, new_addr)), run_time=0.26)
            self._t(new_dbx, new_tv, new_nbx, new_addr)

            link_ar = Arrow(
                np.array([new_cx + BW/2 + NW + 0.06, new_cy, 0]),
                old_head["dbx"].get_center() + np.array([0, 0.04, 0]),
                buff=0.04, stroke_width=5, color=LL_PTR,
                max_tip_length_to_length_ratio=0.36)
            self.play(FadeIn(link_ar), run_time=0.20)
            self._t(link_ar)
            self.play(old_head["dbx"].animate.set_fill(FOUND_COL, 0.28), run_time=0.22)
            self._ll_data.insert(0, val)

        lh = Text("O(1)  update HEAD", color=LL_COL, weight=BOLD).scale(0.28)
        lh.move_to(np.array([self._ll_cx, LY - BW*0.80 - 0.58, 0]))
        self._t(lh)
        self.wait(1.00); self._load_scene(5)

    def _s5_do_delete(self):
        idx = self._s5_sel_idx
        if idx is None or not (0 <= idx < len(self._arr_boxes)):
            self._load_scene(5); return
        if idx < len(self._arr_data): self._arr_data.pop(idx)
        if idx < len(self._ll_data):  self._ll_data.pop(idx)
        self._s5_sel_idx = None
        self._load_scene(5)

    def _s5_do_search(self):
        val = self._pending_val
        if val is None: self._load_scene(5); return
        BW = self._s5_BW; AY = self._s5_AY; LY = self._s5_LY

        found_a = -1
        for i, ab in enumerate(self._arr_boxes):
            self.play(ab["bx"].animate.set_fill(VISIT_COL, 0.55), run_time=0.15)
            self.wait(0.18)
            if ab["val"] == val:
                self.play(ab["bx"].animate.set_fill(FOUND_COL, 0.80), run_time=0.18)
                found_a = i; break
            else:
                ab["bx"].set_fill("#1a1a2e", 1)

        la = Text(f"Array O(n)  {'found!' if found_a>=0 else 'not found'}", color=ARR_COL, weight=BOLD).scale(0.24)
        la.move_to(np.array([self._arr_cx, AY - BW*0.80 - 0.56, 0]))
        self._t(la); self.wait(0.30)

        found_l = -1; cp = None
        for i, ln in enumerate(self._ll_s5):
            if cp: self.remove(cp)
            cp = Arrow(
                np.array([ln["cx"], LY - BW*0.80/2 - 0.42, 0]),
                np.array([ln["cx"], LY - BW*0.80/2 - 0.06, 0]),
                buff=0, stroke_width=3.5, color=VISIT_COL,
                max_tip_length_to_length_ratio=0.36)
            self._t(cp)
            self.play(ln["dbx"].animate.set_fill(VISIT_COL, 0.50), run_time=0.15)
            self.wait(0.18)
            if ln["val"] == val:
                self.play(ln["dbx"].animate.set_fill(FOUND_COL, 0.80), run_time=0.18)
                found_l = i; break
            else:
                self.play(ln["dbx"].animate.set_fill(NODE_FILL, 1), run_time=0.10)

        ll_lbl = Text(f"LL O(n)  {'found!' if found_l>=0 else 'not found'}", color=LL_COL, weight=BOLD).scale(0.24)
        ll_lbl.move_to(np.array([self._ll_cx, LY - BW*0.80 - 0.56, 0]))
        self._t(ll_lbl)
        self.wait(1.20); self._load_scene(5)


    # ═══════════════════════════════════════════ KEYBOARD ════
    def on_key_press(self, symbol, modifiers):
        ctrl  = bool(modifiers & K.MOD_CTRL)
        shift = bool(modifiers & K.MOD_SHIFT)

        # ── النوتة نشطة ─────────────────────────────────────
        if self._notepad and self._notepad.is_active():
            if ctrl:
                self._notepad.key(symbol, modifiers)
                return
            control_keys = {
                K.RETURN, K.BACKSPACE, K.DELETE,
                K.LEFT, K.RIGHT, K.UP, K.DOWN,
                K.HOME, K.END,
            }
            if symbol in control_keys:
                self._notepad.key(symbol, modifiers)
                return
            ch = _sym_to_char(symbol, modifiers)
            if ch:
                self._notepad.insert_text(ch)
            return

        # ── صندوق الإدخال مفتوح ─────────────────────────────
        if self._box_bg is not None:
            if symbol == K.RETURN:
                raw = self._buf.strip(); mode = self._box_mode; idx = self._box_idx
                self._close_box(); self._box_mode = None; self._box_idx = None

                if mode == "s1_v1":
                    try:
                        val = int(raw); self.remove(self._s1_v1)
                        self._s1_v1 = Text(str(val), color=WHITE, weight=BOLD).scale(1.04)
                        self._s1_v1.move_to(np.array([self._s1_N1_DSQCX, self._s1_NY + 0.72, 0]))
                        self.add(self._s1_v1); self._tracked.append(self._s1_v1)
                    except ValueError: pass; return
                if mode == "s1_v2":
                    try:
                        val = int(raw); self.remove(self._s1_v2)
                        self._s1_v2 = Text(str(val), color=WHITE, weight=BOLD).scale(1.04)
                        self._s1_v2.move_to(np.array([self._s1_N2_DSQCX, self._s1_NY + 0.72, 0]))
                        self.add(self._s1_v2); self._tracked.append(self._s1_v2)
                    except ValueError: pass; return
                if mode == "s1_a2":
                    new_addr = raw if raw.startswith("0x") else "0x" + raw
                    self.remove(self._s1_a2)
                    self._s1_a2 = Text(new_addr, color=ADDR_COLOR).scale(0.50)
                    self._s1_a2.move_to(np.array([self._s1_N2_DSQCX, self._s1_NY - 0.32, 0]))
                    self.add(self._s1_a2); self._tracked.append(self._s1_a2)
                    self._s1_update_link_addr(new_addr); return

                if mode == "s2_add":
                    try:
                        val = int(raw)
                        self._ram_data.append(val)
                        self._build_list(self._ram_data, base_y=1.80, override_cx=_cx())
                        self._s2_rebuild_rows()
                        if self._nodes:
                            self.play(self._nodes[-1]["data_sq"].animate.set_fill(FOUND_COL, 0.70), run_time=0.20)
                            self.play(self._nodes[-1]["data_sq"].animate.set_fill(NODE_FILL, 1),    run_time=0.14)
                    except ValueError: pass; return

                if mode == "s5_arr":
                    try:
                        val = int(raw); ab = self._arr_boxes[idx]
                        self.remove(ab["tv"])
                        vs = min(0.50, ab["bw"] * 0.38)
                        nt = Text(str(val), color=WHITE, weight=BOLD).scale(vs)
                        nt.move_to(np.array([ab["cx"], ab["cy"], 0]))
                        ab["tv"] = nt; ab["val"] = val
                        self._arr_data[idx] = val
                        self.add(nt); self._tracked.append(nt)
                    except ValueError: pass; return
                if mode == "s5_ll":
                    try:
                        val = int(raw); ln = self._ll_s5[idx]
                        self.remove(ln["tv"])
                        vs = min(0.46, ln["bw"] * 0.36)
                        nt = Text(str(val), color=WHITE, weight=BOLD).scale(vs)
                        nt.move_to(np.array([ln["cx"], ln["cy"], 0]))
                        ln["tv"] = nt; ln["val"] = val
                        self._ll_data[idx] = val
                        self.add(nt); self._tracked.append(nt)
                    except ValueError: pass; return
                if mode == "s5_search":
                    try:
                        self._pending_val = int(raw)
                        self._action = "s5_search"
                    except ValueError: pass; return
                if mode == "s5_access":
                    try:
                        ti = int(raw)
                        if 0 <= ti < len(self._arr_boxes):
                            self._pending_val = ti
                            self._action = "s5_access"
                    except ValueError: pass; return
                if mode == "s5_insert":
                    try:
                        val = int(raw)
                        self._pending_val = val
                        self._action = "s5_insert"
                    except ValueError: pass; return
                if mode == "s5_delete_idx":
                    try:
                        ti = int(raw)
                        if 0 <= ti < len(self._arr_boxes):
                            self._s5_sel_idx = ti
                            self._action = "s5_delete"
                        else:
                            self._s5_sel_idx = None
                    except ValueError:
                        self._s5_sel_idx = None
                    return

                try: val = int(raw)
                except ValueError: return
                if   mode == "add_head": self._data.insert(0, val); self._pending_val = val; self._action = "add_head"
                elif mode == "add_tail": self._data.append(val);    self._pending_val = val; self._action = "add_tail"
                elif mode == "add_mid":
                    if self._selected is not None:
                        self._data.insert(self._selected + 1, val)
                        self._pending_val = val
                        self._action = "add_mid"
                    else:
                        self._data.append(val)
                        self._pending_val = val
                        self._action = "add_tail"
                elif mode == "search":   self._pending_val = val;   self._action = "search"
                elif mode == "cell":
                    self._edit_val(idx, val)
                    if self._scene_idx == 2: self._s2_update_ram()

            elif symbol == K.BACKSPACE:
                self._buf = self._buf[:-1]; self._refresh_box()
            elif symbol == K.ESCAPE:
                self._close_box(); self._box_mode = None; self._box_idx = None
            else:
                ch = _sym_to_char(symbol, modifiers)
                if ch and ch in "0123456789-xabcdefABCDEF.":
                    self._buf += ch
                    self._refresh_box()
            return

        # ── اختصارات لوحة المفاتيح العامة ────────────────────

        # H: Toggle Help window
        if symbol == K.H and not ctrl:
            self._action = "toggle_help"
            return

        # N: Toggle Notepad
        if symbol == K.N and not ctrl:
            self._action = "toggle_pad"
            return

        # تنقل بين المشاهد
        if symbol == K.RIGHT and not ctrl: 
            self._action = "scene_next"
            return
        if symbol == K.LEFT and not ctrl: 
            self._action = "scene_prev"
            return
        if symbol == K.SPACE:             
            self._action = "space"
            return

        # ── اختصارات المشهد الحالي ──────────────────────────
        si = self._scene_idx

        if si == 3:  # Operations scene
            if symbol == K.H and not ctrl:  # Add Head
                self._desel()
                self._open_box(np.array([_cx(), 2.00, 0]), "Value for Head")
                self._box_mode = "add_head"
                return
            elif symbol == K.T and  ctrl:  # Add Tail
                self._desel()
                self._open_box(np.array([_cx(), 2.00, 0]), "Value for Tail")
                self._box_mode = "add_tail"
                return
            elif symbol == K.M and not ctrl:  # Add Middle
                if self._selected is not None:
                    self._open_box(np.array([_cx(), 2.00, 0]), f"Value after [{self._selected}]")
                    self._box_mode = "add_mid"
                else:
                    self._desel()
                    self._open_box(np.array([_cx(), 2.00, 0]), "Value (no selection = Tail)")
                    self._box_mode = "add_mid"
                return
            elif symbol == K.D and not ctrl:  # Delete selected
                if self._selected is not None:
                    self._action = "delete"
                return
            elif symbol == K.S and not ctrl:  # Search
                self._desel()
                self._open_box(np.array([_cx(), 2.00, 0]), "Search value")
                self._box_mode = "search"
                return
            elif symbol == K.X and not ctrl:  # Reset
                self._action = "reset"
                return

        elif si == 4:  # Traverse/Reverse scene
            if symbol == K.T and not ctrl:  # Traverse
                self._action = "traverse"
                return
            elif symbol == K.R and not ctrl:  # Reverse
                self._action = "reverse"
                return
            elif symbol == K.X and not ctrl:  # Reset
                self._action = "reset"
                return

        elif si == 5:  # Array vs Linked List scene
            if symbol == K.I and not ctrl:  # Access by index
                self._open_box(np.array([_cx(), 2.00, 0]), f"Index (0-{len(self._arr_boxes)-1})")
                self._box_mode = "s5_access"
                return
            elif symbol == K.H and not ctrl:  # Insert head
                self._open_box(np.array([_cx(), 2.00, 0]), "Value to insert")
                self._box_mode = "s5_insert"
                return
            elif symbol == K.D and not ctrl:  # Delete
                if self._s5_sel_idx is not None:
                    self._action = "s5_delete"
                else:
                    self._open_box(np.array([_cx(), 2.00, 0]), f"Select index (0-{len(self._arr_boxes)-1})")
                    self._box_mode = "s5_delete_idx"
                return
            elif symbol == K.F and not ctrl:  # Search
                self._open_box(np.array([_cx(), 2.00, 0]), "Search val")
                self._box_mode = "s5_search"
                return
            elif symbol == K.X and not ctrl:  # Reset
                self._action = "s5_reset"
                return

        super().on_key_press(symbol, modifiers)

    # ═══════════════════════════════════════════════ MOUSE ═══
    def on_mouse_press(self, point, button, mods):
        if self._box_bg is not None: return
        if self._hit_tog(point): self._action = "toggle_pad"; return

        # Check Help window first
        if self._help_window and self._help_window.is_visible():
            if self._help_window.hit(point):
                return  # Click inside help window - just consume it
            else:
                # Click outside help window - close it
                self._help_window.hide()
                return

        if self._notepad:
            if self._notepad.hit_plus(point):  self._notepad.font_up();   return
            if self._notepad.hit_minus(point): self._notepad.font_down(); return
            if self._notepad.hit(point):
                if not self._notepad.is_active():
                    self._notepad.activate()
                self._notepad.click_at(point)
                self._notepad._render(force=True)
                return
            else:
                if self._notepad.is_active(): self._notepad.deactivate()

        si = self._scene_idx
        if   si == 1: self._ms1(point)
        elif si == 2: self._ms2(point)
        elif si == 3: self._ms3(point)
        elif si == 4: self._ms4(point)
        elif si == 5: self._ms5(point)

    def on_mouse_drag(self, point, d_point, button, mods):
        delta = np.array([d_point[0], d_point[1], 0])
        if self._scene_idx == 2 and self._ram_drag and self._ram_tmobs:
            for m in self._ram_tmobs: m.shift(delta)
            self.update_frame(0); return
        if self._drag_idx is not None:
            self._move_node(self._drag_idx, delta)
            self.update_frame(0)

    def on_mouse_release(self, point, button, mods):
        self._ram_drag = False
        if self._drag_idx is not None:
            i = self._drag_idx
            if self._selected != i:
                self._nodes[i]["data_sq"].set_stroke(WHITE, 2.2)
            self._drag_idx = None
