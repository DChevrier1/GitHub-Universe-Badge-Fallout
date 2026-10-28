"""Pip-Boy terminal for the Universe 2026 badge and Badgeware playground.

The 320x240 draw commands and application state come from core.py. This thin
adapter translates only display, input, telemetry and persistent storage.
"""

# BUNDLE_IMPORTS_START
import os
import sys

# The badge launcher normally sets cwd and sys.path itself. Keep direct
# execution (including a transient mpremote mount) useful as well.
for _app_path in ("/system/apps/fallout", "/remote/apps/fallout", "/system/apps/pipboy", "/remote/apps/pipboy"):
    try:
        os.stat(_app_path + "/core.py")
        if _app_path not in sys.path:
            sys.path.insert(0, _app_path)
        break
    except OSError:
        pass

try:
    from .font5x7 import GLYPHS
    from .fontvector import VECTOR_GLYPHS
    from .data import CONFIG
    from .core import PipBoy
    from .companion import CaseLightDriver, ReminderStore, pacific_clock
except (ImportError, ValueError):
    from font5x7 import GLYPHS
    from fontvector import VECTOR_GLYPHS
    from data import CONFIG
    from core import PipBoy
    from companion import CaseLightDriver, ReminderStore, pacific_clock
# BUNDLE_IMPORTS_END

import math
import json
import builtins
import sys
import time


PALETTES = {
    "green": [(2, 10, 5), (8, 36, 16), (40, 110, 51), (84, 236, 112), (156, 255, 171)],
    "amber": [(12, 7, 1), (43, 25, 4), (102, 64, 11), (255, 183, 64), (255, 229, 165)],
    "ice": [(3, 9, 12), (11, 32, 41), (33, 78, 94), (100, 224, 255), (184, 247, 255)],
    "white": [(7, 9, 8), (30, 35, 31), (76, 88, 78), (216, 242, 220), (245, 255, 246)],
}


class BadgeRenderer:
    """Rasterize the same command list used by the local simulator."""

    def __init__(self, surface, colors, vectors, shapes):
        self.screen = surface
        self.color = colors
        self.vec2 = vectors
        self.shape = shapes
        self.theme = None
        self.font_mode = "pixel"
        self.pixel_glow = False
        self.pens = []
        self.pixel_cache = {}
        self.rgb_pens = {}
        self._shade = None
        self._rgb = None
        # Collapse horizontal runs in each glyph so a 5x7 character typically
        # needs 10-15 native rectangles, not 35 Python pixel operations.
        self.glyph_runs = {}
        for char, rows in GLYPHS.items():
            runs = []
            for row, bits in enumerate(rows):
                column = 0
                while column < 5:
                    if bits & (16 >> column):
                        start = column
                        while column < 5 and bits & (16 >> column):
                            column += 1
                        runs.append((start, row, column - start))
                    else:
                        column += 1
            self.glyph_runs[char] = runs

    def pen(self, shade):
        shade = max(0, min(4, int(shade)))
        if shade != self._shade:
            self.screen.pen = self.pens[shade]
            self._shade = shade
            self._rgb = None

    def _pixel_glyph(self, char, x, y, scale):
        char = char.upper() if "a" <= char <= "z" else char
        char = char if char in self.glyph_runs else "?"
        # Native UI uses whole positions/scales. Fractional or clipped glyphs
        # still round exactly as before but do not create unbounded cache keys.
        cacheable = x >= 0 and y >= 0 and x == int(x) and y == int(y)
        key = (char, scale) if cacheable else None
        if key is not None and key in self.pixel_cache:
            return self.pixel_cache[key]
        base_x, base_y = int(x), int(y)
        core = []
        for col, row, width in self.glyph_runs[char]:
            left, top = int(x + col * scale), int(y + row * scale)
            width_px = int(x + (col + width) * scale) - left
            height_px = int(y + (row + 1) * scale) - top
            if width_px > 0 and height_px > 0:
                core.append([left - base_x, top - base_y, width_px, height_px])
        glyph = (core,)
        if key is not None:
            if len(self.pixel_cache) >= 128:
                self.pixel_cache.clear()
            self.pixel_cache[key] = glyph
        return glyph

    def text(self, value, x, y, scale, shade=3):
        scale = max(0.5, float(scale))
        start = x
        pixel_glyphs = []
        for char in str(value):
            if char == "\n":
                x = start
                y += 8 * scale
                continue
            if x > -6 * scale and x < 320 and y > -7 * scale and y < 240:
                if self.font_mode == "vector":
                    # Thicker strokes grow into the existing 5x7 cell rather
                    # than changing advance. Tiny labels retain open counters.
                    weight = max(1, int(scale))
                    for path in VECTOR_GLYPHS.get(char, VECTOR_GLYPHS["?"]):
                        for offset in range(0, len(path) - 2, 2):
                            x1, y1 = int(x + path[offset] * scale), int(y + path[offset + 1] * scale)
                            x2, y2 = int(x + path[offset + 2] * scale), int(y + path[offset + 3] * scale)
                            if x1 == x2 and y1 == y2:
                                self.screen.rectangle(x1, y1, weight, weight)
                            else:
                                for dy in range(weight):
                                    for dx in range(weight):
                                        self.screen.line(x1 + dx, y1 + dy, x2 + dx, y2 + dy)
                else:
                    pixel_glyphs.append((int(x), int(y), self._pixel_glyph(char, x, y, scale)))
            x += 6 * scale
        if pixel_glyphs:
            self.pen(shade)
            for left, top, glyph in pixel_glyphs:
                for col, row, width, height in glyph[0]:
                    self.screen.rectangle(left + col, top + row, width, height)

    def draw(self, commands, theme="green", font_mode="pixel", pixel_glow=False, crt_scanlines=False, crt_phase=0):
        self.font_mode = "vector" if font_mode == "vector" else "pixel"
        self.pixel_glow = False
        if theme != self.theme:
            self.theme = theme
            palette = PALETTES.get(theme, PALETTES["green"])
            self.pens = [self.color.rgb(*rgb) for rgb in palette]
        # The runtime may reset its pen before every frame.
        self._shade = None
        self._rgb = None
        for command in commands:
            kind = command[0]
            if kind == "clear":
                self.pen(0)
                self.screen.rectangle(0, 0, 320, 240)
            elif kind == "rect":
                _, x, y, width, height, shade = command
                self.pen(shade)
                self.screen.rectangle(int(x), int(y), int(width), int(height))
            elif kind == "rgbrect":
                _, x, y, width, height, red, green, blue = command
                rgb = (red, green, blue)
                if rgb not in self.rgb_pens:
                    self.rgb_pens[rgb] = self.color.rgb(*rgb)
                if rgb != self._rgb:
                    self.screen.pen = self.rgb_pens[rgb]
                    self._rgb = rgb
                # Raw sprite colors must not leave the next themed command
                # believing its previous palette pen is still selected.
                self._shade = None
                self.screen.rectangle(int(x), int(y), int(width), int(height))
            elif kind == "line":
                _, x1, y1, x2, y2, shade = command
                self.pen(shade)
                self.screen.line(int(x1), int(y1), int(x2), int(y2))
            elif kind == "text":
                _, value, x, y, scale, shade = command
                self.pen(shade)
                self.text(value, x, y, scale, self._shade)
            elif kind == "poly":
                _, points, shade, fill = command
                self.pen(shade)
                if len(points) < 2:
                    continue
                if fill and len(points) > 2:
                    self.screen.shape(self.shape.custom([self.vec2(*point) for point in points]))
                else:
                    for index, point in enumerate(points):
                        other = points[(index + 1) % len(points)]
                        self.screen.line(int(point[0]), int(point[1]), int(other[0]), int(other[1]))
            elif kind == "circle":
                _, x, y, radius, shade, fill = command
                self.pen(shade)
                if fill:
                    self.screen.circle(self.vec2(x, y), radius)
                else:
                    # Closed one-pixel outline. No undocumented stroke API.
                    points = [(int(x + radius * math.cos(i * math.pi / 16)),
                               int(y + radius * math.sin(i * math.pi / 16))) for i in range(32)]
                    for index, point in enumerate(points):
                        other = points[(index + 1) % 32]
                        self.screen.line(point[0], point[1], other[0], other[1])

        if crt_scanlines:
            # Translucent overlay after ALL content, including headers and text.
            top = int(crt_phase * 96) - 12
            tint = PALETTES.get(theme, PALETTES['green'])[3]
            for offset in range(12):
                y = top + offset
                if 0 <= y < 240:
                    self.screen.pen = self.color.rgb(tint[0], tint[1], tint[2], 24 + offset * 7)
                    self.screen.rectangle(0, y, 320, 1)
            self._shade = None
            self._rgb = None



class BadgeInputs:
    """Use orientation-aware controls and tap/hold Select on every device."""

    def __init__(self, device, namespace):
        self.badge = device
        self.keys = []
        for action, logical, fallback in (
            ("left", "BUTTON_LEFT", "BUTTON_A"),
            ("right", "BUTTON_RIGHT", "BUTTON_C"),
            ("up", "BUTTON_UP", "BUTTON_UP"),
            ("down", "BUTTON_DOWN", "BUTTON_DOWN"),
            ("select", "BUTTON_SELECT", "BUTTON_B"),
            ("back", "BUTTON_BACK", None),
            ("menu", "BUTTON_MENU", None),
            ("home", "BUTTON_HOME", None),
        ):
            button = namespace.get(logical)
            if button is None and fallback:
                button = namespace.get(fallback)
            if button is not None:
                self.keys.append((action, button))
        self.select_time = 0
        self.select_active = False
        self.select_long = False
        self.repeats = {}

    def read(self, dt, pan=False):
        actions = []
        for action, button in self.keys:
            pressed = self.badge.pressed(button)
            held = self.badge.held(button)
            if action == "select":
                # Delay taps until release: a long press changes section and
                # must never activate the previously highlighted item first.
                if pressed:
                    self.select_time = 0
                    self.select_active = True
                    self.select_long = False
                elif self.select_active and held:
                    # dt spans the interval before this sample. On the first
                    # press it includes time before the button was down, which
                    # may be a long rendering frame in the web playground.
                    self.select_time += dt
                    if self.select_time >= 0.55 and not self.select_long:
                        actions.append("menu")
                        self.select_long = True
                if self.select_active and self.badge.released(button):
                    if not self.select_long:
                        actions.append("select")
                    self.select_active = False
                continue
            if pressed:
                actions.append(action)
                self.repeats[action] = 0.0
            elif held and (action in ("up", "down") or (pan and action in ("left", "right"))):
                elapsed = self.repeats.get(action, 0) + dt
                if elapsed >= 0.40:
                    actions.append(action)
                    # Emit at most one repeat after a slow frame. Do not replay
                    # its missed repeats as a burst on subsequent fast frames.
                    elapsed = 0.40 - 0.14
                self.repeats[action] = elapsed
            elif not held:
                self.repeats.pop(action, None)
        return actions


class BadgeSensors:
    """Read documented APIs without changing the board's peripheral setup.

    The 2026 firmware documents relative IMU values, not their physical scale.
    Browser/desktop playground data is never presented as hardware readings.
    """

    ACTIONS = ("up", "down", "left", "right", "select", "back", "menu", "home")

    def __init__(self, device, namespace, native=None):
        self.badge = device
        self.ns = namespace
        self.native = sys.platform == "rp2" if native is None else native
        self.ir_pin = None
        # Only the custom 2026 device exposes both of these APIs. GPIO17 is
        # different on older boards. A Pin handle with no mode argument does
        # not change its mode, pull resistor, interrupt, or output state.
        if self.native and hasattr(device, "imu") and hasattr(device, "touched"):
            try:
                import machine
                self.ir_pin = machine.Pin(17)
            except (ImportError, OSError, ValueError, AttributeError):
                pass

    def read(self, method, *args):
        if not self.native:
            return None
        reader = getattr(self.badge, method, None)
        if reader is not None:
            try:
                return reader(*args)
            except (OSError, ValueError, TypeError, AttributeError, RuntimeError):
                pass
        return None

    @staticmethod
    def number(value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            # Avoid propagating non-finite device values into JSON/canvas.
            if value == value and -1e12 < value < 1e12:
                return value
        return None

    def poll(self, telemetry):
        rows = []

        def add(key, name, value=None, unit="", detail=""):
            rows.append({"id": key, "name": name, "value": value, "unit": unit,
                         "available": value is not None,
                         "detail": detail if self.native else "Requires a physical Universe 2026 badge."})

        imu = self.read("imu")
        for index, key in enumerate(("accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z")):
            value = self.number(imu[index]) if isinstance(imu, (tuple, list)) and len(imu) == 6 else None
            add(key, key.replace("_", " ").upper(), value, "RAW",
                "LSM6DS3TR-C relative readings. Firmware physical units are undocumented.")
        add("light", "AMBIENT LIGHT", self.number(self.read("light_level")), "ADC",
            "PT19 phototransistor. Raw 0-65535 reading; not calibrated lux.")
        for key, name, unit in (("battery", "BATTERY", "%"),
                                ("voltage", "BATTERY VOLTAGE", "V")):
            # ADC averaging was already done by the regular 10s power poll.
            value = telemetry.get(key) if self.native else None
            value = self.number(value)
            if value is not None and key == "voltage":
                value = round(value, 3)
            add(key, name, value, unit, "Firmware battery measurement. Percentage is a voltage-based estimate.")
        for key, name in (("usb", "USB POWER"), ("charging", "CHARGING")):
            value = telemetry.get(key) if self.native else None
            add(key, name, None if value is None else ("YES" if value else "NO"), "", "Firmware power status.")
        inverted = self.read("upside_down")
        add("orientation", "ORIENTATION", None if inverted is None else ("INVERTED" if inverted else "UPRIGHT"),
            "", "Orientation derived by firmware from the onboard motion sensor.")
        for action in self.ACTIONS:
            button = self.ns.get("BUTTON_" + action.upper())
            value = self.read("touched", button) if button is not None else None
            add("touch_" + action, "TOUCH " + action.upper(),
                None if value is None else ("ON" if value else "OFF"), "",
                "CAP1208 capacitive pad, mapped through orientation-aware logical controls.")
        direction = self.read("direction")
        try:
            value = "%.2f, %.2f" % (direction.x, direction.y) if direction is not None else None
        except (AttributeError, TypeError, ValueError):
            value = None
        add("direction", "TOUCH DIRECTION", value, "X,Y", "Processed touch direction vector; not compass heading.")
        value = None
        if self.ir_pin is not None:
            try:
                value = "HIGH" if self.ir_pin.value() else "LOW"
            except (OSError, ValueError, RuntimeError):
                pass
        add("ir", "IR RECEIVER", value, "LEVEL",
            "GPIO17 instant logic level. Brief IR pulses may be missed; no packet decoding or transmission.")
        add("imu_temp", "IMU TEMPERATURE", None, "C",
            "The LSM6DS3TR-C has a temperature channel; the published 2026 badge API does not expose it.")
        return rows




class BadgeApp:
    """Own a core instance and bounded flash writes outside /system."""

    def __init__(self, namespace, config=None):
        self.ns = namespace
        self.badge = namespace["badge"]
        self.state_api = namespace.get("State")
        state = {}
        if self.state_api:
            try:
                self.state_api.load("pipboy", state)
            except (OSError, ValueError) as error:
                print("Pip-Boy could not load saved state:", error)
        self.core = PipBoy(state=state, config=config or CONFIG, copy_config=False)
        self.lights = CaseLightDriver(self.badge)
        self.reminders = ReminderStore(self.core.effects, self.state_api)
        self.inputs = BadgeInputs(self.badge, namespace)
        self.renderer = BadgeRenderer(namespace["screen"], namespace["color"], namespace["vec2"], namespace["shape"])
        self.last_saved = self.core.serialize()
        self.dirty = False
        self.idle_since_change = 0.0
        self.save_elapsed = 0.0
        self.telemetry_elapsed = 30.0
        self.clock_elapsed = 1.0
        self.sensor_elapsed = 1.0
        self.sensors = BadgeSensors(self.badge, namespace)
        self.telemetry = {"simulated": sys.platform != "rp2", "time": "--:--", "time_label": "PT"}
        self.draw_elapsed = 1.0
        self.last_frame = None
        self._backlight_before_saver = None

    def read_clock(self):
        """Prefer NTP's UTC clock; fall back to a Pacific wall-time hardware RTC."""
        self.telemetry["date"] = ""
        self.telemetry["event_date"] = ""
        self.telemetry["event_time"] = ""
        try:
            if sys.platform == "rp2":
                utc = time.gmtime()
                if 2025 <= utc[0] <= 2100:
                    # Current System and Clock apps set the internal RTC to UTC.
                    # System also writes UTC to the external RTC, whereas the
                    # older Clock app writes local time there. Prefer UTC so
                    # either app works without modifying stock configuration.
                    fields = pacific_clock(utc)
                else:
                    rtc = self.ns.get("rtc")
                    if rtc is None:
                        return "--:--"
                    fields = rtc.datetime()
            else:
                fields = pacific_clock(time.gmtime())
            year, month, day, hour, minute, second = fields[:6]
            if (2025 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31
                    and 0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
                month_days = (31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                              31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
                if day > month_days[month - 1]:
                    return "--:--"
                date = "%04d-%02d-%02d" % (year, month, day)
                clock = "%02d:%02d" % (hour, minute)
                self.telemetry.update({"date": date, "event_date": date, "event_time": clock})
                return clock
        except (OSError, ValueError, TypeError, AttributeError, IndexError):
            pass
        return "--:--"

    def save(self):
        state = self.core.serialize()
        if self.state_api and state != self.last_saved:
            try:
                self.state_api.save("pipboy", state)
                self.last_saved = state
            except (OSError, ValueError) as error:
                print("Pip-Boy could not save state:", error)
                return
        self.dirty = False
        self.save_elapsed = 0.0

    def apply_battery_saver(self):
        display_api = self.ns.get("display")
        get_backlight = self.ns.get("get_backlight")
        if not display_api or not get_backlight:
            return
        if self.core.battery_saver and self._backlight_before_saver is None:
            try:
                original = get_backlight() / 100.0
                display_api.backlight(min(original, 0.20))
                self._backlight_before_saver = original
            except (OSError, ValueError, TypeError, AttributeError):
                pass
        elif not self.core.battery_saver:
            self.restore_backlight()

    def restore_backlight(self):
        if self._backlight_before_saver is not None:
            self.ns["display"].backlight(self._backlight_before_saver)
            self._backlight_before_saver = None

    def update(self):
        # Never use the animation frame number as elapsed time. The firmware
        # provides elapsed milliseconds, including slow rendering frames.
        dt = max(0.0, self.badge.ticks_delta / 1000.0)
        repeat_horizontal = (self.core.map_pan or self.core.map_cursor is not None
                             or self.core.search_editing or self.core.help_page is not None)
        actions = self.inputs.read(dt, repeat_horizontal)
        telemetry_update = {}
        self.clock_elapsed += dt
        if self.clock_elapsed >= 1.0:
            self.clock_elapsed = 0.0
            self.telemetry["time"] = self.read_clock()
            for key in ("time", "date", "event_date", "event_time", "time_label", "simulated"):
                if key in self.telemetry:
                    telemetry_update[key] = self.telemetry[key]
        self.telemetry_elapsed += dt
        if self.telemetry_elapsed >= 10.0:
            self.telemetry_elapsed = 0.0
            for key, method in (("battery", "battery_level"), ("voltage", "battery_voltage"),
                                ("usb", "usb_connected"), ("charging", "is_charging")):
                self.telemetry[key] = None
                reader = getattr(self.badge, method, None)
                if reader:
                    try:
                        self.telemetry[key] = reader()
                    except (OSError, ValueError, RuntimeError):
                        pass
                telemetry_update[key] = self.telemetry[key]
        self.sensor_elapsed += dt
        # Fast diagnostics while visible, modest background power use otherwise.
        sensor_interval = 0.2 if self.core.tab == "RADIO" and self.core.subtab == "SENSORS" else 1.0
        if self.core.battery_saver:
            sensor_interval = 5.0 if self.core.tab == "RADIO" and self.core.subtab == "SENSORS" else 30.0
        if self.sensor_elapsed >= sensor_interval:
            self.sensor_elapsed = 0.0
            telemetry_update["sensors"] = self.sensors.poll(self.telemetry)
        was_running = self.core.state["timer"]["running"]
        self.core.update(actions=actions, dt=dt, telemetry=telemetry_update, return_snapshot=False)
        self.apply_battery_saver()
        self.reminders.save()
        self.save_elapsed += dt
        self.idle_since_change += dt
        if actions:
            self.dirty = True
            self.idle_since_change = 0.0
        # Changes settle for one second; active timers checkpoint every 30s.
        # serialize() omits visual animation and telemetry, avoiding idle writes.
        if (self.dirty and self.idle_since_change >= 1.0) or self.save_elapsed >= 30.0:
            self.save()
        if "home" in actions or (was_running and not self.core.state["timer"]["running"]):
            self.save()
        # run() clears before every callback unless default_clear is None.
        # Keep the last framebuffer when there is no new 20Hz animation frame.
        # Static pages also keep their pixels between clock/content changes:
        # avoiding thousands of identical glyph calls leaves more time for
        # input polling, particularly in the slower WASM playground.
        self.draw_elapsed += dt
        if actions or self.draw_elapsed >= (0.5 if self.core.battery_saver else 0.05):
            self.draw_elapsed = 0.0
            display = self.core.state
            crt_enabled = display.get("crt_scanlines", True) and not self.core.battery_saver
            frame = (display.get("theme", "green"), display.get("font_mode", "pixel"),
                     self.core.render(), False, crt_enabled,
                     int(self.core.crt_elapsed * 96) / 96 if crt_enabled else 0)
            self.lights.write(self.core.effects.levels)
            if frame != self.last_frame:
                self.renderer.draw(frame[2], frame[0], frame[1], frame[3], frame[4], frame[5])
                self.last_frame = frame


def _configuration():
    config = dict(CONFIG)
    for path in ("config.json", "/system/apps/fallout/config.json", "/remote/apps/fallout/config.json", "/system/apps/pipboy/config.json", "/remote/apps/pipboy/config.json"):
        try:
            with open(path, "r") as handle:
                custom = json.load(handle)
            if isinstance(custom, dict):
                config.update(custom)
            break
        except (OSError, ValueError):
            pass
    return config


_app = None


def on_exit():
    """The badge launcher calls this before leaving for the system menu."""
    if _app:
        _app.restore_backlight()
        _app.lights.close()
        _app.reminders.save()
        _app.save()


def _start():
    global _app
    namespace = dict(globals())
    # Badgeware's MicroPython names can resolve normally while remaining absent
    # from both builtins.__dict__ and getattr(builtins, ...). Resolve only these
    # fixed API identifiers with Python name lookup, never user-provided text.
    for name in ("badge", "screen", "color", "vec2", "shape", "image", "run", "HIRES", "VSYNC", "State", "rtc",
                 "display", "BUTTON_UP", "BUTTON_DOWN", "BUTTON_LEFT", "BUTTON_RIGHT", "BUTTON_SELECT",
                 "BUTTON_BACK", "BUTTON_MENU", "BUTTON_HOME", "BUTTON_A", "BUTTON_B", "BUTTON_C"):
        try:
            namespace[name] = eval(name)
        except NameError:
            pass
    if not all(key in namespace for key in ("badge", "screen", "run")):
        return
    # The actual screen object is replaced when badge.mode changes resolution.
    namespace["badge"].mode(namespace["HIRES"] | namespace["VSYNC"])
    namespace["screen"] = eval("screen")
    image_api = namespace.get("image")
    if image_api is not None and hasattr(image_api, "OFF"):
        namespace["screen"].antialias = image_api.OFF
    namespace["badge"].default_clear = None
    try:
        from badgeware import State, get_backlight
        namespace["State"] = State
        namespace["get_backlight"] = get_backlight
    except ImportError:
        pass
    _app = BadgeApp(namespace, _configuration())
    namespace["run"](_app.update)


_start()
