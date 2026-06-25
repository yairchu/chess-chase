import random
import socket
import unittest
import marshal
import time
import urllib.error
from unittest import mock

from game_model import GameModel
from net_engine import NetEngine, format_addr, parse_addr
import chess

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
        self.assertEqual(parse_addr('[2001:db8::1]:1234'), ('2001:db8::1', 1234))
        self.assertEqual(format_addr(('2001:db8::1', 1234)), '[2001:db8::1]:1234')

    def test_add_peers_json_groups_candidates(self):
        engine = NetEngine(GameModel())
        engine.address = 'room words'
        engine.my_addr = ('203.0.113.1', 1234)
        engine.local_addr = ('192.168.1.10', 1234)
        engine.add_peers_json('[["203.0.113.1:1234", "10.0.0.10:1234"], ["203.0.113.2:5678", "192.168.1.20:5678", "[2001:db8::2]:5678"]]')
        self.assertEqual(engine.peers, [[('203.0.113.2', 5678), ('192.168.1.20', 5678), ('2001:db8::2', 5678)]])
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

    def test_game_starts_after_direct_udp_packet(self):
        engine = NetEngine(GameModel())
        engine.game.mode = 'connect'
        engine.my_addr = ('203.0.113.1', 1234)
        engine.local_addr = ('192.168.1.10', 1234)
        engine.add_peers_json('[["203.0.113.2:5678"]]')

        self.assertEqual(engine.game.mode, 'connect')

        engine.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(engine.socket.close)
        engine.socket.bind(('127.0.0.1', 0))

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(sender.close)
        sender.sendto(marshal.dumps((123, [])), engine.socket.getsockname())
        engine.communicate()

        self.assertEqual(engine.game.mode, 'play')
        self.assertIn('Direct UDP communication established!', engine.game.messages)

    def test_connect_falls_back_to_lookup_when_room_already_joined(self):
        class Response:
            def __init__(self, body):
                self.body = body.encode('utf-8')

            def read(self):
                return self.body

        engine = NetEngine(GameModel())
        engine.address = 'my room'
        engine.my_addr = ('203.0.113.1', 1234)
        engine.local_addr = ('192.168.1.10', 1234)

        def fake_urlopen(url):
            if '/connect2/' in url:
                raise urllib.error.HTTPError(url, 500, 'AssertionError', {}, None)
            if '/lookup2/' in url:
                return Response('[["203.0.113.2:5678"]]')
            raise AssertionError(url)

        with mock.patch('net_engine.urlopen', fake_urlopen):
            engine.connect_thread_go('their room')

        self.assertEqual(engine.peers, [[('203.0.113.2', 5678)]])
        self.assertIn('Trying direct UDP communication...', engine.game.messages)

    def test_stopped_connect_thread_exits_before_address_registration(self):
        engine = NetEngine(GameModel())
        engine.should_stop = True
        engine.connect_thread_go('SOME GAME')

    def test_en_passant_before_player_has_moved(self):
        game = GameModel()
        game.init()
        white_pawn = game.board.pop((2, 1))
        black_pawn = game.board.pop((1, 6))
        white_pawn.pos = (2, 4)
        black_pawn.pos = (1, 4)
        black_pawn.last_move_time = 10
        game.board[white_pawn.pos] = white_pawn
        game.board[black_pawn.pos] = black_pawn
        game.player_last_move = {black_pawn.player: 10}

        list(white_pawn.sight())

    def test_king_cannot_move_into_threat(self):
        game = GameModel()
        game.init()
        game.board = {}
        king = chess.King(0, (3, 0), game)
        chess.Rook(1, (4, 7), game)

        self.assertNotIn((4, 0), list(king.moves()))

    def test_piece_cannot_expose_king(self):
        game = GameModel()
        game.init()
        game.board = {}
        chess.King(0, (4, 0), game)
        rook = chess.Rook(0, (4, 1), game)
        chess.Rook(1, (4, 7), game)

        self.assertNotIn((5, 1), list(rook.moves()))
        self.assertIn((4, 2), list(rook.moves()))

    def test_pawns_do_not_threaten_forward(self):
        game = GameModel()
        game.init()
        game.board = {}
        chess.King(0, (4, 3), game)
        chess.Pawn(1, (4, 4), game)

        self.assertIsNone(game.threatening_piece(0, (4, 3)))

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
