"""Behavior tests for the shared simulator / MicroPython application core."""

import json
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

# The physical badge imports its entrypoint as apps.pipboy. Loading the portable
# module directly keeps host tests independent of the firmware-only package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "fallout"))
from core import PipBoy, SUBTABS, TABS


FIXTURE = {
    "profile": {"name": "TEST WANDERER", "handle": "test", "role": "BUILDER", "level": 1},
    "inventory": [
        {"id": "badge", "name": "BADGE", "packed": True},
        {"id": "cable", "name": "CABLE", "packed": False},
    ],
    "quests": [
        {"id": "arrive", "title": "ARRIVE", "xp": 75},
        {"id": "build", "title": "BUILD", "xp": 50},
    ],
    "schedule": [
        {"id": "keynote", "title": "KEYNOTE", "day": "OCT 28", "time": "09:00", "location": "FORT MASON"},
        {"id": "closing", "title": "CLOSING", "day": "OCT 29", "time": "16:00", "location": "FORT MASON"},
    ],
    "world": {"title": "WORLD", "pois": [{"id": "gateway", "name": "GATEWAY", "x": 20, "y": 30}], "paths": []},
    "local": {"title": "LOCAL", "pois": [{"id": "entry", "name": "ENTRY", "x": 45, "y": 80}], "paths": []},
}


class PipBoyCoreTests(unittest.TestCase):
    def app(self, state=None):
        return PipBoy(state=state, config=FIXTURE)

    def test_owned_configuration_keeps_one_record_copy_without_mutating_inputs(self):
        config = json.loads(json.dumps(FIXTURE))
        original = json.loads(json.dumps(config))
        app = PipBoy(config=config)
        self.assertIs(app.config["schedule"], app.schedule)
        self.assertIs(app.config["inventory"], app.inventory)
        self.assertIs(app.config["world"], app.maps["WORLD"])
        app.schedule[0]["title"] = "LOCAL EDIT"
        app.maps["WORLD"]["pois"][0]["name"] = "LOCAL LANDMARK"
        self.assertEqual(config, original)

    def test_native_owned_config_does_not_duplicate_map_geometry(self):
        config = json.loads(json.dumps(FIXTURE))
        config['world']['paths'] = [[[0, 0], [1, 1]]]
        app = PipBoy(config=config, copy_config=False)
        self.assertIs(app.maps['WORLD']['paths'], config['world']['paths'])
        app.update(['tab:MAP'], return_snapshot=False)
        self.assertTrue(app.render())

    def test_native_update_and_render_skip_browser_metadata_copies(self):
        app = self.app()
        app.update(["tab:INV"], dt=0)
        with patch("core._clone", side_effect=AssertionError("native loop cloned metadata")):
            self.assertIsNone(app.update(["select"], dt=0, return_snapshot=False))
            self.assertFalse(app.state["packed"]["badge"])
            self.assertTrue(app.render())
        self.assertIn("items", app.snapshot())

    def test_schedule_formats_only_the_five_visible_rows(self):
        config = dict(FIXTURE, schedule=[{"id": str(index), "title": "SESSION " + str(index), "time": "09:00"} for index in range(1000)])
        app = PipBoy(config=config)
        app.update(["tab:DATA", "sub:SCHEDULE", "item:500"], dt=0)
        with patch.object(app, "_schedule_label", wraps=app._schedule_label) as label:
            app.render()
            self.assertEqual(label.call_count, 5)

    def test_packed_mascot_preserves_every_pixel_of_all_twenty_four_source_frames(self):
        expected = json.loads((Path(__file__).parent / "fixtures" / "mascot-pixels.json").read_text())
        app = self.app()
        for style, hashes in expected.items():
            app.state["mascot"] = style
            for index, digest in enumerate(hashes):
                with self.subTest(style=style, frame=index):
                    app.phase = index * 0.15 + 0.01
                    app.commands = []
                    app._mascot(40, 0)
                    pixels = bytearray(80 * 149 * 4)
                    for command in app.commands:
                        x, y, width, height = command[1:5]
                        self.assertTrue(0 <= x < x + width <= 80 and 0 <= y < y + height <= 149)
                        ink = tuple(command[5:]) if command[0] == "rgbrect" else (156, 255, 171)
                        for row in range(y, y + height):
                            pixels[(row * 80 + x) * 4:(row * 80 + x + width) * 4] = bytes((*ink, 255)) * width
                    self.assertEqual(hashlib.sha256(pixels).hexdigest(), digest)
                    decoded = app._mascot_commands
                    app.commands = []
                    app._mascot(40, 0)
                    self.assertIs(app._mascot_commands, decoded)

    def test_navigation_wraps_and_retains_subpages(self):
        app = self.app()
        app.update(["left"], dt=0)
        self.assertEqual(app.tab, "RADIO")
        app.update(["right", "right", "menu"], dt=0)
        self.assertEqual((app.tab, app.subtab), ("INV", "PACKED"))
        app.update(["right", "left"], dt=0)
        self.assertEqual(app.subtab, "PACKED")
        app.update(["home"], dt=0)
        self.assertEqual((app.tab, app.subtab), ("STAT", "STATUS"))

    def test_map_geometry_cache_preserves_output_and_rebuilds_on_zoom(self):
        app = self.app()
        app.update(['tab:MAP'], dt=0)
        first = app.render()
        with patch.object(app, '_render_map_geometry', side_effect=AssertionError('Unchanged map rebuilt')):
            self.assertEqual(app.render(), first)
        with patch.object(app, '_render_map_geometry', wraps=app._render_map_geometry) as draw:
            app.update(['map:zoom_in'], dt=0)
            app.render()
            draw.assert_called_once()

    def test_personal_reminder_is_in_my_schedule_without_claiming_booking(self):
        config = dict(FIXTURE, schedule=[dict(FIXTURE['schedule'][0], personal_reminder=True)], personal_schedule=['keynote'])
        app = PipBoy(config=config)
        self.assertEqual(app._schedule_mark(app.schedule[0]), 'R')
        self.assertIn('keynote', app.personal_schedule)

    def test_city_side_streets_appear_when_zoomed_without_losing_vectors(self):
        config = dict(FIXTURE, world={'coords': 'normalized', 'pois': [], 'paths': [
            {'points': [[45, 45], [55, 55]], 'bbox': [45, 45, 55, 55], 'min_zoom': 2}]})
        app = PipBoy(config=config)
        app.update(['tab:MAP'], dt=0)
        app.commands = []
        app._render_map_geometry(app.maps['WORLD'])
        self.assertFalse(any(c[0] == 'line' and c[-1] == 2 for c in app.commands))
        app.update(['map:zoom_in', 'map:zoom_in'], dt=0)
        app.commands = []
        app._render_map_geometry(app.maps['WORLD'])
        self.assertTrue(any(c[0] == 'line' and c[-1] == 2 for c in app.commands))
        self.assertEqual(len(app.maps['WORLD']['paths']), 1)

    def test_inventory_remains_valid_when_removing_filtered_item(self):
        app = self.app()
        app.update(["tab:INV", "down", "select", "sub:PACKED", "down", "select"], dt=0)
        self.assertEqual(app.snapshot()["packed"], 1)
        self.assertEqual(app.snapshot()["selected_index"], 0)
        self.assertEqual(app.selected_item()["id"], "badge")
        app.update(["select"], dt=0)
        self.assertEqual(app.snapshot()["packed"], 0)
        self.assertIsNone(app.selected_item())
        app.render()

    def test_quest_reopening_does_not_duplicate_experience(self):
        app = self.app()
        app.update(["tab:DATA", "select", "down", "select"], dt=0)
        self.assertEqual(app.snapshot()["xp"], 125)
        self.assertEqual(app.snapshot()["level"], 2)
        app.update(["select", "select", "select"], dt=0)
        self.assertEqual(app.snapshot()["xp"], 75)
        self.assertEqual(app.snapshot()["completed"], 1)

    def test_schedule_favorite_and_map_pin_persist_independently(self):
        app = self.app()
        app.update(["tab:DATA", "sub:SCHEDULE", "down", "select", "tab:MAP", "select", "sub:LOCAL", "waypoint:24,60", "theme:amber"], dt=0)
        saved = json.loads(json.dumps(app.serialize()))
        restored = self.app(saved)
        self.assertEqual(restored.snapshot()["favorites"], ["closing"])
        self.assertEqual(restored.state["waypoints"]["WORLD"]["id"], "gateway")
        self.assertEqual(restored.state["waypoints"]["LOCAL"]["x"], 24)
        self.assertEqual(restored.snapshot()["theme"], "amber")
        restored.update(["waypoint:nan,45"], dt=0)
        self.assertEqual(restored.state["waypoints"]["LOCAL"]["x"], 24)
        restored.update(["select"], dt=0)
        self.assertEqual(restored.snapshot()["waypoint"]["id"], "entry")
        restored.update(["select"], dt=0)
        self.assertIsNone(restored.snapshot()["waypoint"])

    def test_focus_timer_pause_resume_completion_and_reset(self):
        app = self.app()
        app.update(["tab:RADIO", "select"], dt=0)
        app.update(dt=40)
        self.assertEqual(app.snapshot()["timer"]["remaining"], 1460)
        app.update(["select"], dt=0)
        app.update(dt=50)
        self.assertEqual(app.snapshot()["timer"]["remaining"], 1460)
        restored = self.app(json.loads(json.dumps(app.serialize())))
        restored.update(["focus:start"], dt=0)
        restored.update(dt=1500)
        timer = restored.snapshot()["timer"]
        self.assertEqual((timer["remaining"], timer["sessions"], timer["running"]), (0, 1, False))
        self.assertEqual(restored.snapshot()["xp"], 10)
        restored.update(dt=500)
        self.assertEqual(restored.snapshot()["timer"]["sessions"], 1)
        restored.update(["reset_timer"], dt=0)
        self.assertEqual(restored.snapshot()["timer"]["remaining"], 1500)
        self.assertFalse(restored.snapshot()["timer"]["running"])

    def test_running_timer_restores_and_duration_change_is_idle_only(self):
        app = self.app()
        app.update(["tab:RADIO", "down", "select", "select", "select", "up", "select"], dt=0)
        app.update(["down", "select"], dt=30)
        self.assertEqual(app.snapshot()["timer"]["duration"], 900)
        restored = self.app(app.serialize())
        restored.update(dt=20)
        self.assertEqual(restored.snapshot()["timer"]["remaining"], 850)
        restored.update(["up", "select", "down", "select"], dt=0)
        self.assertEqual(restored.snapshot()["timer"]["remaining"], 1500)

    def test_five_buttons_control_profile_fonts_help_and_focus_reset(self):
        app = self.app()
        app.update(["menu", "down", "select"], dt=0)
        self.assertEqual(app.snapshot()["font_mode"], "vector")
        restored = self.app(json.loads(json.dumps(app.serialize())))
        self.assertEqual(restored.snapshot()["font_mode"], "vector")
        restored.update(["select"], dt=0)
        self.assertEqual(restored.snapshot()["font_mode"], "pixel")
        restored.update(["down", "select", "down"], dt=0)
        self.assertEqual(restored.snapshot()["help_page"], 1)
        restored.update(["menu", "left", "select"], dt=0)
        self.assertIsNone(restored.snapshot()["help_page"])
        self.assertTrue(restored.snapshot()["timer"]["running"])
        restored.update(dt=50)
        restored.update(["up", "select"], dt=0)
        self.assertEqual(restored.snapshot()["timer"]["remaining"], 1500)
        self.assertFalse(restored.snapshot()["timer"]["running"])

    def test_font_default_saved_preference_and_invalid_modes(self):
        self.assertEqual(self.app().state["font_mode"], "pixel")
        app = PipBoy(config={"font_mode": "vector"})
        self.assertEqual(app.state["font_mode"], "vector")
        app.update(["font:pixel", "font:unknown"], dt=0)
        self.assertEqual(PipBoy(state=app.serialize(), config={"font_mode": "vector"}).state["font_mode"], "pixel")
        self.assertEqual(PipBoy(state={"font_mode": None}, config={"font_mode": "vector"}).state["font_mode"], "vector")
        self.assertEqual(PipBoy(config={"font_mode": {}}).state["font_mode"], "pixel")

    def test_legacy_glow_is_removed_and_crt_preference_persists(self):
        app = PipBoy(state={'pixel_glow': True}, config={'pixel_glow': True})
        self.assertFalse(app.state['pixel_glow'])
        app.update(['glow:on'], dt=0)
        self.assertFalse(app.state['pixel_glow'])
        self.assertTrue(app.state['crt_scanlines'])
        app.update(['crt:off'], dt=0)
        self.assertFalse(PipBoy(state=app.serialize()).state['crt_scanlines'])
        app.update(['tab:STAT', 'sub:PROFILE'], dt=0)
        self.assertFalse(any(item['id']=='profile:glow' for item in app._items()))

    def test_crt_random_gaps_never_repeat_before_twenty_seconds(self):
        app = self.app()
        app.update(dt=0)
        with patch('core.random.getrandbits', side_effect=[0, 25, 8]):
            app.update(dt=2.75)
            self.assertEqual(app.crt_wait, 20)
            phase = app.snapshot()['crt_phase']
            app.update(dt=19.9)
            self.assertEqual(app.snapshot()['crt_phase'], phase)
            app.update(dt=.2)
            self.assertEqual(app.crt_elapsed, 0)
            app.update(dt=2.75)
            self.assertEqual(app.crt_wait, 45)
        self.assertFalse(app.effects.state['ambience'])

    def test_battery_recovery_starts_full_crt_pause_after_elapsed_eco_interval(self):
        for random_value, wait in ((0, 20), (25, 45)):
            with self.subTest(wait=wait):
                app = self.app()
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
                app = self.app()
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

    def test_profile_credit_is_last_and_select_does_not_change_appearance(self):
        app = self.app()
        app.update(['sub:PROFILE'], dt=0)
        app.state['selected']['STAT:PROFILE'] = len(app._items()) - 1
        self.assertEqual(app.selected_item()['name'], 'Created with AI by DChevrier1')
        before = (app.state['theme'], app.state['mascot'])
        app.update(['select'], dt=0)
        self.assertEqual((app.state['theme'], app.state['mascot']), before)
        self.assertTrue(any('DCHEVRIER1' in str(c).upper() for c in app.render()))

    def test_five_buttons_place_clear_and_cancel_manual_map_pins(self):
        app = self.app()
        app.update(["left", "left", "up", "up", "select", "right", "up", "select"], dt=0)
        self.assertEqual((app.tab, app.subtab), ("MAP", "WORLD"))
        self.assertEqual(app.snapshot()["waypoint"], {"id": "manual", "name": "MANUAL PIN", "x": 51, "y": 49})
        restored = self.app(json.loads(json.dumps(app.serialize())))
        self.assertEqual(restored.snapshot()["waypoint"], app.snapshot()["waypoint"])
        restored.update(["select", "down", "menu"], dt=0)
        self.assertIsNone(restored.snapshot()["map_cursor"])
        self.assertEqual(restored.subtab, "WORLD", "Hold cancels placement without changing the map")
        self.assertEqual(restored.snapshot()["waypoint"]["y"], 49)
        restored.update(["down", "select"], dt=0)
        self.assertIsNone(restored.snapshot()["waypoint"])

    def test_five_buttons_search_type_filter_save_and_view_full_details(self):
        config = dict(FIXTURE)
        config["schedule"] = [{"id": "ai", "title": "AI", "day": "OCT 28", "date": "2026-10-28", "location": "HALL", "speakers": ["ADA"], "detail": "LONG " * 250 + "FINAL SENTENCE"}, {"id": "web", "title": "WEB", "date": "2026-10-29"}]
        app = PipBoy(config=config)
        app.update(["right", "right", "menu", "menu", "menu", "select"], dt=0)
        self.assertTrue(app.search_editing)
        self.assertEqual(app.search_query, "A")
        app.update(["down", "right", "select", "menu"], dt=0)
        self.assertEqual(app.search_query, "AI")
        self.assertFalse(app.search_editing)
        self.assertEqual([item["id"] for item in app.snapshot()["items"]], ["ai", "search:edit"])
        app.update(["select", "menu"], dt=0)
        self.assertEqual(app.subtab, "DETAILS")
        self.assertIn("ai", app.state["favorites"])
        self.assertGreater(app.snapshot()["detail_pages"], 1)
        pages = []
        for _ in range(app.snapshot()["detail_pages"]):
            pages.extend(command[1] for command in app.render() if command[0] == "text")
            app.update(["down"], dt=0)
        for value in ("SPEAKERS: ADA", "HALL", "FINAL SENTENCE"):
            self.assertIn(value, " ".join(pages))
        app.update(["select", "up", "select"], dt=0)
        self.assertTrue(app.search_editing)
        # Start at I (row 1, column 1); wrap Up twice to row 5,
        # then Right three times to DATE (row 5, column 4).
        app.update(["up", "up", "right", "right", "right", "select"], dt=0)
        self.assertEqual(app.search_date, "2026-10-28")
        app.update(["right", "select", "right", "select"], dt=0)
        self.assertTrue(app.search_saved)
        self.assertFalse(app.search_editing)
        self.assertEqual(app.selected_item()["id"], "ai")

    def test_full_details_retain_browsed_gear_across_intermediate_subpages(self):
        app = self.app()
        app.update(["right", "down", "menu", "menu"], dt=0)
        self.assertEqual(app.subtab, "DETAILS")
        self.assertEqual(app.selected_item()["id"], "cable")
        app.update(["select"], dt=0)
        self.assertEqual(app.subtab, "GEAR")
        self.assertEqual(app.selected_item()["id"], "cable")

    def test_five_buttons_read_quests_world_landmarks_and_sensors_in_full(self):
        app = self.app()
        app.update(["right", "right", "down", "menu", "menu", "menu", "menu", "menu"], dt=0)
        self.assertEqual((app.subtab, app.selected_item()["id"]), ("DETAILS", "build"))
        app.update(["right", "select", "menu", "menu"], dt=0)
        self.assertEqual((app.subtab, app.selected_item()["id"]), ("DETAILS", "gateway"))
        app.update(["right", "menu", "menu", "down", "menu"], dt=0, telemetry={"sensors": [{"id": "light", "name": "LIGHT", "detail": "Sensor detail."}]})
        self.assertEqual((app.subtab, app.selected_item()["id"]), ("DETAILS", "light"))

    def test_search_and_details_cache_repeated_frames_and_refresh_after_favorite_change(self):
        app = self.app()
        first = app._search_results()
        self.assertIs(app._search_results(), first)
        app.search_saved = True
        self.assertEqual(app._search_results(), [])
        app.update(["tab:DATA", "sub:SCHEDULE", "select"], dt=0)
        saved = app._search_results()
        self.assertEqual([item["id"] for item in saved], ["keynote"])
        self.assertIs(app._search_results(), saved)
        app.update(["sub:DETAILS"], dt=0)
        first_details = app._detail_lines()
        self.assertIs(app._detail_lines(), first_details)
        app.update(["select", "down", "sub:DETAILS"], dt=0)
        self.assertIsNot(app._detail_lines(), first_details)

    def test_every_active_subtab_has_a_visible_nonoverlapping_hit_region(self):
        app = self.app()
        for tab in TABS:
            for subtab in SUBTABS[tab]:
                app.update(["tab:" + tab, "sub:" + subtab], dt=0, telemetry={"time": "12:59", "time_label": "LOCAL"})
                regions = app.snapshot()["subtab_regions"]
                self.assertIn(subtab, [region["name"] for region in regions])
                self.assertTrue(all(0 <= region["x"] < region["x"] + region["width"] <= 320 for region in regions))
                self.assertTrue(all(left["x"] + left["width"] < right["x"] for left, right in zip(regions, regions[1:])))

    def test_save_is_independent_and_contains_no_volatile_animation(self):
        app = self.app()
        first = app.serialize()
        app.update(dt=5, telemetry={"battery": 42, "time": "12:34", "simulated": False})
        self.assertEqual(first, app.serialize())
        first["packed"]["badge"] = False
        self.assertTrue(app.state["packed"]["badge"])
        self.assertEqual(app.snapshot()["telemetry"]["battery"], 42)
        self.assertNotIn("telemetry", app.serialize())

    def test_exported_theme_is_default_and_saved_preference_wins(self):
        app = PipBoy(config={"theme": "amber"})
        self.assertEqual(app.snapshot()["theme"], "amber")
        app.update(["theme:ice"], dt=0)
        restored = PipBoy(state=app.serialize(), config={"theme": "amber"})
        self.assertEqual(restored.snapshot()["theme"], "ice")
        invalid_save = PipBoy(state={"theme": "invalid"}, config={"theme": "amber"})
        self.assertEqual(invalid_save.snapshot()["theme"], "amber")
        invalid_config = PipBoy(config={"theme": "invalid"})
        self.assertEqual(invalid_config.snapshot()["theme"], "green")

    def test_personal_badge_landing_shows_identity_and_live_telemetry(self):
        app = PipBoy(config={"profile": {
            "name": "Alex Example", "organization": "EXAMPLE TEAM",
            "position": "CONFERENCE EXPLORER", "handle": "example-user",
        }})
        app.update(dt=0, telemetry={"battery": 87, "time": "14:32", "time_label": "LOCAL", "simulated": False})
        texts = [command[1] for command in app.render() if command[0] == "text"]
        for required in ("ALEX EXAMPLE", "EXAMPLE TEAM", "CONFERENCE EXPL..", "87%", "2:32 PM LOCAL"):
            self.assertIn(required, texts)
        commands = app.render()
        for identity in ("ALEX EXAMPLE", "EXAMPLE TEAM", "CONFERENCE EXPL.."):
            self.assertTrue(any(command[0] == "text" and command[1] == identity and command[4] == 2 for command in commands))
        first = app.render()
        app.update(dt=0.2)
        self.assertNotEqual(first, app.render(), "Vault Boy must animate between source frames")

    def test_personal_schedule_unions_bookings_and_favorites(self):
        config = dict(FIXTURE)
        config["personal_schedule"] = ["keynote"]
        app = PipBoy(config=config)
        app.update(["tab:DATA", "sub:SCHEDULE", "down", "select", "sub:MY SCHEDULE"], dt=0)
        self.assertEqual([item["id"] for item in app.snapshot()["items"]], ["keynote", "closing"])
        attendance = {item["id"]: item for item in app.quests if item["id"].startswith("attend:")}
        self.assertTrue(attendance["attend:keynote"]["booked"])
        self.assertFalse(attendance["attend:closing"]["booked"])
        self.assertIn("not a booking", attendance["attend:closing"]["detail"])
        app.update(["down", "select"], dt=0)
        self.assertEqual([item["id"] for item in app.snapshot()["items"]], ["keynote"])
        self.assertEqual(app.snapshot()["selected_index"], 0)
        self.assertEqual(app.snapshot()["personal_schedule"], ["keynote"])

    def test_attendance_completion_survives_remove_and_readd(self):
        app = self.app()
        app.update(["tab:DATA", "sub:SCHEDULE", "select", "sub:QUESTS", "item:2", "select"], dt=0)
        self.assertEqual(app.snapshot()["completed"], 1)
        self.assertEqual(app.snapshot()["xp"], 25)
        app.update(["sub:SCHEDULE", "select"], dt=0)
        self.assertEqual(app.snapshot()["completed"], 0)
        self.assertEqual(app.snapshot()["xp"], 0)
        restored = self.app(app.serialize())
        restored.update(["select", "sub:QUESTS", "item:2"], dt=0)
        self.assertEqual(restored.selected_item()["id"], "attend:keynote")
        self.assertEqual(restored.snapshot()["completed"], 1)
        self.assertEqual(restored.snapshot()["xp"], 25)

    def test_catalog_supports_1000_rows_and_missing_time_is_tbd(self):
        schedule = [{"id": "s" + str(index), "title": "SESSION " + str(index), "time": ""} for index in range(1005)]
        app = PipBoy(config={"schedule": schedule})
        self.assertEqual(len(app.schedule), 1000)
        app.update(["tab:DATA", "sub:SCHEDULE", "item:999", "select", "sub:MY SCHEDULE"], dt=0)
        self.assertEqual(app.selected_item()["id"], "s999")
        texts = [command[1] for command in app.render() if command[0] == "text"]
        self.assertTrue(any("TBD SESSION 999" in text for text in texts))
        restored = PipBoy(state=app.serialize(), config={"schedule": schedule})
        self.assertEqual(restored.selected_item()["id"], "s999")

    def test_malformed_save_is_sanitized_before_first_render(self):
        app = self.app({
            "tab": "UNKNOWN", "subtabs": "bad", "selected": {"STAT:STATUS": -100},
            "packed": None, "quests": ["arrive"], "favorites": "closing", "theme": "ultraviolet",
            "timer": {"duration": "bad", "remaining": float("nan"), "running": "true", "sessions": -1},
            "waypoints": {"LOCAL": {"x": "bad", "y": 500}},
        })
        self.assertEqual(app.tab, "STAT")
        self.assertEqual(app.snapshot()["theme"], "green")
        self.assertEqual(app.snapshot()["timer"], {"duration": 1500, "remaining": 1500, "running": False, "sessions": 0})
        self.assertEqual(app.state["waypoints"]["LOCAL"]["x"], 50)
        app.update([None, {}, "tab:NO", "sub:NO", "theme:NO"], dt=float("inf"), telemetry={"battery": -5})
        self.assertIsNone(app.snapshot()["telemetry"]["battery"])
        app.render()
        json.dumps(app.serialize(), allow_nan=False)

    def test_every_view_renders_on_real_default_content(self):
        app = PipBoy()
        counts = {}
        for tab in TABS:
            for sub in SUBTABS[tab]:
                app.update(["tab:" + tab, "sub:" + sub], dt=0.2)
                frame = app.render()
                self.assertEqual(frame[0], ["clear"])
                self.assertGreater(len(frame), 20)
                self.assertTrue(all(command[0] in ("clear", "rect", "rgbrect", "line", "text", "poly", "circle") for command in frame))
                self.assertTrue(all(command[4] == int(command[4]) for command in frame if command[0] == "text"))
                json.dumps(frame, allow_nan=False)
                counts[tab + ":" + sub] = len(frame)
        self.assertGreater(counts["MAP:WORLD"], counts["STAT:PROFILE"])

    def test_all_empty_lists_are_usable(self):
        app = PipBoy(config={"inventory": [], "quests": [], "schedule": [], "world": {}, "local": {}})
        for tab in TABS:
            for sub in SUBTABS[tab]:
                app.update(["tab:" + tab, "sub:" + sub, "up", "down", "select"], dt=0)
                app.render()
        self.assertEqual(app.snapshot()["inventory_total"], 0)

    def test_schedule_is_chronological_and_reanchors_only_when_opened(self):
        events = [
            {"id": "tomorrow", "date": "2026-10-29", "time": "08:00", "end": "09:00"},
            {"id": "afternoon", "date": "2026-10-28", "time": "13:00", "end": "14:00"},
            {"id": "morning", "date": "2026-10-28", "time": "09:00", "end": "10:00"},
            {"id": "unknown", "title": "TIME TBD"},
        ]
        app = PipBoy(config={"schedule": events, "personal_schedule": ["tomorrow", "afternoon", "morning"]})
        self.assertEqual([event["id"] for event in app.schedule], ["morning", "afternoon", "tomorrow", "unknown"])
        app.update(["tab:DATA", "sub:SCHEDULE"], dt=0, telemetry={"event_date": "2026-10-28", "event_time": "13:20", "date": "2026-10-29", "time": "01:20"})
        self.assertEqual(app.selected_item()["id"], "afternoon", "Use conference clock for the selected session")
        app.update(["up"], dt=0)
        self.assertEqual(app.selected_item()["id"], "morning")
        app.update(dt=60, telemetry={"event_time": "13:21"})
        self.assertEqual(app.selected_item()["id"], "morning", "Live frames must not override deliberate browsing")
        app.update(["sub:MY SCHEDULE"], dt=0)
        self.assertEqual(app.selected_item()["id"], "afternoon")
        app.update(["tab:MAP", "tab:DATA"], dt=0, telemetry={"event_time": "14:00"})
        self.assertEqual(app.selected_item()["id"], "tomorrow", "End time is exclusive; choose next upcoming event")
        app.update(["sub:QUESTS", "sub:SCHEDULE"], dt=0, telemetry={"event_date": "2026-10-30"})
        self.assertEqual(app.selected_item()["id"], "tomorrow", "After all sessions, retain the last dated event")
        app.update(["session:morning"], dt=0)
        self.assertEqual(app.selected_item()["id"], "morning")

    def test_restored_schedule_waits_for_a_valid_clock_then_selects_next(self):
        app = PipBoy(config=FIXTURE, state={"tab": "DATA", "subtabs": {"DATA": "SCHEDULE"}})
        app.update(dt=0, telemetry={"time": "--:--"})
        self.assertEqual(app.selected_item()["id"], "keynote")
        app.update(dt=0, telemetry={"date": "2026-10-28", "time": "14:00"})
        self.assertEqual(app.selected_item()["id"], "closing")
        app.update(["up"], dt=0)
        app.update(dt=0)
        self.assertEqual(app.selected_item()["id"], "keynote")

    def test_clock_and_imported_event_details_use_am_pm(self):
        app = PipBoy(config={"schedule": [{"id": "noon", "date": "2026-10-28", "day": "OCT 28", "time": "12:00", "end": "13:00", "title": "LUNCH", "detail": "12:00-13:00 San Francisco time."}], "personal_schedule": ["noon"]})
        for clock, label in (("00:05", "12:05 AM"), ("12:00", "12:00 PM"), ("23:59", "11:59 PM")):
            app.update(dt=0, telemetry={"time": clock, "time_label": "LOCAL"})
            texts = [command[1] for command in app.render() if command[0] == "text"]
            self.assertIn(label + " LOCAL", texts)
        app.update(["tab:DATA", "sub:SCHEDULE"], dt=0)
        self.assertIn("12:00 PM-1:00 PM", app.snapshot()["detail"])
        self.assertTrue(any("12:00 PM" in command[1] for command in app.render() if command[0] == "text"))
        self.assertIn("12:00 PM", app.quests[-1]["detail"])

    def test_profile_cycles_four_appearances_and_migrates_outline_saves(self):
        app = self.app()
        self.assertEqual(app.snapshot()["mascot"], "color")
        self.assertTrue(any(command[0] == "rgbrect" for command in app.render()))
        app.update(["appearance:green:color", "sub:PROFILE"], dt=0)
        for theme, mascot in (("green", "shaded"), ("amber", "color"),
                              ("amber", "shaded"), ("green", "color")):
            app.update(["select"], dt=0)
            restored = self.app(json.loads(json.dumps(app.serialize())))
            self.assertEqual((restored.state["theme"], restored.state["mascot"]), (theme, mascot))
            restored.update(["sub:STATUS"], dt=0)
            self.assertEqual(any(command[0] == "rgbrect" for command in restored.render()), mascot != "outline")
        app.update(["appearance:unknown:shaded", "appearance:green:unknown", "mascot:invalid"], dt=0)
        self.assertEqual((app.state["theme"], app.state["mascot"]), ("green", "color"))
        self.assertEqual(PipBoy(state={"mascot": "outline"}).state["mascot"], "color")

    def test_shaded_mascot_keeps_original_geometry_and_uses_theme_tint(self):
        app = self.app()
        app.update(["appearance:green:shaded"], dt=0)
        green = [command for command in app.render() if command[0] == "rgbrect"]
        self.assertGreater(len(green), 100)
        self.assertGreater(len({tuple(command[5:]) for command in green}), 3)
        app.update(["appearance:amber:shaded"], dt=0)
        amber = [command for command in app.render() if command[0] == "rgbrect"]
        self.assertEqual([command[:5] for command in green], [command[:5] for command in amber])
        self.assertTrue(all(command[5] >= command[6] >= command[7] for command in amber))
        self.assertNotEqual(green, amber)
        config = dict(FIXTURE, theme="amber", mascot="shaded")
        self.assertEqual(PipBoy(config=config).state["mascot"], "shaded")

    def test_map_views_zoom_pan_and_native_controls_are_independent(self):
        app = self.app()
        app.update(["tab:MAP", "map:zoom_in", "map:zoom_in", "map:pan_right", "map:pan:0:20"], dt=0)
        view = app.snapshot()["map_view"]
        self.assertGreater(view["zoom"], 1)
        self.assertGreater(view["cx"], 50)
        self.assertGreater(view["cy"], 50)
        x, y = app._map_point({"x": view["cx"], "y": view["cy"]}, app.maps["WORLD"])
        self.assertEqual((x, y), (160, 124))
        app.update(["item:3", "select", "left"], dt=0)
        self.assertTrue(app.map_pan)
        self.assertEqual(app.tab, "MAP", "Arrows must pan while native pan mode is active")
        self.assertLess(app.snapshot()["map_view"]["cx"], view["cx"])
        app.update(["menu"], dt=0)
        self.assertFalse(app.map_pan)
        self.assertEqual(app.subtab, "LOCAL")
        self.assertEqual(app.snapshot()["map_view"], {"zoom": 1, "cx": 50, "cy": 50})
        app.update(["map:zoom_in", "map:pan_up"], dt=0)
        restored = self.app(json.loads(json.dumps(app.serialize())))
        self.assertEqual(restored.snapshot()["map_view"], app.snapshot()["map_view"])
        restored.update(["map:reset"], dt=0)
        self.assertEqual(restored.snapshot()["map_view"], {"zoom": 1, "cx": 50, "cy": 50})
        restored.update(["sub:WORLD"], dt=0)
        self.assertGreater(restored.snapshot()["map_view"]["zoom"], 1)

    def test_zoomed_geometry_is_clipped_and_sensors_show_availability(self):
        app = self.app()
        app.update(["tab:MAP", "map:zoom_in"], dt=0)
        app.commands = []
        app._map_line(-100, -100, 500, 500)
        app._map_line(-100, -100, -1, -1)
        self.assertEqual(len(app.commands), 1)
        _, x1, y1, x2, y2, _ = app.commands[0]
        self.assertTrue(8 <= x1 <= 312 and 8 <= x2 <= 312 and 56 <= y1 <= 194 and 56 <= y2 <= 194)
        sensors = [{"id": "light", "name": "LIGHT", "value": 42, "unit": "ADC", "available": True, "detail": "Live raw light reading."}, {"id": "imu", "name": "GYRO X", "value": None, "unit": "RAW", "available": False, "detail": "Physical badge required."}]
        app.update(["sub:SENSORS"], dt=0)
        self.assertEqual(app.subtab, "WORLD", "Sensors no longer belong to MAP")
        app.update(["tab:RADIO", "sub:SENSORS"], dt=0, telemetry={"sensors": sensors})
        self.assertIsNone(app.snapshot()["map"])
        self.assertEqual(app.selected_item()["id"], "light")
        texts = [command[1] for command in app.render() if command[0] == "text"]
        self.assertIn("LIGHT  42 ADC", texts)
        self.assertIn("GYRO X  UNAVAILABLE", texts)
        app.update(["down", "select", "waypoint:10,10", "map:zoom_in"], dt=0)
        self.assertEqual(app.selected_item()["id"], "imu")
        self.assertFalse(app.state["timer"]["running"], "Sensor selection must not start a focus timer")
        app.render()


if __name__ == "__main__":
    unittest.main()
