import chess
import env

class GameModel:
    player_freeze_time = 0 if env.dev_mode else 20

    def __init__(self):
        self.mode = None
        self.board = {}
        self.board_size = [4, 4]
        self.num_boards = 1
        self.messages = []
        self.on_message = []
        self.on_init = []
        self.players = {}
        self.my_id = None
        self.reset()
        chess.King(0, (3, 0), self)
        chess.King(1, (0, 3), self)

    def reset(self):
        self.counter = 0
        self.last_start = 0
        self.cur_actions = []
        self.nicknames = {}

    def add_message(self, msg):
        self.messages.append(msg)
        for x in self.on_message:
            x()

    def active(self):
        return self.mode in ['tutorial', 'play', 'demo']

    def player(self):
        return self.players.get(self.my_id)

    def init(self, num_boards=None):
        '''
        Initialize game.
        Can initialize with more game boards for more players!
        '''

        if num_boards is not None:
            self.num_boards = num_boards
        self.player_last_move = {}
        self.board = {}
        self.board_size = [8*self.num_boards, 8]
        self.num_players = self.num_boards * 2
        for who, (x, y0, y1) in enumerate([(0, 0, 1), (0, 7, 6), (8, 0, 1), (8, 7, 6)][:self.num_players]):
            for dx, piece in enumerate(chess.first_row):
                p = piece(who, (x+dx, y0), self)
                if piece == chess.King:
                    p.on_die = lambda who=who: self.king_captured(who)
                chess.Pawn(who, (x+dx, y1), self)
        for x in self.on_init:
            x()

    def in_bounds(self, pos):
        for x, s in zip(pos, self.board_size):
            if not (0 <= x < s):
                return False
        return True

    def king(self, player):
        for piece in self.board.values():
            if piece.player == player and isinstance(piece, chess.King):
                return piece

    def threatening_piece(self, player, king_pos):
        for piece in self.board.values():
            if piece.side() != player % 2 and king_pos in piece.attacks():
                return piece

    def threatening_piece_after_move(self, piece, dst):
        src = piece.pos
        captured = self.board.get(dst)
        en_passant_pos = None
        en_passant_piece = None
        if isinstance(piece, chess.Pawn) and captured is None and dst[0] != src[0]:
            en_passant_pos = dst[0], src[1]
            en_passant_piece = self.board.get(en_passant_pos)

        del self.board[src]
        piece.pos = dst
        self.board[dst] = piece
        if en_passant_piece is not None:
            del self.board[en_passant_pos]
        king = piece if isinstance(piece, chess.King) else self.king(piece.player)
        threat = self.threatening_piece(piece.player, king.pos) if king is not None else None
        del self.board[dst]
        piece.pos = src
        self.board[src] = piece
        if captured is not None:
            self.board[dst] = captured
        if en_passant_piece is not None:
            self.board[en_passant_pos] = en_passant_piece
        return threat

    def add_action(self, act_type, *params):
        'Queue an action to be executed'
        self.cur_actions.append((act_type, params))

    def nick(self, i):
        r = self.nicknames.get(i)
        if r:
            return r
        player = self.players.get(i)
        if player is None:
            return 'Spectator'
        return self.player_str(player)

    def action_msg(self, i, *txt):
        self.add_message('%s: %s' % (self.nick(i), ' '.join(txt)))

    def action_move(self, _id, src, dst):
        if src not in self.board:
            return
        piece = self.board[src]
        if piece.move(dst):
            if self.mode == 'tutorial' and self.tutorial_messages:
                self.add_message('')
                self.add_message(self.tutorial_messages.pop(0))
    action_move.quiet = True

    def action_surrender(self, i):
        player = self.players.get(i)
        if player is None:
            return
        self.add_message(self.nick(i) + ' surrendered')
        self.king_captured(player)

    def player_str(self, player):
        if player is None:
            return 'spectator'
        r = ['White', 'Black'][player%2]
        if self.num_boards > 1:
            r += '#'+str(player//2)
        return r

    def action_become(self, i, player):
        player = int(player)
        self.add_message(self.nick(i) + ' becomes ' + self.player_str(player))
        self.players[i] = player
        if i == self.my_id:
            for x in self.on_init:
                x()

    def action_credits(self, _nick):
        self.add_message('''
            Programming: Yair Chuchem
            Chess sets/Graphics: Cburnett
            github.com/yairchu/chess2
            ''')

    def action_nick(self, i, nick):
        self.add_message(self.nick(i) + ' renames to ' + nick)
        self.nicknames[i] = nick

    def help(self):
        self.add_message('')
        self.add_message('commands: /help | /nick <name> | /surrender | /credits')
        self.add_message('')
        latency = 5
        rate = 30
        def calc_cooldown(x):
            return (x+latency) / rate
        self.add_message(
            'Cool-downs: player %.1fs, piece %.1fs, king %.1fs, promotion %.1fs' % (
                calc_cooldown(self.player_freeze_time),
                calc_cooldown(chess.Piece.freeze_time),
                calc_cooldown(chess.King.freeze_time),
                calc_cooldown(chess.Pawn.egg_time),
            ))
