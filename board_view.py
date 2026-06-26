import itertools
import operator
import random

from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle
from kivy.uix.widget import Widget

import env

class BoardView(Widget):
    top_margin_squares = .75

    def __init__(self, game, **kwargs):
        super(BoardView, self).__init__(**kwargs)
        self.game = game
        Window.bind(mouse_pos=self.mouse_motion)
        self.bind(pos=self.resized, size=self.resized)
        self.mouse_pos = None
        self.reset()

    def resized(self, *args):
        self.square_size = min(
            self.width / self.game.board_size[0],
            self.height / (self.game.board_size[1] + self.top_margin_squares))
        self.board_x = self.x + (self.width - self.square_size * self.game.board_size[0]) / 2
        self.board_y = self.top - self.square_size * (self.game.board_size[1] + self.top_margin_squares)

    def reset(self):
        self.selected = None
        self.is_dragging = False
        self.resized()

    def piece_rect(self, piece, pos):
        return piece.image_rect(self.square_size, self.screen_pos(pos))

    def draw_piece(self, piece, pos):
        piece_pos, piece_size = self.piece_rect(piece, pos)
        Rectangle(texture=piece.image(), pos=piece_pos, size=piece_size)

    def show_board(self):
        cols, see = self.board_info()

        self.canvas.clear()
        sq = (self.square_size-1, self.square_size-1)
        board_w = self.square_size * self.game.board_size[0]
        board_h = self.square_size * self.game.board_size[1]
        with self.canvas:
            Color(.03, .04, .04, .7)
            Rectangle(pos=(self.board_x - 8, self.board_y - 8), size=(board_w + 16, board_h + 16))
            Color(0, 0, 0, .16)
            Rectangle(pos=(self.board_x, self.board_y), size=(board_w, board_h))
            Color(.42, .72, .67, .55)
            Line(rectangle=(self.board_x, self.board_y, board_w, board_h), width=1)
            for (x, y), col in cols.items():
                sx, sy = self.screen_pos((x, y))
                Color(*[x/255 for x in col])
                Rectangle(pos=(sx, sy), size=sq)
                if (x, y) in self.game.board:
                    piece = self.game.board[x, y]
                    if self.game.board[x, y].freeze_until > self.game.counter:
                        freeze_ratio = (piece.freeze_until - self.game.counter) / piece.freeze_time
                        Color(.90, .73, .38, .72)
                        Rectangle(pos=(sx, sy), size=((self.square_size-1) * freeze_ratio, self.square_size-1))

            for pos, piece in sorted(self.game.board.items(), key=lambda item: -self.screen_pos(item[0])[1]):
                if pos not in see:
                    continue
                transparent = False
                if piece.last_move_time is not None:
                    move_time = (self.game.counter - piece.last_move_time)*0.1
                    if move_time < 1:
                        pos_between = move_time
                        if piece.last_pos is not None:
                            last_pos, _ = self.piece_rect(piece, piece.last_pos)
                            new_pos, piece_size = self.piece_rect(piece, pos)
                            Rectangle(
                                texture=piece.image(),
                                pos=[int(last_pos[i]+(new_pos[i]-last_pos[i])*pos_between) for i in range(2)],
                                size=piece_size)
                if piece is self.selected and self.game.active():
                    transparent = True
                Color(1, 1, 1, .5 if transparent else 1)
                self.draw_piece(piece, pos)

            if self.selected is not None and self.dst_pos is not None and self.game.active():
                Color(1, 1, 1, .5)
                self.draw_piece(self.selected, self.dst_pos)

            if self.is_dragging:
                x, y = self.raw_mouse_pos
                _, piece_size = self.piece_rect(self.selected, self.selected.pos)
                Color(1, 1, 1, .5)
                Rectangle(
                    texture=self.selected.image(),
                    pos=(x - piece_size[0] / 2, y - piece_size[1] / 2),
                    size=piece_size)

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
        for piece in list(self.game.board.values()):
            if player is not None and piece.side() != player%2:
                continue
            see.add(piece.pos)
            moves = set()
            if self.can_control(piece):
                moves = set(piece.moves())
                for dst in piece.base_moves():
                    if dst in moves:
                        continue
                    threat = self.game.threatening_piece_after_move(piece, dst)
                    if threat is not None:
                        see.add(threat.pos)
                        movesee[threat.pos] = threat.sight_color
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
            cols[pos] = (214, 205, 184)
        for pos, col in movesee.items():
            cols[pos] = [118+a*92./max(col) for a in col]
        for pos, col in flash.items():
            cols[pos] = [118+126*x for x in col]

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
        board_pos = [int((x - sx) // self.square_size) for x, sx in zip(pos, (self.board_x, self.board_y))]
        if (self.game.player() or 0) % 2 == 1:
            board_pos = [s-1-x for x, s in zip(board_pos, self.game.board_size)]
        self.mouse_pos = tuple(board_pos)

    def screen_pos(self, pos):
        if (self.game.player() or 0) % 2 == 1:
            pos = [s-1-x for x, s in zip(pos, self.game.board_size)]
        return tuple(sx+self.square_size*x for x, sx in zip(pos, (self.board_x, self.board_y)))

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
        for piece in list(self.game.board.values()):
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
