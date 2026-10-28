import importlib.util, sys, types, unittest
from pathlib import Path
from unittest.mock import patch
APP=Path(__file__).resolve().parents[1]/'apps'/'fallout'
sys.path.insert(0,str(APP))
spec=importlib.util.spec_from_file_location('fallout_runtime',APP/'__init__.py')
runtime=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
class Screen:

    def __init__(self):
        self.calls = []

    def rectangle(self, x, y, w, h):
        self.calls.append(('rect', x, y, w, h))

    def line(self, x1, y1, x2, y2):
        self.calls.append(('line', x1, y1, x2, y2))

    def circle(self, vector, radius):
        self.calls.append(('circle', vector, radius))

    def shape(self, polygon):
        self.calls.append(('poly', polygon))

class PixelScreen(Screen):
    """A small RGB framebuffer for testing exact text pixels and contrast."""

    def __init__(self):
        super().__init__()
        self.pixels = {}

    def rectangle(self, x, y, w, h):
        super().rectangle(x, y, w, h)
        for row in range(max(0, y), min(240, y + h)):
            for col in range(max(0, x), min(320, x + w)):
                self.pixels[col, row] = self.pen

    def line(self, x1, y1, x2, y2):
        super().line(x1, y1, x2, y2)
        dx, dy = (abs(x2 - x1), -abs(y2 - y1))
        sx, sy = (1 if x1 < x2 else -1, 1 if y1 < y2 else -1)
        error = dx + dy
        while True:
            if 0 <= x1 < 320 and 0 <= y1 < 240:
                self.pixels[x1, y1] = self.pen
            if x1 == x2 and y1 == y2:
                break
            twice = 2 * error
            if twice >= dy:
                error += dy
                x1 += sx
            if twice <= dx:
                error += dx
                y1 += sy

class Color:
    rgb = staticmethod(lambda *rgb: rgb)

class Shape:
    custom = staticmethod(lambda points: points)

class Device:
    ticks_delta = 100

    def __init__(self):
        self.buttons = (set(), set(), set())

    def pressed(self, button):
        return button in self.buttons[0]

    def held(self, button):
        return button in self.buttons[1]

    def released(self, button):
        return button in self.buttons[2]

    def battery_level(self):
        return 73

class EffectsTests(unittest.TestCase):
    ns = vars(runtime)
    def test_removed_glow_cannot_be_reenabled_by_legacy_renderer_arguments(self):
        plain, legacy = (PixelScreen(), PixelScreen())
        commands = [['text', 'A.O', 10, 10, 2, 3]]
        self.ns['BadgeRenderer'](plain, Color, lambda *xy: xy, Shape).draw(commands, pixel_glow=False)
        self.ns['BadgeRenderer'](legacy, Color, lambda *xy: xy, Shape).draw(commands, pixel_glow=True)
        self.assertEqual(plain.pixels, legacy.pixels)
    def test_crt_overlay_is_last_and_covers_text_art_and_header(self):
        for phase, top in ((0.32, 18), (0.64, 49)):
            screen = PixelScreen()
            renderer = self.ns['BadgeRenderer'](screen, Color, lambda *xy: xy, Shape)
            commands = [['clear'], ['text', 'PROFILE', 20, top, 1, 3], ['rgbrect', 150, top, 20, 12, 100, 50, 20]]
            renderer.draw(commands, crt_scanlines=True, crt_phase=phase)
            self.assertEqual(screen.calls[-12:], [('rect', 0, top + i, 320, 1) for i in range(12)])
            self.assertEqual(screen.pixels[20, top], screen.pixels[150, top])
            self.assertEqual(len(screen.pixels[20, top]), 4)
            self.assertLess(screen.pixels[20, top][3], 128)
        paused = Screen()
        self.ns['BadgeRenderer'](paused, Color, lambda *xy: xy, Shape).draw([['clear']], crt_scanlines=True, crt_phase=2.75)
        self.assertEqual(paused.calls, [('rect', 0, 0, 320, 240)])
    def test_battery_saver_thresholds_timer_buttons_and_temporary_brightness(self):
        brightness = []
        device = Device()
        device.battery_level = lambda: 9
        app = self.ns['BadgeApp']({'badge': device, 'screen': Screen(), 'color': Color, 'vec2': lambda *xy: xy, 'shape': Shape, 'display': types.SimpleNamespace(backlight=brightness.append), 'get_backlight': lambda: 80})
        app.core.state['timer'].update(running=True, remaining=100)
        app.core.effects.state['ambience'] = True
        before = app.core.phase
        app.update()
        self.assertTrue(app.core.battery_saver)
        self.assertEqual(brightness, [0.2])
        self.assertEqual(app.core.phase, before)
        self.assertLess(app.core.state['timer']['remaining'], 100)
        self.assertFalse(app.last_frame[4])
        self.assertTrue(app.core.state['crt_scanlines'])
        with patch.object(app.inputs, 'read', return_value=['tab:INV']), patch.object(app.lights, 'write') as lights:
            app.update()
            self.assertEqual(app.core.tab, 'INV')
            lights.assert_called_with((0, 0, 0, 0))
        for battery in (None, 10, 11):
            app.core.update(dt=0, telemetry={'battery': battery})
            self.assertTrue(app.core.battery_saver)
        app.core.update(dt=0, telemetry={'battery': 12})
        app.apply_battery_saver()
        self.assertFalse(app.core.battery_saver)
        self.assertEqual(brightness, [0.2, 0.8])
        self.assertGreaterEqual(app.core.crt_wait, 20)
        app.core.update(dt=0, telemetry={'battery': 10})
        self.assertFalse(app.core.battery_saver)
        app.core.update(dt=0, telemetry={'battery': 0})
        app.apply_battery_saver()
        app.restore_backlight()
        self.assertEqual(brightness, [0.2, 0.8, 0.2, 0.8])
        self.assertNotIn('battery_saver', app.core.serialize())

    def test_battery_recovery_starts_full_crt_pause_after_elapsed_eco_interval(self):
        for random_value, wait in ((0, 20), (25, 45)):
            with self.subTest(wait=wait):
                app = self.ns['PipBoy'](config={})
                app.update(dt=0, telemetry={'battery': 50})
                app.update(dt=0, telemetry={'battery': 9})
                app.state['timer'].update(running=True, remaining=100)
                with patch('core.random.getrandbits', return_value=random_value):
                    app.update(dt=30, telemetry={'battery': 12})
                self.assertFalse(app.battery_saver)
                self.assertEqual(app.crt_wait, wait)
                self.assertEqual(app.crt_elapsed, 2.75)
                self.assertEqual(app.state['timer']['remaining'], 70)
                app.update(dt=wait - 0.01)
                self.assertEqual(app.crt_elapsed, 2.75)
                app.update(dt=0.02)
                self.assertEqual(app.crt_elapsed, 0)

    def test_eco_snapshots_and_render_suppress_ambient_and_reminder_lights(self):
        for reminder in (False, True):
            with self.subTest(reminder=reminder):
                app = self.ns['PipBoy'](config={})
                app.effects.state.update(ambience=True, level=2)
                if reminder:
                    app.update(['effects:open', 'choice:3'], dt=0)
                app.update(dt=1.5, telemetry={'battery': 50})
                app.render()
                self.assertTrue(any(app.snapshot()['case_lights']))
                app.update(dt=0, telemetry={'battery': 9})
                self.assertEqual(app.snapshot()['case_lights'], [0, 0, 0, 0])
                app.render()
                self.assertEqual(app.effects.levels, (0, 0, 0, 0))
                self.assertEqual(app.snapshot()['case_lights'], [0, 0, 0, 0])
                self.assertTrue(app.state['crt_scanlines'])
                self.assertTrue(app.effects.state['ambience'])
                self.assertEqual(app.effects.state['level'], 2)
                self.assertEqual(bool(app.effects.active), reminder)
                app.update(dt=0, telemetry={'battery': 12})
                app.render()
                self.assertTrue(any(app.snapshot()['case_lights']))

    def test_directional_hold_does_not_replay_repeat_backlog_after_slow_frame(self):
        for action, pan in (('up', False), ('down', False), ('left', True), ('right', True)):
            with self.subTest(action=action):
                device = Device()
                inputs = self.ns['BadgeInputs'](device, {'BUTTON_' + action.upper(): action})
                device.buttons = ({action}, {action}, set())
                self.assertEqual(inputs.read(0.016, pan), [action])
                device.buttons = (set(), {action}, set())
                self.assertEqual(inputs.read(0.39, pan), [])
                self.assertEqual(inputs.read(0.02, pan), [action])
                self.assertEqual(inputs.read(3, pan), [action])
                # The next repeat still waits a full interval, even though the
                # preceding frame missed many repeats while the button was held.
                for _ in range(8):
                    self.assertEqual(inputs.read(0.016, pan), [])
                self.assertEqual(inputs.read(0.016, pan), [action])
                device.buttons = (set(), set(), {action})
                self.assertEqual(inputs.read(0.016, pan), [])
                device.buttons = ({action}, {action}, set())
                self.assertEqual(inputs.read(0.016, pan), [action])
                device.buttons = (set(), {action}, set())
                self.assertEqual(inputs.read(0.39, pan), [])
