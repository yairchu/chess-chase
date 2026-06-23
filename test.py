import random
import socket
import unittest
import marshal
import time

from game_model import GameModel
from net_engine import NetEngine, parse_addr

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
    def test_parse_addr(self):
        self.assertEqual(parse_addr('127.0.0.1:1234'), ('127.0.0.1', 1234))

    def test_add_peers_json_groups_candidates(self):
        engine = NetEngine(GameModel())
        engine.address = 'room words'
        engine.my_addr = ('203.0.113.1', 1234)
        engine.local_addr = ('192.168.1.10', 1234)
        engine.add_peers_json('[["203.0.113.1:1234", "10.0.0.10:1234"], ["203.0.113.2:5678", "192.168.1.20:5678"]]')
        self.assertEqual(engine.peers, [[('203.0.113.2', 5678), ('192.168.1.20', 5678)]])
        self.assertEqual(engine.peer_count, 1)
        self.assertIn('Trying direct UDP communication...', engine.game.messages)
        self.assertIn('Your address is still: ROOM WORDS', engine.game.messages)
        self.assertNotIn('Direct UDP communication established!', engine.game.messages)

    def test_udp_success_message_waits_for_packet(self):
        engine = NetEngine(GameModel())
        engine.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(engine.socket.close)
        engine.socket.bind(('127.0.0.1', 0))

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(sender.close)
        packet = marshal.dumps((123, []))
        sender.sendto(packet, engine.socket.getsockname())

        for _ in range(100):
            engine.communicate()
            if 'Direct UDP communication established!' in engine.game.messages:
                break
            time.sleep(0.01)

        self.assertIn('Direct UDP communication established!', engine.game.messages)

    def test_stopped_connect_thread_exits_before_address_registration(self):
        engine = NetEngine(GameModel())
        engine.should_stop = True
        engine.connect_thread_go('SOME GAME')

    def test_sync(self):
        instances = [GameInstance() for _ in range(2)]
        for i in range(2):
            other = 1-i
            instances[i].net_engine.peers = [[('127.0.0.1', instances[other].port)]]
            instances[i].net_engine.peer_count = 1
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
