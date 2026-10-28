"""Small, portable case-light effects and Pacific-time conference reminders.

Packaged independently inside each custom app. No network or stock-file writes.
"""
import math


def _clean(value, limit=180):
    return ''.join(c if 32 <= ord(c) < 127 else ' ' for c in str(value))[:limit]


def minute_stamp(date, clock):
    """Validated Gregorian wall-clock minutes, independent of host timezone."""
    try:
        year, month, day = [int(n) for n in str(date)[:10].split('-')]
        text = str(clock).upper().strip()
        if 'T' in text:
            text = text.split('T', 1)[1]
        hour, minute = int(text.split(':')[0]), int(text.split(':')[1][:2])
        if text.endswith(('AM', 'PM')):
            if not 1 <= hour <= 12:
                return None
            hour = hour % 12 + (12 if text.endswith('PM') else 0)
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        months = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
        if not (2025 <= year <= 2100 and 1 <= month <= 12 and
                1 <= day <= months[month - 1] and 0 <= hour < 24 and 0 <= minute < 60):
            return None
        y = year - 1
        days = 365 * y + y // 4 - y // 100 + y // 400 + sum(months[:month - 1]) + day
        return days * 1440 + hour * 60 + minute
    except (ValueError, TypeError, IndexError):
        return None


def reminder_config(config):
    """Export only the personal agenda Trail needs, without maps or identities."""
    config = config if isinstance(config, dict) else {}
    ids = config.get('personal_schedule', [])
    ids = ids if isinstance(ids, (list, tuple)) else []
    rows = config.get('schedule', [])
    rows = rows if isinstance(rows, (list, tuple)) else []
    fields = ('id', 'title', 'date', 'day', 'time', 'start', 'location', 'personal_reminder')
    return {'personal_schedule': [str(i) for i in ids[:1000]],
            'schedule': [{k: row[k] for k in fields if k in row} for row in rows[:1000]
                         if isinstance(row, dict) and row.get('id') in ids]}


class BadgeEffects:
    LEVELS = ('OFF', 'LOW', 'MEDIUM', 'BRIGHT')
    CAPS = (0.0, 0.12, 0.25, 0.45)
    # Delivered firmware applies a nonlinear LED curve: 0.12 is <1% duty.
    FALLOUT_CAPS = (0.0, 0.35, 0.60, 0.85)

    def __init__(self, config=None, saved=None):
        config = config if isinstance(config, dict) else {}
        saved = saved if isinstance(saved, dict) else {}
        level = saved.get('level', 1)
        self.state = {'level': level if isinstance(level, int) and 0 <= level <= 3 else 1,
                      'ambience': saved.get('ambience') is True,
                      'reminders': saved.get('reminders') is not False}
        self.restore_shared(saved.get('shared'))
        personal = config.get('personal_schedule', [])
        self.personal = set(personal if isinstance(personal, (list, tuple)) else [])
        self.events = []
        rows = config.get('schedule', [])
        for row in rows[:1000] if isinstance(rows, (list, tuple)) else []:
            if not isinstance(row, dict) or not row.get('id'):
                continue
            date = str(row.get('date') or row.get('start') or '')[:10]
            if not date:
                parts = str(row.get('day', '')).upper().replace(',', '').split()
                if len(parts) >= 2 and parts[0][:3] == 'OCT' and parts[1].isdigit():
                    date = '2026-10-%02d' % int(parts[1])
            clock = row.get('time') or row.get('start') or ''
            start = minute_stamp(date, clock)
            if start is not None:
                self.events.append({'id': str(row['id']), 'start': start,
                                    'title': _clean(row.get('title', 'SESSION'), 180),
                                    'location': _clean(row.get('location', 'Check your agenda'), 140),
                                    'time': '%d:%02d %s PT' % (((start % 1440) // 60) % 12 or 12,
                                                             start % 60, 'PM' if start % 1440 >= 720 else 'AM'),
                                    'personal_reminder': row.get('personal_reminder') is True})
        self.events.sort(key=lambda e: (e['start'], e['id']))
        self.age = 0.0
        self.alert_age = 0.0
        self.now = None
        self.checked = None
        self.battery = None
        self.active = None
        self.settings = False
        self.selected = 0
        self.levels = (0.0,) * 4

    def restore_shared(self, saved):
        saved = saved if isinstance(saved, dict) else {}
        shared = {}
        for field in ('seen', 'snoozes'):
            raw = saved.get(field, {})
            shared[field] = {k: int(v) for k, v in list(raw.items())[-128:]
                             if isinstance(k, str) and len(k) <= 160 and
                             isinstance(v, (int, float)) and 0 <= v <= 1200000000} if isinstance(raw, dict) else {}
        self.state['shared'] = shared
        self.shared_dirty = False

    def _key(self, event):
        return event['id'] + '|' + str(event['start'])

    def _seen(self, event, stage):
        return self._key(event) + '|' + str(stage)

    def _remember(self, event, stage):
        seen = self.state['shared']['seen']
        seen[self._seen(event, stage)] = self.now
        if len(seen) > 128:
            oldest = min(seen, key=seen.get)
            del seen[oldest]
        self.shared_dirty = True

    def tick(self, dt, telemetry=None, favorites=()):
        self.age = (self.age + max(0, min(float(dt), 86400))) % 100000
        self.alert_age += max(0, min(float(dt), 86400))
        if isinstance(telemetry, dict):
            self.battery = telemetry.get('battery', self.battery)
            if 'event_date' in telemetry or 'date' in telemetry:
                self.now = minute_stamp(telemetry.get('event_date') or telemetry.get('date'),
                                        telemetry.get('event_time') or telemetry.get('time'))
        if not self.state['reminders'] or self.now is None:
            if self.active and not self.active.get('demo'):
                self.active = None
            return
        if self.active:
            if self.active.get('demo'):
                return
            if self.now > self.active['start']:
                self.active = None
            else:
                if self.active['stage'] == 15 and self.active['start'] - self.now <= 5:
                    self.active['stage'] = 5
                    self._remember(self.active, 5)
                    self.alert_age = 0
                return
        eligible = self.personal | set(favorites)
        check = (self.now, tuple(sorted(eligible)))
        if check == self.checked:
            return
        self.checked = check
        shared = self.state['shared']
        for field, cutoff in (('seen', self.now - 4320), ('snoozes', self.now - 15)):
            for key in list(shared[field]):
                if shared[field][key] < cutoff:
                    del shared[field][key]
                    self.shared_dirty = True
        for event in self.events:
            delta = event['start'] - self.now
            if event['id'] not in eligible or not 0 <= delta <= 15:
                continue
            key = self._key(event)
            snooze = shared['snoozes'].get(key)
            if snooze is not None and self.now < snooze:
                continue
            stage = 5 if delta <= 5 else 15
            if snooze is None and self._seen(event, stage) in shared['seen']:
                continue
            shared['snoozes'].pop(key, None)
            self.active = dict(event, stage=stage)
            self._remember(event, stage)
            if stage == 5:
                self._remember(event, 15)
            self.alert_age = 0
            break

    def open_settings(self):
        self.settings, self.selected = True, 0

    def set_reminders(self, enabled):
        self.state['reminders'] = bool(enabled)
        self.checked = None
        if not enabled:
            self.active = None

    def handle(self, action):
        if action in ('reminders:on', 'reminders:off'):
            self.set_reminders(action == 'reminders:on')
            return True
        if self.active:
            event = self.active
            if action == 'right':
                self.set_reminders(False)
            elif action in ('select', 'back', 'menu', 'home', 'reminder:dismiss', 'choice:0'):
                self.active = None
                self.checked = None
            elif action in ('down', 'reminder:snooze', 'choice:1'):
                if not event.get('demo') and self.now is not None and self.now < event['start']:
                    self.state['shared']['snoozes'][self._key(event)] = min(event['start'], self.now + 5)
                    self.shared_dirty = True
                self.active = None
                self.checked = None
            return True
        if action == 'effects:open':
            self.open_settings()
            return True
        if not self.settings:
            return False
        if action in ('home', 'back', 'menu'):
            self.settings = False
        elif action in ('up', 'down'):
            self.selected = (self.selected + (1 if action == 'down' else -1)) % 5
        elif action.startswith('choice:') and action[7:].isdigit():
            self.selected = max(0, min(4, int(action[7:])))
            self.handle('select')
        elif action in ('select', 'left', 'right'):
            if self.selected == 0:
                self.state['ambience'] = not self.state['ambience']
            elif self.selected == 1:
                self.state['level'] = (self.state['level'] + (-1 if action == 'left' else 1)) % 4
            elif self.selected == 2:
                self.set_reminders(not self.state['reminders'])
            elif self.selected == 3:
                self.active = {'id': 'demo', 'start': (self.now or 0) + 15, 'stage': 15,
                               'title': 'YOUR NEXT UNIVERSE SESSION', 'location': 'Preview only - no agenda changes',
                               'time': 'EXAMPLE', 'demo': True}
                self.alert_age = 0
            else:
                self.settings = False
        return True

    def lights(self, scene=''):
        caps = self.FALLOUT_CAPS if scene in ('fallout', 'profile') else self.CAPS
        cap = caps[self.state['level']]
        if isinstance(self.battery, (int, float)) and self.battery < 20:
            cap *= 0.35
        values = [0.0] * 4
        if self.active:
            # Three slow fades, then darkness while the readable card remains.
            if self.alert_age < 9:
                pulse = (0.5 - 0.5 * math.cos(self.alert_age * math.pi * 2 / 3)) * cap
                values = [pulse] * 4
        elif self.state['ambience']:
            if scene in ('fallout', 'profile') and self.age < 2.8:
                values = [cap * max(0, 1 - abs(self.age / 0.55 - i - 0.5)) for i in range(4)]
            elif scene in ('fallout', 'profile'):
                # Continuous slow white phosphor waves on every Fallout page.
                # Keep a visible floor; the former startup-only effect went dark.
                values = [cap * (0.65 + 0.35 * math.sin(self.age * 1.2 - i * 0.8))
                          for i in range(4)]
            elif scene == 'camp':
                values = [cap * (0.35 + 0.18 * math.sin(self.age * 2.1 + i * 0.7)
                                 + 0.12 * math.sin(self.age * 3.7 + i)) for i in range(4)]
            elif scene == 'river':
                values = [cap * (0.15 + 0.35 * (1 + math.sin(self.age * 1.7 - i * 1.2))) for i in range(4)]
        self.levels = tuple(round(max(0, min(cap, v)), 3) for v in values)
        return self.levels

    def metadata(self):
        options = []
        if self.active:
            options = [{'label': 'Dismiss', 'action': 'reminder:dismiss'},
                       {'label': 'Snooze 5 min', 'action': 'reminder:snooze'},
                       {'label': 'Turn reminders off', 'action': 'reminders:off'}]
        elif self.settings:
            options = [{'label': label, 'action': 'choice:' + str(i)} for i, label in enumerate(self._labels())]
        return {'case_lights': list(self.levels), 'reminder': dict(self.active) if self.active else None,
                'reminders_enabled': self.state['reminders'],
                'effects_open': self.settings, 'effects_options': options}

    def _labels(self):
        return ['DECORATIVE LIGHTS: ' + ('ON' if self.state['ambience'] else 'OFF'),
                'BRIGHTNESS: ' + self.LEVELS[self.state['level']],
                'REMINDERS: ' + ('ON' if self.state['reminders'] else 'OFF'), 'TEST REMINDER', 'DONE']

    def overlay(self):
        if not self.active and not self.settings:
            return []
        commands = [['rect', 6, 51, 308, 177, 0], ['rect', 6, 51, 308, 2, 4], ['rect', 6, 226, 308, 2, 4]]
        def text(value, y, shade=4):
            commands.append(['text', _clean(value, 48).upper(), 16, y, 1, shade])
        if self.active:
            event = self.active
            delta = max(0, event['start'] - (self.now or 0))
            text('REMINDER PREVIEW' if event.get('demo') else ('STARTS NOW' if delta == 0 else 'IN %d MINUTES' % delta), 61)
            words, lines, line = event['title'].split(), [], ''
            for word in words:
                if len(line) + len(word) + 1 > 46:
                    lines.append(line)
                    line = ''
                line += (' ' if line else '') + word
            lines.append(line)
            for i, line in enumerate(lines[:3]):
                text(line, 80 + 11 * i)
            text(event['time'], 119, 3)
            text(event['location'][:46], 135, 3)
            text(event['location'][46:92], 146, 3)
            if event.get('personal_reminder'):
                text('PERSONAL REMINDER / REGISTRATION SEPARATE', 165, 2)
            text('SELECT: DISMISS    DOWN: SNOOZE 5 MIN', 199)
            text('RIGHT: REMINDERS OFF (THIS APP)', 214, 2)
        else:
            text('CASE LIGHTS + SESSION REMINDERS', 61)
            for i, label in enumerate(self._labels()):
                if i == self.selected:
                    commands.append(['rect', 12, 80 + i * 21, 296, 19, 1])
                text(('> ' if i == self.selected else '  ') + label, 85 + i * 21)
            text('WHITE LEDS / REMINDERS WHILE APP IS OPEN', 200, 2)
            text('UP/DOWN: CHOOSE   SELECT: CHANGE', 214, 2)
        return commands


class CaseLightDriver:
    """Use the documented API; missing LEDs never prevent using either app."""
    def __init__(self, badge):
        self.writer = getattr(badge, 'caselights', None)
        self.previous = None

    def write(self, values):
        values = tuple(values)
        if self.writer and values != self.previous:
            try:
                self.writer(*values)
                self.previous = values
            except (OSError, ValueError, TypeError, AttributeError, RuntimeError):
                self.writer = None

    def close(self):
        self.write((0, 0, 0, 0))


class ReminderStore:
    """Only our shared acknowledgement ledger, separate from all stock saves."""
    def __init__(self, effects, state_api):
        self.effects, self.api = effects, state_api
        if self.api:
            saved = {}
            try:
                self.api.load('universe_reminders', saved)
                if saved:
                    effects.restore_shared(saved)
            except (OSError, ValueError, TypeError):
                pass

    def save(self):
        if self.api and self.effects.shared_dirty:
            try:
                self.api.save('universe_reminders', self.effects.state['shared'])
                self.effects.shared_dirty = False
            except (OSError, ValueError, TypeError):
                pass


def pacific_clock(fields):
    """Convert a UTC gmtime tuple to Pacific wall time under US DST rules.

    Current System firmware and the browser supply UTC; convert for conference use.
    """
    year, month, day, hour, minute, second, weekday = fields[:7]
    daylight = 3 < month < 11
    first_weekday = (weekday - day + 1) % 7  # Monday = 0.
    first_sunday = 1 + (6 - first_weekday) % 7
    if month == 3:
        # Second Sunday, 2 AM PST = 10 AM UTC.
        daylight = (day, hour) >= (first_sunday + 7, 10)
    elif month == 11:
        # First Sunday, 2 AM PDT = 9 AM UTC.
        daylight = (day, hour) < (first_sunday, 9)
    hour -= 7 if daylight else 8
    if hour < 0:
        hour += 24
        day -= 1
        if day == 0:
            month -= 1
            if month == 0:
                year -= 1
                month = 12
            leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
            day = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]
    return year, month, day, hour, minute, second

