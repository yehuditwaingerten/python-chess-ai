#!/usr/bin/env python3
"""
GUI wrapper for Console Chess that supports:
 - Player vs Computer (human plays White, AI plays Black)
 - Player vs Player (both human players on same machine)

Usage:
  python gui_chess.py [depth]

Requires console_chess.py in same folder exposing:
  GameState, negamax
"""
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

# import game logic from user's console_chess.py
try:
    from console_chess import GameState, negamax
except Exception as e:
    raise ImportError("Unable to import console_chess. Make sure console_chess.py is in the same folder.\nImport error: " + str(e))

# unicode glyphs for pieces (keeps same mapping as your code)
PIECE_GLYPHS = {
    'K': '\u2654', 'Q': '\u2655', 'R': '\u2656', 'B': '\u2657', 'N': '\u2658', 'P': '\u2659',
    'k': '\u265A', 'q': '\u265B', 'r': '\u265C', 'b': '\u265D', 'n': '\u265E', 'p': '\u265F',
    '.': ' '
}

SQUARE_COLORS = ('#F0D9B5', '#B58863')  # light, dark
HIGHLIGHT_COLOR = '#F7FF7F'  # selection highlight
LAST_MOVE_COLOR = '#C7E6FF'  # last move highlight

class ChessGUI(tk.Tk):
    def __init__(self, depth=3):
        super().__init__()
        self.title('Console Chess — GUI')
        self.resizable(False, False)
        self.depth = depth

        # game state
        self.gs = GameState()
        self.selected = None  # (r,c) selected by user
        self.last_move = None  # last move tuple for highlight
        self.mode = tk.StringVar(value='pvc')  # 'pvc' or 'pvp'

        # build UI
        self._build_ui()
        self.draw_board()
        # if black to move and PVC mode, start AI
        if self.gs.to_move == 'b' and self.mode.get() == 'pvc':
            self.after(200, self.start_computer_move)

    def _build_ui(self):
        main = ttk.Frame(self, padding=8)
        main.grid(row=0, column=0)

        # board (8x8 frames+labels)
        board_frame = ttk.Frame(main)
        board_frame.grid(row=0, column=0, rowspan=2)

        self.squares = [[None]*8 for _ in range(8)]
        for r in range(8):
            for c in range(8):
                bg = SQUARE_COLORS[(r + c) % 2]
                f = tk.Frame(board_frame, width=60, height=60, bg=bg, highlightthickness=2, highlightbackground=bg)
                f.grid_propagate(False)
                f.grid(row=r, column=c)
                lbl = tk.Label(f, text=' ', font=('Segoe UI Symbol', 28), bg=bg)
                lbl.bind('<Button-1>', lambda e, rr=r, cc=c: self.on_square_click(rr, cc))
                lbl.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                self.squares[r][c] = (f, lbl)

        # right-side controls
        ctrl = ttk.Frame(main, padding=(10,0,0,0))
        ctrl.grid(row=0, column=1, sticky='n')

        # Mode selection: PvC / PvP
        mode_lbl = ttk.Label(ctrl, text='מצב:')
        mode_lbl.grid(row=0, column=0, sticky='w')
        rb1 = ttk.Radiobutton(ctrl, text='שחקן מול מחשב', variable=self.mode, value='pvc', command=self.on_mode_change)
        rb1.grid(row=1, column=0, sticky='w')
        rb2 = ttk.Radiobutton(ctrl, text='שחקו מול שחקן', variable=self.mode, value='pvp', command=self.on_mode_change)
        rb2.grid(row=2, column=0, sticky='w')

        # status
        self.status_var = tk.StringVar()
        self._update_status()
        status_lbl = ttk.Label(ctrl, textvariable=self.status_var)
        status_lbl.grid(row=3, column=0, pady=(8,8))

        # depth control
        depth_lbl = ttk.Label(ctrl, text='רמת קושי:')
        depth_lbl.grid(row=4, column=0, sticky='w')
        self.depth_spin = tk.Spinbox(ctrl, from_=1, to=6, width=5)
        self.depth_spin.delete(0,'end'); self.depth_spin.insert(0,str(self.depth))
        self.depth_spin.grid(row=5, column=0, sticky='w')

        # buttons
        btn_new = ttk.Button(ctrl, text='משחק חדש', command=self.new_game)
        btn_new.grid(row=6, column=0, pady=(8,2), sticky='ew')
        btn_undo = ttk.Button(ctrl, text='לחזור מהלך', command=self.undo)
        btn_undo.grid(row=7, column=0, pady=2, sticky='ew')
        btn_resign = ttk.Button(ctrl, text='לגמור משחק', command=self.resign)
        btn_resign.grid(row=8, column=0, pady=2, sticky='ew')

        # move log
        log_lbl = ttk.Label(ctrl, text='Move log:')
        log_lbl.grid(row=9, column=0, pady=(8,0), sticky='w')
        self.log = tk.Text(ctrl, width=24, height=12, state='disabled')
        self.log.grid(row=10, column=0, pady=(2,0))

    def on_mode_change(self):
        """
        Handle switching between Player vs Computer and Player vs Player.
        If switched to PVC and it's black's turn, start AI.
        """
        if self.mode.get() == 'pvc' and self.gs.to_move == 'b':
            self.after(200, self.start_computer_move())
        self._update_status()

    def _update_status(self):
        turn = 'לבן' if self.gs.to_move == 'w' else 'שחור'
        mode_text = 'תור של' if self.mode.get()=='pvc' else 'שחקן מול שחקן'
        self.status_var.set(f'{mode_text} : {turn}')

    def draw_board(self):
        """
        Update the 8x8 label board based on self.gs.board.
        Also show selection and last-move highlights.
        """
        for r in range(8):
            for c in range(8):
                f, lbl = self.squares[r][c]
                base_bg = SQUARE_COLORS[(r + c) % 2]
                # highlight last move squares
                if self.last_move:
                    (fr,fc,tr,tc,_) = self.last_move
                else:
                    fr = fc = tr = tc = None

                if (r, c) == (fr, fc) or (r, c) == (tr, tc):
                    bg = LAST_MOVE_COLOR
                else:
                    bg = base_bg

                # selection highlight
                if self.selected == (r,c):
                    f.config(highlightbackground=HIGHLIGHT_COLOR)
                else:
                    f.config(highlightbackground=base_bg)

                f.config(bg=bg)
                lbl.config(bg=bg)
                piece = self.gs.board[r][c]
                lbl.config(text=PIECE_GLYPHS.get(piece, ' '))

        self._update_status()

    def on_square_click(self, r, c):
        """
        Handle a click:
         - In PVC: human is White only. Ignore clicks when it's black's turn.
         - In PVP: both sides play by clicking.
        """
        # if PVC and it's black's turn, ignore clicks
        if self.mode.get() == 'pvc' and self.gs.to_move == 'b':
            return

        piece = self.gs.board[r][c]
        # if no selection yet: try to select a piece of the correct side
        if self.selected is None:
            if piece == '.':
                return
            # determine allowed to select:
            if self.mode.get() == 'pvc':
                # human is white -> only select white (uppercase)
                if not piece.isupper():
                    return
            else:
                # pvp -> allow selecting a piece that matches side to move
                if self.gs.to_move == 'w' and not piece.isupper():
                    return
                if self.gs.to_move == 'b' and not piece.islower():
                    return
            self.selected = (r, c)
            self.draw_board()
            return

        # a piece was selected before -> attempt to move it to (r,c)
        fr, fc = self.selected
        tr, tc = r, c
        moving_piece = self.gs.board[fr][fc]
        prom = None
        # handle pawn promotion default to queen
        if moving_piece.upper() == 'P' and (tr == 0 or tr == 7):
            # choose queen by default; GameState expects lowercase or uppercase 'q'?
            prom = 'q' if moving_piece.islower() else 'q'
        move = (fr, fc, tr, tc, prom)

        legal = self.gs.generate_moves()
        if move not in legal:
            # try other promotions if pawn
            if moving_piece.upper() == 'P' and (tr == 0 or tr == 7):
                for pr in ['q','r','b','n']:
                    mv = (fr,fc,tr,tc,pr)
                    if mv in legal:
                        move = mv
                        break

        if move in legal:
            self.gs.make_move(move)
            self.last_move = move
            self.log_move(move)
            self.selected = None
            self.draw_board()
            # if pvc and now it's black's turn -> start AI
            if self.mode.get() == 'pvc' and self.gs.to_move == 'b':
                self.after(50, self.start_computer_move)
        else:
            # illegal move: if clicked another friendly piece then select it
            if self.mode.get() == 'pvc':
                # only white human selectable — so check only uppercase
                if piece != '.' and piece.isupper():
                    self.selected = (r,c)
                else:
                    self.selected = None
            else:
                # pvp: allow selecting piece of the side to move
                if piece != '.':
                    if self.gs.to_move == 'w' and piece.isupper():
                        self.selected = (r,c)
                    elif self.gs.to_move == 'b' and piece.islower():
                        self.selected = (r,c)
                    else:
                        self.selected = None
                else:
                    self.selected = None
            self.draw_board()

    def log_move(self, move):
        fr,fc,tr,tc,prom = move
        try:
            san = self.gs.coords_to_algebraic(fr,fc)+self.gs.coords_to_algebraic(tr,tc)+(prom or '')
        except Exception:
            # fallback if GameState does not provide coords_to_algebraic
            san = f"{fr}{fc}->{tr}{tc}" + (prom or '')
        self.log.config(state='normal')
        self.log.insert('end', san + '\n')
        self.log.see('end')
        self.log.config(state='disabled')

    def start_computer_move(self):
        # only start if mode = pvc and it's black's turn
        if self.mode.get() != 'pvc' or self.gs.to_move != 'b':
            return
        try:
            depth = int(self.depth_spin.get())
        except Exception:
            depth = self.depth
        # spawn background thread
        t = threading.Thread(target=self._computer_move_thread, args=(depth,), daemon=True)
        t.start()

    def _computer_move_thread(self, depth):
        self.status_var.set('...רגע המחשב חושב')
        t0 = time.time()
        val, m = negamax(self.gs, depth, -10**9, 10**9)
        t1 = time.time()
        if m is None:
            # checkmate or stalemate
            if self.gs.is_checkmate():
                winner = 'הלבן' if self.gs.to_move == 'b' else 'השחור'
                self.after(1, lambda: messagebox.showinfo('Game over', f'מט! {winner} ניצח'))
            else:
                self.after(1, lambda: messagebox.showinfo('Game over', 'Draw / no legal moves'))
            return
        # apply move on main thread
        self.after(1, lambda: self._apply_computer_move(m, val, t1-t0))

    def _apply_computer_move(self, m, val, elapsed):
        self.gs.make_move(m)
        self.last_move = m
        self.log_move(m)
        self.draw_board()
        fr,fc,tr,tc,prom = m
        try:
            san = self.gs.coords_to_algebraic(fr,fc)+self.gs.coords_to_algebraic(tr,tc)+(prom or '')
        except Exception:
            san = f"{fr}{fc}->{tr}{tc}"
        self.status_var.set(f"המחשב שיחק {san} (eval {val}, זמן {elapsed:.2f}s)")

        if self.gs.is_checkmate():
            messagebox.showinfo('Game over', 'Checkmate!')
        elif self.gs.is_stalemate():
            messagebox.showinfo('Game over', 'Stalemate / Draw')

    def new_game(self):
        self.gs = GameState()
        self.selected = None
        self.last_move = None
        self.log.config(state='normal'); self.log.delete('1.0','end'); self.log.config(state='disabled')
        self.draw_board()
        # if switched to PVC and black to move -> AI
        if self.mode.get() == 'pvc' and self.gs.to_move == 'b':
            self.after(200, self.start_computer_move)

    def undo(self):
        """
        Undo last move(s):
         - In PVC: undo last two plies (AI + human) when possible, to return to same side to move.
         - In PVP: undo single ply (last move).
        """
        try:
            self.gs.undo()
        except Exception:
            # if undo not available / fails, ignore
            pass

        if self.mode.get() == 'pvc':
            # if after one undo it's still black's turn (AI moved), undo again so human gets turn back
            if self.gs.to_move == 'b':
                try:
                    self.gs.undo()
                except Exception:
                    pass
        # reset selection and last_move highlight
        self.selected = None
        self.last_move = None
        self.draw_board()

    def resign(self):
        if messagebox.askyesno('Resign', 'האם לגמור את המשחק?'):
            winner = 'השחור' if self.gs.to_move == 'w' else 'הלבן'
            messagebox.showinfo('Resigned', f'המנצח הוא. {winner} .')
            self.new_game()


if __name__ == '__main__':
    d = 3
    if len(sys.argv) > 1:
        try:
            d = int(sys.argv[1])
        except:
            pass
    app = ChessGUI(depth=d)
    app.mainloop()
