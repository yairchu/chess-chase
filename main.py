'''
A networked real-time strategy game based on Chess
'''

import os
import argparse
import sys

os.environ.setdefault('KIVY_NO_ARGS', '1')

def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--dev-state', choices=['menu', 'setup', 'tutorial', 'play', 'demo'], default='menu')
    parser.add_argument('--screenshot', help='write a PNG after opening the requested dev state')
    parser.add_argument('--window-size', default='1200x800', help='WIDTHxHEIGHT for dev screenshots')
    parser.add_argument('--exit-after', type=float, default=0.5, help='seconds to wait before screenshot/exit')
    return parser.parse_known_args(argv)[0]

args = parse_args(sys.argv[1:])
if args.screenshot:
    os.environ['CHESSCHASE_DEV'] = '1'

import ssl_certs

ssl_certs.configure_certifi()

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.config import Config
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

import env
from board_view import BoardView
from game_model import GameModel
from net_engine import NetEngine
from widgets import WrappedLabel, WrappedButton

num_msg_lines = 3 if env.is_mobile else 8
TEXT_COLOR = (.92, .94, .92, 1)
MUTED_TEXT_COLOR = (.72, .76, .74, 1)
BUTTON_COLOR = (.20, .22, .22, 1)
PRIMARY_BUTTON_COLOR = (.16, .39, .36, 1)

def style_button(button, primary=False):
    button.background_normal = ''
    button.background_down = ''
    button.background_color = PRIMARY_BUTTON_COLOR if primary else BUTTON_COLOR
    button.color = TEXT_COLOR
    button.font_size = '22sp'
    button.bold = True
    button.valign = 'middle'
    return button

class RecentMovesView(Widget):
    def __init__(self, game, **kwargs):
        super().__init__(**kwargs)
        self.game = game
        self.size_hint = (1, 0)
        self.size_hint_min_y = 112

    def show(self):
        pieces = [
            piece for piece in self.game.board.values()
            if piece.last_move_time is not None
        ]
        pieces.sort(key=lambda piece: piece.last_move_time, reverse=True)
        pieces = pieces[:6]

        self.canvas.clear()
        if not pieces:
            return

        with self.canvas:
            label = CoreLabel(text='Last moved', font_size=24, color=MUTED_TEXT_COLOR)
            label.refresh()
            pad = 14
            gap = 8
            icon = max(32, min(58, (self.width - pad * 2) / len(pieces) - gap))
            width = len(pieces) * icon + (len(pieces) - 1) * gap
            x = self.x + max(pad, (self.width - width) / 2)
            y = self.y + 14

            Color(*MUTED_TEXT_COLOR)
            Rectangle(texture=label.texture, pos=(x, y + icon + 6), size=label.texture.size)

            for piece in pieces:
                remaining = max(
                    piece.freeze_until,
                    self.game.player_last_move.get(piece.player, 0) + self.game.player_freeze_time,
                ) - self.game.counter
                total = max(piece.freeze_time, self.game.player_freeze_time, 1)
                ratio = max(0, min(1, remaining / total))

                Color(.86, .89, .86, 1)
                Rectangle(pos=(x - 4, y - 8), size=(icon + 8, icon + 14))
                Color(1, 1, 1, 1)
                Rectangle(texture=piece.image(), pos=(x, y), size=(icon, icon))
                Color(.18, .55, .50, 1)
                Rectangle(pos=(x, y - 8), size=(icon * ratio, 5))
                x += icon + gap

class Game(BoxLayout):
    game_title = 'Chess Chase: No turns, no sight!'

    def __init__(self, **kwargs):
        super(Game, self).__init__(**kwargs)
        self.game_model = GameModel()
        self.game_model.king_captured = self.king_captured
        self.game_model.on_message.append(self.update_label)
        self.net_engine = NetEngine(self.game_model)

        self.score = [0, 0]

        self.board_view = BoardView(self.game_model)
        self.recent_moves_view = RecentMovesView(self.game_model)
        self.game_model.on_init.append(self.board_view.reset)
        self.game_model.on_init.append(self.on_game_init)

        self.info_pane = BoxLayout(
            orientation='vertical',
            size_hint_min_y=500,
            padding=[28, 18, 28, 18],
            spacing=12)

        row_args = {'size_hint': (1, 0), 'size_hint_min_y': 70}

        self.title_label = WrappedLabel(
            halign='center',
            text=self.game_title,
            color=TEXT_COLOR,
            font_size='24sp',
            bold=True,
            **row_args)
        if not env.is_mobile:
            self.info_pane.add_widget(self.title_label)

        self.button_pane = BoxLayout(orientation='vertical', size_hint=(1, .4), spacing=12)
        self.info_pane.add_widget(self.button_pane)

        self.button_pane.add_widget(style_button(WrappedButton(
            halign='center',
            text='Tutorial: How to play',
            on_press=self.start_tutorial)))
        self.button_pane.add_widget(style_button(WrappedButton(
            halign='center',
            text='Start Game' if env.is_mobile else 'Start Game: Play with friends',
            on_press=self.start_game), primary=True))
        self.menu_button = style_button(WrappedButton(
            halign='center',
            size_hint=(1, 0),
            size_hint_min_y=58,
            text='Menu',
            on_press=self.show_menu))

        self.score_label = WrappedLabel(
            halign='center',
            color=MUTED_TEXT_COLOR,
            font_size='21sp',
            **row_args)
        self.info_pane.add_widget(self.score_label)

        self.label = WrappedLabel(
            halign='center',
            valign='middle',
            color=TEXT_COLOR,
            font_size='21sp')
        self.info_pane.add_widget(self.label)

        self.text_input = TextInput(
            multiline=False,
            text_validate_unfocus=env.is_mobile,
            background_color=(.92, .94, .92, 1),
            foreground_color=(.06, .07, .07, 1),
            cursor_color=(.16, .39, .36, 1),
            font_size='22sp',
            padding=[14, 14, 14, 14],
            **row_args)
        self.text_input.bind(on_text_validate=self.handle_text_input)
        if env.is_mobile:
            self.text_input.keyboard_mode = 'managed'
            def on_focus(*args):
                if self.text_input.focus:
                    self.text_input.show_keyboard()
        else:
            def on_focus(*args):
                if not self.text_input.focus:
                    # Steal focus
                    self.text_input.focus = True
        self.text_input.bind(focus=on_focus)
        self.info_pane.add_widget(self.text_input)

        self.game_model.add_message('')
        self.game_model.add_message(self.game_title if env.is_mobile else 'Welcome to Chess Chase!')

        self.bind(size=self.resized)
        self.refresh_layout()
        Clock.schedule_interval(self.on_clock, 1/30)

    @mainthread
    def on_game_init(self):
        self.refresh_layout()
        if env.is_mobile and self.game_model.mode == 'play':
            self.text_input.hide_keyboard()

    def screen(self):
        if self.game_model.mode in ['tutorial', 'play', 'demo', 'replay']:
            return 'game'
        if self.game_model.mode == 'connect':
            return 'setup'
        return 'menu'

    def refresh_layout(self):
        screen = self.screen()
        if screen == 'game':
            self.orientation = 'horizontal' if self.size[0] > self.size[1] else 'vertical'

        self.clear_widgets()
        self.info_pane.clear_widgets()
        if screen == 'game':
            if self.orientation == 'vertical':
                self.add_widget(self.recent_moves_view)
            self.add_widget(self.board_view)
        self.add_widget(self.info_pane)

        if not env.is_mobile and screen != 'game':
            self.info_pane.add_widget(self.title_label)
        if screen == 'menu':
            self.info_pane.add_widget(self.button_pane)
            self.info_pane.add_widget(self.label)
            self.text_input.focus = False
        else:
            self.info_pane.add_widget(self.menu_button)
            if screen == 'game':
                if self.orientation == 'horizontal':
                    self.info_pane.add_widget(self.recent_moves_view)
                self.info_pane.add_widget(self.score_label)
            self.info_pane.add_widget(self.label)
            self.info_pane.add_widget(self.text_input)
        self.resized()

    def show_menu(self, _=None):
        if env.is_mobile:
            self.text_input.hide_keyboard()
        self.stop_net_engine()
        self.game_model.mode = None
        self.game_model.messages.clear()
        self.game_model.add_message('')
        self.game_model.add_message(self.game_title if env.is_mobile else 'Welcome to Chess Chase!')
        self.refresh_layout()

    def stop_net_engine(self):
        if not self.net_engine:
            return
        self.net_engine.should_stop = True

    def restart_net_engine(self):
        self.stop_net_engine()
        self.net_engine = NetEngine(self.game_model)

    def start_game(self, _):
        self.text_input.focus = True
        if env.is_mobile:
            self.text_input.show_keyboard()
        self.game_model.mode = 'connect'
        self.refresh_layout()
        self.score = [0, 0]
        self.restart_net_engine()
        self.game_model.messages.clear()
        self.game_model.add_message('Establishing server connection...')
        self.game_model.init()
        self.net_engine.start()

    def start_tutorial(self, i):
        if env.is_mobile:
            self.text_input.hide_keyboard()
        self.game_model.mode = 'tutorial'
        self.game_model.reset()
        self.restart_net_engine()
        self.game_model.messages.clear()
        self.game_model.add_message('Move the chess pieces and see what happens!')
        self.game_model.tutorial_messages = [
            'Keep moving the pieces at your own pace.',
            'Each piece has its own color, and the board is painted to show where it can move.',
            'You only see where your pieces can move',
            'You will also see any piece that threatens the king.',
            'Note that unlike classic chess, the king can move to a threatened position!',
            'There are no turns!',
            'There are cool-downs (rate limits) instead.',
            'You win the game by capturing the opponent king',
            'The game is played with friends over the internet.',
            'To start a game both you and your friend need to click "Start Game".',
            'Then either you or the friend should type the game identifier that the other was given.',
            'This concludes our tutorial!',
            ]
        self.game_model.init()
        self.refresh_layout()
        self.game_model.players[self.game_model.my_id] = 0
        self.net_engine.iter_actions = {}

    def update_label(self):
        self.score_label.text = 'White: %d   Black: %d' % tuple(self.score)
        self.label.text = '\n'.join(self.game_model.messages[-num_msg_lines:])

    def resized(self, *args):
        if self.screen() != 'game':
            self.info_pane.size_hint = (1, 1)
            self.button_pane.orientation = 'vertical'
            self.button_pane.size_hint = (1, .35)
            self.button_pane.size_hint_min_y = 140
            return

        orientation = 'horizontal' if self.size[0] > self.size[1] else 'vertical'
        if self.orientation != orientation:
            self.orientation = orientation
            self.refresh_layout()
            return
        p = 1/3
        if self.orientation == 'horizontal':
            self.info_pane.size_hint = (p, 1)
            self.board_view.size_hint = (self.game_model.num_boards, 1)
            self.button_pane.orientation = 'vertical'
            self.button_pane.size_hint = (1, .4)
            self.button_pane.size_hint_min_y = 140
        else:
            self.info_pane.size_hint = (1, p)
            self.board_view.size_hint = (1, 1 / self.game_model.num_boards)
            self.recent_moves_view.size_hint = (1, 0)
            self.recent_moves_view.size_hint_min_y = 112
            self.button_pane.orientation = 'horizontal'
            self.button_pane.size_hint = (1, .4)
            self.button_pane.size_hint_min_y = 70

    def handle_text_input(self, entry):
        if env.is_mobile:
            self.text_input.hide_keyboard()
        command = entry.text
        entry.text = ''
        if not command:
            return
        if command[:1] == '/':
            if command == '/help':
                self.game_model.help()
                return
            self.game_model.add_action(*command[1:].split())
            return
        if self.game_model.mode in [None, 'connect']:
            self.net_engine.connect(command)
            return
        # Chat
        self.game_model.add_action('msg', command)

    def king_captured(self, who):
        if self.game_model.mode == 'replay':
            return
        winner = 1 - who%2
        self.score[winner] += 1
        self.game_model.add_message('')
        self.game_model.add_message('%s King Captured!' % self.game_model.player_str(who))
        self.game_model.add_message('%s wins!' % self.game_model.player_str(winner))
        self.net_engine.start_replay()

    def on_clock(self, _interval):
        self.net_engine.iteration()
        self.board_view.update_dst()
        self.board_view.show_board()
        self.recent_moves_view.show()

class ChessChaseApp(App):
    def __init__(self, dev_args=None, **kwargs):
        super().__init__(**kwargs)
        self.dev_args = dev_args

    def build(self):
        self.game = Game()
        if not env.is_mobile:
            self.game.text_input.focus = True
        if self.dev_args and (self.dev_args.screenshot or self.dev_args.dev_state != 'menu'):
            Clock.schedule_once(self.enter_dev_state, 0)
        return self.game

    def enter_dev_state(self, _interval):
        if self.dev_args.dev_state == 'setup':
            self.game.start_game(None)
        elif self.dev_args.dev_state == 'tutorial':
            self.game.start_tutorial(None)
            self.seed_recent_moves()
        elif self.dev_args.dev_state == 'play':
            self.game.game_model.mode = 'play'
            self.game.game_model.players[self.game.game_model.my_id] = 0
            self.game.game_model.init()
            self.game.game_model.messages.clear()
            self.game.game_model.add_message('Dev game preview')
            self.seed_recent_moves()
            self.game.refresh_layout()
        elif self.dev_args.dev_state == 'demo':
            self.game.game_model.mode = 'demo'
            self.game.game_model.players[self.game.game_model.my_id] = 0
            self.game.game_model.init()
            self.game.game_model.messages.clear()
            self.game.game_model.add_message('Dev demo: control both sides')
            if self.dev_args.screenshot:
                self.seed_recent_moves()
            self.game.refresh_layout()
        if self.dev_args.screenshot:
            Clock.schedule_once(self.save_screenshot, self.dev_args.exit_after)

    def seed_recent_moves(self):
        self.game.game_model.counter = 100
        pieces = []
        for player in range(2):
            pieces.extend(sorted(
                (piece for piece in self.game.game_model.board.values() if piece.player == player),
                key=lambda piece: piece.pos)[:3])
        for i, piece in enumerate(pieces):
            piece.freeze_time = 80
            piece.last_move_time = 100 - (i + 1) * 12
            piece.freeze_until = piece.last_move_time + piece.freeze_time

    def save_screenshot(self, _interval):
        self.game.on_clock(0)
        self.game.export_to_png(self.dev_args.screenshot)
        self.stop()
    def stop(self):
        self.game.stop_net_engine()
        super().stop()

if __name__ == '__main__':
    Config.set('input', 'mouse', 'mouse,multitouch_on_demand')
    Window.softinput_mode = 'pan'
    Window.clearcolor = (.04, .05, .05, 1)
    if args.screenshot:
        Window.size = tuple(map(int, args.window_size.lower().split('x', 1)))
    ChessChaseApp(args).run()
