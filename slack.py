import websocket
import requests

import json
from threading import Timer


class EventFilter(object):
    def _inv_match(self, data):
        return not self._inv_match_func(data)

    def __init__(self, match_func=lambda x: True, invert=False):
        super(EventFilter, self).__init__()
        if invert:
            self.match_func = self._inv_match
            self._inv_match = match_func
        else:
            self.match_func = match_func
        self._attach = []
        self._attachprime = []

    def attach(self, callback, prime=False):
        if prime:
            self._attachprime.append(callback)
            return
        self._attach.append(callback)

    def dispatch(self, data):
        if self.match_func(data):
            for atch in self._attach:
                atch(data)
        else:
            for atch in self._attachprime:
                atch(data)


class Slack(object):
    def __init__(self, team, email=None, passw=None, token=None,
                 useragent="Mozilla/5.0 PySlack Client"):
        self.connected = False
        self.team_url = 'https://' + team + '.slack.com'
        self.ok = True
        self.userAgent = useragent
        self.events = EventFilter()
        if token is not None:
            self.token = token
            print('connecting')
            self._connect()
            print('logging in')
            self._boot_data = self.do_api('rtm.start', {})
        else:
            print('connecting')
            self.userAgent += " Like Gecko"  # makes sure were not nudged off
            self._connect()
            if not self.ok:
                return
            print('logging in')
            self._login(email, passw)
            if not self.ok:
                return

        self.parse_boot_data()
        self.setup_ws()
        if not self.ok:
            return
        self.setup_ping()
        if not self.ok:
            return
        self.status = 'ok'
        self.connected = True

    def do_api(self, method, args):
        """perform an api method"""
        args.update({'token:', self.token})
        return self._send_unauth_api(method, args)

    def _send_unauth_api(self, method, args):
        return self._s.post(self.team_url + '/api/' + method, data=args).json()

    def _connect(self):
        self._s = requests.Session()
        if self._s:
            self._s.headers.update({'User-Agent':
                                    self.userAgent})
            return
        self.ok = False
        self.status = 'failed to establish a session'

    def _get_sub(self, string, start, end):
        string = string[string.find(start) + len(start):]
        return string[:string.find(end)]

    def _login(self, email, passw):
        first = self._s.get(self.team_url).text
        self._team = self._get_sub(first, 'Bugsnag.metaData.team = ', ';')
        self._team = json.loads(self._team.replace('id', '"id"')
                                          .replace('name', '"name"')
                                          .replace('domain', '"domain"'))
        crumb = self._get_sub(first, 'name="crumb" value="', '"')

        resp = self._send_unauth_api('auth.findUser', {
            'email': email,
            'team': self._team['id'],
        })
        if resp['ok'] is not True:
            self.ok = False
            self.status = resp['error']
            return
        self._user = {'name': resp['user'], 'id': resp['user_id']}

        data = {
            'redir': 1,
            'signin': 1,
            'remember': 'off',
            'email': email,
            'password': passw,
            'crumb': crumb,
        }
        second = self._s.post(self.team_url, data).text
        self._boot_data = json.loads(self._get_sub(second,
                                                   'boot_data.login_data = ',
                                                   ';'))
        if self._boot_data['ok'] is not True:
            self.ok = False
            self.status = self._boot_data['error']
            return

    def parse_boot_data(self):
        self._ws_url = self._boot_data['url']

    def _message(self, message):
        print(message)
        if 'ok' in message and message['ok'] is not True:
            print(message['error'])
            return
        if 'reply_to' in message:
            if message['reply_to'] in self.track:
                self.track.remove(message['reply_to'])
            print(len(self.track))
            return
        self.events.dispatch(message)

    def setup_ws(self):
        self.ws = websocket.create_connection(self._ws_url)
        self.track = []
        self.nid = 1

    def _get_next_id(self):
        temp = self.nid
        self.nid += 1
        return temp

    def send_event(self, event_type, data=None, track=False):
        eid = self._get_next_id()
        if track:
            self.track.append(eid)
        args = {
            'type': event_type,
            'id': eid,
        }
        if data:
            args.update(data)
        self.ws.send(json.dumps(args))

    def _send_ping(self):
        Timer(5.00, self._send_ping).start()
        self.send_event("ping", track=True)

    def setup_ping(self):
        Timer(5.00, self._send_ping).start()

    def pass_control(self):
        while True:
            self._message(json.loads(self.ws.recv()))
