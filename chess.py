import itertools
import os
import sys
from itertools import count

from kivy.uix.image import Image

import env

ROOT = getattr(sys, '_MEIPASS', os.path.dirname(__file__))

class Piece:
    freeze_time = 0 if env.dev_mode else 80
    last_move_time = None

    last_pos = None

    def __init__(self, player, pos, game):
        self.player = player
        self.pos = pos
        self.freeze_until = 0
        self.game = game
        game.board[pos] = self

    def image(self):
        'Get image for piece'
        return self._images[self.player]

    def side(self):
        return self.player % 2

    def die(self):
        if self.game.board[self.pos] == self:
            del self.game.board[self.pos]
        self.on_die()

    def on_die(self):
        'Callback for actions on piece dying (overridden for King)'
        pass

    def move(self, pos):
        if self.game.board[self.pos] is not self or pos not in self.moves():
            # Situation changed since move queued, can't perform this move!
            return False
        self.prev_pos = self.pos
        self._move(pos)
        return True

    def _move(self, pos):
        assert isinstance(pos[0], int)
        del self.game.board[self.pos]
        self.last_pos = self.pos
        self.last_move_time = self.game.counter
        self.pos = pos
        if pos in self.game.board:
            self.game.board[pos].die()
        self.game.board[self.pos] = self
        self.freeze_until = self.game.counter+self.freeze_time
        self.game.player_last_move[self.player] = self.game.counter

    def moves(self):
        freeze_time = self.game.player_freeze_time
        if self.game.counter < max(
                self.freeze_until,
                self.game.player_last_move.get(self.player, -freeze_time) + freeze_time):
            return
        yield from self.base_moves()

    def sight(self):
        'What squares can this piece see (overridden for Pawn)'
        yield from self.base_moves()

    def base_moves(self):
        for streak in self._moves(*self.pos):
            for dst in streak:
                if dst in self.game.board and self.game.board[dst].side() == self.side():
                    break
                if self.game.in_bounds(dst):
                    yield dst
                else:
                    break
                if dst in self.game.board:
                    break

class Rook(Piece):
    sight_color = (0.5, 0.5, 1)
    @staticmethod
    def _moves(x, y):
        yield ((x+d, y) for d in count(1))
        yield ((x-d, y) for d in count(1))
        yield ((x, y+d) for d in count(1))
        yield ((x, y-d) for d in count(1))

class Bishop(Piece):
    sight_color = (0, 0, 1)
    @staticmethod
    def _moves(x, y):
        yield ((x+d, y+d) for d in count(1))
        yield ((x-d, y-d) for d in count(1))
        yield ((x+d, y-d) for d in count(1))
        yield ((x-d, y+d) for d in count(1))

class Queen(Rook, Bishop):
    sight_color = (1, 0, 0)
    @staticmethod
    def _moves(x, y):
        return itertools.chain(Rook._moves(x, y), Bishop._moves(x, y))

class Knight(Piece):
    sight_color = (0, 1, 0)
    @staticmethod
    def _moves(x, y):
        for a in [-1, 1]:
            for b in [-2, 2]:
                yield [(x+a, y+b)]
                yield [(x+b, y+a)]

class King(Piece):
    sight_color = (0, 1, 1)
    freeze_time = 60

    def sight(self):
        yield from self.base_moves()
        for streak in itertools.chain(Knight._moves(*self.pos), Queen._moves(*self.pos)):
            for pos in streak:
                if not self.game.in_bounds(pos):
                    break
                if pos in self.game.board:
                    if self.pos in self.game.board[pos].base_moves():
                        yield pos
                    break

    def move(self, pos):
        (x, y) = pos
        (sx, sy) = self.pos
        if abs(x - sx) <= 1:
            return super(King, self).move(pos)
        # Castling
        assert y == sy
        dir = 1 if x > sx else -1
        piece = self.castling(sx, sy, dir)
        if piece is None:
            return
        self._move(pos)
        piece._move((sx + dir, sy))
        return True

    def _moves(self, x, y):
        for a in range(x-1, x+2):
            for b in range(y-1, y+2):
                if (a, b) != (x, y):
                    yield [(a, b)]
        if self.last_move_time is not None:
            return
        for dir in [-1, 1]:
            if self.castling(x, y, dir):
                yield [(x+dir*2, y)]

    def castling(self, x, y, dir):
        dest = x+dir
        while self.game.in_bounds((dest, y)):
            piece = self.game.board.get((dest, y))
            if piece is not None:
                if abs(dest-x) > 2 and type(piece) == Rook and piece.last_move_time is None:
                    return piece
                break
            dest += dir

class Pawn(Piece):
    sight_color = (0.5, 0.5, 0.5)
    egg_time = 0 if env.dev_mode else 60

    def move(self, pos):
        prev_x, prev_y = self.pos
        dst_piece = self.game.board.get(pos)
        if not super(Pawn, self).move(pos):
            return False

        if (self.side() == 0 and pos[1] == 7) or (self.side() == 1 and pos[1] == 0):
            # Become Queen
            self.die()
            new_piece = Queen(self.player, pos, self.game)
            new_piece.freeze_until = self.game.counter+self.egg_time

        x, y = pos
        if dst_piece is None and x != prev_x:
            # En passant
            self.game.board[x, prev_y].die()

        return True

    def sight(self):
        yield from self.base_moves()
        delta = -1 if self.side() else 1
        x, y = self.pos
        for a in [x-1, x+1]:
            dst = a, y+delta
            if self.game.in_bounds(dst):
                yield dst
        for piece in self.en_passant(x, y):
            yield piece.pos

    def _moves(self, x, y):
        start_row, delta = (6, -1) if self.side() else (1, 1)

        # Move forward
        m = [(x, y+delta)]
        if y == start_row:
            m.append((x, y+2*delta))
        for c, p in enumerate(m):
            if p in self.game.board:
                m = m[:c]
                break
        yield m

        # Capture
        for a in [x-1, x+1]:
            if (a, y+delta) in self.game.board:
                yield [(a, y+delta)]

        # En passant
        for piece in self.en_passant(x, y):
            yield [(a, y+delta)]

    def en_passant(self, x, y):
        for a in [x-1, x+1]:
            piece = self.game.board.get((a, y))
            if type(piece) != Pawn:
                continue
            if piece.player % 2 == self.player % 2:
                # Same team
                continue
            if piece.last_move_time is None:
                continue
            if self.game.player_last_move.get(self.player, -1) > piece.last_move_time:
                # Already moved after this pawn
                continue
            yield piece

first_row = [Rook, Knight, Bishop, Queen, King, Bishop, Knight, Rook]

pieces_image = Image(source=os.path.join(ROOT, 'chess-chase-pieces.png')).texture
image_h = pieces_image.size[1]
black_regions = [
    (56, 29, 141, 203),
    (143, 29, 236, 205),
    (247, 30, 325, 203),
    (337, 43, 421, 204),
    (446, 57, 528, 203),
    (542, 86, 614, 205),
]
white_regions = [
    (53, 226, 135, 391),
    (149, 226, 233, 391),
    (247, 224, 322, 392),
    (338, 232, 423, 393),
    (445, 240, 530, 392),
    (545, 268, 618, 392),
]

def region(bounds):
    x0, y0, x1, y1 = bounds
    return pieces_image.get_region(x0, image_h - y1, x1 - x0, y1 - y0)

Piece.image_scale_height = max(y1 - y0 for x0, y0, x1, y1 in black_regions + white_regions)

for x, piece in enumerate([King, Queen, Bishop, Knight, Rook, Pawn]):
    piece._images = [region(white_regions[x]), region(black_regions[x])]

for preference, piece in enumerate([King, Pawn, Knight, Bishop, Rook, Queen]):
    piece.move_preference = preference
