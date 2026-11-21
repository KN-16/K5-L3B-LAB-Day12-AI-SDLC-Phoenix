"""Kiểm runner v1.1 tại giao diện bàn giao với hai lát mô phỏng."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from chonoi.contract import load_contract, validate_tuning
from chonoi.errors import BadInput
from chonoi.headless import main
from chonoi.inputs import BUTTONS_V11, InputPlayer
from chonoi.live import LiveGame
from chonoi.runner import Session, run
from chonoi.scenario import load_scenario
from helpers import ROOT, Workdir, read_jsonl, write_json


def phase2_contract():
    root = Path(ROOT)
    with (root / "docs/contracts/phase-2.tuning.json").open(encoding="utf-8") as file:
        delta = json.load(file)
    contract = load_contract()
    for key, values in delta["tuning"].items():
        if isinstance(values, dict):
            contract["tuning"][key] = {**contract["tuning"].get(key, {}), **values}
        else:
            contract["tuning"][key] = values
    contract["contract_version"] = delta["contract_version"]
    return contract


class GatherFixture:
    mode = phase = "gather"

    def __init__(self, tuning, scenario, streams, ids, *, day):
        self.settings = tuning["gather"]
        self.stock = {kind: scenario.get("hold", []).count(kind) for kind in scenario.get("hold", [])}
        self.money = self.earned = 0
        self.reputation = 3
        self.time_left_ticks = 1
        self.done = False

    def inventory_items(self):
        return dict(self.stock)

    def snapshot(self):
        oxygen = self.settings["oxygen_max_s"] * 60
        hp = self.settings["hp_max"]
        return {"player": {"pos": self.settings["start_pos"], "oxygen_max_ticks": oxygen,
                           "oxygen_ticks": oxygen, "hp": hp, "hp_max": hp, "at_surface": True},
                "hold": list(self.stock), "hold_capacity": self.settings["hold_capacity"]}

    def step(self, inp):
        self.time_left_ticks = 0
        self.done = True
        return [("gather_end", {"reason": "time", "inventory": {"items": self.inventory_items()}})]


class QuanFixture:
    mode = phase = "quan"

    def __init__(self, tuning, scenario, streams, ids, inventory, *, day_plan, progress):
        if scenario.get("stock_required") and not inventory:
            raise BadInput("fixture cần kho bàn giao")
        self.stock = inventory
        self.plan = day_plan
        self.money, self.earned, self.reputation = (progress[key] for key in ("money", "earned", "reputation"))
        self.time_left_ticks = 1
        self.done = False

    def snapshot(self):
        return {"stock": dict(self.stock)}

    def step(self, inp):
        self.time_left_ticks = 0
        self.done = True
        return [("quan_end", {"reason": "time"})]


class TestDay(unittest.TestCase):
    def setUp(self):
        self.contract = phase2_contract()
        self.tuning = self.contract["tuning"]
        validate_tuning(self.tuning, phase2=True)
        for name, fixture in (("GatherSim", GatherFixture), ("QuanSim", QuanFixture)):
            mock = patch(f"chonoi.runner.{name}", fixture)
            mock.start()
            self.addCleanup(mock.stop)

    def test_pause_preserves_shop_and_upgrades_apply_next_day(self):
        session = Session("day", self.tuning,
                          {"day": {"money": 200, "earned": 200, "reputation": 4},
                           "gather": {"hold": ["ca_loc"]}}, 42, days=2)
        self.assertEqual([e["name"] for e in session.initial_events()], ["day_start", "day_plan", "phase_start"])
        self.assertEqual(session.snapshot()["score"], 600)
        input_player = InputPlayer([
            {"tick": 2, "pause": True, "buy": "hp"},
            {"tick": 3, "pause": False},
            {"tick": 4, "pause": True, "buy": "oxygen"},
            {"tick": 5, "shop_done": True},
        ], BUTTONS_V11)
        rows = []
        for tick in range(6):
            rows += session.step(input_player.advance(tick))
            if tick == 0:
                self.assertEqual(session.snapshot()["stock"], {"ca_loc": 1})
                self.assertEqual(session.snapshot()["phase_tick"], 0)
            if tick == 3:
                snap = session.snapshot()
                self.assertEqual((snap["tick"], snap["sim_tick"], snap["phase_tick"]), (4, 2, 0))
                self.assertEqual((snap["state"], snap["time_left_ticks"]), ("paused", 600))
            if tick == 4:
                snap = session.snapshot()
                self.assertEqual(snap["upgrades"], {"oxygen": 1})
                self.assertEqual(snap["active_upgrades"], {})
        self.assertEqual(
            [(r["tick"], r["phase"], r["name"]) for r in rows],
            [(1, "gather", "gather_end"), (1, "quan", "phase_start"),
             (2, "quan", "quan_end"), (2, "shop", "phase_start"),
             (3, "shop", "paused"), (5, "shop", "resumed"), (5, "shop", "bought"),
             (6, "shop", "shop_end"), (6, "gather", "day_start"),
             (6, "gather", "day_plan"), (6, "gather", "phase_start")],
        )
        snap = session.snapshot()
        self.assertEqual(snap["player"]["oxygen_max_ticks"], 2700)
        self.assertEqual((snap["day"], snap["money"], snap["earned"], snap["score"]), (2, 0, 200, 600))

    def test_headless_output_has_snapshot_at_each_phase_start(self):
        with Workdir() as work, patch("chonoi.headless.load_contract", return_value=self.contract):
            output = work.path("day.jsonl")
            exit_code = main(["--mode", "day", "--seed", "42", "--ticks", "1000", "--out", output])
            self.assertEqual(exit_code, 0)
            rows = read_jsonl(output)
            snapshots = {row["tick"]: row for row in rows if row["type"] == "snapshot"}
            self.assertEqual((snapshots[1]["phase"], snapshots[1]["phase_tick"]), ("quan", 0))
            self.assertEqual((snapshots[2]["phase"], snapshots[2]["phase_tick"]), ("shop", 0))
            self.assertEqual((rows[-1]["reason"], rows[-1]["days_completed"], rows[-1]["ticks"]),
                             ("days_complete", 1, 602))

    def test_buy_is_one_frame_and_runs_before_shop_done(self):
        with Workdir() as work:
            path = work.path("day.jsonl")
            run("day", self.tuning, {"day": {"money": 200, "earned": 200}}, 42,
                [{"tick": 2, "buy": "oxygen", "shop_done": True}], 20, path, 10)
            events = [r["name"] for r in read_jsonl(path) if r.get("tick") == 3 and r["type"] == "event"]
            self.assertEqual(events, ["bought", "shop_end"])
        inputs = InputPlayer([{"tick": 0, "buy": "oxygen"}], BUTTONS_V11)
        self.assertEqual(inputs.advance(0).buy, "oxygen")
        self.assertIsNone(inputs.advance(1).buy)

    def test_invalid_late_quan_fixture_preserves_output(self):
        with Workdir() as work:
            output = write_json(work.path("day.jsonl"), {"old": True})
            with self.assertRaises(BadInput):
                run("day", self.tuning, {"quan": {"stock_required": True}}, 42, [], 10, output, 10)
            self.assertEqual(Path(output).read_text(encoding="utf-8"), '{"old": true}')

    def test_day_fixture_rejects_wrong_stock_and_bad_plan(self):
        with Workdir() as work:
            for fixture in (
                {"quan": {"stock": {"ca_loc": 1}}},
                {"day": {"money": 2, "earned": 1}},
                {"day": {"day_plan": [{"day": 1, "dishes": {"ca_loc_nuong_trui": 1}, "ingredients": {"ca_loc": 2}}]}},
            ):
                with self.subTest(fixture=fixture), self.assertRaises(BadInput):
                    load_scenario(write_json(work.path("scenario.json"), fixture), "day", self.tuning)

    def test_live_intro_holds_timers_and_shop_uses_same_session(self):
        game = LiveGame("day", self.tuning, {"day": {"money": 200, "earned": 200}}, 42, days=1)
        self.assertEqual(json.loads(game.state_json())["screen"], "menu")
        game.set_screen("play")
        game._tick_once()
        self.assertEqual(game.session.tick, 0)
        game.set_screen("day_intro")
        game._tick_once()
        self.assertEqual(json.loads(game.state_json())["screen"], "evening_intro")
        game.set_screen("evening_intro")
        game._tick_once()
        self.assertEqual(json.loads(game.state_json())["screen"], "day_result")
        game.set_screen("day_result")
        game.set_input({"buy": "oxygen", "shop_done": True})
        game._tick_once()
        status = json.loads(game.state_json())
        self.assertEqual((status["screen"], status["money"], status["upgrades"]), ("summary", 0, {"oxygen": 1}))
