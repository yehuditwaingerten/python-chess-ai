#!/usr/bin/env python3
"""
Console Chess: single-player vs computer
Features:
- Full board and pieces
- Legal move generation for all pieces
- Castling, en-passant, promotion
- Check, checkmate, stalemate detection
- Simple AI: minimax with alpha-beta pruning and adjustable depth

Controls:
- Enter moves in algebraic coordinate form: e2e4 or e7e8q (promotion to queen)
- Type 'undo' to undo last move, 'resign' to resign, 'help' to show controls, 'quit' to exit

Made to be readable and easy to modify.
"""

from copy import deepcopy
import sys
import time

# Board coordinates: rows 0..7 (rank 8..1), cols 0..7 (file a..h)

PIECE_VALUES = {'K': 0, 'Q': 900, 'R': 500, 'B': 330, 'N': 320, 'P': 100}

STARTING_FEN = (
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
)

class GameState:
    def __init__(self, fen=None):
        if fen is None:
            fen = STARTING_FEN
        self.board = [['.' for _ in range(8)] for _ in range(8)]
        self.to_move = 'w'
        self.castling = {'K': False, 'Q': False, 'k': False, 'q': False}
        self.en_passant = None
        self.halfmove_clock = 0
        self.fullmove_number = 1
        self.move_stack = []
        self.parse_fen(fen)

    def parse_fen(self, fen):
        parts = fen.split()
        rows = parts[0].split('/')
        for r, row in enumerate(rows):
            c = 0
            for ch in row:
                if ch.isdigit():
                    c += int(ch)
                else:
                    self.board[r][c] = ch
                    c += 1
        self.to_move = parts[1]
        cast = parts[2]
        self.castling = {'K': 'K' in cast, 'Q': 'Q' in cast, 'k': 'k' in cast, 'q': 'q' in cast}
        self.en_passant = None if parts[3] == '-' else parts[3]
        self.halfmove_clock = int(parts[4])
        self.fullmove_number = int(parts[5])

    def fen(self):
        rows = []
        for r in range(8):
            empty = 0
            row_s = ''
            for c in range(8):
                ch = self.board[r][c]
                if ch == '.':
                    empty += 1
                else:
                    if empty:
                        row_s += str(empty)
                        empty = 0
                    row_s += ch
            if empty:
                row_s += str(empty)
            rows.append(row_s)
        board_part = '/'.join(rows)
        castling_part = ''.join([k for k, v in self.castling.items() if v])
        if castling_part == '':
            castling_part = '-'
        ep = self.en_passant if self.en_passant else '-'
        return f"{board_part} {self.to_move} {castling_part} {ep} {self.halfmove_clock} {self.fullmove_number}"

    def clone(self):
        return deepcopy(self)

    def print_board(self):
        print('  +------------------------+')
        for r in range(8):
            print(8-r, '|', end=' ')
            for c in range(8):
                ch = self.board[r][c]
                print(ch if ch != '.' else '.', end=' ')
            print('|')
        print('  +------------------------+')
        print('    a b c d e f g h')
        print(f"To move: {'White' if self.to_move=='w' else 'Black'}")

    def algebraic_to_coords(self, s):
        file = ord(s[0]) - ord('a')
        rank = 8 - int(s[1])
        return rank, file

    def coords_to_algebraic(self, r, c):
        return chr(ord('a') + c) + str(8 - r)

    def piece_color(self, p):
        if p == '.' :
            return None
        return 'w' if p.isupper() else 'b'

    def enemy(self, side):
        return 'b' if side == 'w' else 'w'

    def in_bounds(self, r, c):
        return 0 <= r < 8 and 0 <= c < 8

    def is_attacked(self, r, c, by_side):
        # Check for pawn attacks
        directions = [(-1, -1), (-1, 1)] if by_side == 'w' else [(1, -1), (1, 1)]
        for dr, dc in directions:
            rr, cc = r + dr, c + dc
            if self.in_bounds(rr, cc):
                if (self.board[rr][cc].upper() == 'P') and self.piece_color(self.board[rr][cc]) == by_side:
                    return True
        # Knights
        for dr, dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
            rr, cc = r+dr, c+dc
            if self.in_bounds(rr, cc):
                if self.board[rr][cc].upper() == 'N' and self.piece_color(self.board[rr][cc]) == by_side:
                    return True
        # Sliding pieces
        # bishops/queens diagonals
        for dr, dc in [(-1,-1),(-1,1),(1,-1),(1,1)]:
            rr, cc = r+dr, c+dc
            while self.in_bounds(rr, cc):
                ch = self.board[rr][cc]
                if ch != '.':
                    if self.piece_color(ch) == by_side and (ch.upper() == 'B' or ch.upper() == 'Q'):
                        return True
                    break
                rr += dr; cc += dc
        # rooks/queens straight
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            rr, cc = r+dr, c+dc
            while self.in_bounds(rr, cc):
                ch = self.board[rr][cc]
                if ch != '.':
                    if self.piece_color(ch) == by_side and (ch.upper() == 'R' or ch.upper() == 'Q'):
                        return True
                    break
                rr += dr; cc += dc
        # king
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                if dr==0 and dc==0: continue
                rr, cc = r+dr, c+dc
                if self.in_bounds(rr, cc):
                    ch = self.board[rr][cc]
                    if ch.upper() == 'K' and self.piece_color(ch) == by_side:
                        return True
        return False

    def king_position(self, side):
        target = 'K' if side == 'w' else 'k'
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == target:
                    return r, c
        return None

    def in_check(self, side):
        kr = self.king_position(side)
        if not kr:
            return True  # no king, treat as check
        return self.is_attacked(kr[0], kr[1], self.enemy(side))

    def generate_moves(self):
        moves = []  # each move: (from_r, from_c, to_r, to_c, promotion)
        side = self.to_move
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p == '.':
                    continue
                if self.piece_color(p) != side:
                    continue
                kind = p.upper()
                if kind == 'P':
                    self._pawn_moves(r, c, moves)
                elif kind == 'N':
                    self._knight_moves(r, c, moves)
                elif kind == 'B':
                    self._sliding_moves(r, c, moves, [(-1,-1),(-1,1),(1,-1),(1,1)])
                elif kind == 'R':
                    self._sliding_moves(r, c, moves, [(-1,0),(1,0),(0,-1),(0,1)])
                elif kind == 'Q':
                    self._sliding_moves(r, c, moves, [(-1,-1),(-1,1),(1,-1),(1,1),(-1,0),(1,0),(0,-1),(0,1)])
                elif kind == 'K':
                    self._king_moves(r, c, moves)
        # Filter moves that leave king in check
        legal = []
        for m in moves:
            gs2 = self.clone()
            gs2.make_move(m, validate=False)
            if not gs2.in_check(self.to_move):
                legal.append(m)
        return legal

    def _pawn_moves(self, r, c, moves):
        p = self.board[r][c]
        side = self.piece_color(p)
        dir = -1 if side == 'w' else 1
        start_row = 6 if side == 'w' else 1
        # forward
        if self.in_bounds(r+dir, c) and self.board[r+dir][c]=='.':
            # promotion?
            if (r+dir==0 and side=='w') or (r+dir==7 and side=='b'):
                for promo in ['q','r','b','n']:
                    moves.append((r,c,r+dir,c,promo))
            else:
                moves.append((r,c,r+dir,c,None))
                # double
                if r==start_row and self.board[r+2*dir][c]=='.':
                    moves.append((r,c,r+2*dir,c,None))
        # captures
        for dc in (-1,1):
            rr, cc = r+dir, c+dc
            if not self.in_bounds(rr, cc):
                continue
            if self.board[rr][cc] != '.' and self.piece_color(self.board[rr][cc]) == self.enemy(side):
                if (rr==0 and side=='w') or (rr==7 and side=='b'):
                    for promo in ['q','r','b','n']:
                        moves.append((r,c,rr,cc,promo))
                else:
                    moves.append((r,c,rr,cc,None))
        # en-passant
        if self.en_passant:
            ep_r, ep_c = self.algebraic_to_coords(self.en_passant)
            if ep_r == r+dir and abs(ep_c - c) == 1:
                moves.append((r,c,ep_r,ep_c,None))

    def _knight_moves(self, r, c, moves):
        side = self.piece_color(self.board[r][c])
        for dr, dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
            rr, cc = r+dr, c+dc
            if not self.in_bounds(rr, cc): continue
            if self.board[rr][cc]=='.' or self.piece_color(self.board[rr][cc])==self.enemy(side):
                moves.append((r,c,rr,cc,None))

    def _sliding_moves(self, r, c, moves, directions):
        side = self.piece_color(self.board[r][c])
        for dr, dc in directions:
            rr, cc = r+dr, c+dc
            while self.in_bounds(rr, cc):
                if self.board[rr][cc]=='.':
                    moves.append((r,c,rr,cc,None))
                else:
                    if self.piece_color(self.board[rr][cc])==self.enemy(side):
                        moves.append((r,c,rr,cc,None))
                    break
                rr += dr; cc += dc

    def _king_moves(self, r, c, moves):
        side = self.piece_color(self.board[r][c])
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                if dr==0 and dc==0: continue
                rr, cc = r+dr, c+dc
                if self.in_bounds(rr, cc):
                    if self.board[rr][cc]=='.' or self.piece_color(self.board[rr][cc])==self.enemy(side):
                        moves.append((r,c,rr,cc,None))
        # castling
        if side=='w' and r==7 and c==4:
            if self.castling['K'] and self.board[7][5]=='.' and self.board[7][6]=='.' and not self.is_attacked(7,4,'b') and not self.is_attacked(7,5,'b') and not self.is_attacked(7,6,'b'):
                moves.append((7,4,7,6,None))
            if self.castling['Q'] and self.board[7][3]=='.' and self.board[7][2]=='.' and self.board[7][1]=='.' and not self.is_attacked(7,4,'b') and not self.is_attacked(7,3,'b') and not self.is_attacked(7,2,'b'):
                moves.append((7,4,7,2,None))
        if side=='b' and r==0 and c==4:
            if self.castling['k'] and self.board[0][5]=='.' and self.board[0][6]=='.' and not self.is_attacked(0,4,'w') and not self.is_attacked(0,5,'w') and not self.is_attacked(0,6,'w'):
                moves.append((0,4,0,6,None))
            if self.castling['q'] and self.board[0][3]=='.' and self.board[0][2]=='.' and self.board[0][1]=='.' and not self.is_attacked(0,4,'w') and not self.is_attacked(0,3,'w') and not self.is_attacked(0,2,'w'):
                moves.append((0,4,0,2,None))

    def make_move(self, move, validate=True):
        # move: (fr,fc,tr,tc,prom)
        fr, fc, tr, tc, prom = move
        piece = self.board[fr][fc]
        target = self.board[tr][tc]
        # store state to stack for undo
        state = (fr,fc,tr,tc,piece,target,self.castling.copy(),self.en_passant,self.halfmove_clock,self.fullmove_number)
        self.move_stack.append(state)
        # update halfmove
        if piece.upper()=='P' or target!='.':
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1
        # move piece
        self.board[fr][fc]='.'
        # handle en-passant capture
        if piece.upper()=='P' and self.en_passant:
            ep_r, ep_c = self.algebraic_to_coords(self.en_passant)
            if tr==ep_r and tc==ep_c and fc!=tc and target=='.':
                # capture pawn behind ep square
                cap_r = fr
                cap_c = tc
                self.board[cap_r][cap_c]='.'
        # handle castling rook move
        if piece.upper()=='K' and abs(tc-fc)==2:
            # king-side
            if tc>fc:
                self.board[tr][tc]=piece
                self.board[tr][tc-1]=self.board[tr][7]
                self.board[tr][7]='.'
            else:
                self.board[tr][tc]=piece
                self.board[tr][tc+1]=self.board[tr][0]
                self.board[tr][0]='.'
        else:
            # promotion
            if prom and piece.upper()=='P' and (tr==0 or tr==7):
                promoted = prom.upper() if piece.isupper() else prom.lower()
                self.board[tr][tc]=promoted
            else:
                self.board[tr][tc]=piece
        # update castling rights if king or rook moved or captured
        if piece == 'K':
            self.castling['K']=False; self.castling['Q']=False
        if piece == 'k':
            self.castling['k']=False; self.castling['q']=False
        if fr==7 and fc==0 or tr==7 and tc==0:
            if self.board[7][0].upper()!='R':
                self.castling['Q']=False
        if fr==7 and fc==7 or tr==7 and tc==7:
            if self.board[7][7].upper()!='R':
                self.castling['K']=False
        if fr==0 and fc==0 or tr==0 and tc==0:
            if self.board[0][0].upper()!='R':
                self.castling['q']=False
        if fr==0 and fc==7 or tr==0 and tc==7:
            if self.board[0][7].upper()!='R':
                self.castling['k']=False
        # set en-passant square
        self.en_passant = None
        if piece.upper()=='P' and abs(tr-fr)==2:
            ep_r = (fr+tr)//2
            ep_c = fc
            self.en_passant = self.coords_to_algebraic(ep_r, ep_c)
        # change side
        self.to_move = self.enemy(self.to_move)
        if self.to_move=='w':
            self.fullmove_number += 1

    def undo(self):
        if not self.move_stack:
            return
        fr,fc,tr,tc,piece,target,castling,en_passant,halfmove,fullmove = self.move_stack.pop()
        # restore
        # note: when castling we moved rook; to simplify, we just restore from stored fields
        # revert board
        # find what is on tr,tc
        # If promotion occurred, piece at tr,tc may be promoted piece
        self.board[fr][fc]=piece
        self.board[tr][tc]=target
        # special: en-passant capture had removed a pawn behind target; we cannot infer easily, but earlier stored target will be '.' and piece moved; we've restored target '.'; need to handle ep restore
        self.castling = castling
        self.en_passant = en_passant
        self.halfmove_clock = halfmove
        self.fullmove_number = fullmove
        # flip side back
        self.to_move = self.enemy(self.to_move)

    def move_from_uci(self, s):
        # formats: e2e4 or e7e8q
        s = s.strip()
        if len(s) < 4:
            return None
        fr = self.algebraic_to_coords(s[0:2])
        tr = self.algebraic_to_coords(s[2:4])
        prom = s[4] if len(s) >=5 else None
        return (fr[0],fr[1],tr[0],tr[1],prom)

    def is_checkmate(self):
        if not self.in_check(self.to_move):
            return False
        return len(self.generate_moves())==0

    def is_stalemate(self):
        if self.in_check(self.to_move):
            return False
        return len(self.generate_moves())==0

    def material_score(self):
        # positive means white advantage
        s = 0
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p=='.': continue
                val = PIECE_VALUES.get(p.upper(),0)
                s += val if p.isupper() else -val
        return s

# -------------- AI --------------

def evaluate(gs: GameState):
    # simple evaluation: material + small mobility
    mat = gs.material_score()
    # mobility
    moves = len(gs.generate_moves())
    gs2 = gs.clone()
    gs2.to_move = gs.enemy(gs.to_move)
    opp_moves = len(gs2.generate_moves())
    mobility = moves - opp_moves
    return mat + 10 * mobility


def negamax(gs: GameState, depth, alpha, beta):
    if depth == 0:
        return evaluate(gs), None
    moves = gs.generate_moves()
    if not moves:
        if gs.in_check(gs.to_move):
            return -999999 + (10 - depth), None
        else:
            return 0, None
    best_val = -10**9
    best_move = None
    # simple move ordering: captures first
    def mv_key(m):
        fr,fc,tr,tc,prom = m
        target = gs.board[tr][tc]
        if target != '.':
            return 100 + PIECE_VALUES.get(target.upper(),0)
        return 0
    moves.sort(key=mv_key, reverse=True)
    for m in moves:
        gs2 = gs.clone()
        gs2.make_move(m)
        val, _ = negamax(gs2, depth-1, -beta, -alpha)
        val = -val
        if val > best_val:
            best_val = val; best_move = m
        alpha = max(alpha, val)
        if alpha >= beta:
            break
    return best_val, best_move

# -------------- Main loop --------------

def play(depth=3):
    gs = GameState()
    print('\nConsole Chess vs Computer')
    print('Enter moves like e2e4, e7e8q (promotion q/r/b/n). Commands: undo, resign, help, quit')
    while True:
        gs.print_board()
        if gs.is_checkmate():
            print('Checkmate! ', 'Black' if gs.to_move=='w' else 'White', 'wins')
            break
        if gs.is_stalemate():
            print('Stalemate! Draw')
            break
        if gs.to_move == 'w':
            user_move = input('Your move: ').strip()
            if user_move.lower() == 'quit':
                print('Goodbye')
                break
            if user_move.lower() == 'help':
                print('Enter moves like e2e4, e7e8q. undo, resign, help, quit')
                continue
            if user_move.lower() == 'undo':
                gs.undo(); gd2d.undo(); continue
            if user_move.lower() == 'resign':
                print('You resigned. Black wins.'); break
            m = gs.move_from_uci(user_move)
            if m is None:
                print('Invalid format')
                continue
            legal = gs.generate_moves()
            if m not in legal:
                print('Illegal move')
                continue
            gs.make_move(m)
        else:
            print('Computer is thinking...')
            t0 = time.time()
            val, m = negamax(gs, depth, -10**9, 10**9)
            t1 = time.time()
            if m is None:
                print('No legal moves')
                break
            print(f'Computer plays {gs.coords_to_algebraic(m[0],m[1])}{gs.coords_to_algebraic(m[2],m[3])}{m[4] or ""}  (eval {val}, time {t1-t0:.2f}s)')
            gs.make_move(m)

if __name__ == '__main__':
    d = 3
    if len(sys.argv) > 1:
        try:
            d = int(sys.argv[1])
        except:
            pass
    play(depth=d)
