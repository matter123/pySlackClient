import websocket
import requests

import json
import threading.Timer as Timer


class Slack(object):
    def __init__(self, team, email=None, passw=None, token=None,
    	         userAgent="Mozilla/5.0 PySlack Client"):
        self.team_url = 'https://' + team + '.slack.com'
        self.ok = True
        self.userAgent = userAgent
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

    def setup_ws(self):
        self.ws = websocket.create_connection(self._ws_url)

    def sendEvent(self, Type, data=None, track=False):
    	eid = self.getNextId()
    	self.ws.send(json.dumps({
    			'type': Type,
    			'id': eid
    		}))

    def _send_ping(self):
    	Timer(2.00, send_ping).start()
    	self.send_event("ping", track=True)

    def setup_ping(self):
        Timer(2.00, self._send_ping).start()
