import json
import marshal
import random
import select
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import stun

import env

MATCH_SERVER = 'https://game-match-server.yairchu.workers.dev'
STUN_SERVERS = [
    ('stun.l.google.com', 19302),
    ('stun1.l.google.com', 19302),
    ('stun2.l.google.com', 19302),
    ('stun3.l.google.com', 19302),
    ('stun4.l.google.com', 19302),
]

def poll(sock):
    return select.select([sock], [], [], 0)[0] != []

def any_actions(actions):
    return any(acts for _, acts in actions)

def urlopen(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Chess-Chase/0.1'})
    return urllib.request.urlopen(req, timeout=10)

def quote_path(value):
    return urllib.parse.quote(value, safe='')

def get_lan_ipv4():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('8.8.8.8', 80))
        return sock.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        sock.close()

def get_lan_ipv6():
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    try:
        sock.connect(('2001:4860:4860::8888', 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()

def format_addr(addr):
    host, port = addr
    return '[%s]:%d' % (host, port) if ':' in host else '%s:%d' % (host, port)

def parse_addr(value):
    if value.startswith('['):
        host, port_str = value[1:].rsplit(']:', 1)
        return host, int(port_str)
    host, port_str = value.rsplit(':', 1)
    return host, int(port_str)

class NetEngine:
    latency = 5
    replay_max_wait = 30

    def __init__(self, game_model):
        self.game = game_model
        self.socket = None
        self.threads = []
        self.reset()
        self.game.my_id = random.randrange(2**64)

    def reset(self):
        self.peers = []
        self.peer_count = 0
        self.address = None
        self.last_comm_time = None
        self.had_peer_packet = False
        self.my_addrs = []
        self.sockets = []
        self.comm_gap_msg_at = 10
        self.should_start_replay = False
        self.iter_actions = {}

    def start(self):
        self.game.reset()
        self.should_stop = False
        net_thread = threading.Thread(target=self.net_thread_go, daemon=True)
        self.threads.append(net_thread)
        if not env.dev_mode:
            net_thread.start()

    def net_thread_go(self):
        if not self.setup_socket():
            return
        if not self.setup_addr_name():
            return
        self.wait_for_connections()

    def setup_socket(self):
        self.game.add_message('Finding public UDP address...')
        while True:
            local_port = random.randint(1024, 65535)
            for stun_host, stun_port in STUN_SERVERS:
                if self.should_stop:
                    return False
                try:
                    _nat_type, gamehost, gameport = stun.get_ip_info(
                        '0.0.0.0',
                        local_port,
                        stun_host=stun_host,
                        stun_port=stun_port)
                    if gameport is None:
                        print('retrying stun connection')
                        continue
                    self.my_addr = (gamehost, gameport)
                    self.local_addr = (get_lan_ipv4(), local_port)
                    self.local_ipv6_addr = None
                    self.game.add_message('Public UDP address: %s' % format_addr(self.my_addr))
                    self.game.add_message('Local UDP address: %s' % format_addr(self.local_addr))
                    print('external host %s' % format_addr(self.my_addr))
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.bind(('', local_port))
                    print('listening on port %d' % local_port)
                    self.socket = sock
                    self.sockets = [sock]
                    ipv6 = get_lan_ipv6()
                    if ipv6:
                        try:
                            sock6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                            sock6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                            sock6.bind(('::', local_port))
                            self.local_ipv6_addr = (ipv6, local_port)
                            self.sockets.append(sock6)
                            self.game.add_message('Local IPv6 UDP address: %s' % format_addr(self.local_ipv6_addr))
                        except OSError as err:
                            print('IPv6 UDP unavailable: %s' % err)
                    self.my_addrs = [self.my_addr, self.local_addr]
                    if self.local_ipv6_addr:
                        self.my_addrs.append(self.local_ipv6_addr)
                    return True
                except socket.error as err:
                    self.game.add_message('Network setup failed; retrying: %s' % err)
                    print('retrying establishing server')
                    continue
            self.game.add_message('STUN failed; retrying...')

    def setup_addr_name(self):
        self.game.add_message('Registering with match server...')
        try:
            self.address = self.register_addrs()
        except urllib.error.HTTPError as err:
            self.game.add_message('Match server rejected registration: HTTP %d' % err.code)
            return False
        except Exception as err:
            self.game.add_message('Match server registration failed: %s' % err)
            return False
        self.game.add_message('')
        self.game.add_message('Your address is:')
        self.game.add_message(self.address.upper())
        self.game.add_message('')
        self.game.add_message('Type the address of a friend to play with them')
        return True

    def register_addrs(self):
        candidates = [format_addr(addr) for addr in self.my_addrs]
        url = MATCH_SERVER + '/register3/chesschase0/%s/' % quote_path(json.dumps(candidates, separators=(',', ':')))
        print('registering at %s' % url)
        try:
            return urlopen(url).read().decode('utf-8')
        except urllib.error.HTTPError as err:
            if err.code != 404:
                raise
        url = MATCH_SERVER + '/register2/chesschase0/%s/%d/%s/' % (
            quote_path(self.my_addr[0]), self.my_addr[1], quote_path(self.local_addr[0]))
        print('registering at %s' % url)
        return urlopen(url).read().decode('utf-8')

    def wait_for_connections(self):
        while not self.peers:
            time.sleep(5)
            if self.should_stop:
                return
            url = MATCH_SERVER + '/lookup2/chesschase0/%s/' % quote_path(self.address)
            print('checking game at %s' % url)
            try:
                self.add_peers_json(urlopen(url).read().decode('utf-8'))
            except Exception as err:
                self.game.add_message('Match server lookup failed: %s' % err)

    def connect(self, address):
        connect_thread = threading.Thread(target=self.connect_thread_go, args=(address, ), daemon=True)
        self.threads.append(connect_thread)
        connect_thread.start()

    def connect_thread_go(self, addr):
        self.game.add_message('Establishing connection with: %s' % addr)
        while self.address is None:
            if self.should_stop:
                return
            # Net thread didn't finish
            time.sleep(1)
        self.game.add_message('Your address is still: %s' % self.address.upper())
        url = MATCH_SERVER + '/connect2/chesschase0/%s/%s/' % (
            quote_path(self.address), quote_path(addr.lower()))
        print('looking up host at %s' % url)
        try:
            response = urlopen(url).read()
        except urllib.error.HTTPError as err:
            if err.code == 404:
                self.game.add_message('No such game: %s' % addr)
            else:
                self.game.add_message('Server error when looking up game: %s' % addr)
            return
        except Exception as err:
            self.game.add_message('Match server connection failed: %s' % err)
            return
        self.add_peers_json(response.decode('utf-8'))

    def add_peers_json(self, peers_json):
        for addresses in json.loads(peers_json):
            peer = [parse_addr(address) for address in addresses]
            if any(address in self.own_addrs() for address in peer):
                continue
            if peer in self.peers:
                continue
            print('established connection with %s' % peer)
            self.peers.append(peer)
            self.peer_count += 1
            self.game.messages.clear()
            self.game.add_message('')
            self.game.add_message('Peer found by match server.')
            self.game.add_message('Trying direct UDP communication...')
            if self.address:
                self.game.add_message('Your address is still: %s' % self.address.upper())
            self.game.mode = 'play'
            self.game.init()
            self.last_comm_time = time.time()
            self.comm_gap_msg_at = 10

    def communicate(self):
        if self.socket is None:
            return
        packet = marshal.dumps((
            self.game.my_id,
            [(i, self.iter_actions.setdefault(i, {}).setdefault(self.game.my_id, []))
                for i in
                range(
                    max(0, self.game.counter-self.latency),
                    self.game.counter+self.latency)]))
        for peer in self.peers:
            for address in peer:
                sock = self.socket_for(address)
                if sock is None:
                    continue
                try:
                    sock.sendto(packet, 0, self.socket_addr(address))
                except OSError as err:
                    print('failed sending to %s: %s' % (format_addr(address), err))
        for sock in self.sockets or [self.socket]:
            while poll(sock):
                self.last_comm_time = time.time()
                packet, peer = sock.recvfrom(0x1000)
                if not self.had_peer_packet:
                    self.had_peer_packet = True
                    self.game.messages.clear()
                    self.game.add_message('')
                    self.game.add_message('Direct UDP communication established!')
                    self.game.add_message('THE GAME BEGINS!')
                peer_id, peer_iter_actions = marshal.loads(packet)
                for i, actions in peer_iter_actions:
                    acts = self.iter_actions.setdefault(i, {})
                    if peer_id in acts:
                        assert acts[peer_id] == actions, '%s %s' % (acts[peer_id], actions)
                    else:
                        acts[peer_id] = actions

        if self.last_comm_time is None:
            return
        time_since_comm = time.time() - self.last_comm_time
        if time_since_comm >= self.comm_gap_msg_at:
            if self.had_peer_packet:
                self.game.add_message('No communication for %d seconds' % self.comm_gap_msg_at)
            else:
                self.game.add_message('Waiting for direct UDP packets for %d seconds' % self.comm_gap_msg_at)
            self.comm_gap_msg_at += 5
        elif time_since_comm < 5:
            self.comm_gap_msg_at = 5

    def socket_for(self, address):
        host, _port = address
        if ':' in host:
            return self.sockets[1] if len(self.sockets) > 1 else None
        return self.socket

    def socket_addr(self, address):
        host, port = address
        return (host, port, 0, 0) if ':' in host else address

    def own_addrs(self):
        if self.my_addrs:
            return self.my_addrs
        return [addr for addr in [getattr(self, 'my_addr', None), getattr(self, 'local_addr', None)] if addr]

    def get_replay_actions(self):
        return sorted(self.iter_actions.get(self.game.counter, {}).items())

    def act(self):
        if self.game.mode == 'replay':
            all_actions = self.get_replay_actions()
            if any_actions(all_actions):
                self.replay_wait = 0
            else:
                self.game.counter += 1
                all_actions = self.get_replay_actions()
                self.replay_wait += 1
                if self.replay_wait == self.replay_max_wait:
                    self.replay_wait = 0
                    while not any_actions(all_actions) and self.game.counter+1 < self.replay_stop:
                        self.game.counter += 1
                        all_actions = self.get_replay_actions()
        elif self.game.active():
            if self.game.counter < self.latency:
                self.game.counter += 1
                return
            if len(self.iter_actions.get(self.game.counter, {})) <= self.peer_count:
                # We haven't got communications from all peers for this iteration.
                # So we'll wait.
                return
            all_actions = sorted(self.iter_actions[self.game.counter].items())
        else:
            return

        if self.game.counter == self.latency:
            # Assign players
            for player, i in enumerate(i for i, _ in all_actions):
                self.game.players[i] = player

        for i, actions in all_actions:
            for action_type, params in actions:
                action_func = getattr(self.game, 'action_'+action_type, None)
                if action_func is None:
                    self.game.add_message(action_type + ': no such action')
                else:
                    prev_messages = len(self.game.messages)
                    if env.dev_mode:
                        action_func(i, *params)
                    else:
                        try:
                            action_func(i, *params)
                        except:
                            self.game.add_message('action ' + action_type + ' failed')
                    if prev_messages == len(self.game.messages) and not getattr(action_func, 'quiet', False):
                        self.game.add_message('%s did %s' % (self.game.nick(i), action_type.upper()))

        self.game.counter += 1

        if self.game.mode == 'replay' and self.game.counter == self.replay_stop:
            self.game.mode = 'play'
            self.game.last_start = self.game.counter
            self.game.init()
        assert not self.game.mode == 'replay' or self.game.counter < self.replay_stop

        if self.should_start_replay:
            self.should_start_replay = False
            print('start replay!')
            self.game.mode = 'replay'
            self.replay_stop = self.game.counter
            self.game.counter = self.game.last_start
            self.replay_wait = 0
            self.game.init()

    def iteration(self):
        self.communicate()

        if self.game.mode != 'replay' and self.game.my_id not in self.iter_actions.setdefault(self.game.counter+self.latency, {}):
            self.iter_actions[self.game.counter+self.latency][self.game.my_id] = self.game.cur_actions
            self.game.cur_actions = []

        self.act()

    def start_replay(self):
        self.should_start_replay = True
