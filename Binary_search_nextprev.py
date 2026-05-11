"""
Binary Search — keyboard-only interactive Manim scene
======================================================

Navigation
----------
  Space / Enter   Auto-play (all steps with animation)
  →               Next step  (one step forward)
  ←               Previous step (one step back)
  R               Reset to defaults
  + / =           Speed up auto-play
  - / _           Slow down auto-play

Editing
-------
  Ctrl+A          Add a value
  Ctrl+D          Delete selected cell (or last)
  Ctrl+T          Set search target
  Delete          Remove selected cell (or last)
  Esc             Cancel input / deselect
  H               Toggle shortcut panel

  Click cell once  → select
  Click again      → edit value
"""

from manimlib import *
import pyglet.window.key as K
from collections import defaultdict

GRAY_COLOR = "#B0B0B0"
SEL_COLOR  = "#f39c12"

DEFAULT_ARR    = [34, 7, 23, 32, 5, 62, 78, 12]
DEFAULT_TARGET = 23
ARRAY_Y        = 0.0

# auto-play delay between steps (seconds) — changed by +/-
AUTO_SPEEDS = [0.4, 0.7, 1.0, 1.5, 2.2]   # index 2 = default
AUTO_DEFAULT_IDX = 2


# ══════════════════════════════════════════════════════════════════════
# Pre-compute every visual state (snapshot)
# Each snapshot is a plain dict — no Manim objects inside.
# ══════════════════════════════════════════════════════════════════════
def _make_color(hex_str):
    return hex_str

def compute_snapshots(data_in, target):
    """
    Returns list of snapshot dicts.

    Keys per snapshot
    -----------------
    data   : list[int]        array values in current order
    fills  : list[str]        hex fill colour per cell ("" = transparent)
    strokes: list[str]        hex stroke colour per cell
    widths : list[float]      stroke width per cell
    low    : int (-1=hidden)
    mid    : int (-1=hidden)
    high   : int (-1=hidden)
    step_n : int              displayed step number
    label  : str              short label shown nowhere (debug only)
    swap   : (i,j)|None       which two cells are physically swapped
                              (used by _go_to_snapshot to play() them)
    """
    data  = data_in[:]
    n     = len(data)
    snaps = []

    def W(i):  return [""] * n if i == -1 else None   # unused

    def snap(data, fills, strokes, widths,
             low, mid, high, step_n, label, swap=None):
        snaps.append(dict(
            data    = data[:],
            fills   = fills[:],
            strokes = strokes[:],
            widths  = widths[:],
            low     = low,
            mid     = mid,
            high    = high,
            step_n  = step_n,
            label   = label,
            swap    = swap,
        ))

    def neutral_style(n):
        return ([""] * n,
                [WHITE] * n,
                [2.0]   * n)

    # ── idle (step 0) ─────────────────────────────────────────────────
    f, s, w = neutral_style(n)
    snap(data, f, s, w, -1, -1, -1, 0, "idle")

    # ── bubble sort phase ─────────────────────────────────────────────
    # We record a snapshot BEFORE and AFTER each swap so the physical
    # animation can slide two cells.

    f, s, w = neutral_style(n)
    snap(data, f, s, w, -1, -1, -1, 0, "sort-start")

    swapped = True
    while swapped:
        swapped = False
        for j in range(len(data) - 1):
            if data[j] > data[j + 1]:
                swapped = True
                # highlight the pair being compared
                f2, s2, w2 = neutral_style(n)
                f2[j] = f2[j+1] = "#1a5276"
                snap(data, f2, s2, w2, -1, -1, -1, 0,
                     f"compare {data[j]},{data[j+1]}")

                # record swap — swap=(...) tells _go_to_snapshot to animate
                data[j], data[j+1] = data[j+1], data[j]
                f3, s3, w3 = neutral_style(n)
                snap(data, f3, s3, w3, -1, -1, -1, 0,
                     f"swapped", swap=(j, j+1))

    # after sort: fixed index labels, neutral colours
    sorted_data = data[:]
    f, s, w = neutral_style(n)
    snap(data, f, s, w, -1, -1, -1, 0, "sort-done")

    # ── binary search phase ───────────────────────────────────────────
    left, right = 0, n - 1
    fills  = [""] * n
    found  = False
    step_n = 0

    while left <= right:
        step_n += 1
        mid_i = (left + right) // 2
        val   = data[mid_i]

        # show pointers + highlight mid
        f2 = fills[:]
        f2[mid_i] = "#d4ac0d"
        snap(data, f2, [WHITE]*n, [2.0]*n,
             left, mid_i, right, step_n,
             f"step{step_n}-check")

        if val == target:
            f3 = f2[:]
            f3[mid_i] = "#1e8449"
            snap(data, f3, [WHITE]*n, [2.0]*n,
                 left, mid_i, right, step_n,
                 f"step{step_n}-found")
            found = True
            break
        elif val < target:
            for k in range(left, mid_i + 1):
                fills[k] = "#566573"
            f4 = fills[:]
            snap(data, f4, [WHITE]*n, [2.0]*n,
                 left, mid_i, right, step_n,
                 f"step{step_n}-elimleft")
            left = mid_i + 1
        else:
            for k in range(mid_i, right + 1):
                fills[k] = "#566573"
            f4 = fills[:]
            snap(data, f4, [WHITE]*n, [2.0]*n,
                 left, mid_i, right, step_n,
                 f"step{step_n}-elimright")
            right = mid_i - 1

    if not found:
        f_end = fills[:]
        snap(data, f_end, [WHITE]*n, [2.0]*n,
             -1, -1, -1, step_n, "not-found")

    return snaps


# ══════════════════════════════════════════════════════════════════════
class BinarySearch(Scene):
# ══════════════════════════════════════════════════════════════════════

    # ── geometry ──────────────────────────────────────────────────────
    def _spacing(self, n):
        return min(1.20, 11.0 / max(n, 1))

    def _cell_center(self, i, n):
        sp = self._spacing(n)
        return np.array([i * sp - sp * (n - 1) / 2, ARRAY_Y, 0])

    def _sq_size(self, n):
        return min(1.05, self._spacing(n) * 0.86)

    # ── hit test ──────────────────────────────────────────────────────
    def _hit(self, mob, pt):
        bb = mob.get_bounding_box()
        mn, mx = bb[0], bb[2]
        return (mn[0] <= pt[0] <= mx[0]) and (mn[1] <= pt[1] <= mx[1])

    # ══════════════════════════════════════════════════════════════════
    # BUILD ARRAY FROM SCRATCH (no animation)
    # ══════════════════════════════════════════════════════════════════
    def _build_array(self, snap):
        for m in list(self._arr_mobs):
            self.remove(m)
        self._arr_mobs = []
        self.sq_list   = []
        self.num_list  = []
        self.idx_list  = []
        data    = snap["data"]
        fills   = snap["fills"]
        strokes = snap["strokes"]
        widths  = snap["widths"]
        n       = len(data)
        sq_size = self._sq_size(n)
        for i, v in enumerate(data):
            c  = self._cell_center(i, n)
            sq = Square(side_length=sq_size)
            fc = fills[i]
            sq.set_stroke(strokes[i], widths[i])
            if fc:
                sq.set_fill(fc, opacity=0.70)
            else:
                sq.set_fill(BLACK, opacity=0)
            sq.move_to(c)
            txt = Text(str(v)).scale(min(0.55, sq_size * 0.50)).move_to(c)
            idl = Text(str(i), color=GRAY_COLOR).scale(0.32)
            idl.move_to(c + DOWN * (sq_size / 2 + 0.26))
            self.sq_list.append(sq)
            self.num_list.append(txt)
            self.idx_list.append(idl)
            self.add(sq, txt, idl)
            self._arr_mobs.extend([sq, txt, idl])

    # ══════════════════════════════════════════════════════════════════
    # GO TO SNAPSHOT  — animated transition
    # ══════════════════════════════════════════════════════════════════
    def _go_to_snapshot(self, idx, play_speed=1.0):
        """Animate from current visual state to snapshot[idx]."""
        s    = self._snaps[idx]
        data = s["data"]
        n    = len(data)
        sp   = self._spacing(n)
        sq_size = self._sq_size(n)

        # ── physical swap animation ───────────────────────────────────
        if s["swap"] is not None:
            j, k = s["swap"]
            sqa, sqb = self.sq_list[j],  self.sq_list[k]
            nma, nmb = self.num_list[j], self.num_list[k]
            ida, idb = self.idx_list[j], self.idx_list[k]
            rt = max(0.08, 0.22 / play_speed)
            self.play(
                sqa.animate.shift(RIGHT * sp),
                sqb.animate.shift(LEFT  * sp),
                nma.animate.shift(RIGHT * sp),
                nmb.animate.shift(LEFT  * sp),
                ida.animate.shift(RIGHT * sp),
                idb.animate.shift(LEFT  * sp),
                run_time=rt,
            )
            self.sq_list[j],  self.sq_list[k]  = sqb, sqa
            self.num_list[j], self.num_list[k]  = nmb, nma
            self.idx_list[j], self.idx_list[k]  = idb, ida

            # fix index labels after sort phase swaps
            for i in range(n):
                old = self.idx_list[i]
                self.remove(old)
                if old in self._arr_mobs:
                    self._arr_mobs.remove(old)
                ni = Text(str(i), color=GRAY_COLOR).scale(0.32)
                ni.move_to(
                    self.sq_list[i].get_center() + DOWN * (sq_size / 2 + 0.26))
                self.idx_list[i] = ni
                self.add(ni)
                self._arr_mobs.append(ni)
            return   # fills/colours handled by next snap

        # ── colour transitions (fill, stroke) ─────────────────────────
        anims = []
        fills   = s["fills"]
        strokes = s["strokes"]
        widths  = s["widths"]

        for i, sq in enumerate(self.sq_list):
            fc = fills[i]
            if fc:
                anims.append(sq.animate.set_fill(fc, opacity=0.70)
                               .set_stroke(strokes[i], widths[i]))
            else:
                anims.append(sq.animate.set_fill(BLACK, opacity=0)
                               .set_stroke(strokes[i], widths[i]))

        rt = max(0.10, 0.22 / play_speed)
        if anims:
            self.play(*anims, run_time=rt)

        # ── pointers ──────────────────────────────────────────────────
        if s["low"] >= 0:
            self._place_pointers(s["low"], s["mid"], s["high"])
        else:
            self._clear_pointers()

        # ── step counter ──────────────────────────────────────────────
        self._set_step(s["step_n"])

    # ══════════════════════════════════════════════════════════════════
    # RENDER SNAPSHOT INSTANTLY (no animation) — used for ← backward
    # ══════════════════════════════════════════════════════════════════
    def _render_snapshot(self, idx):
        s = self._snaps[idx]
        self._build_array(s)
        if s["low"] >= 0:
            self._place_pointers(s["low"], s["mid"], s["high"])
        else:
            self._clear_pointers()
        self._set_step(s["step_n"])

    # ══════════════════════════════════════════════════════════════════
    # POINTERS
    # ══════════════════════════════════════════════════════════════════
    def _clear_pointers(self):
        for lbl in (self._low_lbl, self._mid_lbl, self._high_lbl):
            if lbl in self.mobjects:
                self.remove(lbl)

    def _place_pointers(self, low_i, mid_i, high_i):
        n = len(self.sq_list)
        self.add(self._low_lbl, self._mid_lbl, self._high_lbl)
        base_y = self.sq_list[0].get_top()[1]
        SLOT   = 0.36
        col_map = defaultdict(list)
        col_map[low_i ].append((self._low_lbl,  "LOW"))
        col_map[mid_i ].append((self._mid_lbl,  "MID"))
        col_map[high_i].append((self._high_lbl, "HIGH"))
        order = {"HIGH": 0, "MID": 1, "LOW": 2}
        for ci, items in col_map.items():
            items_s = sorted(items, key=lambda x: order[x[1]])
            cx = self._cell_center(ci, n)[0]
            for slot, (mob, _) in enumerate(items_s):
                mob.move_to(np.array([cx, base_y + 0.10 + slot * SLOT, 0]))

    # ══════════════════════════════════════════════════════════════════
    # STEP COUNTER
    # ══════════════════════════════════════════════════════════════════
    def _set_step(self, n):
        self.remove(self._step_mob)
        self._step_mob = Text(f"Step  {n}", color=YELLOW).scale(0.50)
        self._step_mob.to_corner(UR, buff=0.28)
        self.add(self._step_mob)

    # ══════════════════════════════════════════════════════════════════
    # TARGET DISPLAY
    # ══════════════════════════════════════════════════════════════════
    def _refresh_target(self):
        self.remove(self._tgt_mob)
        self._tgt_mob = Text(f"Target : {self._target}", color=YELLOW).scale(0.46)
        self._tgt_mob.to_corner(UL, buff=0.28)
        self.add(self._tgt_mob)

    # ══════════════════════════════════════════════════════════════════
    # SPEED DISPLAY
    # ══════════════════════════════════════════════════════════════════
    def _refresh_speed(self):
        self.remove(self._spd_mob)
        delay = AUTO_SPEEDS[self._speed_idx]
        # نستعمل أرقام بدل الرموز (1 = أبطأ, 5 = أسرع)
        speed_level = len(AUTO_SPEEDS) - self._speed_idx
        label = f"Speed  {speed_level}/5"
        self._spd_mob = Text(label, color=GRAY_COLOR).scale(0.32)
        self._spd_mob.to_corner(UR, buff=0.28)
        self._spd_mob.shift(DOWN * 0.55)
        self.add(self._spd_mob)

    # ══════════════════════════════════════════════════════════════════
    # INPUT BOX
    # ══════════════════════════════════════════════════════════════════
    def _open_box(self, pos, prompt):
        self._buf        = ""
        self._box_bg     = Rectangle(width=1.4, height=0.55)
        self._box_bg.set_fill("#111133", opacity=0.97).set_stroke(YELLOW, 2.5)
        self._box_bg.move_to(pos)
        self._box_prompt = Text(prompt, color=GRAY_COLOR).scale(0.22)
        self._box_prompt.next_to(self._box_bg, UP, buff=0.04)
        self._box_cursor = Text("_", color=YELLOW).scale(0.55)
        self._box_cursor.move_to(self._box_bg.get_center())
        self.add(self._box_bg, self._box_prompt, self._box_cursor)

    def _close_box(self):
        if self._box_bg is not None:
            self.remove(self._box_bg, self._box_prompt, self._box_cursor)
            self._box_bg = None

    def _refresh_box(self):
        self.remove(self._box_cursor)
        self._box_cursor = Text((self._buf or "") + "_", color=YELLOW).scale(0.55)
        self._box_cursor.move_to(self._box_bg.get_center())
        self.add(self._box_cursor)

    # ══════════════════════════════════════════════════════════════════
    # CELL SELECTION
    # ══════════════════════════════════════════════════════════════════
    def _select_cell(self, i):
        self._deselect_cell()
        self._selected_idx = i
        self.sq_list[i].set_stroke(SEL_COLOR, 4)
        badge = Text("selected", color=SEL_COLOR).scale(0.24)
        badge.next_to(self.sq_list[i], UP, buff=0.28)
        self._sel_badge = badge
        self.add(badge)

    def _deselect_cell(self):
        if self._selected_idx is not None:
            if self._selected_idx < len(self.sq_list):
                self.sq_list[self._selected_idx].set_stroke(WHITE, 2)
            if self._sel_badge:
                self.remove(self._sel_badge)
                self._sel_badge = None
            self._selected_idx = None

    # ══════════════════════════════════════════════════════════════════
    # HELP PANEL
    # ══════════════════════════════════════════════════════════════════
    SHORTCUTS = [
        ("Space / Enter", "Auto-play"),
        ("→",             "Next step"),
        ("←",             "Previous step"),
        ("+ / Ctrl+-",         "Speed up / slow down"),
        ("R",             "Reset"),
        ("Ctrl+A",        "Add value"),
        ("Ctrl+D",        "Delete selected / last"),
        ("Ctrl+T",        "Set target"),
        ("Delete",        "Remove cell"),
        ("H",             "Toggle this panel"),
        ("Esc",           "Cancel / deselect"),
    ]

    def _build_help(self):
        hdr  = Text("Shortcuts", color=YELLOW).scale(0.34)
        rows = [hdr]
        for k, d in self.SHORTCUTS:
            rows.append(VGroup(
                Text(k, color=YELLOW).scale(0.26),
                Text(d, color=WHITE ).scale(0.24),
            ).arrange(RIGHT, buff=0.14))
        panel = VGroup(*rows).arrange(DOWN, aligned_edge=LEFT, buff=0.10)
        bg = Rectangle(width=panel.get_width() + 0.28,
                       height=panel.get_height() + 0.22)
        bg.set_fill("#0d1117", opacity=0.95).set_stroke(YELLOW, 1.1)
        bg.move_to(panel.get_center())
        grp = VGroup(bg, panel)
        grp.to_corner(DR, buff=0.20)
        return grp

    def _toggle_help(self):
        if self._help_panel is None:
            self._help_panel = self._build_help()
            self.add(self._help_panel)
        else:
            self.remove(self._help_panel)
            self._help_panel = None

    # ══════════════════════════════════════════════════════════════════
    # WAIT LOOP
    # ══════════════════════════════════════════════════════════════════
    def _wait_for_input(self):
        self._action = None
        while self._action is None and not self.is_window_closing():
            self.update_frame(1 / self.camera.fps)

    # ══════════════════════════════════════════════════════════════════
    # CONSTRUCT
    # ══════════════════════════════════════════════════════════════════
    def construct(self):
        self._data         = DEFAULT_ARR.copy()
        self._target       = DEFAULT_TARGET
        self._arr_mobs     = []
        self._box_bg       = None
        self._box_mode     = None
        self._box_idx      = None
        self._selected_idx = None
        self._sel_badge    = None
        self._action       = None
        self._help_panel   = None
        self._snaps        = []
        self._snap_idx     = 0
        self._speed_idx    = AUTO_DEFAULT_IDX

        self._low_lbl  = Text("LOW",  color=BLUE  ).scale(0.38)
        self._mid_lbl  = Text("MID",  color=YELLOW).scale(0.42)
        self._high_lbl = Text("HIGH", color=RED   ).scale(0.38)

        # ── permanent UI ──────────────────────────────────────────────
        title = Text("Binary Search", weight=BOLD).scale(0.80)
        title.to_edge(UP, buff=0.18)
        self.add(title)

        self._step_mob = Text("Step  0", color=YELLOW).scale(0.50)
        self._step_mob.to_corner(UR, buff=0.28)
        self.add(self._step_mob)

        self._tgt_mob = Text(f"Target : {self._target}", color=YELLOW).scale(0.46)
        self._tgt_mob.to_corner(UL, buff=0.28)
        self.add(self._tgt_mob)

        self._spd_mob = Text("", color=GRAY_COLOR).scale(0.32)
        self.add(self._spd_mob)
        self._refresh_speed()

        # build initial idle snapshot and draw it
        self._rebuild_snaps()
        self._build_array(self._snaps[0])

        # ── main loop ─────────────────────────────────────────────────
        while not self.is_window_closing():
            self._wait_for_input()
            act = self._action

            if   act == "run":         self._do_auto_play()
            elif act == "next":        self._step_forward()
            elif act == "prev":        self._step_backward()
            elif act == "reset":       self._do_reset()
            elif act == "toggle_help": self._toggle_help()

    # ══════════════════════════════════════════════════════════════════
    # SNAPSHOT MANAGEMENT
    # ══════════════════════════════════════════════════════════════════
    def _rebuild_snaps(self):
        self._snaps    = compute_snapshots(self._data, self._target)
        self._snap_idx = 0

    def _invalidate(self):
        """Call after any data/target change."""
        self._rebuild_snaps()
        self._clear_pointers()

    # ══════════════════════════════════════════════════════════════════
    # STEP NAVIGATION
    # ══════════════════════════════════════════════════════════════════
    def _step_forward(self):
        if not self._snaps:
            self._rebuild_snaps()
        if self._snap_idx < len(self._snaps) - 1:
            self._snap_idx += 1
            self._go_to_snapshot(self._snap_idx, play_speed=1.0)

    def _step_backward(self):
        if not self._snaps:
            self._rebuild_snaps()
        if self._snap_idx > 0:
            self._snap_idx -= 1
            # Going back: instant redraw (no forward animation)
            self._render_snapshot(self._snap_idx)

    # ══════════════════════════════════════════════════════════════════
    # AUTO-PLAY
    # ══════════════════════════════════════════════════════════════════
    def _do_auto_play(self):
        if not self._snaps:
            self._rebuild_snaps()
        # restart from beginning if already at end
        if self._snap_idx >= len(self._snaps) - 1:
            self._snap_idx = 0
            self._render_snapshot(0)

        speed = 1.0 / AUTO_SPEEDS[self._speed_idx]   # higher = faster

        while (self._snap_idx < len(self._snaps) - 1
               and not self.is_window_closing()):
            self._snap_idx += 1
            self._go_to_snapshot(self._snap_idx, play_speed=speed)

            # pause between steps — pump events so keys work
            delay = AUTO_SPEEDS[self._speed_idx]
            t = 0.0
            self._action = None
            while t < delay and not self.is_window_closing():
                self.update_frame(1 / self.camera.fps)
                t += 1 / self.camera.fps
                if self._action is not None:
                    act = self._action
                    self._action = None
                    if act == "reset":
                        self._do_reset()
                        return
                    elif act == "run":
                        # restart auto-play from current position
                        self._do_auto_play()
                        return
                    elif act == "next":
                        # skip waiting, go to next step immediately
                        break
                    elif act == "prev":
                        self._step_backward()
                        return
                    elif act == "speed_up":
                        self._speed_idx = max(0, self._speed_idx - 1)
                        self._refresh_speed()
                        speed = 1.0 / AUTO_SPEEDS[self._speed_idx]
                    elif act == "speed_dn":
                        self._speed_idx = min(len(AUTO_SPEEDS)-1,
                                              self._speed_idx + 1)
                        self._refresh_speed()
                        speed = 1.0 / AUTO_SPEEDS[self._speed_idx]

    # ══════════════════════════════════════════════════════════════════
    # RESET
    # ══════════════════════════════════════════════════════════════════
    def _do_reset(self):
        self._data   = DEFAULT_ARR.copy()
        self._target = DEFAULT_TARGET
        self._invalidate()
        self._build_array(self._snaps[0])
        self._refresh_target()
        self._set_step(0)

    # ══════════════════════════════════════════════════════════════════
    # KEYBOARD
    # ══════════════════════════════════════════════════════════════════
    def on_key_press(self, symbol, modifiers):
        ctrl = bool(modifiers & K.MOD_CTRL)

        # ── input box ─────────────────────────────────────────────────
        if self._box_bg is not None:
            if symbol == K.RETURN:
                raw  = self._buf.strip()
                mode = self._box_mode
                idx  = self._box_idx
                self._close_box()
                self._box_mode = None
                self._box_idx  = None
                try:
                    val = int(raw)
                except ValueError:
                    return
                if mode == "cell":
                    self._data[idx] = val
                    self._invalidate()
                    self._build_array(self._snaps[0])
                elif mode == "target":
                    self._target = val
                    self._invalidate()
                    self._refresh_target()
                elif mode == "add":
                    self._data.append(val)
                    self._invalidate()
                    self._build_array(self._snaps[0])
            elif symbol == K.BACKSPACE:
                self._buf = self._buf[:-1]
                self._refresh_box()
            elif symbol == K.ESCAPE:
                if self._box_mode == "cell" and self._box_idx is not None:
                    if self._box_idx < len(self.sq_list):
                        self.sq_list[self._box_idx].set_stroke(WHITE, 2)
                self._close_box()
                self._box_mode = None
                self._box_idx  = None
            else:
                ch = chr(symbol) if 32 <= symbol <= 126 else ""
                if ch in "0123456789-":
                    self._buf += ch
                    self._refresh_box()
            return

        # ── global shortcuts ──────────────────────────────────────────
        if symbol == K.ESCAPE:
            self._deselect_cell()
            return

        if symbol == K.H:
            self._action = "toggle_help"
            return

        if symbol == K.R and not ctrl:
            self._action = "reset"
            return

        if (symbol == K.SPACE or symbol == K.RETURN) and not ctrl:
            self._action = "run"
            return

        if symbol == K.RIGHT:
            self._action = "next"
            return

        if symbol == K.LEFT:
            self._action = "prev"
            return

        # speed: + speeds up (shorter delay), - slows down
        if symbol in (K.PLUS, K.EQUAL, K.NUM_ADD):
            self._speed_idx = max(0, self._speed_idx - 1)
            self._refresh_speed()
            self._action = "speed_up"
            return

        if ctrl:
            # Ctrl + 6 (tirer 6 بدون Shift) → نقص السرعة (أبطأ)
            if symbol == K._6:
                self._speed_idx = min(len(AUTO_SPEEDS) - 1, self._speed_idx + 1)
                self._refresh_speed()
                self._action = "speed_dn"
                return
            
        if ctrl and symbol == K.A:
            self._deselect_cell()
            self._open_box(np.array([0, ARRAY_Y + 1.60, 0]),
                           "Add value  →  Enter")
            self._box_mode = "add"
            return

        if ctrl and symbol == K.D:
            if len(self._data) <= 1:
                return
            if self._selected_idx is not None:
                idx = self._selected_idx
                self._deselect_cell()
                self._data.pop(idx)
            else:
                self._data.pop()
            self._invalidate()
            self._build_array(self._snaps[0])
            return

        if ctrl and symbol == K.T:
            self._deselect_cell()
            self._open_box(np.array([0, ARRAY_Y + 1.60, 0]),
                           "New target  →  Enter")
            self._box_mode = "target"
            return

        if symbol == K.DELETE:
            if len(self._data) <= 1:
                return
            if self._selected_idx is not None:
                idx = self._selected_idx
                self._deselect_cell()
                self._data.pop(idx)
            else:
                self._data.pop()
            self._invalidate()
            self._build_array(self._snaps[0])
            return

        super().on_key_press(symbol, modifiers)

    # ══════════════════════════════════════════════════════════════════
    # MOUSE  —  cell select / edit only
    # ══════════════════════════════════════════════════════════════════
    def on_mouse_press(self, point, button, mods):
        if self._box_bg is not None:
            return

        for i, sq in enumerate(self.sq_list):
            if self._hit(sq, point):
                if self._selected_idx == i:
                    self._deselect_cell()
                    sq.set_stroke(YELLOW, 4)
                    self._open_box(sq.get_center(), f"Edit [{i}]  →  Enter")
                    self._box_mode = "cell"
                    self._box_idx  = i
                else:
                    self._select_cell(i)
                return

        self._deselect_cell()