"""Test lát Lặn & Hái (gather), kiểu HỘP ĐEN: chạy `headless_cmd` trong game.contract.json rồi đọc JSONL/file kho.

Đối chiếu DocsPhase.txt, PRD-0 Phase 1: mục D (scenario), E (payload event, snapshot), F (thứ tự một bước "Gather").
Số liệu đọc từ game.contract.json. Mọi fixture tắt cá mặc định (`random_fish: false`) và khai nút/đàn tường minh để
không phụ thuộc dữ liệu mặc định của phase sau.

Chạy: PYTHONPATH=tests:. python3 -m unittest discover -s tests -p 'test_gather.py' -v
"""

import json
import os
import unittest

from helpers import ROOT, Workdir, events, frames, read_jsonl, run_headless, snapshots, write_json

TICK = 60

with open(os.path.join(ROOT, "game.contract.json"), encoding="utf-8") as _f:
    G = json.load(_f)["tuning"]["gather"]

SD = G["surface_depth"]
SPEED = G["swim_speed"]
STEP = SPEED / TICK  # quãng bơi mỗi tick ở vận tốc đích
OXY_MAX = int(round(G["oxygen_max_s"] * TICK))
REFILL = G["oxygen_refill_per_tick"]
CHOKE = G["choke_interval_ticks"]
HP = G["hp_max"]
UNDER = [20, 10]  # dưới nước, ngoài bến, quanh đó không có nút/đàn


def ev(rows, name):
    """[(tick, data)] của mọi event `name`, theo thứ tự ghi."""
    return [(r["tick"], r["data"]) for r in events(rows, name)]


def at(rows):
    """Snapshot theo tick."""
    return {s["tick"]: s for s in snapshots(rows)}


class GatherCase(unittest.TestCase):
    def play(self, block, inputs=(), ticks=1, every=1):
        """Chạy gather với fixture `block` (mặc định không cá, không nút); trả các dòng JSONL."""
        scenario = {"gather": {"random_fish": False, "nodes": [], "fish": [], **block}}
        with Workdir() as w:
            args = ["--mode", "gather", "--seed", "1", "--ticks", str(ticks), "--snapshot-every", str(every),
                    "--scenario", write_json(w.path("sc.json"), scenario), "--out", w.path("o.jsonl")]
            if inputs:
                args += ["--inputs", write_json(w.path("in.json"), frames(*inputs))]
            code, err = run_headless(*args)
            self.assertEqual(code, 0, err)
            return read_jsonl(w.path("o.jsonl"))


class SwimOxygenChoke(GatherCase):
    """AC-P1-01: dive/surface theo vị trí sau bước bơi, oxy theo d cuối bước, ngạt."""

    def test_dive_when_crossing_surface_after_move(self):
        d0 = 0.4
        k = next(k for k in range(1, TICK) if d0 + k * STEP > SD)  # vel = vận tốc đích nên d tăng đều STEP
        rows = self.play({"player": {"pos": [20, d0], "vel": [0, SPEED]}}, [{"tick": 0, "move": [0, 1]}], ticks=k + 2)
        dive = ev(rows, "dive")
        self.assertEqual([t for t, _ in dive], [k])
        self.assertGreater(dive[0][1]["pos"][1], SD)
        self.assertEqual(ev(rows, "surface"), [])

    def test_surface_when_crossing_surface_after_move(self):
        d0 = SD + STEP / 2  # nửa bước dưới biên: một bước bơi lên là qua biên
        rows = self.play({"player": {"pos": [20, d0], "vel": [0, -SPEED]}}, [{"tick": 0, "move": [0, -1]}], ticks=2)
        surface = ev(rows, "surface")
        self.assertEqual([t for t, _ in surface], [1])
        self.assertLessEqual(surface[0][1]["pos"][1], SD)
        self.assertEqual(ev(rows, "dive"), [])

    def test_no_dive_or_surface_without_crossing(self):
        for pos in ([20, 0], UNDER):  # bơi ngang trên mặt nước / dưới nước
            rows = self.play({"player": {"pos": pos}}, [{"tick": 0, "move": [1, 0]}], ticks=30)
            self.assertEqual(ev(rows, "dive") + ev(rows, "surface"), [], pos)

    def test_oxygen_minus_one_underwater_plus_refill_at_surface_clamped(self):
        n = 20
        s = at(self.play({"player": {"pos": UNDER}}, ticks=n))
        self.assertEqual([s[k]["player"]["oxygen_ticks"] for k in range(n + 1)], [OXY_MAX - k for k in range(n + 1)])
        start = max(0, OXY_MAX - 3 * REFILL - 1)  # chạm trần ở tick 4
        s = at(self.play({"player": {"pos": [20, 0], "oxygen_ticks": start}}, ticks=6))
        self.assertEqual([s[k]["player"]["oxygen_ticks"] for k in range(7)],
                         [min(OXY_MAX, start + REFILL * k) for k in range(7)])

    def test_oxygen_empty_once_when_reaching_zero(self):
        rows = self.play({"player": {"pos": UNDER, "oxygen_ticks": 3}}, ticks=10)
        self.assertEqual(ev(rows, "oxygen_empty"), [(3, {"oxygen_ticks": 0})])

    def test_first_choke_at_t_plus_59_counting_the_empty_step(self):
        """Mục F: chạm oxy 0 ở t, ở dưới nước liên tục -> ngạt lần đầu ở t+59, rồi mỗi choke_interval_ticks."""
        rows = self.play({"player": {"pos": UNDER, "oxygen_ticks": 1}}, ticks=1 + 2 * CHOKE)
        self.assertEqual(ev(rows, "oxygen_empty"), [(1, {"oxygen_ticks": 0})])
        t1 = 1 + CHOKE - 1
        self.assertEqual(ev(rows, "choke"), [(t1, {"hp": HP - 1}), (t1 + CHOKE, {"hp": HP - 2})])
        s = at(rows)
        self.assertEqual(s[t1 - 1]["player"]["zero_oxy_ticks"], CHOKE - 1)
        self.assertEqual((s[t1]["player"]["zero_oxy_ticks"], s[t1]["player"]["hp"]), (0, HP - 1))

    def test_choke_continues_counter_from_scenario(self):
        rows = self.play({"player": {"pos": UNDER, "oxygen_ticks": 0, "zero_oxy_ticks": CHOKE - 1}}, ticks=2)
        self.assertEqual(ev(rows, "choke"), [(1, {"hp": HP - 1})])
        self.assertEqual(ev(rows, "oxygen_empty"), [], "oxy đã 0 từ đầu: không phát lại oxygen_empty")

    def test_surfacing_on_the_choke_step_refills_without_choke(self):
        d0 = SD + STEP / 2
        player = {"pos": [20, d0], "vel": [0, -SPEED], "oxygen_ticks": 0, "zero_oxy_ticks": CHOKE - 1}
        rows = self.play({"player": player}, [{"tick": 0, "move": [0, -1]}], ticks=1)
        self.assertEqual([t for t, _ in ev(rows, "surface")], [1])
        self.assertEqual(ev(rows, "choke"), [])
        p = at(rows)[1]["player"]
        self.assertEqual((p["oxygen_ticks"], p["zero_oxy_ticks"], p["hp"]), (min(OXY_MAX, REFILL), 0, HP))

    def test_dive_then_oxygen_empty_in_processing_order(self):
        d0 = SD - STEP / 2  # nửa bước trên biên: một bước bơi xuống là qua biên
        rows = self.play({"player": {"pos": [20, d0], "vel": [0, SPEED], "oxygen_ticks": 1}},
                         [{"tick": 0, "move": [0, 1]}], ticks=1)
        self.assertEqual([r["name"] for r in events(rows) if r["tick"] == 1], ["dive", "oxygen_empty"])


if __name__ == "__main__":
    unittest.main()
