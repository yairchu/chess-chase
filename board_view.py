import itertools
import operator
import random

from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.uix.widget import Widget

import env

class BoardView(Widget):
    def __init__(self, game, **kwargs):
        super(BoardView, self).__init__(**kwargs)
        self.game = game
        Window.bind(mouse_pos=self.mouse_motion)
        self.bind(size=self.resized)
        self.mouse_pos = None
        self.reset()

    def resized(self, *args):
        self.square_size = min(p / s for p, s in zip(self.size, self.game.board_size))

    def reset(self):
        self.selected = None
        self.is_dragging = False
        self.resized()

    def show_board(self):
        cols, see = self.board_info()

        self.canvas.clear()
        sq = (self.square_size-1, self.square_size-1)
        with self.canvas:
            self.draw_recent_moves(see)
            for (x, y), col in cols.items():
                sx, sy = self.screen_pos((x, y))
                Color(*[x/255 for x in col])
                Rectangle(pos=(sx, sy), size=sq)
                if (x, y) in self.game.board:
                    piece = self.game.board[x, y]
                    if self.game.board[x, y].freeze_until > self.game.counter:
                        freeze_ratio = (piece.freeze_until - self.game.counter) / piece.freeze_time
                        Color(.7, .7, .7)
                        Rectangle(pos=(sx, sy), size=((self.square_size-1) * freeze_ratio, self.square_size-1))

            for pos, piece in self.game.board.items():
                if pos not in see:
                    continue
                transparent = False
                if piece.last_move_time is not None:
                    move_time = (self.game.counter - piece.last_move_time)*0.1
                    if move_time < 1:
                        pos_between = move_time
                        if piece.last_pos is not None:
                            last_screen_pos = self.screen_pos(piece.last_pos)
                            new_screen_pos = self.screen_pos(pos)
                            Rectangle(
                                texture=piece.image(),
                                pos=[int(last_screen_pos[i]+(new_screen_pos[i]-last_screen_pos[i])*pos_between) for i in range(2)],
                                size=sq)
                if piece is self.selected and self.game.active():
                    transparent = True
                Color(1, 1, 1, .5 if transparent else 1)
                Rectangle(
                    texture=piece.image(),
                    pos=self.screen_pos(pos),
                    size=sq)

            if self.selected is not None and self.dst_pos is not None and self.game.active():
                Color(1, 1, 1, .5)
                Rectangle(
                    texture=self.selected.image(),
                    pos=self.screen_pos(self.dst_pos),
                    size=sq)

            if self.is_dragging:
                x, y = self.raw_mouse_pos
                Color(1, 1, 1, .5)
                Rectangle(
                    texture=self.selected.image(),
                    pos=(x-self.square_size//2, y-self.square_size//2),
                    size=sq)

    def draw_recent_moves(self, see):
        board_h = self.square_size * self.game.board_size[1]
        spare_h = self.height - board_h

        pieces = [
            piece for pos, piece in self.game.board.items()
            if pos in see and piece.last_move_time is not None
        ]
        pieces.sort(key=lambda piece: piece.last_move_time, reverse=True)
        pieces = pieces[:6]
        if not pieces:
            return

        pad = 18
        icon = max(32, min(
            86,
            max(54, max(spare_h, self.square_size * 2) * .18),
            (self.width - pad * 2) / len(pieces) - 10))
        gap = 10
        width = len(pieces) * icon + (len(pieces) - 1) * gap
        x = self.x + max(pad, (self.width - width) / 2)
        y = self.y + board_h + 34 if spare_h >= icon + 70 else self.y + board_h - icon - 34

        label = CoreLabel(text='Last moved', font_size=20, color=(.72, .76, .74, 1))
        label.refresh()
        Color(.72, .76, .74, 1)
        Rectangle(texture=label.texture, pos=(x, y + icon + 6), size=label.texture.size)

        for piece in pieces:
            remaining = max(
                piece.freeze_until,
                self.game.player_last_move.get(piece.player, 0) + self.game.player_freeze_time,
            ) - self.game.counter
            total = max(piece.freeze_time, self.game.player_freeze_time, 1)
            ratio = max(0, min(1, remaining / total))

            Color(.12, .14, .14, 1)
            Rectangle(pos=(x - 4, y - 8), size=(icon + 8, icon + 14))
            Color(1, 1, 1, 1)
            Rectangle(texture=piece.image(), pos=(x, y), size=(icon, icon))
            Color(.18, .55, .50, 1)
            Rectangle(pos=(x, y - 8), size=(icon * ratio, 5))
            x += icon + gap

    def board_info(self):
        player = None if self.game.mode in ['demo', 'replay'] else self.game.player()
        flash = {}
        if not env.is_mobile and not self.is_dragging:
            flashy = self.game.board.get(self.mouse_pos)
            if flashy is not None and self.can_control(flashy):
                for pos in flashy.moves():
                    flash[pos] = flashy.sight_color

        movesee = {}
        see = set()
        for piece in self.game.board.values():
            if player is not None and piece.side() != player%2:
                continue
            see.add(piece.pos)
            moves = set()
            if self.can_control(piece):
                moves = set(piece.moves())
                if self.mouse_pos in moves and not self.is_dragging and piece == self.selected:
                    flash[piece.pos] = piece.sight_color
                else:
                    movesee[piece.pos] = piece.sight_color
            for dst in itertools.chain(piece.sight()):
                see.add(dst)
                if dst in moves:
                    movesee[dst] = list(map(operator.add, movesee.get(dst, [0]*3), piece.sight_color))

        cols = {}
        for pos in see:
            cols[pos] = (240, 240, 240)
        for pos, col in movesee.items():
            cols[pos] = [128+a*127./max(col) for a in col]
        for pos, col in flash.items():
            cols[pos] = [255*x for x in col]

        return cols, see

    def on_touch_down(self, event):
        if not self.game.active():
            return
        self.calc_mouse_pos(event.pos)
        if self.is_choice_event(event):
            if [] == self.potential_pieces:
                return
            d = -1 if event.button == 'scrollup' else 1
            self.selected = self.potential_pieces[
                (self.potential_pieces.index(self.selected)+d)%len(self.potential_pieces)]
            return
        if self.mouse_pos in self.game.board and self.can_control(self.game.board[self.mouse_pos]):
            self.is_dragging = True
            self.selected = self.game.board[self.mouse_pos]
            self.dst_pos = None

    def is_choice_event(self, event):
        if env.is_mobile:
            return False
        return event.is_mouse_scrolling or event.button == 'right'

    def mouse_motion(self, _win, pos):
        if not self.game.active():
            return
        self.raw_mouse_pos = pos
        self.calc_mouse_pos(pos)

    def on_touch_up(self, event):
        if not self.game.active():
            return
        if self.is_choice_event(event):
            return
        self.calc_mouse_pos(event.pos)
        self.is_dragging = False
        if self.selected is None or self.dst_pos is None:
            return
        self.game.add_action('move', self.selected.pos, self.dst_pos)
        self.selected = None

    def calc_mouse_pos(self, pos):
        board_pos = [int((x - sx) // self.square_size) for x, sx in zip(pos, self.pos)]
        if (self.game.player() or 0) % 2 == 1:
            board_pos = [s-1-x for x, s in zip(board_pos, self.game.board_size)]
        self.mouse_pos = tuple(board_pos)

    def screen_pos(self, pos):
        if (self.game.player() or 0) % 2 == 1:
            pos = [s-1-x for x, s in zip(pos, self.game.board_size)]
        return tuple(sx+self.square_size*x for x, sx in zip(pos, self.pos))

    def can_control(self, piece):
        return self.game.mode == 'demo' or piece.player == self.game.player()

    last_pos = None
    def update_dst(self):
        if self.selected is not None and self.game.board.get(self.selected.pos) is not self.selected:
            self.selected = None
        if self.is_dragging and self.selected is not None:
            self.dst_pos = None
            if self.mouse_pos in self.selected.moves():
                self.dst_pos = self.mouse_pos
            return
        self.is_dragging = False
        self.potential_pieces = []
        for piece in self.game.board.values():
            if self.can_control(piece) and self.mouse_pos in piece.moves():
                self.potential_pieces.append(piece)
        self.potential_pieces.sort(key = lambda x: x.move_preference)
        if [] == self.potential_pieces:
            self.selected = None
        else:
            self.dst_pos = self.mouse_pos
            if self.last_pos != self.dst_pos or self.selected not in self.potential_pieces:
                self.selected = self.potential_pieces[0]
            self.last_pos = self.dst_pos
