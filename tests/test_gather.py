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
R_INTERACT = G["interact_radius"]
R_CATCH = G["catch_radius"]
CAP = G["hold_capacity"]
NODE_YIELD = G["node_yield"]
FISH_YIELD = G["fish_yield"]
REGROW = int(round(G["regrow_s"] * TICK))
CATCH_CD = int(round(G["catch_cooldown_s"] * TICK))
TIE = 0.5  # độ lệch biểu diễn chính xác, nằm trong mọi bán kính hợp lệ (0.5–5 m) -> hòa khoảng cách thật
PRESS_E = [{"tick": 0, "interact": True}]
PRESS_SPACE = [{"tick": 0, "catch": True}]


def node(nid, x, kind="bong_sung", regrow=0):
    return {"id": nid, "kind": kind, "pos": [x, 0], "regrow_ticks": regrow}


def school(fid, pos, kind="ca_linh"):
    return {"id": fid, "kind": kind, "pos": pos}


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


class GatherCatch(GatherCase):
    """AC-P1-02 (hái, bắt) và giỏ của AC-P1-01: chọn ứng viên, lấy đủ hoặc giữ nguyên, mọc lại, hồi chiêu."""

    def test_prd_example_gathers_node_at_interact_radius_edge(self):
        """Scenario mẫu mục D (nút đúng mép bán kính hái) và dòng event mẫu mục E."""
        block = {"player": {"pos": [20, 0], "heading_deg": 0}, "hold": ["ca_loc", "bong_sung"],
                 "nodes": [{"id": "N1", "kind": "bong_dien_dien", "pos": [20 + R_INTERACT, 0]}], "time_left_ticks": 120}
        rows = self.play(block, PRESS_E, ticks=1)
        self.assertEqual(events(rows, "gather"), [{"type": "event", "tick": 1, "phase": "gather", "name": "gather",
                                                    "data": {"node_id": "N1", "kind": "bong_dien_dien",
                                                             "amount": NODE_YIELD}}])
        s = at(rows)[1]
        self.assertEqual(s["hold"], ["ca_loc", "bong_sung"] + ["bong_dien_dien"] * NODE_YIELD)
        self.assertEqual(s["hold_count"], 2 + NODE_YIELD)
        self.assertEqual([(n["id"], n["ready"], n["regrow_ticks"]) for n in s["nodes"]], [("N1", False, REGROW)])

    def test_gather_tie_on_distance_prefers_smaller_numeric_id(self):
        block = {"player": {"pos": [20, 0]}, "nodes": [node("N10", 20 + TIE), node("N2", 20 - TIE)]}
        rows = self.play(block, PRESS_E, ticks=1)
        self.assertEqual([d["node_id"] for _, d in ev(rows, "gather")], ["N2"])

    def test_gather_skips_node_not_ready(self):
        block = {"player": {"pos": [20, 0]}, "nodes": [node("N1", 20 + TIE / 2, regrow=50), node("N2", 20 + TIE)]}
        rows = self.play(block, PRESS_E, ticks=1)
        self.assertEqual([d["node_id"] for _, d in ev(rows, "gather")], ["N2"])

    def test_node_regrown_after_regrow_ticks_and_gatherable_in_same_step(self):
        """Mục F: nút từ 1 về 0 phát node_regrown và hái được ngay trong bước đó."""
        inputs = [{"tick": 0, "interact": True}, {"tick": 1, "interact": False}, {"tick": REGROW, "interact": True}]
        rows = self.play({"player": {"pos": [20, 0]}, "nodes": [node("N1", 20)]}, inputs,
                         ticks=REGROW + 1, every=REGROW + 1)
        self.assertEqual([t for t, _ in ev(rows, "gather")], [1, REGROW + 1])
        self.assertEqual(ev(rows, "node_regrown"), [(REGROW + 1, {"node_id": "N1"})])
        self.assertEqual([r["name"] for r in events(rows) if r["tick"] == REGROW + 1], ["node_regrown", "gather"])

    def test_interact_gathers_nothing_underwater_or_out_of_range(self):
        cases = {"mặt nước, nút ngoài tầm": [20 + R_INTERACT + 1, 0]}
        if R_INTERACT > SD:
            cases["dưới nước, nút trong tầm"] = [20, (SD + R_INTERACT) / 2]
        for label, pos in cases.items():
            rows = self.play({"player": {"pos": pos}, "nodes": [node("N1", 20)]}, PRESS_E, ticks=1)
            self.assertEqual(ev(rows, "gather") + ev(rows, "hold_full"), [], label)
            self.assertEqual(at(rows)[1]["hold"], [], label)

    def test_gather_hold_full_keeps_node_ready(self):
        block = {"player": {"pos": [20, 0]}, "hold": ["ca_loc"] * CAP, "nodes": [node("N1", 20)]}
        rows = self.play(block, PRESS_E, ticks=1)
        self.assertEqual(ev(rows, "hold_full"),
                         [(1, {"action": "gather", "node_id": "N1", "required": NODE_YIELD, "free": 0})])
        self.assertEqual(ev(rows, "gather"), [])
        s = at(rows)[1]
        self.assertEqual((s["hold_count"], s["nodes"][0]["ready"], s["nodes"][0]["regrow_ticks"]), (CAP, True, 0))

    def test_catch_at_radius_edge_takes_whole_yield_removes_school_sets_cooldown(self):
        rows = self.play({"player": {"pos": [30, 10 + R_CATCH]}, "fish": [school("F1", [30, 10])]}, PRESS_SPACE, ticks=1)
        y = FISH_YIELD["ca_linh"]
        self.assertEqual(ev(rows, "fish_caught"), [(1, {"fish_id": "F1", "kind": "ca_linh", "yield": y})])
        s = at(rows)[1]
        self.assertEqual((s["hold"], s["fish"], s["player"]["catch_cd_ticks"]), (["ca_linh"] * y, [], CATCH_CD))

    @unittest.skipIf(CATCH_CD < 3, "cần hồi chiêu >= 3 tick để dựng frame bấm lại")
    def test_catch_cooldown_set_at_t_reusable_from_t_plus_L(self):
        block = {"player": {"pos": [30, 12]}, "fish": [school("F1", [30, 12 - TIE]), school("F2", [30, 12 + 2 * TIE], "ca_loc")]}
        for press, caught in ((CATCH_CD - 1, ["F1"]), (CATCH_CD, ["F1", "F2"])):
            inputs = [{"tick": 0, "catch": True}, {"tick": 1, "catch": False}, {"tick": press, "catch": True}]
            rows = self.play(block, inputs, ticks=press + 1, every=press + 1)
            self.assertEqual([d["fish_id"] for _, d in ev(rows, "fish_caught")], caught, press)

    def test_catch_does_nothing_at_surface_or_without_school_in_range(self):
        cases = {"mặt nước, đàn trong tầm": ([30, 0], [30, 1]),
                 "dưới nước, không đàn trong tầm": ([30, 10], [30, 10 + R_CATCH + 1])}
        for label, (pos, fish_pos) in cases.items():
            rows = self.play({"player": {"pos": pos}, "fish": [school("F1", fish_pos)]}, PRESS_SPACE, ticks=1)
            self.assertEqual(ev(rows, "fish_caught") + ev(rows, "hold_full"), [], label)
            s = at(rows)[1]
            self.assertEqual((s["player"]["catch_cd_ticks"], [f["id"] for f in s["fish"]]), (0, ["F1"]), label)

    def test_catch_hold_full_keeps_school_and_cooldown_without_trying_other_school(self):
        y_linh, y_loc = FISH_YIELD["ca_linh"], FISH_YIELD["ca_loc"]
        free = y_linh - 1  # thiếu chỗ cho đàn linh gần nhất, nhưng đủ cho đàn lóc xa hơn
        self.assertLessEqual(y_loc, free, "fixture cần đàn xa hơn vừa chỗ để chứng minh không thử đàn khác")
        block = {"player": {"pos": [30, 12]}, "hold": ["bong_sung"] * (CAP - free),
                 "fish": [school("F1", [30, 12 - TIE]), school("F2", [30, 12 + 2 * TIE], "ca_loc")]}
        rows = self.play(block, PRESS_SPACE, ticks=1)
        self.assertEqual(ev(rows, "hold_full"),
                         [(1, {"action": "catch", "fish_id": "F1", "required": y_linh, "free": free})])
        self.assertEqual(ev(rows, "fish_caught"), [])
        s = at(rows)[1]
        self.assertEqual(([f["id"] for f in s["fish"]], s["player"]["catch_cd_ticks"], s["hold_count"]),
                         (["F1", "F2"], 0, CAP - free))

    def test_catch_tie_on_distance_prefers_smaller_numeric_id(self):
        block = {"player": {"pos": [30, 12]}, "fish": [school("F10", [30, 12 + TIE]), school("F2", [30, 12 - TIE])]}
        rows = self.play(block, PRESS_SPACE, ticks=1)
        self.assertEqual([d["fish_id"] for _, d in ev(rows, "fish_caught")], ["F2"])


if __name__ == "__main__":
    unittest.main()
