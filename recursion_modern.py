from manimlib import *
import numpy as np, ast, types, ctypes

def _center_window():
    try:
        import threading, time
        def _do():
            time.sleep(0.6)
            hwnd = ctypes.windll.user32.FindWindowW(None, "FullScene")
            if not hwnd:
                hwnd = ctypes.windll.user32.FindWindowW(None, "ManimGL")
            if hwnd:
                sw = ctypes.windll.user32.GetSystemMetrics(0)
                sh = ctypes.windll.user32.GetSystemMetrics(1)
                ww, wh = 1280, 720
                x = (sw - ww) // 2
                y = (sh - wh) // 2
                ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, ww, wh, 0x0040)
        threading.Thread(target=_do, daemon=True).start()
    except Exception:
        pass

_center_window()

# == PALETTE ==
N     = 5
SPEED = 1.2
AUTO_SPEED = 0.55

BG    = "#03060e"
SURF  = "#060d18"
SURF2 = "#091320"
CC    = "#4fc3f7"
CA    = "#ffb74d"
CR    = "#69f0ae"
CB_C  = "#f48fb1"
CF    = "#ce93d8"
CDIM  = "#0f2035"
CTXT  = "#dceeff"
CSUB  = "#3a566e"
CERR  = "#ef5350"
COLS  = ["#4fc3f7","#f48fb1","#ffb74d","#69f0ae",
         "#b39ddb","#4dd0e1","#fff176","#a5d6a7"]

CHOVER   = "#ffe082"
CSEL     = "#80deea"
CDRAG    = "#ff8a65"

def T(t,fast=False): return t * (SPEED * 0.3 if fast else SPEED)

EX   = -4.30
TCX  =  1.50
EXP_X=  5.10
PY   = -0.50
PH   =  5.20

TMPL = [
  "def recsum(n):\n    if n <= 0:\n        return 0\n    return n + recsum(n-1)",
  "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n-1)",
  "def power(n):\n    if n == 0:\n        return 1\n    return 2 * power(n-1)",
  "def fib(n):\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)",
]
DEFAULT_CODE = TMPL[0]


def make_explanation(fn_name, step, all_steps, src_lines):
    import re as _re
    act   = step["act"]
    sv    = step["n"]
    base  = step["base"]
    depth = step["depth"]
    nid   = step["nid"]
    res   = step.get("result")
    src   = src_lines or []

    cond_expr = ""; base_ret_expr = ""; rec_line = ""
    for ln in src:
        s = ln.strip()
        m = _re.match(r"if (.+):", s)
        if m and not cond_expr:         cond_expr     = m.group(1)
        if s.startswith("return") and fn_name+"(" not in s and not base_ret_expr:
                                        base_ret_expr = s[6:].strip()
        if "return" in s and fn_name+"(" in s and not rec_line:
                                        rec_line      = s

    def ev(expr, n_val):
        try:    return eval(expr, {"n": n_val})
        except: return None

    col = CB_C if base else (CR if act=="pop" else CA)
    lines = []

    state = "BASE CASE" if base else ("RETURNING" if act=="pop" else "CALLING")
    lines.append((f"  {fn_name}({sv})   [{state}]", col))
    lines.append(("  " + "─"*26, CDIM))
    lines.append(("", CSUB))
    lines.append((f"  Input  :  n = {sv}", CTXT))
    lines.append((f"  Depth  :  {depth}", CSUB))
    lines.append(("", CSUB))

    if cond_expr:
        cv = ev(cond_expr, sv)
        if cv is True:
            lines.append((f"  if {cond_expr}:", CTXT))
            lines.append((f"    n={sv}  →  Yes  (base case)", CB_C))
            bval = ev(base_ret_expr, sv)
            lines.append((f"  return {bval}", CB_C))
        else:
            lines.append((f"  if {cond_expr}:", CTXT))
            lines.append((f"    n={sv}  →  No  (recurse)", CA))
            if rec_line:
                display = _re.sub(r'\bn\b', str(sv), rec_line.strip())
                lines.append((f"  {display}", col))
        lines.append(("", CSUB))

    if act == "pop" and res is not None and not base:
        pop_map = {s2["nid"]: s2.get("result")
                   for s2 in all_steps if s2["act"]=="pop"}
        sub_nid = next((s2["nid"] for s2 in all_steps
                        if s2["act"]=="push" and s2["parent"]==nid), None)
        sub_r   = pop_map.get(sub_nid) if sub_nid is not None else None

        lines.append(("  Calculation:", CSUB))
        if sub_r is not None and rec_line:
            formula = _re.sub(fn_name+r"[(][^)]*[)]", str(sub_r), rec_line.strip())
            formula = _re.sub(r'\bn\b', str(sv), formula)
            formula = formula.replace("return","").strip()
            lines.append((f"    {formula}", CTXT))
            lines.append((f"    = {res}", CR))
        else:
            lines.append((f"    result = {res}", CR))

    if act == "pop" and base and res is not None:
        lines.append(("  Calculation:", CSUB))
        lines.append((f"    base value = {res}", CB_C))

    return lines


def trace(code_str, n, max_calls=500):
    try:    tree = ast.parse(code_str)
    except SyntaxError as e:
        return None,[],None,f"SyntaxError line {e.lineno}: {e.msg}"
    fn_name=None
    for node in ast.walk(tree):
        if isinstance(node,ast.FunctionDef): fn_name=node.name; break
    if not fn_name: return None,[],None,"No function found."

    for node in ast.walk(tree):
        if isinstance(node,ast.FunctionDef) and node.name==fn_name:
            nargs = len(node.args.args)
            if nargs != 1:
                return fn_name,[],None,f"Function needs exactly 1 arg (got {nargs})."
            break

    import builtins
    safe_builtins = vars(builtins).copy()
    safe_builtins["input"]  = lambda *a,**kw: str(n)
    safe_builtins["print"]  = lambda *a,**kw: None
    safe_builtins["open"]   = lambda *a,**kw: (_ for _ in ()).throw(PermissionError("open blocked"))
    safe_builtins["__import__"] = lambda *a,**kw: None

    ns = {"__builtins__": safe_builtins}
    try: exec(compile(tree,"<ed>","exec"),ns)
    except Exception as e: return fn_name,[],None,str(e)
    original=ns[fn_name]; steps=[]; counter=[0]; nid_ctr=[0]

    def is_base(x):
        hit=[False]
        g=ns.copy()
        g[fn_name]=lambda *a,**kw: hit.__setitem__(0,True) or 0
        try:
            p=types.FunctionType(original.__code__,g,original.__name__,
                                 original.__defaults__,original.__closure__)
            p(x)
        except Exception: pass
        return not hit[0]

    def make_tracer(depth,parent_nid):
        def tracer(x):
            counter[0]+=1
            if counter[0]>max_calls: raise RecursionError(f"Too many calls (>{max_calls}).")
            base=is_base(x); my_nid=nid_ctr[0]; nid_ctr[0]+=1
            steps.append(dict(act="push",n=x,depth=depth,
                              nid=my_nid,parent=parent_nid,base=base))
            g=ns.copy(); g[fn_name]=make_tracer(depth+1,my_nid)
            try:
                p=types.FunctionType(original.__code__,g,original.__name__,
                                     original.__defaults__,original.__closure__)
                result=p(x)
            except RecursionError: raise
            except Exception: result=None
            steps.append(dict(act="pop",n=x,depth=depth,
                              nid=my_nid,parent=parent_nid,base=base,result=result))
            return result
        return tracer
    try:
        final=make_tracer(0,-1)(n); return fn_name,steps,final,None
    except RecursionError as e:
        msg=str(e)
        if steps: msg+=f"  (stopped at {len(steps)} steps)"
        return fn_name,steps,None,msg
    except Exception as e: return fn_name,steps,None,str(e)


def tree_layout_zz(steps, cx, top_y, lvl_h, avail_h=5.0):
    push = [s for s in steps if s["act"]=="push"]
    if not push: return {}
    info     = {s["nid"]:s for s in push}
    children = {}
    for s in push:
        children.setdefault(s["parent"],[]).append(s["nid"])
    by_d = {}
    for s in push: by_d.setdefault(s["depth"],[]).append(s["nid"])
    pos  = {}

    is_linear = all(len(v)<=1 for v in children.values())

    if is_linear:
        n_levels = max(by_d.keys())+1 if by_d else 1
        if n_levels * lvl_h <= avail_h * 1.05:
            for d,row in by_d.items():
                for nid in row:
                    pos[nid] = np.array([cx, top_y - d*lvl_h, 0.0])
        else:
            col_x = [cx - 0.55, cx + 0.55]
            row_h = avail_h / max(n_levels/2, 1)
            row_h = min(row_h, lvl_h)
            for d,row in by_d.items():
                col  = d % 2
                yi   = d // 2
                y    = top_y - yi * row_h*2 - (row_h if col==1 else 0)
                for nid in row:
                    pos[nid] = np.array([col_x[col], y, 0.0])
    else:
        min_sep = 0.90
        for d,row in by_d.items():
            cnt=len(row); span=(cnt-1)*min_sep
            x0=cx-span/2; y=top_y-d*lvl_h
            for i,nid in enumerate(row):
                pos[nid]=np.array([x0+i*min_sep,y,0.0])
    return pos


class DynamicArrow(VGroup):
    def __init__(self, start_mob, end_mob,
                 color=CC, sw=1.8, tip_size=0.11,
                 start_r=0.35, end_r=0.35,
                 ret_arrow=False, **kw):
        super().__init__(**kw)
        self.start_mob = start_mob
        self.end_mob   = end_mob
        self.color     = color
        self.sw        = sw
        self.tip_size  = tip_size
        self.start_r   = start_r
        self.end_r     = end_r
        self.ret_arrow = ret_arrow
        self._line = VMobject(stroke_color=color, stroke_width=sw)
        self._tip  = VMobject(stroke_color=color, stroke_width=0,
                              fill_color=color, fill_opacity=1.0)
        self.add(self._line, self._tip)
        self.refresh()

    def _compute(self):
        s = self.start_mob.get_center()
        e = self.end_mob.get_center()

        if self.ret_arrow:
            perp = np.array([-(e[1]-s[1]), e[0]-s[0], 0])
            nrm  = np.linalg.norm(perp)
            if nrm > 1e-6: perp = perp / nrm * 0.22
            s = s + perp; e = e + perp

        diff = e - s
        dist = np.linalg.norm(diff)
        if dist < 1e-6:
            return s, e, s, e
        d = diff / dist
        p0 = s + d * self.start_r
        p1 = e - d * self.end_r

        mid = (p0 + p1) / 2
        perp2 = np.array([-d[1], d[0], 0])
        curve_amount = min(0.18, dist * 0.08)
        if self.ret_arrow: curve_amount = -curve_amount
        ctrl = mid + perp2 * curve_amount

        return p0, ctrl, p1, d

    def refresh(self):
        p0, ctrl, p1, d = self._compute()

        pts = []
        steps = 20
        for i in range(steps + 1):
            t = i / steps
            pt = (1-t)**2 * p0 + 2*(1-t)*t * ctrl + t**2 * p1
            pts.append(pt)
        self._line.set_points_as_corners(pts)
        self._line.set_stroke(color=self.color, width=self.sw)

        tip_pts = self._make_tip(p1, d)
        self._tip.set_points_as_corners(tip_pts)
        self._tip.set_fill(color=self.color, opacity=1.0)
        self._tip.set_stroke(width=0)

    def _make_tip(self, tip_pos, direction):
        angle = np.arctan2(direction[1], direction[0])
        ts    = self.tip_size
        back  = tip_pos - direction * ts * 1.8
        perp  = np.array([-direction[1], direction[0], 0])
        a = tip_pos
        b = back + perp * ts * 0.7
        c = back - perp * ts * 0.7
        return [a, b, c, a]

    def set_opacity_level(self, v):
        self._line.set_stroke(opacity=v)
        self._tip.set_fill(opacity=v)
        return self

    def recolor(self, c):
        self.color = c
        self._line.set_stroke(color=c)
        self._tip.set_fill(color=c)
        self.refresh()


class DraggableNode(VGroup):
    def __init__(self, fn_name, n_val, radius=0.35,
                 base=False, lbl_sz=14, **kw):
        super().__init__(**kw)
        self.fn_name  = fn_name
        self.n_val    = n_val
        self.radius   = radius
        self.base     = base
        self.lbl_sz   = lbl_sz
        self.state    = "base" if base else "pending"
        self._dragging = False
        self._hover    = False
        self.arrows    = []

        self._circ = Circle(radius=radius)
        self._lbl  = Text(f"{fn_name}({n_val})",
                          font_size=lbl_sz, weight=BOLD)
        self.add(self._circ, self._lbl)
        self._apply_state()

    def _col_for_state(self):
        if self._dragging: return CDRAG
        if self._hover:    return CHOVER
        s = self.state
        if s == "active":   return CA
        if s == "returned": return CR
        if s == "base":     return CB_C
        return CC

    def _apply_state(self):
        c = self._col_for_state()
        self._circ.set_stroke(color=c, width=2.2)
        fill_op = 0.45 if (self._dragging or self._hover) else 0.22
        self._circ.set_fill(color=c, opacity=fill_op)
        self._lbl.set_color("#ffffff")
        self._lbl.move_to(self._circ.get_center())

    def set_state(self, state):
        self.state = state
        self._apply_state()

    def set_hover(self, v):
        self._hover = v
        self._apply_state()

    def set_dragging(self, v):
        self._dragging = v
        self._apply_state()

    def move_to(self, pos):
        super().move_to(pos)
        self._lbl.move_to(self._circ.get_center())
        self._refresh_arrows()
        return self

    def shift(self, delta):
        super().shift(delta)
        self._lbl.move_to(self._circ.get_center())
        self._refresh_arrows()
        return self

    def _refresh_arrows(self):
        for arr in self.arrows:
            try: arr.refresh()
            except Exception: pass

    def show_result(self, val):
        rl = Text(f"={val}", font_size=max(10, self.lbl_sz-2),
                  color="#ffffff")
        rl.next_to(self._lbl, DOWN, buff=0.02)
        self.add(rl)


def box(w,h,fill=SURF2,stroke=CDIM,sw=1.2,r=0.13):
    return RoundedRectangle(width=w,height=h,corner_radius=r,
        fill_color=fill,fill_opacity=1,stroke_color=stroke,stroke_width=sw)

_FONTS_HEAD = ["Segoe UI","Arial","sans-serif"]
_FONTS_BODY = ["Segoe UI","Arial","sans-serif"]
_FONTS_CODE = ["Consolas","Courier New","monospace"]

def _pick_font(stack):
    for f in stack:
        try:
            Text("test", font=f, font_size=12)
            return f
        except Exception:
            continue
    return ""

_FH = _pick_font(_FONTS_HEAD)
_FB2= _pick_font(_FONTS_BODY)
_FC = _pick_font(_FONTS_CODE)

def tx(t, sz=14, c=CTXT, bold=False, kind="body"):
    font = _FH if kind=="head" else (_FC if kind=="code" else _FB2)
    try:
        return Text(t, font=font, font_size=sz, color=c,
                    weight=BOLD if bold else NORMAL)
    except Exception:
        return Text(t, font_size=sz, color=c,
                    weight=BOLD if bold else NORMAL)

def txh(t, sz=14, c=CTXT, bold=True):
    return tx(t, sz, c, bold, kind="head")

def txc(t, sz=12, c=CTXT, bold=False):
    return tx(t, sz, c, bold, kind="code")


_FB=[""]
def clipboard_get():
    try:
        import pyperclip; return pyperclip.paste()
    except Exception: pass
    try:
        ctypes.windll.user32.OpenClipboard(0)
        h=ctypes.windll.user32.GetClipboardData(13)
        t=ctypes.wstring_at(h); ctypes.windll.user32.CloseClipboard()
        if t: return t
    except Exception: pass
    try:
        import tkinter as tk
        r=tk.Tk(); r.withdraw(); r.update(); t=r.clipboard_get(); r.destroy(); return t
    except Exception: pass
    return _FB[0]

def clipboard_copy(text):
    _FB[0]=text
    try:
        import pyperclip; pyperclip.copy(text); return
    except Exception: pass
    try:
        data=(text+"\0").encode("utf-16-le")
        h=ctypes.windll.kernel32.GlobalAlloc(0x2000,len(data))
        p=ctypes.windll.kernel32.GlobalLock(h)
        ctypes.memmove(p,data,len(data)); ctypes.windll.kernel32.GlobalUnlock(h)
        ctypes.windll.user32.OpenClipboard(0); ctypes.windll.user32.EmptyClipboard()
        ctypes.windll.user32.SetClipboardData(13,h); ctypes.windll.user32.CloseClipboard()
    except Exception: pass


# ══════════════════════════════════════════════════════
#  HELP PANEL  –  يظهر / يختفي بضغط H
# ══════════════════════════════════════════════════════
class HelpPanel(VGroup):
    """Panel بختصارات لوحة المفاتيح — يظهر بضغط H ويختفي بضغطة ثانية."""

    W = 5.20
    H = 5.60

    # كل سطر: (اختصار, شرح, لون_الاختصار)
    SHORTCUTS = [
        # ── التنقل في الخطوات ──────────────────────────
        ("NAVIGATION", None, CC),
        ("Space",        "الخطوة التالية  (next step)",           CC),
        ("Enter",        "تشغيل تلقائي  (auto-run all)",          CA),
        ("R",            "إعادة التشغيل  (restart)",               CR),

        # ── المحرر ────────────────────────────────────
        ("EDITOR", None, CC),
        ("Click editor", "تفعيل المحرر  (activate editor)",        CTXT),
        ("Ctrl + Enter", "تنفيذ الكود المعدّل  (run edited code)", CA),
        ("Escape",       "إلغاء تفعيل المحرر  (deactivate)",       CSUB),
        ("Tab",          "إضافة 4 مسافات  (indent)",               CTXT),
        ("Enter",        "سطر جديد مع indent تلقائي",              CTXT),
        ("Backspace",    "حذف محرف للخلف",                          CTXT),
        ("Delete",       "حذف محرف للأمام",                         CTXT),
        ("Home / End",   "بداية / نهاية السطر",                    CTXT),
        ("↑ ↓ ← →",      "تحريك المؤشر",                           CTXT),
        ("Shift + ↑↓←→", "تحديد نص  (select text)",               CSEL),
        ("Ctrl + A",     "تحديد الكل  (select all)",               CSEL),
        ("Ctrl + C",     "نسخ  (copy)",                            CSEL),
        ("Ctrl + X",     "قص  (cut)",                              CSEL),
        ("Ctrl + V",     "لصق  (paste)",                           CSEL),

        # ── قوالب جاهزة ───────────────────────────────
        ("TEMPLATES", None, CC),
        ("F1",  "recsum    — مجموع تراكمي",                         CB_C),
        ("F2",  "factorial — المضروب",                               CB_C),
        ("F3",  "power     — القوى",                                 CB_C),
        ("F4",  "fib       — فيبوناتشي",                             CB_C),

        # ── قيمة n ────────────────────────────────────
        ("N VALUE", None, CC),
        ("Click  n =",   "تفعيل حقل n  (activate n-field)",        CHOVER),
        ("0-9",          "إدخال قيمة n الجديدة",                   CHOVER),
        ("Enter",        "تأكيد قيمة n وإعادة التشغيل",            CHOVER),
        ("Escape",       "إلغاء تعديل n",                           CSUB),

        # ── شجرة الاستدعاء ────────────────────────────
        ("CALL TREE", None, CC),
        ("Drag node",    "سحب عقدة لإعادة ترتيبها",               CDRAG),
        ("Hover node",   "تمييز العقدة  (highlight)",              CHOVER),
        ("Scroll (exp)", "تمرير لوحة الشرح  (scroll explanation)", CTXT),

        # ── هذه اللوحة ────────────────────────────────
        ("HELP", None, CC),
        ("H",   "إظهار / إخفاء هذه اللوحة  (toggle help)",        CF),
    ]

    def __init__(self, **kw):
        super().__init__(**kw)

        # ── خلفية ──────────────────────────────────────
        outer = RoundedRectangle(
            width=self.W, height=self.H, corner_radius=0.18,
            fill_color="#020b18", fill_opacity=0.97,
            stroke_color=CF, stroke_width=2.0)

        # ── شريط العنوان ───────────────────────────────
        title_bar = RoundedRectangle(
            width=self.W, height=0.46, corner_radius=0.13,
            fill_color="#081628", fill_opacity=1, stroke_width=0)
        title_bar.align_to(outer, UP)

        key_icon = tx("⌨", 18, CF)
        title_txt = txh("  SHORTCUTS  —  H to close", 12, CF, bold=True)
        title_grp = VGroup(key_icon, title_txt).arrange(RIGHT, buff=0.10)
        title_grp.move_to(title_bar)

        # ── محتوى الاختصارات ───────────────────────────
        content = VGroup()
        LH      = 0.272         # ارتفاع كل سطر
        KW      = 1.55          # عرض عمود الاختصار
        INNER_W = self.W - 0.40  # عرض المحتوى الداخلي

        for key, desc, col in self.SHORTCUTS:
            if desc is None:
                # ── عنوان فئة: نص + خط أفقي تحته ──
                cat = txh(f" {key} ", 8, col, bold=True)
                # خط من طرف لطرف بنفس عرض المحتوى
                line_left  = Line(
                    ORIGIN, RIGHT * INNER_W,
                    stroke_color=col, stroke_width=0.6)
                line_left.set_stroke(opacity=0.35)
                # نضع النص في المنتصف فوق الخط، ثم نجمعهم عمودياً
                grp = VGroup(cat, line_left)
                grp.arrange(DOWN, buff=0.04, aligned_edge=LEFT)
                content.add(grp)
            else:
                # ── سطر اختصار عادي ──
                k_bg = RoundedRectangle(
                    width=KW, height=LH * 0.78, corner_radius=0.06,
                    fill_color="#0d2540", fill_opacity=0.80,
                    stroke_color=col, stroke_width=0.7)
                k_txt = txc(key, 9, col, bold=True)
                k_txt.move_to(k_bg)
                k_grp = VGroup(k_bg, k_txt)

                d_txt = tx(desc, 9, CTXT)
                row = VGroup(k_grp, d_txt).arrange(RIGHT, buff=0.14)
                content.add(row)

        content.arrange(DOWN, buff=0.060, aligned_edge=LEFT)
        content.align_to(outer.get_top() + DOWN * 0.58, UP)
        content.align_to(outer.get_left() + RIGHT * 0.22, LEFT)

        # ── dim overlay hint ───────────────────────────
        hint = tx("Press  H  to close", 9, CSUB)
        hint.align_to(outer, DOWN).shift(UP * 0.12)

        self.add(outer, title_bar, title_grp, content, hint)
        self.move_to(ORIGIN)


# ══════════════════════════════════════════════════════

class CodeEditor(VGroup):
    W=3.80; H=PH; LH=0.38; MAX_V=12

    def __init__(self,code=DEFAULT_CODE,**kw):
        super().__init__(**kw)
        self.lines=code.split("\n")
        self.cl=len(self.lines)-1; self.cc=len(self.lines[-1])
        self.active=False; self.sel_all=False; self._scroll=0; self.hl=-1
        self.sel_start=None; self.sel_end=None

        self.bg=box(self.W,self.H,fill=SURF2,stroke=CC,sw=1.3)
        tb=RoundedRectangle(width=self.W,height=0.40,corner_radius=0.10,
            fill_color="#0c1e33",fill_opacity=1,stroke_width=0)
        tb.align_to(self.bg,UP)
        dots=VGroup(*[Dot(radius=0.055,color=c)
            for c in["#ef5350","#ffb74d","#69f0ae"]]
            ).arrange(RIGHT,buff=0.08)
        dots.move_to(tb).align_to(tb,LEFT).shift(RIGHT*0.13)
        self.fn_lbl=txh("code.py",11,CSUB); self.fn_lbl.move_to(tb)

        self.lg=VGroup()
        self.add(self.bg,tb,dots,self.fn_lbl,self.lg)
        self._draw()

    def _has_sel(self):
        if self.sel_all: return True
        if self.sel_start is None: return False
        return self.sel_start != (self.cl, self.cc)

    def _sel_range(self):
        if self.sel_all:
            return (0,0),(len(self.lines)-1,len(self.lines[-1]))
        if self.sel_start is None:
            return (self.cl,self.cc),(self.cl,self.cc)
        s,e=(self.sel_start,(self.cl,self.cc))
        if s>e: s,e=e,s
        return s,e

    def _sel_text(self):
        (l0,c0),(l1,c1)=self._sel_range()
        if l0==l1: return self.lines[l0][c0:c1]
        parts=[self.lines[l0][c0:]]
        for l in range(l0+1,l1): parts.append(self.lines[l])
        parts.append(self.lines[l1][:c1])
        return "\n".join(parts)

    def _delete_sel(self):
        (l0,c0),(l1,c1)=self._sel_range()
        if l0==l1:
            self.lines[l0]=self.lines[l0][:c0]+self.lines[l0][c1:]
        else:
            self.lines[l0]=self.lines[l0][:c0]+self.lines[l1][c1:]
            del self.lines[l0+1:l1+1]
        self.cl=l0; self.cc=c0
        self.sel_start=None; self.sel_all=False

    def _draw(self):
        self.remove(self.lg); self.lg=VGroup()
        total=len(self.lines)
        we=self._scroll+self.MAX_V-1
        if self.cl<self._scroll: self._scroll=self.cl
        elif self.cl>we:         self._scroll=self.cl-self.MAX_V+1
        self._scroll=max(0,min(self._scroll,max(0,total-self.MAX_V)))
        vis=self.lines[self._scroll:self._scroll+self.MAX_V]
        ty=self.bg.get_top()[1]-0.52
        has_sel=self._has_sel()
        (sl0,sc0),(sl1,sc1)=self._sel_range()

        for i,ln in enumerate(vis):
            ai=self._scroll+i; is_cur=self.active and ai==self.cl
            if ai==self.hl and not self.active:
                hl=Rectangle(width=self.W-0.16,height=self.LH*0.88,
                    fill_color=CA,fill_opacity=0.18,stroke_width=0)
                hl.align_to(self.bg.get_left()+RIGHT*0.08,LEFT)
                hl.set_y(ty-i*self.LH)
                bar=Rectangle(width=0.05,height=self.LH*0.86,
                    fill_color=CA,fill_opacity=1,stroke_width=0)
                bar.align_to(self.bg.get_left()+RIGHT*0.08,LEFT)
                bar.set_y(ty-i*self.LH)
                self.lg.add(hl,bar)
            if has_sel and sl0<=ai<=sl1:
                sel_hl=Rectangle(width=self.W-0.18,height=self.LH*0.84,
                    fill_color=CC,fill_opacity=0.22,stroke_width=0)
                sel_hl.align_to(self.bg.get_left()+RIGHT*0.09,LEFT)
                sel_hl.set_y(ty-i*self.LH)
                self.lg.add(sel_hl)
            if has_sel and sl0<=ai<=sl1: c=CTXT
            elif is_cur:                 c=CTXT
            elif ai==self.hl:            c=CA
            else:                        c=CSUB
            disp=ln
            if is_cur and not has_sel:
                disp=ln[:self.cc]+"▌"+ln[self.cc:]
            num=txc(str(ai+1).rjust(2),8,CDIM)
            num.align_to(self.bg.get_left()+RIGHT*0.10,LEFT); num.set_y(ty-i*self.LH)
            row=txc(disp,12,c)
            row.align_to(self.bg.get_left()+RIGHT*0.38,LEFT); row.set_y(ty-i*self.LH)
            self.lg.add(num,row)
        self.add(self.lg)

    def highlight(self,li): self.hl=li; self._draw()

    def set_active(self,v):
        self.active=v
        self.bg.set_stroke(color=CA if v else CC,width=2.0 if v else 1.3)
        self._draw()

    def set_status(self,msg,c):
        pass

    def set_fn(self,name):
        new=txh(name+".py",11,CC); new.move_to(self.fn_lbl); self.fn_lbl.become(new)

    def set_error(self,msg): self.set_status(f"ERR: {msg[:40]}",CERR)
    def get_code(self): return "\n".join(self.lines)

    def load(self,s):
        self.lines=s.split("\n"); self.cl=len(self.lines)-1
        self.cc=len(self.lines[-1]); self.sel_all=False; self._scroll=0; self.hl=-1
        self._draw()

    def _mv_up(self):
        if self.cl>0: self.cl-=1; self.cc=min(self.cc,len(self.lines[self.cl]))
    def _mv_down(self):
        if self.cl<len(self.lines)-1: self.cl+=1; self.cc=min(self.cc,len(self.lines[self.cl]))
    def _mv_left(self):
        if self.cc>0: self.cc-=1
        elif self.cl>0: self.cl-=1; self.cc=len(self.lines[self.cl])
    def _mv_right(self):
        if self.cc<len(self.lines[self.cl]): self.cc+=1
        elif self.cl<len(self.lines)-1: self.cl+=1; self.cc=0
    def _mv_home(self):
        ln=self.lines[self.cl]; fc=len(ln)-len(ln.lstrip())
        self.cc=0 if self.cc==fc else fc
    def _mv_end(self): self.cc=len(self.lines[self.cl])

    def move_up(self):    self._mv_up();    self._draw()
    def move_down(self):  self._mv_down();  self._draw()
    def move_left(self):  self._mv_left();  self._draw()
    def move_right(self): self._mv_right(); self._draw()
    def move_home(self):  self._mv_home();  self._draw()
    def move_end(self):   self._mv_end();   self._draw()

    def sel_move(self, fn):
        if self.sel_start is None:
            self.sel_start=(self.cl,self.cc)
        self.sel_all=False
        fn(); self._draw()

    def click_to_pos(self, pt, extend_sel=False):
        bg_top  = self.bg.get_top()[1]
        bg_left = self.bg.get_left()[0]
        ty      = bg_top - 0.52
        CHAR_W  = 0.082
        NUM_OFF = 0.38

        dy = ty - pt[1]
        vis_line = int(dy / self.LH + 0.15)
        vis_line = max(0, min(vis_line, self.MAX_V - 1))
        abs_line = self._scroll + vis_line
        abs_line = min(abs_line, len(self.lines) - 1)

        dx = pt[0] - (bg_left + NUM_OFF)
        col = max(0, round(dx / CHAR_W))
        col = min(col, len(self.lines[abs_line]))

        if extend_sel:
            if self.sel_start is None:
                self.sel_start = (self.cl, self.cc)
            self.sel_all = False
        else:
            self.sel_start = None
            self.sel_all   = False

        self.cl = abs_line
        self.cc = col
        self._draw()

    def insert(self,ch):
        if self._has_sel(): self._delete_sel()
        ln=self.lines[self.cl]
        self.lines[self.cl]=ln[:self.cc]+ch+ln[self.cc:]
        self.cc+=len(ch); self._draw()

    def backspace(self):
        if self._has_sel(): self._delete_sel(); self._draw(); return
        if self.cc>0:
            ln=self.lines[self.cl]
            self.lines[self.cl]=ln[:self.cc-1]+ln[self.cc:]; self.cc-=1
        elif self.cl>0:
            prev=self.lines[self.cl-1]; self.cc=len(prev)
            self.lines[self.cl-1]=prev+self.lines[self.cl]
            del self.lines[self.cl]; self.cl-=1
        self._draw()

    def delete_fwd(self):
        if self._has_sel(): self._delete_sel(); self._draw(); return
        ln=self.lines[self.cl]
        if self.cc<len(ln): self.lines[self.cl]=ln[:self.cc]+ln[self.cc+1:]
        elif self.cl<len(self.lines)-1:
            self.lines[self.cl]=ln+self.lines[self.cl+1]; del self.lines[self.cl+1]
        self._draw()

    def newline(self):
        if self._has_sel(): self._delete_sel()
        ln=self.lines[self.cl]; rest=ln[self.cc:]; indent=""
        for ch in ln:
            if ch in(" ","	"): indent+=" "
            else: break
        if ln.rstrip().endswith(":"): indent+="    "
        self.lines[self.cl]=ln[:self.cc]; self.cl+=1
        self.lines.insert(self.cl,indent+rest); self.cc=len(indent); self._draw()

    def select_all(self):
        self.sel_all=True; self.sel_start=None; self._draw()
        self.set_status("Ctrl+C=copy  Ctrl+X=cut  type=replace",CC)

    def deselect(self):
        self.sel_all=False; self.sel_start=None; self._draw()

    def copy(self):
        if self._has_sel():
            clipboard_copy(self._sel_text()); self.set_status("Copied!",CC)
        else:
            clipboard_copy(self.lines[self.cl]); self.set_status("Line copied",CC)

    def cut(self):
        if self._has_sel():
            clipboard_copy(self._sel_text()); self._delete_sel()
            self._draw(); self.set_status("Cut",CA)
        else:
            clipboard_copy(self.lines[self.cl]); self.lines[self.cl]=""
            self.cc=0; self._draw(); self.set_status("Line cut",CA)

    def paste(self):
        txt=clipboard_get()
        if not txt: return
        if self._has_sel(): self._delete_sel()
        txt="".join(c for c in txt if c=="\n" or c=="\t" or (ord(c)>=32 and ord(c)<0xFFF0))
        txt=txt.replace("\r\n","\n").replace("\r","\n")
        parts=txt.split("\n")
        for i,part in enumerate(parts):
            if i==0:
                ln=self.lines[self.cl]
                self.lines[self.cl]=ln[:self.cc]+part+ln[self.cc:]
                self.cc+=len(part)
            else:
                rest=self.lines[self.cl][self.cc:]
                self.lines[self.cl]=self.lines[self.cl][:self.cc]
                self.cl+=1; self.lines.insert(self.cl,part+rest); self.cc=len(part)
        self.sel_start=None; self.sel_all=False
        self._draw(); self.set_status("Pasted!",CR)


class ExplanationPanel(VGroup):
    W=3.80; H=PH; LH=0.300
    TITLE_H  = 0.36
    TXT_H    = 2.80
    DGM_H    = 1.70
    MODEBAR_H= 0.28
    PAD      = 0.06

    def __init__(self,**kw):
        super().__init__(**kw)
        self.MAX_LINES = int(self.TXT_H / self.LH)
        self._all_lines = []
        self._scroll    = 0

        top = self.H/2
        self._y_title   =  top - self.TITLE_H/2
        self._y_txt_top =  top - self.TITLE_H - self.PAD
        self._y_div     =  self._y_txt_top - self.TXT_H - self.PAD
        self._y_dgm_top =  self._y_div - self.PAD
        self._y_mode    = -top + self.MODEBAR_H/2 + self.PAD

        self.bg=box(self.W,self.H,fill="#050e1c",stroke=CC,sw=1.2)

        tb=RoundedRectangle(width=self.W,height=self.TITLE_H,corner_radius=0.09,
            fill_color="#0a1e38",fill_opacity=1,stroke_width=0)
        tb.align_to(self.bg,UP)
        hdr=txh("EXPLANATION",11,CC,bold=True); hdr.move_to(tb)

        self.div=Line(LEFT*(self.W/2-0.12), RIGHT*(self.W/2-0.12),
                      stroke_color="#1a3050", stroke_width=0.8)
        self.div.set_y(self._y_div)

        self.dgm_bg=RoundedRectangle(
            width=self.W-0.18, height=self.DGM_H,
            corner_radius=0.08,
            fill_color="#030810",fill_opacity=1,
            stroke_color="#0d1e30",stroke_width=0.6)
        self.dgm_bg.set_y(self._y_dgm_top - self.DGM_H/2)

        self.sc_bg=Rectangle(width=0.04, height=self.TXT_H,
            fill_color=CDIM,fill_opacity=0.30,stroke_width=0)
        self.sc_bg.align_to(self.bg,RIGHT).shift(LEFT*0.05)
        self.sc_bg.set_y(self._y_txt_top - self.TXT_H/2)
        self.sc_bar=Rectangle(width=0.04,height=0.30,
            fill_color=CC,fill_opacity=0.55,stroke_width=0)
        self.sc_bar.align_to(self.sc_bg,UP).align_to(self.sc_bg,RIGHT)

        self.txt_grp = VGroup()
        self.dgm_grp = VGroup()
        self.add(self.bg, tb, hdr,
                 self.div, self.dgm_bg,
                 self.sc_bg, self.sc_bar,
                 self.txt_grp, self.dgm_grp)

    def _redraw_text(self):
        for item in list(self.txt_grp.submobjects):
            self.txt_grp.remove(item)
        self.remove(self.txt_grp)
        self.txt_grp = VGroup()
        vis = self._all_lines[self._scroll:self._scroll+self.MAX_LINES]
        cx  = self.bg.get_center()
        y0  = cx[1] + self._y_txt_top - self.LH*0.5
        for i,(txt,col) in enumerate(vis):
            t = tx(txt,11,col)
            t.align_to(self.bg.get_left()+RIGHT*0.14, LEFT)
            t.set_y(y0 - i*self.LH)
            self.txt_grp.add(t)
        self.add(self.txt_grp)
        total=len(self._all_lines)
        if total>self.MAX_LINES:
            frac_top = self._scroll/total
            frac_h   = self.MAX_LINES/total
            bar_h    = max(0.14, self.TXT_H*frac_h)
            bar_y    = self.sc_bg.get_top()[1] - self.TXT_H*frac_top - bar_h/2
            self.sc_bar.set_height(bar_h,stretch=True)
            self.sc_bar.set_y(bar_y)
            self.sc_bar.align_to(self.sc_bg,RIGHT)
            self.sc_bar.set_fill(opacity=0.75)
        else:
            self.sc_bar.set_fill(opacity=0)

    def set_content(self, lines_data):
        self._all_lines=list(lines_data)
        self._scroll = 0
        self._redraw_text()

    def scroll_up(self):
        if self._scroll>0: self._scroll-=1; self._redraw_text()

    def scroll_down(self):
        total=len(self._all_lines)
        if self._scroll+self.MAX_LINES<total: self._scroll+=1; self._redraw_text()

    def draw_diagram(self, step, fn_name, push_map):
        self.remove(self.dgm_grp); self.dgm_grp=VGroup(); self.add(self.dgm_grp)

        bg_c   = self.bg.get_center()
        cx     = bg_c[0]
        dz_top = bg_c[1] + self._y_dgm_top
        dz_h   = self.DGM_H
        dz_ctr = dz_top - dz_h/2

        node_r = min(0.26, dz_h * 0.14)
        top_y  = dz_ctr + dz_h*0.30
        bot_y  = dz_ctr - dz_h*0.30

        act  = step["act"]
        nv   = step["n"]
        base = step["base"]
        depth= step["depth"]
        pid  = step["parent"]
        res  = step.get("result")

        col_cur = CB_C if base else (CR if act=="pop" else CA)

        def _snode(y, label, col, sub=None):
            c = Circle(radius=node_r, fill_color=col, fill_opacity=0.20,
                       stroke_color=col, stroke_width=2.2)
            c.move_to([cx, y, 0])
            l = tx(label, 9, col, bold=True); l.move_to(c)
            g = VGroup(c, l)
            if sub:
                s = tx(sub, 8, col); s.next_to(l, DOWN, buff=0.02); g.add(s)
            return g

        def _sarr(y1, y2, col, lbl):
            s_pt = np.array([cx, y1, 0])
            e_pt = np.array([cx, y2, 0])
            line = Line(s_pt, e_pt, stroke_color=col, stroke_width=1.8)
            tip  = Triangle(fill_color=col,fill_opacity=1,stroke_width=0)
            tip.set_height(0.13); tip.move_to(e_pt); tip.rotate(-PI/2)
            lb   = tx(lbl, 9, col); lb.next_to(line, RIGHT, buff=0.09)
            return VGroup(line, tip, lb)

        if act == "push":
            if pid >= 0 and pid in push_map:
                pn = push_map[pid]["n"]
                self.dgm_grp.add(_snode(top_y, f"{fn_name}({pn})", CC))
            else:
                lbl = tx("entry point", 9, CSUB); lbl.move_to([cx, top_y, 0])
                self.dgm_grp.add(lbl)
            self.dgm_grp.add(_sarr(top_y - node_r - 0.04,
                                   bot_y + node_r + 0.04,
                                   CA, f"call  n={nv}"))
            sub_lbl = "BASE CASE" if base else f"depth {depth}"
            self.dgm_grp.add(_snode(bot_y, f"{fn_name}({nv})", col_cur, sub=sub_lbl))
        elif act == "pop":
            ret_lbl = f"={res}" if res is not None else ""
            self.dgm_grp.add(_snode(top_y, f"{fn_name}({nv})", CR, sub=ret_lbl))
            arr_lbl = f"return  {res}" if res is not None else "return"
            self.dgm_grp.add(_sarr(top_y - node_r - 0.04,
                                   bot_y + node_r + 0.04,
                                   CR, arr_lbl))
            if pid >= 0 and pid in push_map:
                pn = push_map[pid]["n"]
                self.dgm_grp.add(_snode(bot_y, f"{fn_name}({pn})", CC))
            else:
                done = txh("RESULT: "+str(res), 10, CF, bold=True)
                done.move_to([cx, bot_y, 0])
                self.dgm_grp.add(done)

    def set_mode(self,mode_str,col):
        pass

    def clear_content(self):
        self._all_lines=[]; self._scroll=0; self._redraw_text()
        self.remove(self.dgm_grp); self.dgm_grp=VGroup(); self.add(self.dgm_grp)


class CallTree(VGroup):
    R_NORM=0.35; R_BASE=0.42

    def __init__(self,fn_name,steps,cx,**kw):
        super().__init__(**kw)
        self.fn=fn_name; self.cx=cx
        n_push  = sum(1 for s in steps if s["act"]=="push")
        n_levels= max((s["depth"] for s in steps if s["act"]=="push"), default=0)+1
        self.fast = n_push > 20

        self.R_NORM  = 0.35
        self.R_BASE  = 0.42
        self._lbl_sz = 14

        tree_top = PY + PH/2 - 0.55
        avail_h  = PH - 0.85
        lvl_h    = min(0.88, avail_h / max(n_levels,1))
        lvl_h    = max(0.68, lvl_h)
        self.lvl_h = lvl_h

        self.pos = tree_layout_zz(steps, cx, tree_top, lvl_h, avail_h=avail_h)
        self.info={s["nid"]:s for s in steps if s["act"]=="push"}

        self.node_mob: dict = {}
        self.edge_mob: dict = {}
        self.ret_mob:  dict = {}

        self.tree_grp = VGroup()
        self.add(self.tree_grp)

        self._hover_nid = None

    def _r(self,nid):
        return self.R_BASE if self.info[nid]["base"] else self.R_NORM

    def push(self, scene, nid):
        info = self.info[nid]
        fast = self.fast

        pid = info["parent"]
        r   = self._r(nid)

        node = DraggableNode(
            self.fn, info["n"],
            radius=r,
            base=info["base"],
            lbl_sz=self._lbl_sz
        )
        node.move_to(self.pos[nid])
        self.node_mob[nid] = node
        self.tree_grp.add(node)

        if pid >= 0 and pid in self.node_mob:
            ecol = COLS[info["depth"] % len(COLS)]
            p_node = self.node_mob[pid]
            arr = DynamicArrow(
                p_node, node,
                color=ecol, sw=1.8, tip_size=0.11,
                start_r=self._r(pid)+0.03, end_r=r+0.03,
                ret_arrow=False
            )
            p_node.arrows.append(arr)
            node.arrows.append(arr)
            self.edge_mob[(pid, nid)] = arr
            self.tree_grp.add(arr)
            self.tree_grp.submobjects.remove(arr)
            self.tree_grp.submobjects.insert(0, arr)

        if not fast:
            scene.play(FadeIn(node), run_time=T(0.18, fast))
            if info["base"]:
                diamond = Square(side_length=0.18, fill_color=CB_C,
                                 fill_opacity=0.90, stroke_width=0)
                diamond.rotate(PI/4)
                diamond.move_to(self.pos[nid] + UP*(self.R_BASE+0.22))
                scene.play(FadeIn(diamond), run_time=T(0.12))
                scene.play(diamond.animate.shift(UP*0.25).set_opacity(0),
                           run_time=T(0.22))
                self.remove(diamond)
            ring = Circle(radius=r+0.10, fill_opacity=0,
                          stroke_color=CA, stroke_width=1.2)
            ring.move_to(self.pos[nid])
            scene.play(ShowCreation(ring), run_time=T(0.10))
            scene.play(ring.animate.scale(1.5).set_stroke(opacity=0),
                       run_time=T(0.18))
            self.remove(ring)

    def pop(self, scene, nid, result=None):
        if nid not in self.node_mob: return
        node = self.node_mob[nid]
        info = self.info[nid]
        fast = self.fast
        pid  = info["parent"]
        r    = self._r(nid)

        node.set_state("returned")
        if result is not None:
            node.show_result(result)

        if not fast:
            scene.play(node.animate.scale(1.06), run_time=T(0.08))
            scene.play(node.animate.scale(1/1.06), run_time=T(0.06))

            if pid >= 0 and pid in self.node_mob:
                p_node = self.node_mob[pid]
                ret_arr = DynamicArrow(
                    node, p_node,
                    color=CR, sw=1.8, tip_size=0.11,
                    start_r=r+0.03, end_r=self._r(pid)+0.03,
                    ret_arrow=True
                )
                node.arrows.append(ret_arr)
                p_node.arrows.append(ret_arr)
                self.ret_mob[(pid, nid)] = ret_arr
                self.tree_grp.add(ret_arr)
                self.tree_grp.submobjects.remove(ret_arr)
                self.tree_grp.submobjects.insert(0, ret_arr)

                scene.play(ShowCreation(ret_arr), run_time=T(0.18))

                if result is not None:
                    mid = (node.get_center() + p_node.get_center()) / 2
                    val_bg = Circle(radius=0.20, fill_color=CR,
                                    fill_opacity=0.30, stroke_color=CR,
                                    stroke_width=1.2)
                    val_tx = tx(str(result), 10, CR, bold=True)
                    val_grp = VGroup(val_bg, val_tx)
                    val_grp.move_to(mid)
                    self.add(val_grp)
                    scene.play(FadeIn(val_grp), run_time=T(0.08))
                    target = p_node.get_center() + DOWN*(self._r(pid)+0.10)
                    scene.play(
                        val_grp.animate.move_to(target).set_opacity(0),
                        run_time=T(0.26)
                    )
                    self.remove(val_grp)

                scene.play(
                    ret_arr.animate.set_opacity_level(0.28),
                    run_time=T(0.10)
                )

            elif result is not None:
                bub_bg = Circle(radius=0.26, fill_color=CF,
                                fill_opacity=0.28, stroke_color=CF, stroke_width=1.4)
                bub_tx = tx(str(result), 13, CF, bold=True)
                bub = VGroup(bub_bg, bub_tx)
                bub.move_to(node.get_center() + UP*(r+0.22))
                self.add(bub)
                scene.play(FadeIn(bub), run_time=T(0.10))
                scene.play(bub.animate.shift(UP*0.60).set_opacity(0),
                           run_time=T(0.36))
                self.remove(bub)

        else:
            if result is not None and pid >= 0 and pid in self.node_mob:
                p_grp = self.node_mob[pid]
                rl = tx(f"←{result}", max(10, self._lbl_sz-2), CR)
                rl.next_to(p_grp, RIGHT, buff=0.04)
                self.tree_grp.add(rl)
                self._pending_labels = getattr(self, '_pending_labels', [])
                self._pending_labels.append(rl)

            self.tree_grp.remove(node)
            del self.node_mob[nid]
            for key in [(pid, nid)]:
                if key in self.edge_mob:
                    self.tree_grp.remove(self.edge_mob[key])
                    del self.edge_mob[key]

            if hasattr(self, '_pending_labels') and len(self._pending_labels) > 6:
                old_lbl = self._pending_labels.pop(0)
                try: self.tree_grp.remove(old_lbl)
                except: pass

    def hit_node(self, pt):
        for nid, node in reversed(list(self.node_mob.items())):
            c  = node.get_center()
            r  = node.radius + 0.08
            if np.linalg.norm(pt - c) <= r:
                return nid
        return None

    def drag_node(self, nid, new_pos):
        node = self.node_mob.get(nid)
        if node is None: return
        node.move_to(new_pos)

    def set_node_hover(self, nid, v):
        node = self.node_mob.get(nid)
        if node: node.set_hover(v)

    def set_node_dragging(self, nid, v):
        node = self.node_mob.get(nid)
        if node: node.set_dragging(v)

    def highlight_step(self, nid):
        for n2, nd in self.node_mob.items():
            if nd.state in ("pending", "active"):
                nd.set_state("active" if n2 == nid else "pending")


class NCounter(VGroup):
    def __init__(self,n,**kw):
        super().__init__(**kw)
        self.val=n
        self._bg=RoundedRectangle(width=1.00,height=0.48,corner_radius=0.11,
            fill_color="#0d1f35",fill_opacity=1,stroke_color=CC,stroke_width=1.6)
        self._num=txh(str(n),20,CC,bold=True); self._num.move_to(self._bg)
        self.add(self._bg,self._num)

    def update_val(self,scene,v,color=CA):
        new=txh(str(v),20,color,bold=True); new.move_to(self._bg)
        scene.play(Transform(self._num,new),run_time=T(0.12)); self.val=v


class ModeIndicator(VGroup):
    def __init__(self,**kw):
        super().__init__(**kw)
        self.bg=RoundedRectangle(width=2.20,height=0.36,corner_radius=0.09,
            fill_color="#0a1e38",fill_opacity=1,stroke_color=CDIM,stroke_width=0.8)
        self.lbl=txh("STEP  mode",10,CC,bold=True); self.lbl.move_to(self.bg)
        self.add(self.bg,self.lbl)

    def set(self,label,color):
        new=txh(label,10,color,bold=True); new.move_to(self.bg); self.lbl.become(new)
        self.bg.set_stroke(color=color,width=1.4)


class FullScene(Scene):

    def setup(self):
        self.camera.background_color=BG
        self._n=N; self._code=DEFAULT_CODE
        self._spc=False; self._enter=False; self._restart=False
        self._nc=False; self._do_run=False
        self._editor=None; self._n_mob=None; self._mode_ind=None; self._exp_panel=None
        self._panels=[]; self._drag_mob=None; self._drag_off=np.zeros(3)
        self._ed_on=False; self._n_on=False; self._n_buf=""
        self._auto=False

        self._node_drag_nid  = None
        self._node_drag_off  = np.zeros(3)
        self._call_tree: CallTree | None = None
        self._hover_nid = None

        # ── Help Panel state ──
        self._help_panel: HelpPanel | None = None
        self._help_visible: bool = False
        self._toggle_help: bool = False       # flag set by key handler

    # ── toggle helper ──────────────────────────────────────────────────────
    def _show_help(self):
        if self._help_panel is None:
            self._help_panel = HelpPanel()
            self.add(self._help_panel)
        else:
            self.add(self._help_panel)
        self._help_visible = True

    def _hide_help(self):
        if self._help_panel is not None:
            try: self.remove(self._help_panel)
            except Exception: pass
        self._help_visible = False

    def _do_toggle_help(self):
        if self._help_visible:
            self._hide_help()
        else:
            self._show_help()

    # ── keyboard ───────────────────────────────────────────────────────────
    def on_key_press(self,symbol,modifiers):
        from pyglet.window import key as K
        CTRL=bool(modifiers&K.MOD_CTRL)
        SHIFT=bool(modifiers&(K.MOD_SHIFT|K.MOD_CAPSLOCK))

        # H key — toggle help (works everywhere, including editor mode)
        if symbol == K.H and not CTRL and not self._ed_on:
            self._toggle_help = True
            return

        if self._ed_on and self._editor is not None:
            ed=self._editor
            if CTRL:
                if symbol in(K.RETURN,K.NUM_ENTER):
                    self._code=ed.get_code(); self._do_run=True; self._spc=True
                    self._ed_on=False; ed.set_active(False)
                elif symbol==K.A: ed.select_all()
                elif symbol==K.C: ed.copy()
                elif symbol==K.X: ed.cut()
                elif symbol==K.V: ed.paste()
                return
            if   symbol==K.ESCAPE:    self._ed_on=False; ed.set_active(False)
            elif symbol==K.RETURN:
                if ed.sel_all: ed.deselect()
                ed.newline()
            elif symbol==K.BACKSPACE: ed.backspace()
            elif symbol==K.DELETE: ed.delete_fwd()
            elif symbol==K.TAB: ed.insert("    ")
            elif symbol==K.UP:
                if SHIFT: ed.sel_move(ed._mv_up)
                else: ed.deselect(); ed.move_up()
            elif symbol==K.DOWN:
                if SHIFT: ed.sel_move(ed._mv_down)
                else: ed.deselect(); ed.move_down()
            elif symbol==K.LEFT:
                if SHIFT: ed.sel_move(ed._mv_left)
                else: ed.deselect(); ed.move_left()
            elif symbol==K.RIGHT:
                if SHIFT: ed.sel_move(ed._mv_right)
                else: ed.deselect(); ed.move_right()
            elif symbol==K.HOME:
                if SHIFT: ed.sel_move(ed._mv_home)
                else: ed.deselect(); ed.move_home()
            elif symbol==K.END:
                if SHIFT: ed.sel_move(ed._mv_end)
                else: ed.deselect(); ed.move_end()
            elif symbol==K.F1: ed.load(TMPL[0]); ed.set_status("recsum",CC)
            elif symbol==K.F2: ed.load(TMPL[1]); ed.set_status("factorial",CC)
            elif symbol==K.F3: ed.load(TMPL[2]); ed.set_status("power",CC)
            elif symbol==K.F4: ed.load(TMPL[3]); ed.set_status("fib",CC)
            else:
                try:
                    ch=chr(symbol)
                    if ch.isprintable() and len(ch)==1:
                        SH={"1":"!","2":"@","3":"#","4":"$","5":"%",
                            "6":"^","7":"&","8":"*","9":"(","0":")",
                            "-":"_","=":"+","[":"{","]":"}","\\":"|",
                            ";":":","'":'"',",":"<",".":">","/":"?","`":"~"}
                        if SHIFT: ch=ch.upper() if ch.isalpha() else SH.get(ch,ch)
                        if ed.sel_all: ed.deselect()
                        ed.insert(ch)
                except(ValueError,OverflowError): pass
            return

        if self._n_on:
            DIG={K._0:"0",K._1:"1",K._2:"2",K._3:"3",K._4:"4",
                 K._5:"5",K._6:"6",K._7:"7",K._8:"8",K._9:"9",
                 K.NUM_0:"0",K.NUM_1:"1",K.NUM_2:"2",K.NUM_3:"3",
                 K.NUM_4:"4",K.NUM_5:"5",K.NUM_6:"6",K.NUM_7:"7",
                 K.NUM_8:"8",K.NUM_9:"9"}
            if symbol in DIG:
                b=self._n_buf+DIG[symbol]
                if len(b)<=3: self._n_buf=b; self._rnf()
            elif symbol==K.BACKSPACE: self._n_buf=self._n_buf[:-1]; self._rnf()
            elif symbol in(K.RETURN,K.NUM_ENTER):
                if self._n_buf:
                    v=int(self._n_buf)
                    if v>=1 and v!=self._n: self._n=v; self._nc=True; self._spc=True
                self._n_on=False; self._rnf()
            elif symbol==K.ESCAPE: self._n_on=False; self._rnf()
            return

        super().on_key_press(symbol,modifiers)
        if symbol==K.SPACE:                   self._spc=True
        elif symbol in(K.RETURN,K.NUM_ENTER): self._enter=True; self._spc=True
        elif symbol==K.R:                     self._restart=True; self._spc=True

    def _rnf(self):
        if self._n_mob is None: return
        txt=(self._n_buf+"_") if self._n_on else str(self._n)
        c=CA if self._n_on else CC
        new=tx(txt,15,c,bold=True); new.move_to(self._n_mob); self._n_mob.become(new)

    def _tree_zone(self):
        return self._call_tree is not None and not self._ed_on

    def on_mouse_press(self,point,button,mods):
        super().on_mouse_press(point,button,mods)
        pt=np.array(point)
        SHIFT=bool(mods&1)

        # Close help panel if user clicks outside it
        if self._help_visible and self._help_panel is not None:
            hp = self._help_panel
            c  = hp.get_center()
            hw = hp.get_width()/2 + 0.10
            hh = hp.get_height()/2 + 0.10
            if not (abs(pt[0]-c[0]) < hw and abs(pt[1]-c[1]) < hh):
                self._hide_help()
                return

        def in_box(mob, pad=0):
            c=mob.get_center()
            return (abs(pt[0]-c[0]) < mob.get_width()/2+pad and
                    abs(pt[1]-c[1]) < mob.get_height()/2+pad)

        def in_text_area(ed):
            tl=ed.bg.get_top()[1]-0.44
            bl=ed.bg.get_bottom()[1]+0.32
            lx=ed.bg.get_left()[0]+0.08
            rx=ed.bg.get_right()[0]-0.08
            return lx<pt[0]<rx and bl<pt[1]<tl

        if self._call_tree is not None and not self._ed_on:
            nid = self._call_tree.hit_node(pt)
            if nid is not None:
                self._node_drag_nid = nid
                self._node_drag_off = self._call_tree.node_mob[nid].get_center() - pt
                self._call_tree.set_node_dragging(nid, True)
                self._n_on = False; self._rnf()
                self._ed_on = False
                if self._editor: self._editor.set_active(False)
                return

        ed=self._editor
        if ed is not None and in_box(ed):
            if in_text_area(ed):
                if not self._ed_on:
                    self._ed_on=True; ed.set_active(True)
                    ed.click_to_pos(pt, extend_sel=False)
                else:
                    ed.click_to_pos(pt, extend_sel=SHIFT)
                self._n_on=False; self._rnf()
                return
            else:
                if not self._ed_on:
                    self._ed_on=True; ed.set_active(True)
                self._n_on=False; self._rnf()
                return

        if self._n_mob is not None and in_box(self._n_mob, pad=0.38):
            self._n_on=True; self._n_buf=""
            self._ed_on=False
            if ed: ed.set_active(False)
            self._rnf(); return

        if self._ed_on:
            self._ed_on=False
            if ed: ed.set_active(False)
        if self._n_on:
            self._n_on=False; self._rnf()

        for mob in self._panels:
            if in_box(mob):
                self._drag_mob=mob; self._drag_off=mob.get_center()-pt; break

    def on_mouse_drag(self,point,d_point,buttons,modifiers):
        pt=np.array(point)

        if self._node_drag_nid is not None and self._call_tree is not None:
            new_pos = pt + self._node_drag_off
            self._call_tree.drag_node(self._node_drag_nid, new_pos)
            return

        if self._drag_mob is not None:
            self._drag_mob.move_to(pt+self._drag_off)
        elif self._ed_on and self._editor is not None:
            ed=self._editor
            lx=ed.bg.get_left()[0]+0.08; rx=ed.bg.get_right()[0]-0.08
            tl=ed.bg.get_top()[1]-0.44;  bl=ed.bg.get_bottom()[1]+0.32
            if lx<pt[0]<rx and bl<pt[1]<tl:
                ed.click_to_pos(pt, extend_sel=True)
        else:
            super().on_mouse_drag(point,d_point,buttons,modifiers)

    def on_mouse_release(self,point,button,mods):
        super().on_mouse_release(point,button,mods)
        if self._node_drag_nid is not None and self._call_tree is not None:
            self._call_tree.set_node_dragging(self._node_drag_nid, False)
            self._node_drag_nid = None
        self._drag_mob=None

    def on_mouse_move(self, point, d_point):
        super().on_mouse_move(point, d_point)
        pt = np.array(point)
        if self._call_tree is None: return
        nid = self._call_tree.hit_node(pt)
        if nid != self._hover_nid:
            if self._hover_nid is not None:
                self._call_tree.set_node_hover(self._hover_nid, False)
            self._hover_nid = nid
            if nid is not None:
                self._call_tree.set_node_hover(nid, True)

    def on_mouse_scroll(self,point,offset):
        pt=np.array(point)
        if hasattr(self,'_exp_panel') and self._exp_panel is not None:
            ep=self._exp_panel
            c=ep.get_center(); hw=ep.get_width()/2; hh=ep.get_height()/2
            if abs(pt[0]-c[0])<hw and abs(pt[1]-c[1])<hh:
                if offset[1]>0: ep.scroll_up()
                else:           ep.scroll_down()
                return
        super().on_mouse_scroll(point,offset)

    # ── stop condition also checks help-toggle flag ────────────────────────
    def _pause_step(self):
        self._spc=False; self._enter=False

        def _cond():
            if self._toggle_help:
                self._toggle_help = False
                self._do_toggle_help()
            return self._spc or self._enter

        self.wait(600, stop_condition=_cond)

    def _should_abort(self):
        return self._do_run or self._restart or self._nc

    def construct(self):
        while True:
            self._spc=self._restart=self._nc=self._do_run=self._enter=False
            self._panels=[]; self._drag_mob=None
            self._ed_on=False; self._n_on=False; self._auto=False
            self._node_drag_nid=None; self._hover_nid=None
            self._call_tree=None
            # keep help panel state across restarts
            self._show(self._n,self._code); self.clear()

    def _show(self,n,code):
        fn_name,steps,final,error=trace(code,n)
        if not fn_name: fn_name="func"

        src_lines=code.split("\n")
        rec_lines=[i for i,l in enumerate(src_lines)
                   if "return" in l and fn_name in l and fn_name+"(" in l]
        base_lines=[i for i,l in enumerate(src_lines)
                    if "return" in l and fn_name+"(" not in l]
        total=len(steps)

        top_bg=Rectangle(width=16,height=0.72,
            fill_color="#04091a",fill_opacity=1,stroke_width=0)
        top_bg.move_to([0,3.36,0])
        title=txh("RECURSION ",35,CC,bold=True)
        title.move_to([-1.20,3.40,0])
        tl_dots=VGroup(*[Dot(radius=0.065,color=c)
            for c in["#ef5350","#080501","#69f0ae"]]
            ).arrange(RIGHT,buff=0.09)
        tl_dots.next_to(title,LEFT,buff=0.22)
        sub=tx(f"{fn_name}({n})",11,CSUB)
        sub.next_to(title,DOWN,buff=0.03).align_to(title,LEFT)
        sep=Line(LEFT*7.5,RIGHT*7.5,stroke_color=CC,stroke_width=0.4)
        sep.set_stroke(opacity=0.10); sep.move_to([0,3.18,0])

        mode_ind=ModeIndicator(); mode_ind.move_to([-5.50,3.38,0])
        self._mode_ind=mode_ind

        nc=NCounter(n); nc.move_to([6.60,3.38,0])
        self._n_mob=nc._num
        nc_lbl=txh("n =",11,CSUB)
        nc_lbl.next_to(nc,LEFT,buff=0.12)
        sc=tx(f"0/{total}",9,CSUB)
        sc.next_to(nc_lbl,DOWN,buff=0.04).align_to(nc_lbl,LEFT)

        # ── H hint badge ─────────────────────────────────────────────────
        h_badge = RoundedRectangle(width=0.90, height=0.28, corner_radius=0.08,
            fill_color="#081628", fill_opacity=1,
            stroke_color=CF, stroke_width=0.9)
        h_badge.move_to([5.60, 3.38, 0])
        h_lbl = txh("H = help", 9, CF, bold=True)
        h_lbl.move_to(h_badge)
        h_grp = VGroup(h_badge, h_lbl)

        def leg(col,lbl,x):
            c=Circle(radius=0.09,fill_color=col,fill_opacity=0.55,
                     stroke_color=col,stroke_width=1.2)
            t=tx(lbl,11,CSUB)
            return VGroup(c,t).arrange(RIGHT,buff=0.07).move_to([x,3.38,0])
        lg=VGroup(leg(CC,"call",0.80),leg(CA,"active",1.52),
                  leg(CR,"return",2.28),leg(CB_C,"base",3.00))

        ed=CodeEditor(code);    ed.move_to([EX,PY,0])
        ct=CallTree(fn_name,steps,TCX)
        self._call_tree = ct

        exp=ExplanationPanel(); exp.move_to([EXP_X,PY,0])
        self._editor=ed; self._exp_panel=exp; self._panels=[]

        self.add(top_bg)
        self.play(Write(title),run_time=T(0.22))
        self.play(FadeIn(tl_dots),FadeIn(sub),FadeIn(sep),run_time=T(0.12))
        self.play(FadeIn(mode_ind),FadeIn(nc_lbl),FadeIn(nc),
                  FadeIn(sc),run_time=T(0.12))
        self.play(FadeIn(lg),FadeIn(h_grp),run_time=T(0.10))

        self.add(ed,ct,exp)

        if error:
            em=tx(f"Error: {error[:55]}",12,CERR); em.move_to([TCX,0,0])
            ed.set_error(error[:40])
            self.play(FadeIn(em),run_time=T(0.16))
            self._pause_step(); self.clear(); return

        ed.set_fn(fn_name)
        init_lines = [
            (f"Function : {fn_name}(n)", CC),
            (f"Input    : n = {n}",      CTXT),
            ("", CSUB),
            ("SPACE  = next step",  CC),
            ("Enter  = auto-run",   CA),
            ("R      = restart",    CR),
            ("H      = shortcuts",  CF),
            ("C+Enter = edit & run",CSUB),
            ("", CSUB),
            ("DRAG nodes  to rearrange", CHOVER),
            ("HOVER node  to highlight", CHOVER),
        ]
        exp.set_content(init_lines)
        _pm = {s["nid"]:s for s in steps if s["act"]=="push"}
        if steps: exp.draw_diagram(steps[0], fn_name, _pm)
        self._pause_step()
        if self._should_abort(): self.clear(); return

        if self._enter:
            self._auto=True
            mode_ind.set("AUTO  mode",CA)
            exp.set_mode("Auto mode - running all",CA)

        push_map = {s["nid"]:s for s in steps if s["act"]=="push"}

        for i,s in enumerate(steps):
            if self._should_abort(): self.clear(); return
            fin=(i==len(steps)-1)
            nid=s["nid"]; base=s["base"]; nv=s["n"]; depth=s["depth"]

            nsc=tx(f"{i+1}/{total}",9,CC); nsc.move_to(sc)
            self.play(Transform(sc,nsc),run_time=0.05)
            new_sub=tx(f"{fn_name}({n})   depth {depth}  |  step {i+1}/{total}",
                       10,CSUB); new_sub.move_to(sub)
            self.play(Transform(sub,new_sub),run_time=0.05)

            exp_lines=make_explanation(fn_name,s,steps,src_lines)
            exp.set_content(exp_lines)
            exp.draw_diagram(s, fn_name, push_map)

            if s["act"]=="push":
                nc.update_val(self,n,CB_C if base else COLS[depth%len(COLS)])
                hl_idx=(base_lines[0] if (base and base_lines) else
                        (rec_lines[0] if rec_lines else -1))
                ed.highlight(hl_idx)
                ct.push(self,nid)

            elif s["act"]=="pop":
                res=s.get("result")
                hl_idx=(base_lines[0] if (base and base_lines) else
                        (rec_lines[0] if rec_lines else -1))
                ed.highlight(hl_idx)
                ct.pop(self,nid,res)

            if fin:
                ed.highlight(-1)
            else:
                # process help-toggle during auto-run wait too
                if self._auto:
                    def _auto_cond():
                        if self._toggle_help:
                            self._toggle_help = False
                            self._do_toggle_help()
                        return self._should_abort()
                    self.wait(AUTO_SPEED, stop_condition=_auto_cond)
                else:
                    self._pause_step()
                    if self._should_abort(): self.clear(); return
                    if self._enter and not self._auto:
                        self._auto=True
                        mode_ind.set("AUTO  mode",CA)
                        exp.set_mode("Auto mode - running all",CA)

        ed.highlight(-1)
        if 0 in ct.pos:
            for rad,op in[(0.50,0.7),(0.75,0.4),(1.00,0.2)]:
                glow=Circle(radius=rad,fill_opacity=0,stroke_color=CF,stroke_width=1.5)
                glow.set_stroke(opacity=op); glow.move_to(ct.pos[0])
                self.play(ShowCreation(glow),run_time=T(0.16))
                self.play(glow.animate.scale(1.3).set_stroke(opacity=0),run_time=T(0.20))
                self.remove(glow)

        nc.update_val(self,n,CF)
        mode_ind.set("DONE",CF)

        exp.set_content([
            ("COMPLETE!",CF),
            ("",""),
            (f"{fn_name}({n}) = {final}",CF),
            ("",""),
            ("All calls resolved.",CSUB),
            ("",""),
            ("DRAG nodes freely — arrows adapt!", CHOVER),
            ("H = shortcuts panel",CF),
            ("SPACE / R = restart",CC),
            ("click editor to edit",CSUB),
        ])
        self.wait(T(0.18))
        self._pause_step()

    def _idle(self,fn_name,n,result):
        self._pause_step()