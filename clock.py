import datetime
import json
import logging
import urllib
import urllib2

from google.appengine.ext import ndb
import pytz
import webapp2

import secrets


_SLACK_API_URL = 'https://slack.com/api/'


def hit_slack_api(method, data=None):
    if data is None:
        data = {}
    data['token'] = secrets.slack_bot_token
    data['as_user'] = True
    res = urllib2.urlopen(_SLACK_API_URL + method,
                          data=urllib.urlencode(data))
    decoded = json.loads(res.read())
    if not decoded['ok']:
        raise RuntimeError("not ok, slack said %s" % decoded)
    return decoded


ASCII_COLON = [' ', '.', '.']
ASCII_SPACE = [' ', ' ', ' ']


def ascii_digit(d):
    if d == 0:
        return [' _ ', '| |', '|_|']
    elif d == 1:
        return ['   ', '  |', '  |']
    elif d == 2:
        return [' _ ', ' _|', '|_ ']
    elif d == 3:
        return [' _ ', ' _|', ' _|']
    elif d == 4:
        return ['   ', '|_|', '  |']
    elif d == 5:
        return [' _ ', '|_ ', ' _|']
    elif d == 6:
        return [' _ ', '|_ ', '|_|']
    elif d == 7:
        return [' _ ', '  |', '  |']
    elif d == 8:
        return [' _ ', '|_|', '|_|']
    elif d == 9:
        return [' _ ', '|_|', '  |']
    else:
        raise ValueError


def ascii_concat(grids):
    return [''.join(grid[i] for grid in grids) for i in xrange(len(grids[0]))]


def ascii_clock(dt, twentyfour):
    if twentyfour:
        hh = dt.hour
    else:
        hh = dt.hour % 12
    mm = dt.minute
    return '\n'.join(ascii_concat([
        ascii_digit(hh / 10),
        ASCII_SPACE,
        ascii_digit(hh % 10),
        ASCII_SPACE,
        ASCII_COLON,
        ASCII_SPACE,
        ascii_digit(mm / 10),
        ASCII_SPACE,
        ascii_digit(mm % 10),
    ]))


class Clock(ndb.Model):
    """The options for a clock.

    Keyed on channel name, at most one per channel.
    """
    twentyfour = ndb.BooleanProperty()
    tz = ndb.StringProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    # Filled in after the first send
    channel_id = ndb.StringProperty(required=False)
    slack_ts = ndb.StringProperty(required=False)

    def slack_text(self):
        dt = datetime.datetime.now(pytz.timezone(self.tz))
        return '```%s```' % ascii_clock(dt, self.twentyfour)

    def remove(self):
        if self.slack_ts:
            try:
                hit_slack_api('chat.delete', {
                    'ts': self.slack_ts,
                    'channel': self.channel_id,
                })
            except:
                logging.warning("Couldn't delete old message")
        self.key.delete()

    def update(self):
        if not self.slack_ts:
            # We need to post a new message
            # TODO(benkraft): warn the user if we're not already in the
            # channel
            resp = hit_slack_api('chat.postMessage', {
                'channel': self.key.id(),
                'text': self.slack_text(),
                'as_user': True,
            })
            self.slack_ts = resp['ts']
            self.channel_id = resp['channel']
            self.put()
        else:
            hit_slack_api('chat.update', {
                'ts': self.slack_ts,
                'channel': self.channel_id,
                'text': self.slack_text(),
            })

    @staticmethod
    def prune(n=5):
        for clock in Clock.query().order(-Clock.created).fetch(100)[n:]:
            clock.remove()

TZ_ALIASES = {
    'est': 'America/New_York',
    'edt': 'America/New_York',
    'eastern': 'America/New_York',
    'cst': 'America/Chicago',
    'cdt': 'America/Chicago',
    'central': 'America/Chicago',
    'mst': 'America/Denver',
    'mdt': 'America/Denver',
    'mountain': 'America/Denver',
    'pst': 'America/Los_Angeles',
    'pdt': 'America/Los_Angeles',
    'pacific': 'America/Los_Angeles',
}

DEFAULT_TZ = 'America/Los_Angeles'


def canonicalize_timezone(name):
    if not name:
        return DEFAULT_TZ
    if name.lower() in TZ_ALIASES:
        return TZ_ALIASES[name.lower()]
    try:
        pytz.timezone(name)
        return name
    except pytz.UnknownTimeZoneError:
        return None


class SlackCommand(webapp2.RequestHandler):
    """Invoked by the slack slash command."""
    def post(self):
        if self.request.POST.get('token') != secrets.slack_command_token:
            logging.warning("token didn't match")
            return
        channel_id = self.request.POST['channel_id']
        raw_tz = self.request.POST['text']
        tz = canonicalize_timezone(raw_tz)
        if not tz:
            self.response.write(json.dumps(
                {'text': '"%s" is not a valid timezone.' % raw_tz}))
            return
        existing = Clock.get_by_id(channel_id)
        if existing:
            existing.remove()
        else:
            Clock.prune()
        # TODO(benkraft): support 24-hour time clocks
        Clock(id=channel_id, twentyfour=False, tz=tz).update()


class Update(webapp2.RequestHandler):
    """Invoked by cron."""
    def get(self):
        for clock in Clock.query().fetch(100):
            try:
                clock.update()
            except Exception as e:
                logging.exception(e)

app = webapp2.WSGIApplication([
    ('/command', SlackCommand),
    ('/update', Update),
])
