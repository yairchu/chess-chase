import random
import socket
import unittest

from game_model import GameModel
from net_engine import NetEngine

class GameInstance:
    def __init__(self):
        self.game = GameModel()
        self.game.king_captured = self.king_captured
        self.game.init()
        self.game.mode = 'play'
        self.game.add_message = print
        self.net_engine = NetEngine(self.game)
        self.init_net_engine_socket()

    def king_captured(self, who):
        if self.game.mode != 'replay':
            self.net_engine.start_replay()

    def init_net_engine_socket(self):
        while True:
            self.port = random.randint(1024, 65535)
            try:
                self.net_engine.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.net_engine.socket.bind(('127.0.0.1', self.port))
            except socket.error:
                print('retrying establishing server')
                continue
            break

class TestSync(unittest.TestCase):
    def test_stopped_connect_thread_exits_before_address_registration(self):
        engine = NetEngine(GameModel())
        engine.should_stop = True
        engine.connect_thread_go('SOME GAME')

    def test_sync(self):
        instances = [GameInstance() for _ in range(2)]
        for i in range(2):
            other = 1-i
            instances[i].net_engine.peers = [('127.0.0.1', instances[other].port)]
        for i in range(1000000):
            inst = random.choice(instances)
            r = random.random()
            if r < 0.3:
                inst.net_engine.iteration()
            elif r < 0.99999:
                if len(inst.game.cur_actions) > 3:
                    continue
                (src, piece) = random.choice(list(inst.game.board.items()))
                opts = list(piece.moves())
                if not opts:
                    continue
                dst = random.choice(opts)
                inst.game.add_action('move', src, dst)
            else:
                inst.game.add_action('surrender')

if __name__ == '__main__':
    unittest.main()
