"""Portable, dependency-free Pip-Boy conference companion.

The same application runs in the browser simulator and on MicroPython. Rendering
returns small drawing commands, never framebuffer or platform objects. Controls:
left/right change the five main tabs; menu/back cycle a tab's subpages; up/down
select a row or map landmark; select toggles the selected action. On FOCUS,
up/down choose start/pause, duration or reset and select activates it. ``home``
opens STAT. Direct ``tab:MAP``, ``sub:LOCAL``, ``theme:amber``, ``reset_timer``
and ``waypoint:50,50`` actions support simulator controls and touch adapters.

HP is the packed-kit readiness meter. AP is completed field objectives. Neither
represents a medical measurement. Maps use manual landmarks, never claimed GPS.
"""

import math
import random

try:
    from .companion import BadgeEffects
except (ImportError, ValueError):
    from companion import BadgeEffects

try:
    from .mascot import VAULT_BOY_WIDTH, VAULT_BOY_DELAY, VAULT_BOY_FRAMES
except (ImportError, ValueError):
    from mascot import VAULT_BOY_WIDTH, VAULT_BOY_DELAY, VAULT_BOY_FRAMES

try:
    from .mascot import VAULT_BOY_COLOR_FRAMES, VAULT_BOY_COLOR_PALETTE
except (ImportError, ValueError):
    try:
        from mascot import VAULT_BOY_COLOR_FRAMES, VAULT_BOY_COLOR_PALETTE
    except ImportError:
        VAULT_BOY_COLOR_FRAMES, VAULT_BOY_COLOR_PALETTE = (), ()

try:
    from .mascot import VAULT_BOY_SHADED_FRAMES, VAULT_BOY_SHADED_PALETTE
except (ImportError, ValueError):
    try:
        from mascot import VAULT_BOY_SHADED_FRAMES, VAULT_BOY_SHADED_PALETTE
    except ImportError:
        VAULT_BOY_SHADED_FRAMES, VAULT_BOY_SHADED_PALETTE = (), ()

try:
    from .data import CONFIG as _DEFAULT_CONFIG
except (ImportError, ValueError):
    try:
        from data import CONFIG as _DEFAULT_CONFIG
    except ImportError:
        _DEFAULT_CONFIG = {
            "profile": {"name": "WANDERER", "handle": "github-user", "role": "DEVELOPER"},
            "inventory": [
                {"id": "badge", "name": "UNIVERSE BADGE", "detail": "Your personal conference terminal.", "packed": True},
                {"id": "cable", "name": "USB-C CABLE", "detail": "Keep your badge and devices charged."},
                {"id": "water", "name": "WATER BOTTLE", "detail": "Refill between conference sessions."},
                {"id": "notebook", "name": "FIELD NOTES", "detail": "Capture discoveries and people to follow up with."},
            ],
            "quests": [
                {"id": "arrive", "title": "ENTER THE COMMONWEALTH", "detail": "Check in at Universe and collect your badge.", "xp": 25},
                {"id": "connect", "title": "MAKE A CONNECTION", "detail": "Meet a developer and exchange GitHub handles.", "xp": 40},
            ],
            "schedule": [],
            "world": {"title": "FORT MASON", "note": "MANUAL LANDMARKS", "pois": [], "paths": []},
            "local": {"title": "CONFERENCE", "note": "ROOM PLAN PENDING", "pois": [], "paths": []},
        }


TABS = ("STAT", "INV", "DATA", "MAP", "RADIO")
SUBTABS = {
    "STAT": ("STATUS", "PROFILE"),
    "INV": ("GEAR", "PACKED", "DETAILS"),
    "DATA": ("QUESTS", "SCHEDULE", "MY SCHEDULE", "SEARCH", "DETAILS"),
    "MAP": ("WORLD", "LOCAL", "DETAILS"),
    "RADIO": ("FOCUS", "SIGNAL", "SENSORS", "DETAILS"),
}
THEMES = ("green", "amber", "ice")
MASCOTS = ("color", "shaded")
FONT_MODES = ("pixel", "vector")
APPEARANCES = tuple((theme, mascot) for theme in ("green", "amber") for mascot in MASCOTS)
WIDTH, HEIGHT = 320, 240
MAP_CONTROLS = (
    {"id": "map:zoom_in", "name": "ZOOM IN", "detail": "Select to magnify the map."},
    {"id": "map:zoom_out", "name": "ZOOM OUT", "detail": "Select to widen the map view."},
    {"id": "map:pan", "name": "PAN MAP", "detail": "Select, then move with all four arrows. Select again to finish."},
    {"id": "map:reset", "name": "RESET VIEW", "detail": "Restore the full map and center."},
    {"id": "map:pin", "name": "PLACE MANUAL PIN", "detail": "Select, then move the cursor with all four arrows. Select to place the pin. Hold Select to cancel."},
    {"id": "map:clear_pin", "name": "CLEAR WAYPOINT", "detail": "Remove this map's landmark or manual waypoint."},
)
PROFILE_CONTROLS = (
    {"id": "profile:appearance", "name": "APPEARANCE", "detail": "Select to cycle four theme and Vault Boy combinations."},
    {"id": "profile:font", "name": "FONT", "detail": "Select to switch pixel and vector text. Pixel is the built-in compatibility option."},
    {"id": "profile:help", "name": "CONTROLS / HELP", "detail": "Button controls, hardware fallbacks and offline features."},
    {"id": "profile:lights", "name": "LIGHTS / REMINDERS", "detail": "White case lighting, brightness, and 15 / 5 minute agenda reminders. Reminders work while either custom app is open."},
    {"id": "profile:crt", "name": "CRT SWEEP", "detail": "A translucent pass over everything, then a random 20–45 second pause. Off below 10% battery; a fresh pause starts on recovery at 12%."},
    {"id": "profile:credits", "name": "Created with AI by DChevrier1", "detail": "Created with AI by DChevrier1"},
)
FOCUS_CONTROLS = (
    {"id": "focus:toggle", "name": "START / PAUSE", "detail": "Start, pause or resume the focus timer."},
    {"id": "focus:duration", "name": "DURATION", "detail": "Select to cycle 15, 25, 45 and 60 minutes while paused. Changing duration resets the timer."},
    {"id": "focus:reset", "name": "RESET TIMER", "detail": "Stop the timer and restore its full duration."},
)
SEARCH_KEYS = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") + ("SPACE", "DEL", "CLEAR", "DATE", "SAVED", "DONE")
SEARCH_EDIT = {"id": "search:edit", "title": "EDIT SEARCH / FILTERS", "detail": "Open the button keyboard. DATE cycles conference days; SAVED shows your personal schedule."}
HELP_PAGES = (
    ("FIVE-BUTTON CONTROLS", "LEFT / RIGHT: MAIN TABS", "UP / DOWN: CHOOSE A ROW", "TAP SELECT: ACTIVATE", "HOLD SELECT: NEXT SUBPAGE", "RELEASE AFTER EVERY HOLD", "", "ON A MAP: CHOOSE PAN OR PLACE PIN", "THEN MOVE WITH THE FOUR ARROWS.", "SELECT FINISHES; HOLD CANCELS PIN."),
    ("READ / FIND / CUSTOMIZE", "DETAILS SHOWS THE LAST BROWSED ITEM", "UP / DOWN PAGES; SELECT RETURNS", "DATA > SEARCH: BUTTON KEYBOARD", "DATE / SAVED: FILTER THE RESULTS", "DONE: BROWSE AND SAVE SESSIONS", "", "PROFILE: STYLE, FONT, CRT SWEEP", "ECO BELOW 10% / RECOVERS AT 12%", "FOCUS: START, DURATION AND RESET"),
    ("HARDWARE / OFFLINE", "HOLD SELECT WORKS WITHOUT TOUCH", "TOUCH MENU ALSO CHANGES SUBPAGES", "", "LOAD YOUR CONTENT BEFORE THE EVENT", "MAP PINS ARE MANUAL; THERE IS NO GPS", "SAVED SESSIONS ARE NOT BOOKINGS", "SIGNAL IS A VISUALIZER, NOT RADIO", "SENSORS SHOW UNAVAILABLE IF ABSENT", "BROWSER TOOLS PREPARE / EXPORT DATA"),
    ("LIGHTS / REMINDERS", "PROFILE > LIGHTS / REMINDERS", "WHITE CASE LEDS: OFF / LOW / MED / BRIGHT", "DECORATIVE LIGHTS OFF BY DEFAULT", "", "AGENDA ALERTS: 15 AND 5 MINUTES BEFORE", "SELECT DISMISSES; DOWN SNOOZES 5 MIN", "SHARED WITH TRAIL; TRAIL PAUSES", "REQUIRES CORRECT PACIFIC CLOCK", "ONLY WHILE A CUSTOM APP IS OPEN / AWAKE"),
    ("OPTIONAL REMINDERS", "PROFILE > LIGHTS / REMINDERS", "CHOOSE REMINDERS; SELECT ON / OFF", "ON AN ALERT: RIGHT TURNS REMINDERS OFF", "OFF IS SAVED SEPARATELY FOR EACH APP", "TURN OFF IN BOTH FOR NO AUTO ALERTS", "AGENDA AND DECORATIVE LIGHTS STAY", "WAIT TWO SECONDS TO SAVE; HOME SAVES TOO", "TEST REMINDER IS AN EXPLICIT PREVIEW", "INSTALL APPS BY USB MASS STORAGE"),
)


def _clone(value):
    if isinstance(value, dict):
        return {key: _clone(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clone(item) for item in value]
    return value


def _number(value, default=0, low=0, high=1000000):
    try:
        value = float(value)
        if value != value or value < low or value > high:
            return default
        return value
    except (TypeError, ValueError, OverflowError):
        return default


def _ascii(value, limit=100):
    value = str(value or "")[:limit]
    return "".join(char if 32 <= ord(char) < 127 else " " for char in value)


def _short(value, length):
    value = _ascii(value)
    return value if len(value) <= length else value[:max(0, length - 2)] + ".."


def _padded(value, width=2):
    """MicroPython's compact str type does not provide CPython's zfill."""
    value = str(value)
    return "0" * max(0, width - len(value)) + value


def _minutes(value):
    value = str(value or "").strip().upper()
    if "T" in value and len(value) >= 16:
        value = value[11:16]
    parts = value.split(":")
    if len(parts) < 2:
        return None
    try:
        hour, minute = int(parts[0]), int(parts[1][:2])
        if "AM" in value or "PM" in value:
            if not 1 <= hour <= 12:
                return None
            hour = hour % 12 + (12 if "PM" in value else 0)
        return hour * 60 + minute if 0 <= hour < 24 and 0 <= minute < 60 else None
    except (TypeError, ValueError):
        return None


def _clock(value, fallback="TBD"):
    minutes = _minutes(value)
    if minutes is None:
        return fallback
    hour = minutes // 60
    return str(hour % 12 or 12) + ":" + _padded(minutes % 60) + (" PM" if hour >= 12 else " AM")


def _display_times(value):
    """Format embedded clock times in imported descriptions without regex."""
    value = str(value or "")
    result, index = "", 0
    while index < len(value):
        if value[index].isdigit() and (index == 0 or not value[index - 1].isdigit()):
            end = index
            while end < len(value) and value[end].isdigit():
                end += 1
            if 1 <= end - index <= 2 and value[end:end + 1] == ":" and value[end + 1:end + 3].isdigit():
                clock_end = end + 3
                suffix = value[clock_end:clock_end + 3].upper()
                if suffix in (" AM", " PM"):
                    clock_end += 3
                parsed = _minutes(value[index:clock_end])
                if parsed is not None:
                    result += _clock(value[index:clock_end])
                    index = clock_end
                    continue
        result += value[index]
        index += 1
    return result


def _event_date(item):
    value = str(item.get("date") or item.get("start") or "")[:10]
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        return value
    parts = str(item.get("day") or "").upper().replace(",", "").split()
    months = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
    if len(parts) >= 2 and parts[0][:3] in months:
        try:
            day = int(parts[1])
            year = int(parts[2]) if len(parts) > 2 else 2026
            if 1 <= day <= 31:
                return str(year) + "-" + _padded(months.index(parts[0][:3]) + 1) + "-" + _padded(day)
        except ValueError:
            pass
    return ""


def _event_key(item):
    minutes = _minutes(item.get("time") or item.get("start"))
    return (_event_date(item) or "9999-99-99", minutes if minutes is not None else 1440)


def _record_list(value, label, copy_records=True):
    """Ignore malformed records instead of crashing a physical badge at boot."""
    result = []
    seen = set()
    if not isinstance(value, (list, tuple)):
        return result
    for index, record in enumerate(value[:1000]):
        if not isinstance(record, dict):
            continue
        if copy_records:
            record = _clone(record)
        record_id = _ascii(record.get("id", label + str(index)), 64)
        if not record_id or record_id in seen:
            continue
        record["id"] = record_id
        seen.add(record_id)
        result.append(record)
    return result


class PipBoy:
    """Conference app with JSON-safe persistence and drawing-command output."""

    def __init__(self, state=None, config=None, copy_config=True):
        source = dict(_DEFAULT_CONFIG)
        if isinstance(config, dict):
            for key, value in config.items():
                if key == "profile" and isinstance(value, dict):
                    profile = dict(source.get("profile", {}))
                    profile.update(value)
                    source[key] = profile
                else:
                    source[key] = value
        # Native apps own their loaded configuration. Avoid a second full copy
        # of map geometry on the badge; browser sessions retain isolation.
        self.config = _clone(source) if copy_config else source
        # One owned copy: normalized model records also back the configuration.
        self.inventory = _record_list(self.config.get("inventory", []), "gear", False)
        self.config["inventory"] = self.inventory
        self.base_quests = _record_list(self.config.get("quests", []), "quest", False)
        self.config["quests"] = self.base_quests
        self.quests = list(self.base_quests)
        self.schedule = _record_list(self.config.get("schedule", []), "event", False)
        self.schedule.sort(key=_event_key)
        self.config["schedule"] = self.schedule
        booked = self.config.get("personal_schedule", [])
        booked = booked if isinstance(booked, (list, tuple)) else []
        self.personal_schedule = [item["id"] for item in self.schedule if item["id"] in booked]
        self.maps = {}
        for sub in ("WORLD", "LOCAL"):
            raw = self.config.get(sub.lower(), {})
            raw = raw if isinstance(raw, dict) else {}
            self.maps[sub] = raw
            self.maps[sub]["pois"] = _record_list(raw.get("pois", []), "poi", False)
            self.config[sub.lower()] = raw
        state = state if isinstance(state, dict) else {}
        self.effects = BadgeEffects(self.config, state.get("effects"))
        tab = state.get("tab", "STAT")
        theme = state.get("theme", self.config.get("theme", "green"))
        if theme not in THEMES:
            theme = self.config.get("theme", "green")
        self.state = {
            "version": 1,
            "tab": tab if tab in TABS else "STAT",
            "subtabs": {},
            "selected": {},
            "packed": {},
            "quests": {},
            "favorites": [],
            "waypoints": {"WORLD": None, "LOCAL": None},
            "theme": theme if theme in THEMES else "green",
            "mascot": state.get("mascot", self.config.get("mascot", "color")),
            "font_mode": state.get("font_mode", self.config.get("font_mode", "pixel")),
            "pixel_glow": False,  # Ignore legacy glow preferences; text is always crisp.
            "crt_scanlines": state.get("crt_scanlines", self.config.get("crt_scanlines", True)) is not False,
            "map_views": {},
            "detail_sources": {},
            "timer": {},
        }
        if self.state["mascot"] not in MASCOTS:
            self.state["mascot"] = "color"
        if self.state["font_mode"] not in FONT_MODES:
            self.state["font_mode"] = self.config.get("font_mode", "pixel")
        if self.state["font_mode"] not in FONT_MODES:
            self.state["font_mode"] = "pixel"
        subs = state.get("subtabs", {})
        subs = subs if isinstance(subs, dict) else {}
        selected = state.get("selected", {})
        selected = selected if isinstance(selected, dict) else {}
        for main in TABS:
            sub = subs.get(main)
            self.state["subtabs"][main] = sub if sub in SUBTABS[main] else SUBTABS[main][0]
            for sub in SUBTABS[main]:
                key = main + ":" + sub
                self.state["selected"][key] = int(_number(selected.get(key), 0, 0, 999))
            sources = state.get("detail_sources", {})
            source = sources.get(main) if isinstance(sources, dict) else None
            self.state["detail_sources"][main] = source if source in SUBTABS[main] and source != "DETAILS" else SUBTABS[main][0]
        for key, records, default_field in (("packed", self.inventory, "packed"), ("quests", self.quests, "complete")):
            saved = state.get(key, {})
            saved = saved if isinstance(saved, dict) else {}
            for item in records:
                default = item.get(default_field, item.get("completed", False))
                value = saved.get(item["id"], default)
                self.state[key][item["id"]] = value is True
        favorites = state.get("favorites", [])
        if isinstance(favorites, (list, tuple)):
            self.state["favorites"] = [item["id"] for item in self.schedule if item["id"] in favorites]
        saved_quests = state.get("quests", {})
        if isinstance(saved_quests, dict):
            for item in self.schedule:
                quest_id = "attend:" + item["id"]
                if quest_id in saved_quests:
                    self.state["quests"][quest_id] = saved_quests[quest_id] is True
        self._sync_schedule_quests()
        waypoints = state.get("waypoints", {})
        if isinstance(waypoints, dict):
            for sub in ("WORLD", "LOCAL"):
                point = waypoints.get(sub)
                if isinstance(point, dict):
                    self.state["waypoints"][sub] = {
                        "id": _ascii(point.get("id", "manual"), 64),
                        "name": _ascii(point.get("name", "MANUAL PIN"), 45),
                        "x": _number(point.get("x"), 50, 0, 100),
                        "y": _number(point.get("y"), 50, 0, 100),
                    }
        views = state.get("map_views", {})
        views = views if isinstance(views, dict) else {}
        for sub in ("WORLD", "LOCAL"):
            view = views.get(sub, {})
            view = view if isinstance(view, dict) else {}
            zoom = _number(view.get("zoom"), 1, 1, 8)
            edge = 50 / zoom
            self.state["map_views"][sub] = {
                "zoom": zoom,
                "cx": _number(view.get("cx"), 50, edge, 100 - edge),
                "cy": _number(view.get("cy"), 50, edge, 100 - edge),
            }
        self.map_pan = False
        self.map_cursor = None
        self.detail_page = 0
        self.help_page = None
        self.search_query = ""
        self.search_date = ""
        self.search_saved = False
        self.search_editing = self.tab == "DATA" and self.subtab == "SEARCH"
        self.search_key = 0
        self._search_cache_key = None
        self._search_cache = []
        self._detail_cache_item = None
        self._detail_cache_lines = []
        timer = state.get("timer", {})
        timer = timer if isinstance(timer, dict) else {}
        duration = int(_number(timer.get("duration"), 1500, 60, 7200))
        remaining = _number(timer.get("remaining"), duration, 0, duration)
        self.state["timer"] = {
            "duration": duration,
            "remaining": remaining,
            "running": timer.get("running") is True and remaining > 0,
            "sessions": int(_number(timer.get("sessions"), 0, 0, 100000)),
        }
        self.profile = self.config.get("profile", {})
        self.profile = self.profile if isinstance(self.profile, dict) else {}
        self.telemetry = {"battery": None, "time": "--:--", "date": "", "event_time": "", "event_date": "", "time_label": "PT", "simulated": True, "sensors": []}
        self._pending_schedule_anchor = self.tab == "DATA" and self.subtab in ("SCHEDULE", "MY SCHEDULE")
        self.phase = 0.0
        self.battery_saver = False
        self.crt_elapsed = 0.0
        self.crt_wait = 0.0
        self._crt_first_update = True
        self.notice = ""
        self.notice_time = 0.0
        self.commands = []
        self._mascot_key = None
        self._mascot_commands = []
        self._clamp_selection()

    @property
    def tab(self):
        return self.state["tab"]

    @property
    def subtab(self):
        return self.state["subtabs"][self.tab]

    def _key(self):
        return self.tab + ":" + self.subtab

    def _items(self):
        if self.subtab == "DETAILS":
            item = self._detail_record()
            return [item] if item else []
        return self._items_for(self.tab, self.subtab)

    def _items_for(self, tab, subtab):
        if tab == "STAT" and subtab == "PROFILE":
            return PROFILE_CONTROLS
        if tab == "INV":
            if subtab == "PACKED":
                return [item for item in self.inventory if self.state["packed"][item["id"]]]
            return self.inventory
        if tab == "DATA":
            if subtab == "QUESTS":
                return self.quests
            if subtab == "MY SCHEDULE":
                return self._my_schedule
            if subtab == "SEARCH":
                return self._search_results() + [SEARCH_EDIT]
            return self.schedule
        if tab == "RADIO" and subtab == "SENSORS":
            return self.telemetry["sensors"]
        if tab == "RADIO" and subtab == "FOCUS":
            return FOCUS_CONTROLS
        if tab == "MAP" and subtab in self.maps:
            return self.maps[subtab]["pois"] + list(MAP_CONTROLS)
        return []

    def _detail_record(self):
        source = self.state["detail_sources"][self.tab]
        items = self._items_for(self.tab, source)
        index = self.state["selected"].get(self.tab + ":" + source, 0)
        return items[min(index, len(items) - 1)] if items else None

    def _search_results(self):
        cache_key = (self.search_query, self.search_date, self.search_saved, tuple(self.state["favorites"]) if self.search_saved else ())
        if cache_key == self._search_cache_key:
            return self._search_cache
        words = self.search_query.lower().split()
        saved = set(self.personal_schedule + self.state["favorites"])
        result = []
        for item in self.schedule:
            if self.search_saved and item["id"] not in saved:
                continue
            if self.search_date and _event_date(item) != self.search_date:
                continue
            speakers = item.get("speakers", "")
            if isinstance(speakers, (tuple, list)):
                speakers = " ".join(str(speaker) for speaker in speakers)
            searchable = " ".join(str(value or "") for value in (item.get("title"), item.get("day"), _event_date(item), item.get("location"), speakers, item.get("detail"), item.get("description"))).lower()
            if all(word in searchable for word in words):
                result.append(item)
        self._search_cache_key = cache_key
        self._search_cache = result
        return result

    def _clamp_selection(self):
        key = self._key()
        self.state["selected"][key] = min(self.state["selected"].get(key, 0), max(0, len(self._items()) - 1))

    def selected_item(self):
        items = self._items()
        return items[self.state["selected"].get(self._key(), 0)] if items else None

    def _notify(self, message):
        self.notice = message
        self.notice_time = 2.5

    def _sync_schedule_quests(self):
        """Turn saved or imported sessions into clearly labeled personal tasks."""
        self.quests = list(self.base_quests)
        self._my_schedule = []
        booked_ids = set(self.personal_schedule)
        saved_ids = set(self.state["favorites"])
        for item in self.schedule:
            booked = item["id"] in booked_ids
            if not booked and item["id"] not in saved_ids:
                continue
            self._my_schedule.append(item)
            quest_id = "attend:" + item["id"]
            prefix = "Your personal calendar reminder; registration is separate. " if item.get("personal_reminder") else "Your Universe schedule. " if booked else "Your saved session; not a booking. "
            when = str(item.get("day") or item.get("date") or "DATE TBD") + " " + _clock(item.get("time") or item.get("start"), "TIME TBD")
            self.quests.append({
                "id": quest_id,
                "title": "ATTEND: " + str(item.get("title", "SESSION")),
                "detail": prefix + when + ". " + str(item.get("location") or "ROOM TBD") + ". Mark complete after attending.",
                "xp": 25,
                "session_id": item["id"],
                "booked": booked and not item.get("personal_reminder", False),
            })
            self.state["quests"].setdefault(quest_id, False)

    def _anchor_schedule(self):
        """Focus an ongoing session or the next dated session on menu entry."""
        if self.tab != "DATA" or self.subtab not in ("SCHEDULE", "MY SCHEDULE"):
            return
        date = self.telemetry.get("event_date") or self.telemetry.get("date")
        minutes = _minutes(self.telemetry.get("event_time") or self.telemetry.get("time"))
        if not date or minutes is None:
            self._pending_schedule_anchor = True
            return
        self._pending_schedule_anchor = False
        now = (date, minutes)
        items = self._items()
        active, upcoming, last = None, None, None
        for index, item in enumerate(items):
            start = _event_key(item)
            if start[0] == "9999-99-99" or start[1] == 1440:
                continue
            last = index
            finish = _minutes(item.get("end") or item.get("end_time") or item.get("finish"))
            end_date = str(item.get("finish") or "")[:10] or start[0]
            if finish is not None and start <= now < (end_date, finish):
                if active is None or start > _event_key(items[active]):
                    active = index
            elif upcoming is None and start >= now:
                upcoming = index
        selected = active if active is not None else upcoming if upcoming is not None else last
        if selected is not None:
            self.state["selected"][self._key()] = selected

    def update(self, actions=(), dt=0.1, telemetry=None, return_snapshot=True):
        """Advance animation/timer, then handle a sequence of portable actions."""
        elapsed = _number(dt, 0, 0, 86400)
        self.notice_time = max(0, self.notice_time - elapsed)
        if isinstance(telemetry, dict):
            if "battery" in telemetry:
                battery = telemetry["battery"]
                self.telemetry["battery"] = None if battery is None else _number(battery, None, 0, 100)
            if "time" in telemetry:
                self.telemetry["time"] = _ascii(telemetry["time"], 16)
            for field in ("date", "event_date", "event_time"):
                if field in telemetry:
                    self.telemetry[field] = _ascii(telemetry[field], 16)
            if "time_label" in telemetry:
                self.telemetry["time_label"] = _ascii(telemetry["time_label"], 5).upper()
            if "simulated" in telemetry:
                self.telemetry["simulated"] = telemetry["simulated"] is True
            if "sensors" in telemetry:
                self.telemetry["sensors"] = _record_list(telemetry["sensors"], "sensor")[:64]
                self._clamp_selection()
        battery = self.telemetry.get("battery")
        previous_saver = self.battery_saver
        if isinstance(battery, (int, float)):
            if battery < 10:
                self.battery_saver = True
            elif battery >= 12:
                self.battery_saver = False
        if self.battery_saver:
            self.crt_elapsed = 2.75
            self.crt_wait = 20
            # Publish the effective output immediately, including snapshots
            # taken before the next render. Keep the user's preferences intact.
            self.effects.levels = (0.0,) * 4
        elif previous_saver:
            self.crt_elapsed = 2.75
            self.crt_wait = 20 + random.getrandbits(16) % 26
        if not self.battery_saver:
            self.phase = (self.phase + elapsed) % 10000
            # One quick pass, then a genuinely idle random gap. No per-frame RNG
            # and no animation-driven redraws during the 20–45 second wait.
            # Recovery starts a fresh pause now; elapsed belongs to the interval
            # before this battery sample, when ECO was still active.
            crt_dt = 0 if self._crt_first_update or previous_saver else elapsed
            self._crt_first_update = False
            if self.crt_wait > 0:
                self.crt_wait = max(0, self.crt_wait - crt_dt)
                if self.crt_wait == 0:
                    self.crt_elapsed = 0
            elif self.crt_elapsed < 2.75:
                self.crt_elapsed = min(2.75, self.crt_elapsed + crt_dt)
                if self.crt_elapsed == 2.75:
                    self.crt_wait = 20 + random.getrandbits(16) % 26
        if self._pending_schedule_anchor:
            self._anchor_schedule()
        self.effects.tick(elapsed, self.telemetry, self.state["favorites"])
        timer = self.state["timer"]
        if timer["running"]:
            timer["remaining"] = max(0, timer["remaining"] - elapsed)
            if timer["remaining"] == 0:
                timer["running"] = False
                timer["sessions"] += 1
                self._notify("FOCUS COMPLETE  +10 XP")
        if isinstance(actions, str):
            actions = [actions]
        if not isinstance(actions, (list, tuple)):
            actions = ()
        for action in actions:
            if isinstance(action, str):
                if self.effects.handle(action):
                    continue
                previous = self._key()
                self._action(action)
                if self.subtab != "DETAILS" and self._key() == previous and (action in ("up", "down", "select") or action.startswith("item:") or action.startswith("session:")):
                    # Remember deliberate browsing while Menu passes through
                    # intermediate subpages on the way to full details.
                    self.state["detail_sources"][self.tab] = self.subtab
                if self._key() != previous:
                    self.map_pan = False
                    self.map_cursor = None
                    self.help_page = None
                    self.detail_page = 0
                    self.search_editing = self.tab == "DATA" and self.subtab == "SEARCH" and previous != "DATA:DETAILS"
                    self._anchor_schedule()
                self._clamp_selection()
        if return_snapshot:
            return self.snapshot(include_content=False)

    def _action(self, action):
        if self.help_page is not None:
            if action in ("up", "down", "left", "right"):
                self.help_page = (self.help_page + (-1 if action in ("up", "left") else 1)) % len(HELP_PAGES)
                return
            if action in ("select", "menu", "back"):
                self.help_page = None
                return
        if self.subtab == "DETAILS":
            if action in ("up", "down"):
                pages = max(1, (len(self._detail_lines()) + 10) // 11)
                self.detail_page = (self.detail_page + (-1 if action == "up" else 1)) % pages
                return
            if action == "select":
                self.state["subtabs"][self.tab] = self.state["detail_sources"][self.tab]
                return
        if self.tab == "DATA" and self.subtab == "SEARCH":
            if action.startswith("search:"):
                self.search_query = _ascii(action[7:], 48).upper()
                self.state["selected"][self._key()] = 0
                self.search_editing = False
                return
            if self.search_editing:
                if action in ("up", "down", "left", "right"):
                    row, column = self.search_key // 7, self.search_key % 7
                    if action == "left": column = (column - 1) % 7
                    elif action == "right": column = (column + 1) % 7
                    elif action == "up": row = (row - 1) % 6
                    else: row = (row + 1) % 6
                    self.search_key = row * 7 + column
                    return
                if action == "select":
                    self._search_input(SEARCH_KEYS[self.search_key])
                    return
                if action in ("menu", "back"):
                    self.search_editing = False
                    self.state["selected"][self._key()] = 0
                    return
        if action in ("crt:on", "crt:off"):
            self.state["crt_scanlines"] = action == "crt:on"
            return
        if action in ("glow:on", "glow:off"):
            self.state["pixel_glow"] = False
            return
        if action.startswith("font:") or action.startswith("font_mode:"):
            mode = action.split(":", 1)[1].lower()
            if mode in FONT_MODES:
                self.state["font_mode"] = mode
            return
        if action.startswith("session:") and self.tab == "DATA" and self.subtab in ("SCHEDULE", "MY SCHEDULE"):
            session_id = action[8:]
            for index, item in enumerate(self._items()):
                if item["id"] == session_id:
                    self.state["selected"][self._key()] = index
                    break
            return
        if action.startswith("appearance:"):
            appearance = tuple(action[11:].split(":"))
            if appearance in APPEARANCES:
                self.state["theme"], self.state["mascot"] = appearance
            return
        if action.startswith("mascot:"):
            if action[7:] in MASCOTS:
                self.state["mascot"] = action[7:]
            return
        if action.startswith("map:") and self.tab == "MAP" and self.subtab in self.maps:
            self._map_action(action[4:])
            return
        if self.map_cursor is not None and self.tab == "MAP":
            if action in ("left", "right", "up", "down"):
                dx, dy = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}[action]
                # One percent steps permit every coordinate in the browser's
                # integer pin picker, independent of the current zoom.
                self.map_cursor["x"] = max(0, min(100, self.map_cursor["x"] + dx))
                self.map_cursor["y"] = max(0, min(100, self.map_cursor["y"] + dy))
                view = self.state["map_views"][self.subtab]
                edge = 50 / view["zoom"]
                view["cx"] = max(edge, min(100 - edge, self.map_cursor["x"]))
                view["cy"] = max(edge, min(100 - edge, self.map_cursor["y"]))
                return
            if action == "select":
                self.state["waypoints"][self.subtab] = self.map_cursor
                self.map_cursor = None
                self._notify("MANUAL WAYPOINT SET")
                return
            if action in ("menu", "back"):
                self.map_cursor = None
                self._notify("PIN PLACEMENT CANCELLED")
                return
        if self.map_pan and self.tab == "MAP" and self.subtab in self.maps:
            if action in ("left", "right", "up", "down"):
                self._map_action("pan_" + action)
                return
            if action == "select":
                self.map_pan = False
                self._notify("MAP PAN FINISHED")
                return
        if action.startswith("tab:"):
            main = action[4:].upper()
            if main in TABS:
                self.state["tab"] = main
            return
        if action.startswith("sub:"):
            sub = action[4:].upper()
            if sub in SUBTABS[self.tab]:
                self.state["subtabs"][self.tab] = sub
            return
        if action.startswith("theme:"):
            theme = action[6:].lower()
            if theme in THEMES:
                self.state["theme"] = theme
            return
        if action.startswith("item:"):
            index = _number(action[5:], None, 0, max(0, len(self._items()) - 1))
            if index is not None:
                self.state["selected"][self._key()] = int(index)
            return
        if action.startswith("waypoint:") and self.tab == "MAP" and self.subtab in self.maps:
            parts = action[9:].split(",")
            if len(parts) == 2:
                x = _number(parts[0], None, 0, 100)
                y = _number(parts[1], None, 0, 100)
                if x is not None and y is not None:
                    self.state["waypoints"][self.subtab] = {"id": "manual", "name": "MANUAL PIN", "x": x, "y": y}
                    self._notify("MANUAL WAYPOINT SET")
            return
        if action == "clear_waypoint" and self.tab == "MAP" and self.subtab in self.maps:
            self.state["waypoints"][self.subtab] = None
            return
        if action == "home":
            self.state["tab"] = "STAT"
            self.state["subtabs"]["STAT"] = "STATUS"
        elif action in ("left", "right"):
            direction = -1 if action == "left" else 1
            self.state["tab"] = TABS[(TABS.index(self.tab) + direction) % len(TABS)]
        elif action in ("back", "menu"):
            options = SUBTABS[self.tab]
            self.state["subtabs"][self.tab] = options[(options.index(self.subtab) + 1) % len(options)]
        elif action in ("up", "down"):
            items = self._items()
            if items:
                key = self._key()
                self.state["selected"][key] = (self.state["selected"][key] + (-1 if action == "up" else 1)) % len(items)
        elif action in ("reset_timer", "focus:reset"):
            timer = self.state["timer"]
            timer["remaining"] = timer["duration"]
            timer["running"] = False
            self._notify("FOCUS TIMER RESET")
        elif action in ("focus:start", "focus:pause"):
            timer = self.state["timer"]
            if action == "focus:start" and timer["remaining"] <= 0:
                timer["remaining"] = timer["duration"]
            timer["running"] = action == "focus:start"
        elif action == "select":
            item = self.selected_item()
            if self.tab == "INV" and item:
                key = item["id"]
                self.state["packed"][key] = not self.state["packed"][key]
                self._notify("ITEM PACKED" if self.state["packed"][key] else "ITEM REMOVED FROM KIT")
            elif self.tab == "DATA" and item:
                key = item["id"]
                if self.subtab == "SEARCH" and key == "search:edit":
                    self.search_editing = True
                    return
                if self.subtab == "QUESTS":
                    self.state["quests"][key] = not self.state["quests"][key]
                    self._notify("OBJECTIVE COMPLETE" if self.state["quests"][key] else "OBJECTIVE REOPENED")
                elif key in self.state["favorites"]:
                    self.state["favorites"].remove(key)
                    self._notify("REMOVED FROM FAVORITES")
                else:
                    self.state["favorites"].append(key)
                    self._notify("SAVED TO FAVORITES")
                self._sync_schedule_quests()
            elif self.tab == "MAP" and item:
                if item["id"].startswith("map:"):
                    self._map_action(item["id"][4:])
                    return
                point = self.state["waypoints"][self.subtab]
                if point and point["id"] == item["id"]:
                    self.state["waypoints"][self.subtab] = None
                    self._notify("WAYPOINT CLEARED")
                else:
                    self.state["waypoints"][self.subtab] = {
                        "id": item["id"], "name": _ascii(item.get("name"), 45),
                        "x": _number(item.get("x"), 50, 0, 100),
                        "y": _number(item.get("y"), 50, 0, 100),
                    }
                    self._notify("MANUAL WAYPOINT SET")
            elif self.tab == "RADIO" and self.subtab == "FOCUS":
                timer = self.state["timer"]
                if item["id"] == "focus:reset":
                    self._action("reset_timer")
                elif item["id"] == "focus:duration":
                    if timer["running"]:
                        self._notify("PAUSE TIMER TO CHANGE DURATION")
                    else:
                        options = (900, 1500, 2700, 3600)
                        old = options.index(timer["duration"]) if timer["duration"] in options else 1
                        timer["duration"] = options[(old + 1) % len(options)]
                        timer["remaining"] = timer["duration"]
                else:
                    if timer["remaining"] <= 0:
                        timer["remaining"] = timer["duration"]
                    timer["running"] = not timer["running"]
            elif self.tab == "STAT" and self.subtab == "PROFILE":
                if item["id"] == "profile:help":
                    self.help_page = 0
                elif item["id"] == "profile:lights":
                    self.effects.open_settings()
                elif item["id"] == "profile:font":
                    self.state["font_mode"] = FONT_MODES[(FONT_MODES.index(self.state["font_mode"]) + 1) % len(FONT_MODES)]
                    self._notify(self.state["font_mode"].upper() + " FONT SELECTED")
                elif item["id"] == "profile:credits":
                    return
                elif item["id"] == "profile:crt":
                    self.state["crt_scanlines"] = not self.state["crt_scanlines"]
                    self._notify("CRT SWEEP " + ("ON" if self.state["crt_scanlines"] else "OFF"))
                else:
                    appearance = (self.state["theme"], self.state["mascot"])
                    index = APPEARANCES.index(appearance) if appearance in APPEARANCES else -1
                    self.state["theme"], self.state["mascot"] = APPEARANCES[(index + 1) % len(APPEARANCES)]
                    self._notify(("POWER ARMOR" if self.state["theme"] == "amber" else "GREEN") + " / " + self.state["mascot"].upper())

    def _search_input(self, key):
        if key == "DEL":
            self.search_query = self.search_query[:-1]
        elif key == "CLEAR":
            self.search_query = ""
            self.search_date = ""
            self.search_saved = False
        elif key == "DATE":
            dates = [""] + sorted(set(_event_date(item) for item in self.schedule if _event_date(item)))
            index = dates.index(self.search_date) if self.search_date in dates else 0
            self.search_date = dates[(index + 1) % len(dates)]
        elif key == "SAVED":
            self.search_saved = not self.search_saved
        elif key == "DONE":
            self.search_editing = False
        elif len(self.search_query) < 48:
            self.search_query += " " if key == "SPACE" else key
        self.state["selected"][self._key()] = 0

    def _detail_lines(self):
        item = self._detail_record()
        if not item:
            return ["NO ITEM SELECTED", "RETURN TO A LIST TO SELECT AN ITEM."]
        if item is self._detail_cache_item:
            return self._detail_cache_lines
        values = [item.get("name", item.get("title", "DETAILS"))]
        day = item.get("day") or item.get("date") or ""
        clock = item.get("time") or item.get("start")
        if day or clock:
            when = str(day) + (" " + _clock(clock) if clock else "")
            end = item.get("end") or item.get("end_time") or item.get("finish")
            if end: when += " - " + _clock(end)
            values.append(when)
        if item.get("location"):
            values.append(item["location"])
        speakers = item.get("speakers")
        if speakers:
            values.append("SPEAKERS: " + (", ".join(str(speaker) for speaker in speakers) if isinstance(speakers, (list, tuple)) else str(speakers)))
        detail = item.get("detail") or item.get("description")
        if detail:
            values.append(_display_times(detail))
        lines = []
        for value in values:
            row = ""
            for word in _ascii(value, 6000).upper().split():
                if row and len(row) + len(word) + 1 > 48:
                    lines.append(row)
                    row = ""
                while len(word) > 48:
                    lines.append(word[:48])
                    word = word[48:]
                row += (" " if row else "") + word
            if row: lines.append(row)
            lines.append("")
        self._detail_cache_item = item
        self._detail_cache_lines = lines or ["NO DETAILS AVAILABLE"]
        return self._detail_cache_lines

    def _map_action(self, action):
        view = self.state["map_views"][self.subtab]
        if action == "reset":
            view.update({"zoom": 1, "cx": 50, "cy": 50})
            self.map_pan = False
            self.map_cursor = None
        elif action == "pin":
            self.map_pan = False
            point = self.state["waypoints"][self.subtab]
            self.map_cursor = {"id": "manual", "name": "MANUAL PIN", "x": int(point["x"] if point else view["cx"]), "y": int(point["y"] if point else view["cy"])}
            self._notify("ARROWS: MOVE PIN   SELECT: PLACE")
        elif action == "clear_pin":
            self.state["waypoints"][self.subtab] = None
            self._notify("WAYPOINT CLEARED")
        elif action in ("zoom_in", "zoom_out"):
            view["zoom"] = max(1, min(8, view["zoom"] * (1.5 if action == "zoom_in" else 1 / 1.5)))
        elif action == "pan":
            self.map_pan = not self.map_pan
            self._notify("ARROWS: PAN   SELECT: FINISH" if self.map_pan else "MAP PAN FINISHED")
        elif action.startswith("pan"):
            deltas = {"pan_left": (-24, 0), "pan_right": (24, 0), "pan_up": (0, -18), "pan_down": (0, 18)}
            delta = deltas.get(action)
            if action.startswith("pan:"):
                parts = action[4:].split(":")
                if len(parts) == 2:
                    delta = (_number(parts[0], 0, -2000, 2000), _number(parts[1], 0, -2000, 2000))
            if delta:
                view["cx"] += delta[0] / (3.02 * view["zoom"])
                view["cy"] += delta[1] / (1.33 * view["zoom"])
        edge = 50 / view["zoom"]
        view["cx"] = max(edge, min(100 - edge, view["cx"]))
        view["cy"] = max(edge, min(100 - edge, view["cy"]))

    def serialize(self):
        """Return an independent JSON-safe save; telemetry is deliberately live."""
        result = _clone(self.state)
        result["effects"] = _clone(self.effects.state)
        return result

    def snapshot(self, include_content=True, display_only=False):
        """Return UI metadata; omit catalog/map copies in native animation loops."""
        complete = sum(1 for item in self.quests if self.state["quests"][item["id"]])
        packed = sum(1 for value in self.state["packed"].values() if value)
        xp = sum(int(_number(item.get("xp"), 25, 0, 10000)) for item in self.quests if self.state["quests"][item["id"]])
        xp += self.state["timer"]["sessions"] * 10
        level = int(_number(self.profile.get("level"), 1, 1, 99)) + xp // 100
        hints = {
            "STAT:STATUS": "HOLD SELECT: PROFILE   L/R: TABS",
            "STAT:PROFILE": "U/D: OPTION   SELECT: CHANGE / OPEN",
            "INV:GEAR": "SELECT: PACK / UNPACK",
            "INV:PACKED": "SELECT: UNPACK ITEM",
            "INV:DETAILS": "U/D: PAGES   SELECT: BACK   HOLD: SUBPAGE",
            "DATA:QUESTS": "SELECT: COMPLETE / REOPEN",
            "DATA:SCHEDULE": "SELECT: SAVE / UNSAVE",
            "DATA:MY SCHEDULE": "SELECT: SAVE / UNSAVE   HOLD: SEARCH",
            "DATA:SEARCH": "U/D: RESULTS   SELECT: SAVE   HOLD: DETAILS",
            "DATA:DETAILS": "U/D: PAGES   SELECT: BACK   HOLD: SUBPAGE",
            "MAP:WORLD": "U/D: LANDMARKS + ZOOM/PAN CONTROLS",
            "MAP:LOCAL": "U/D: BUILDINGS + ZOOM/PAN CONTROLS",
            "MAP:DETAILS": "U/D: PAGES   SELECT: BACK   HOLD: SUBPAGE",
            "RADIO:SENSORS": "U/D: SENSOR DETAILS   HOLD: FULL DETAILS",
            "RADIO:FOCUS": "U/D: TIMER CONTROLS   SELECT: ACTIVATE",
            "RADIO:SIGNAL": "VISUALIZER ONLY - NO FM AUDIO",
            "RADIO:DETAILS": "U/D: PAGES   SELECT: BACK   HOLD: SUBPAGE",
        }
        hint = "U/D: HELP PAGES   SELECT: CLOSE" if self.help_page is not None else "ARROWS: KEYS   SELECT: TYPE   HOLD: RESULTS" if self.search_editing else "ARROWS: PIN   SELECT: PLACE   HOLD: CANCEL" if self.map_cursor is not None else "ARROWS: PAN   SELECT: FINISH" if self.map_pan else hints[self._key()]
        if display_only:
            return {"hint": hint, "packed": packed, "inventory_total": len(self.inventory),
                    "completed": complete, "quests_total": len(self.quests), "xp": xp, "level": level,
                    "notice": self.notice if self.notice_time > 0 else ""}
        item = self.selected_item()
        detail = ""
        title = self.subtab
        if item:
            title = item.get("name", item.get("title", ""))
            detail = _display_times(item.get("detail", item.get("description", "")))
        metadata = self.effects.metadata()
        metadata.update({
            "tab": self.tab, "subtab": self.subtab, "theme": self.state["theme"], "mascot": self.state["mascot"],
            "font_mode": self.state["font_mode"],
            "pixel_glow": self.state["pixel_glow"], "crt_scanlines": self.state["crt_scanlines"] and not self.battery_saver, "crt_phase": self.crt_elapsed, "battery_saver": self.battery_saver,
            "title": _ascii(title), "detail": _ascii(detail, 500),
            "hint": hint, "selected": _clone(item),
            "selected_index": self.state["selected"][self._key()],
            "items": _clone(self._items()) if include_content else [], "packed": packed, "inventory_total": len(self.inventory),
            "completed": complete, "quests_total": len(self.quests), "xp": xp, "level": level,
            "timer": _clone(self.state["timer"]), "favorites": _clone(self.state["favorites"]),
            "personal_schedule": _clone(self.personal_schedule),
            "waypoint": _clone(self.state["waypoints"].get(self.subtab)),
            "map": _clone(self.maps[self.subtab]) if include_content and self.tab == "MAP" and self.subtab in self.maps else None,
            "map_view": _clone(self.state["map_views"].get(self.subtab)), "map_pan": self.map_pan,
            "map_cursor": _clone(self.map_cursor),
            "search_query": self.search_query, "search_date": self.search_date,
            "search_saved": self.search_saved, "search_editing": self.search_editing,
            "detail_page": self.detail_page, "detail_pages": max(1, (len(self._detail_lines()) + 10) // 11) if self.subtab == "DETAILS" else 0,
            "help_page": self.help_page, "subtab_regions": self._subtab_layout(),
            "profile": _clone(self.profile), "telemetry": _clone(self.telemetry),
            "notice": self.notice if self.notice_time > 0 else "",
        })
        return metadata

    def _line(self, x1, y1, x2, y2, shade=3):
        self.commands.append(["line", int(x1), int(y1), int(x2), int(y2), shade])

    def _rect(self, x, y, w, h, shade=3):
        self.commands.append(["rect", int(x), int(y), max(0, int(w)), max(0, int(h)), shade])

    def _text(self, value, x, y, scale=1, shade=3):
        self.commands.append(["text", _ascii(value), int(x), int(y), scale, shade])

    def _center(self, value, y, scale=1, shade=3, center=160):
        value = _ascii(value)
        self._text(value, center - (len(value) * 6 - 1) * scale / 2, y, scale, shade)

    def _circle(self, x, y, radius, shade=3, fill=False):
        self.commands.append(["circle", int(x), int(y), int(radius), shade, fill])

    def _poly(self, points, shade=3, fill=False):
        self.commands.append(["poly", [[int(x), int(y)] for x, y in points], shade, fill])

    def _box(self, x, y, w, h, shade=3):
        self._line(x, y, x + w, y, shade)
        self._line(x, y + h, x + w, y + h, shade)
        self._line(x, y, x, y + h, shade)
        self._line(x + w, y, x + w, y + h, shade)

    def _wrap(self, text, x, y, width, lines=2, shade=3):
        words = _ascii(text, 500).upper().split()
        row = ""
        rows = []
        for word in words:
            if row and len(row) + len(word) + 1 > width:
                rows.append(row)
                row = word
            else:
                row += (" " if row else "") + word
        if row:
            rows.append(row)
        for index, row in enumerate(rows[:lines]):
            self._text(_short(row, width), x, y + index * 11, 1, shade)

    def _bar(self, x, y, width, value, total, shade=3):
        self._box(x, y, width, 6, 2)
        if total:
            amount = min(width - 2, int((width - 2) * value / total))
            if amount > 0:
                self._rect(x + 1, y + 1, amount, 5, shade)

    def render(self):
        """Return a complete 320x240 frame using the documented command schema."""
        self.commands = [["clear"]]
        snapshot = self.snapshot(display_only=True)
        self._header()
        if self.help_page is not None:
            self._render_help()
        elif self.subtab == "DETAILS":
            self._render_details()
        elif self.tab == "STAT":
            self._render_status(snapshot) if self.subtab == "STATUS" else self._render_profile(snapshot)
        elif self.tab == "INV":
            self._render_inventory()
        elif self.tab == "DATA":
            if self.subtab == "SEARCH":
                self._render_search()
            else:
                self._render_quests() if self.subtab == "QUESTS" else self._render_schedule()
        elif self.tab == "MAP":
            self._render_map()
        elif self.subtab == "SENSORS":
            self._render_sensors()
        else:
            self._render_focus() if self.subtab == "FOCUS" else self._render_signal()
        self._footer(snapshot)
        if self.battery_saver:
            self.effects.levels = (0.0,) * 4
        else:
            self.effects.lights("profile" if self.tab == "STAT" and self.subtab == "PROFILE" else "fallout")
        self.commands.extend(self.effects.overlay())
        return self.commands

    def _subtab_layout(self):
        """Share exact clickable/header geometry with browser adapters."""
        clock = _clock(self.telemetry["time"], "--:--") + " " + self.telemetry["time_label"]
        limit = 267 if self.tab == "MAP" and self.subtab in self.maps else 305 - len(clock) * 6
        options = SUBTABS[self.tab]
        active = options.index(self.subtab)
        start = 0
        if sum(len(sub) * 6 + 21 for sub in options) > limit - 10:
            start = max(0, active - 1)
        while start < active and sum(len(sub) * 6 + 21 for sub in options[start:active + 1]) > limit - 10:
            start += 1
        regions, x = [], 10
        for sub in options[start:]:
            width = len(sub) * 6
            if x + width > limit:
                break
            regions.append({"name": sub, "x": x, "y": 32, "width": width, "height": 16})
            x += width + 21
        return regions

    def _header(self):
        positions = (10, 66, 111, 169, 217)
        self._line(6, 27, 314, 27, 2)
        for index, tab in enumerate(TABS):
            x = positions[index]
            active = self.tab == tab
            self._text(tab, x, 8, 2, 4 if active else 2)
            if active:
                width = len(tab) * 12 + 7
                self._line(x - 4, 5, x + width - 5, 5, 4)
                self._line(x - 4, 5, x - 4, 27, 4)
                self._line(x + width - 5, 5, x + width - 5, 27, 4)
                self._line(x - 3, 27, x + width - 6, 27, 0)
        battery = self.telemetry["battery"]
        battery_label = "--%" if battery is None else str(int(battery)) + "%"
        self._text(battery_label, 313 - len(battery_label) * 6, 8, 1, 3)
        self._box(288, 19, 21, 5, 2)
        self._rect(310, 20, 2, 3, 2)
        if self.battery_saver:
            self._text("ECO", 290, 29, 1, 3)
        if battery is not None:
            self._rect(290, 20, int(17 * battery / 100), 4, 3)
        regions = self._subtab_layout()
        for region in regions:
            sub, x = region["name"], region["x"]
            active = sub == self.subtab
            self._text(sub, x, 36, 1, 4 if active else 2)
            if active:
                self._line(x, 46, x + len(sub) * 6 - 2, 46, 4)
        if regions and regions[0]["name"] != SUBTABS[self.tab][0]:
            self._text("<", 1, 36, 1, 2)
        if self.tab == "MAP" and self.subtab in self.maps:
            zoom = self.state["map_views"][self.subtab]["zoom"]
            self._text(str(round(zoom, 1)) + "X", 277, 37, 1, 2)
        else:
            clock = _clock(self.telemetry["time"], "--:--") + " " + self.telemetry["time_label"]
            self._text(clock, 313 - len(clock) * 6, 37, 1, 2)

    def _footer(self, status):
        hint = status["notice"] or status["hint"]
        self._rect(5, 209, 310, 10, 0)
        self._center(_short(hint, 50), 210, 1, 4 if status["notice"] else 2)
        self._line(6, 222, 314, 222, 2)
        self._text("HP", 8, 229, 1, 4)
        self._bar(26, 229, 72, status["packed"], status["inventory_total"])
        self._text(str(status["packed"]) + "/" + str(status["inventory_total"]), 103, 229, 1, 3)
        self._center("LVL " + _padded(status["level"]), 229, 1, 4)
        self._text("AP", 207, 229, 1, 4)
        self._bar(225, 229, 59, status["completed"], status["quests_total"])
        self._text(_padded(status["completed"]), 294, 229, 1, 3)

    def _render_status(self, status):
        name = _ascii(self.profile.get("name", "WANDERER"), 32).upper()
        self._text(_short(name, 17), 12, 60, 2, 4)
        self._line(12, 81, 191, 81, 2)
        self._text(_short(self.profile.get("organization", ""), 17).upper(), 12, 90, 2, 3)
        self._text(_short(self.profile.get("position", self.profile.get("role", "DEVELOPER")), 17).upper(), 12, 115, 2, 3)
        handle = self.profile.get("handle", "")
        if handle:
            self._text("@" + _short(handle, 27), 12, 142, 1, 2)
        self._text("GITHUB UNIVERSE 2026", 12, 161, 1, 3)
        self._text("SAN FRANCISCO / FORT MASON", 12, 177, 1, 2)
        self._text("XP " + _padded(status["xp"], 3) + "   QUESTS " + _padded(status["completed"]), 12, 195, 1, 3)
        self._mascot(260, 56)

    def _mascot(self, cx, top):
        """Decode only the current animation frame, reusing it until it advances."""
        left = cx - VAULT_BOY_WIDTH // 2
        frames, palette = (), ()
        if self.state["mascot"] == "color":
            frames, palette = VAULT_BOY_COLOR_FRAMES, VAULT_BOY_COLOR_PALETTE
        elif self.state["mascot"] == "shaded":
            frames, palette = VAULT_BOY_SHADED_FRAMES, VAULT_BOY_SHADED_PALETTE
        frames = frames or VAULT_BOY_FRAMES
        index = int(self.phase / VAULT_BOY_DELAY) % len(frames)
        key = (self.state["mascot"], self.state["theme"], index, left, top)
        if key == self._mascot_key:
            self.commands.extend(self._mascot_commands)
            return
        if self.state["mascot"] == "shaded":
            if self.state["theme"] == "amber":
                # Preserve the original animation's brightness and dark ink;
                # recolor its green phosphor to Power Armor's amber/gold.
                palette = tuple((g, int(g * 0.75), int(g * 0.25)) for r, g, b in palette)
            elif self.state["theme"] == "ice":
                palette = tuple((int(g * 0.55), int(g * 0.87), g) for r, g, b in palette)
        commands, frame = [], frames[index]
        if palette:
            for color_index, rectangles in enumerate(frame):
                r, g, b = palette[color_index]
                for offset in range(0, len(rectangles), 4):
                    commands.append(["rgbrect", left + rectangles[offset], top + rectangles[offset + 1],
                                     rectangles[offset + 2], rectangles[offset + 3], r, g, b])
        else:
            for offset in range(0, len(frame), 4):
                commands.append(["rect", left + frame[offset], top + frame[offset + 1],
                                 frame[offset + 2], frame[offset + 3], 4])
        self._mascot_key, self._mascot_commands = key, commands
        self.commands.extend(commands)

    def _render_profile(self, status):
        self._text("PERSONAL INFORMATION", 12, 59, 1, 2)
        self._text(_short(self.profile.get("name", "WANDERER"), 24).upper(), 12, 75, 2, 4)
        self._text(_short(self.profile.get("organization", ""), 48).upper(), 12, 99, 1, 3)
        self._text(_short(self.profile.get("position", self.profile.get("role", "DEVELOPER")), 48).upper(), 12, 114, 1, 3)
        handle = self.profile.get("handle", "your-handle")
        self._text("@" + _short(handle, 43), 12, 129, 1, 2)
        self._line(12, 144, 307, 144, 2)
        theme = "GOLD" if self.state["theme"] == "amber" else self.state["theme"].upper()
        labels = ["STYLE: " + theme + " / " + self.state["mascot"].upper(), "FONT: " + self.state["font_mode"].upper(), "CONTROLS / HELP", "LIGHTS / REMINDERS", "CRT SWEEP: " + ("ON" if self.state["crt_scanlines"] else "OFF"), "Created with AI by DChevrier1"]
        self._list_rows(PROFILE_CONTROLS, self.state["selected"][self._key()], top=158, rows=3, labels=labels)

    def _render_help(self):
        page = HELP_PAGES[self.help_page]
        self._text(page[0], 12, 58, 1, 4)
        for index, line in enumerate(page[1:]):
            self._text(line, 12, 78 + index * 12, 1, 3)
        self._center("HELP " + str(self.help_page + 1) + " / " + str(len(HELP_PAGES)), 199, 1, 2)

    def _render_details(self):
        lines = self._detail_lines()
        pages = max(1, (len(lines) + 10) // 11)
        self.detail_page = min(self.detail_page, pages - 1)
        self._text(self.state["detail_sources"][self.tab] + " / FULL DETAILS", 12, 57, 1, 2)
        for index, line in enumerate(lines[self.detail_page * 11:(self.detail_page + 1) * 11]):
            self._text(line, 12, 75 + index * 11, 1, 3)
        self._center("PAGE " + str(self.detail_page + 1) + " / " + str(pages), 199, 1, 2)

    def _render_search(self):
        if self.search_editing:
            self._text("FIND: " + (self.search_query[-42:] or "_"), 12, 57, 1, 4)
            for index, key in enumerate(SEARCH_KEYS):
                x, y = 12 + (index % 7) * 43, 81 + (index // 7) * 17
                active = index == self.search_key
                if active: self._rect(x - 2, y - 3, 41, 14, 3)
                self._text(key, x + (40 - len(key) * 6) // 2, y, 1, 0 if active else 3)
            self._text("DAY: " + (self.search_date or "ALL") + "   " + ("SAVED" if self.search_saved else "ALL SESSIONS"), 12, 183, 1, 2)
            self._text(str(len(self._search_results())) + " MATCHES  /  DONE TO BROWSE", 12, 198, 1, 3)
            return
        items = self._items()
        selected = self.state["selected"][self._key()]
        self._text(str(len(items) - 1) + " MATCHES: " + _short(self.search_query or "ALL", 32), 12, 57, 1, 2)
        self._list_rows(items, selected, top=76, rows=5, marks=self._schedule_mark)
        self._line(12, 164, 306, 164, 2)
        self._wrap(items[selected].get("title", ""), 12, 176, 48, 3, 3)

    def _list_rows(self, items, selected, top=60, rows=6, width=294, labels=None, marks=None):
        first = max(0, min(selected - rows // 2, len(items) - rows))
        for row, index in enumerate(range(first, min(first + rows, len(items)))):
            item = items[index]
            label = labels(item) if callable(labels) else labels[index] if labels else item.get("name", item.get("title", ""))
            mark = marks(item) if callable(marks) else marks[index] if marks else ""
            y = top + row * 17
            active = index == selected
            if active:
                self._rect(10, y - 3, width, 14, 3)
            self._text(mark, 14, y, 1, 0 if active else 2)
            self._text(_short(label, (width - 36) // 6).upper(), 32, y, 1, 0 if active else 3)
        if len(items) > rows:
            self._line(309, top - 3, 309, top + rows * 17 - 7, 1)
            height = rows * 17 - 5
            cursor = int((height - 9) * selected / max(1, len(items) - 1))
            self._rect(308, top - 3 + cursor, 3, 9, 3)

    def _render_inventory(self):
        items = self._items()
        if not items:
            self._center("NOTHING PACKED YET", 99, 2, 3)
            self._center("OPEN GEAR TO BUILD YOUR LOADOUT", 129, 1, 2)
            return
        selected = self.state["selected"][self._key()]
        self._list_rows(items, selected, rows=6, marks=["+" if self.state["packed"][item["id"]] else "-" for item in items])
        item = items[selected]
        self._line(12, 166, 305, 166, 2)
        self._text("PACKED" if self.state["packed"][item["id"]] else "NEEDED", 12, 175, 1, 4)
        self._wrap(item.get("detail", item.get("description", "")), 12, 190, 48, 2, 2)

    def _render_quests(self):
        items = self.quests
        if not items:
            self._center("NO ACTIVE OBJECTIVES", 105, 2)
            return
        selected = self.state["selected"][self._key()]
        self._list_rows(items, selected, rows=5, marks=["X" if self.state["quests"][item["id"]] else ">" for item in items])
        item = items[selected]
        self._line(12, 149, 306, 149, 2)
        xp = int(_number(item.get("xp"), 25, 0, 10000))
        self._text(("COMPLETED" if self.state["quests"][item["id"]] else "ACTIVE OBJECTIVE") + "    +" + str(xp) + " XP", 12, 158, 1, 4)
        self._wrap(item.get("detail", item.get("description", "")), 12, 177, 48, 3, 3)

    def _schedule_label(self, item):
        day = str(item.get("day") or item.get("date") or "")
        return day + (" " if day else "") + _clock(item.get("time") or item.get("start")) + " " + str(item.get("title", "EVENT"))

    def _schedule_mark(self, item):
        return "R" if item.get("personal_reminder") and item["id"] in self.personal_schedule else "B" if item["id"] in self.personal_schedule else "*" if item["id"] in self.state["favorites"] else " "

    def _render_schedule(self):
        items = self._items()
        if not items:
            if self.subtab == "MY SCHEDULE":
                self._center("NO SAVED SESSIONS", 102, 2)
                self._center("SELECT SESSIONS IN SCHEDULE", 130, 1, 2)
            else:
                self._center("AGENDA NOT YET LOADED", 102, 2)
                self._center("CHECK OFFICIAL UNIVERSE UPDATES", 130, 1, 2)
            return
        selected = self.state["selected"][self._key()]
        self._list_rows(items, selected, rows=5, labels=self._schedule_label, marks=self._schedule_mark)
        item = items[selected]
        self._line(12, 149, 306, 149, 2)
        self._text(_short(item.get("day", "") + "  " + item.get("location", ""), 48).upper(), 12, 159, 1, 4)
        # The list truncates long titles; the selected session needs its full
        # name on the badge where there is no companion detail panel.
        self._wrap(item.get("title", "EVENT"), 12, 177, 48, 3, 3)

    def _map_point(self, point, data):
        if isinstance(point, dict):
            x, y = point.get("x", 50), point.get("y", 50)
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            x, y = point[0], point[1]
        else:
            x, y = 50, 50
        if data.get("coords") == "screen":
            x = (_number(x, 160, 8, 312) - 9) / 3.02
            y = (_number(y, 124.5, 56, 194) - 58) / 1.33
        else:
            x = _number(x, 50, 0, 100)
            y = _number(y, 50, 0, 100)
        view = self.state["map_views"][self.subtab]
        return (int(160 + (x - view["cx"]) * 3.02 * view["zoom"]),
                int(124.5 + (y - view["cy"]) * 1.33 * view["zoom"]))

    def _map_line(self, x1, y1, x2, y2, shade=3):
        """Liang-Barsky clipping keeps zoomed geometry inside the map viewport."""
        dx, dy = x2 - x1, y2 - y1
        start, finish = 0.0, 1.0
        for p, q in ((-dx, x1 - 8), (dx, 312 - x1), (-dy, y1 - 56), (dy, 194 - y1)):
            if p == 0:
                if q < 0:
                    return
                continue
            ratio = q / p
            if p < 0:
                start = max(start, ratio)
            else:
                finish = min(finish, ratio)
            if start > finish:
                return
        self._line(max(8, min(312, x1 + start * dx)), max(56, min(194, y1 + start * dy)),
                   max(8, min(312, x1 + finish * dx)), max(56, min(194, y1 + finish * dy)), shade)

    def _map_visible(self, x, y, radius=0):
        return 8 + radius <= x <= 312 - radius and 56 + radius <= y <= 194 - radius

    def _render_map_geometry(self, data):
        view = self.state['map_views'][self.subtab]
        edge = 50 / view['zoom']
        for offset in range(0, 101, 10):
            for first, last in (((offset, 0), (offset, 100)), ((0, offset), (100, offset))):
                a, b = self._map_point(first, {}), self._map_point(last, {})
                self._map_line(a[0], a[1], b[0], b[1], 1)
        for path in data.get("paths", []):
            if isinstance(path, dict):
                if path.get('min_zoom', 1) > view['zoom']:
                    continue
                box = path.get('bbox')
                if box and data.get('coords') == 'normalized' and (box[2] < view['cx'] - edge or box[0] > view['cx'] + edge or box[3] < view['cy'] - edge or box[1] > view['cy'] + edge):
                    continue
            raw_points = path.get("points", []) if isinstance(path, dict) else path
            if not isinstance(raw_points, (list, tuple)):
                continue
            points = [self._map_point(point, data) for point in raw_points]
            shade = 3 if isinstance(path, dict) and path.get("kind") == "building" else 2
            for index in range(1, len(points)):
                self._map_line(points[index - 1][0], points[index - 1][1], points[index][0], points[index][1], shade)
            if isinstance(path, dict) and path.get("closed") and len(points) > 2:
                self._map_line(points[-1][0], points[-1][1], points[0][0], points[0][1], shade)
        for room in data.get("rooms", []):
            if not isinstance(room, dict):
                continue
            start = self._map_point(room, data)
            end = self._map_point([room.get("x", 0) + room.get("w", 0), room.get("y", 0) + room.get("h", 0)], data)
            for a, b in ((start, (end[0], start[1])), ((end[0], start[1]), end), (end, (start[0], end[1])), ((start[0], end[1]), start)):
                self._map_line(a[0], a[1], b[0], b[1], 2)
            if self._map_visible(start[0], start[1]) and self._map_visible(end[0], end[1]) and end[0] - start[0] > 50 and end[1] - start[1] > 18:
                self._text(_short(room.get("name", ""), (end[0] - start[0] - 8) // 6).upper(), start[0] + 4, start[1] + 6, 1, 2)
    def _render_map(self):
        data = self.maps[self.subtab]
        view = self.state["map_views"][self.subtab]
        key = (self.subtab, view["zoom"], view["cx"], view["cy"], self.state['font_mode'])
        if getattr(self, "_map_geometry_key", None) != key:
            output = self.commands
            self.commands = []
            self._render_map_geometry(data)
            self._map_geometry_commands = self.commands
            self._map_geometry_key = key
            self.commands = output
        self.commands.extend(self._map_geometry_commands)
        item = self.selected_item()
        for poi in data["pois"]:
            x, y = self._map_point(poi, data)
            if not self._map_visible(x, y, 4):
                continue
            active = item and poi["id"] == item["id"]
            self._rect(x - 4, y - 4, 9, 9, 0)
            self._circle(x, y, 3, 4 if active else 3, active)
            if active:
                radius = 7 + int(math.sin(self.phase * 4) > 0)
                self._map_line(x - radius, y, x - 5, y, 4)
                self._map_line(x + 5, y, x + radius, y, 4)
                self._map_line(x, y - radius, x, y - 5, 4)
                self._map_line(x, y + 5, x, y + radius, 4)
        point = self.state["waypoints"][self.subtab]
        if point:
            x, y = self._map_point(point, {} if point["id"] == "manual" else data)
            points = [(x, y - 12), (x - 5, y - 20), (x + 5, y - 20), (x, y - 12)]
            for index in range(1, len(points)):
                a, b = points[index - 1], points[index]
                self._map_line(a[0], a[1], b[0], b[1], 4)
            self._map_line(x, y - 11, x, y - 5, 4)
        if self.map_cursor is not None:
            x, y = self._map_point(self.map_cursor, {})
            self._map_line(x - 9, y, x + 9, y, 4)
            self._map_line(x, y - 9, x, y + 9, 4)
            self._rect(199, 57, 87, 11, 0)
            self._text("PIN " + str(int(self.map_cursor["x"])) + "," + str(int(self.map_cursor["y"])), 200, 59, 1, 4)
        self._rect(10, 57, 179, 11, 0)
        self._text(_short(data.get("note", "MANUAL LANDMARKS"), 29).upper(), 12, 59, 1, 2)
        if data.get("north") == "right":
            self._text("N", 301, 73, 1, 3)
            self._line(280, 76, 296, 76, 3)
            self._poly([(291, 72), (296, 76), (291, 80)], 3)
        else:
            self._text("N", 297, 60, 1, 3)
            self._line(300, 72, 300, 87, 3)
            self._poly([(296, 77), (300, 72), (304, 77)], 3)
        if data.get("attribution"):
            attribution = _short(data["attribution"], 46).upper()
            self._rect(10, 182, len(attribution) * 6 + 5, 12, 0)
            self._text(attribution, 12, 185, 1, 2)
        self._rect(8, 197, 305, 10, 0)
        label = item.get("name", "SELECT A LANDMARK") if item else data.get("title", "MAP")
        self._text("> " + _short(label, 43).upper(), 10, 199, 1, 4)

    def _render_sensors(self):
        items = self._items()
        if not items:
            self._center("BADGE SENSOR TELEMETRY", 79, 2, 4)
            self._center("LIVE READINGS REQUIRE THE 2026 BADGE", 117, 1, 2)
            self._center("NO SENSOR DATA AVAILABLE", 143, 1, 3)
            return
        selected = self.state["selected"][self._key()]
        labels = []
        for item in items:
            value = str(item.get("value")) if item.get("available") and item.get("value") is not None else "UNAVAILABLE"
            unit = str(item.get("unit") or "") if item.get("available") else ""
            labels.append(str(item.get("name") or item["id"]) + "  " + value + (" " + unit if unit else ""))
        self._list_rows(items, selected, rows=6, labels=labels, marks=["+" if item.get("available") else "-" for item in items])
        self._line(12, 166, 306, 166, 2)
        self._wrap(items[selected].get("detail", "Live sensor reading from this badge."), 12, 177, 48, 3, 3)

    def _render_focus(self):
        timer = self.state["timer"]
        seconds = int(math.ceil(timer["remaining"]))
        value = _padded(seconds // 60) + ":" + _padded(seconds % 60)
        self._center("DEEP WORK TRANSMISSION", 59, 1, 2)
        self._center(value, 82, 4, 4)
        if timer["running"]:
            status = "FOCUS CHANNEL OPEN"
        elif timer["remaining"] == 0:
            status = "SESSION COMPLETE"
        elif timer["remaining"] < timer["duration"]:
            status = "TRANSMISSION PAUSED"
        else:
            status = "READY TO TRANSMIT"
        self._center(status, 125, 1, 3)
        self._bar(53, 142, 214, timer["duration"] - timer["remaining"], timer["duration"], 4)
        labels = ["PAUSE" if timer["running"] else "RESUME" if 0 < timer["remaining"] < timer["duration"] else "START", "DURATION: " + str(timer["duration"] // 60) + " MIN", "RESET TIMER"]
        self._list_rows(FOCUS_CONTROLS, self.state["selected"][self._key()], top=160, rows=3, labels=labels)

    def _wave(self, x, y, width, height, animate=True):
        last = (x, y)
        for offset in range(0, width + 1, 3):
            phase = self.phase * 5 if animate else 0
            signal = (math.sin(offset * 0.055 + phase) * math.sin(offset * 0.018 - phase * 0.31))
            point = (x + offset, y + int(signal * height))
            self._line(last[0], last[1], point[0], point[1], 3)
            last = point

    def _render_signal(self):
        self._text("UNIVERSE FIELD SIGNAL", 12, 60, 1, 4)
        self._text("VISUAL DEMO", 237, 60, 1, 2)
        self._box(12, 79, 294, 72, 2)
        self._line(13, 115, 305, 115, 1)
        self._wave(14, 115, 289, 29, True)
        for index in range(30):
            height = 3 + int((math.sin(index * 0.6 + self.phase * 3) + 1) * 12)
            self._rect(16 + index * 10, 183 - height, 6, height, 2 if index % 4 else 3)
        self._center("NO FM RECEIVER / NO AUDIO PLAYBACK", 196, 1, 2)
