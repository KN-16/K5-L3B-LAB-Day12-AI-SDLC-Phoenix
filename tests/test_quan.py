import subprocess
import sys
import unittest

from chonoi.contract import load_contract
from chonoi.inputs import InputPlayer
from chonoi.runner import Session
from helpers import ROOT, Workdir, write_json

DISH = "ca_loc_nuong_trui"


def customer(**fields):
    return {"id": "C1", "table_id": "T1", "dish_id": DISH, **fields}


def cooked_dish(order_id="C1", base_price=60):
    return {"order_id": order_id, "dish_id": DISH, "base_price": base_price}


class QuanTests(unittest.TestCase):
    def setUp(self):
        self.tuning = load_contract()["tuning"]

    def play(self, scenario, ticks, frames=(), inventory=None):
        session = Session("quan", self.tuning, scenario, seed=42, inventory=inventory)
        inputs = InputPlayer(frames)
        snapshots = [session.snapshot()]
        events = []
        for tick in range(ticks):
            events.extend(session.step(inputs.advance(tick)))
            snapshots.append(session.snapshot())
            if session.done:
                break
        return events, snapshots

    def test_arrival_uses_phase_tick_and_reserves_recipe_from_inventory(self):
        events, snapshots = self.play(
            {"time_left_ticks": 121}, 120, inventory={"ca_loc": 1}
        )
        self.assertEqual(events, [{
            "type": "event", "tick": 120, "phase": "quan", "name": "customer_arrived",
            "data": {"order_id": "C1", "table_id": "T1", "dish_id": DISH},
        }])
        self.assertEqual(snapshots[119]["customers"], [])
        self.assertEqual(snapshots[120]["stock"], {"ca_loc": 1})
        arrived = snapshots[120]["customers"][0]
        self.assertEqual(arrived["reserved"], {"ca_loc": 1})
        self.assertEqual(arrived["patience_ticks_left"], 3600)

    def test_no_dish_only_when_a_table_is_free(self):
        events, _ = self.play({}, 1020)
        self.assertEqual([(e["tick"], e["name"], e["data"]) for e in events],
                         [(120, "no_dish", {}), (1020, "no_dish", {})])
        events, _ = self.play({"stock": {"ca_loc": 1}, "customers": [customer()]}, 120)
        self.assertEqual(events, [])

    def test_inventory_reserved_for_one_table_is_unavailable_to_another(self):
        self.tuning["quan"]["tables"].append({"id": "T2", "pos": [4, 4]})
        events, snapshots = self.play(
            {"stock": {"ca_loc": 1}, "customers": [customer()]}, 120
        )
        self.assertEqual([e["name"] for e in events], ["no_dish"])
        self.assertEqual(snapshots[0]["customers"][0]["reserved"], {"ca_loc": 1})
        self.assertIsNone(snapshots[-1]["tables"][1]["customer_id"])

    def test_fixture_conflicts_exit_2_before_opening_output(self):
        fixtures = (
            {"customers": [customer()]},
            {"stock": {"ca_loc": 2}, "customers": [customer(reserved={"ca_loc": 2})]},
            {"customers": [customer(order_status="assigned")]},
            {"customers": [customer(state="eating", order_status="served", eat_ticks_left=1)]},
            {"customers": [customer(order_status="assigned", patience_ticks_left=-1)]},
            {"hand": {"order_id": "C9", "dish_id": DISH, "base_price": 60}},
            {"stoves": [{"id": "B1", "state": "cooking", "cook_ticks_left": 0}]},
            {"tables": [{"id": "T1", "customer_id": "C1"}]},
        )
        with Workdir() as work:
            out = work.path("out.jsonl")
            with open(out, "w", encoding="utf-8") as file:
                file.write("original")
            for fixture in fixtures:
                with self.subTest(fixture=fixture):
                    scenario = write_json(work.path("scenario.json"), {"quan": fixture})
                    result = subprocess.run([
                        sys.executable, "-B", "-m", "chonoi.headless", "--mode", "quan",
                        "--scenario", scenario, "--seed", "42", "--ticks", "0", "--out", out,
                    ], cwd=ROOT, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    with open(out, encoding="utf-8") as file:
                        self.assertEqual(file.read(), "original")

    def test_cook_pick_on_ready_tick_and_serve_after_releasing_button(self):
        scenario = {
            "player": {"pos": [2, 8]},
            "tables": [{"id": "T1", "pos": [3, 8]}],
            "stock": {"ca_loc": 1},
            "customers": [customer()],
            "random_customers": False,
        }
        events, snapshots = self.play(scenario, 381, [
            {"tick": 0, "interact": True},
            {"tick": 1, "interact": False},
            {"tick": 360, "interact": True},
            {"tick": 361, "move": [1, 0]},
            {"tick": 379, "interact": False, "move": [0, 0]},
            {"tick": 380, "interact": True},
        ])
        self.assertEqual([(e["tick"], e["name"]) for e in events], [
            (1, "cook_started"), (361, "dish_ready"), (361, "dish_picked"), (381, "served"),
        ])
        self.assertEqual(events[0]["data"], {
            "stove_id": "B1", **cooked_dish(), "items": ["ca_loc"],
        })
        self.assertEqual(snapshots[1]["customers"][0]["reserved"], {})
        self.assertEqual(snapshots[1]["stock"], {})
        self.assertEqual(snapshots[360]["stoves"][0]["cook_ticks_left"], 1)
        self.assertEqual(snapshots[361]["hand"], cooked_dish())
        self.assertIsNone(snapshots[381]["hand"])
        self.assertEqual(snapshots[381]["customers"][0]["eat_ticks_left"], 600)

    def test_equal_distance_selects_stove_even_if_it_cannot_interact(self):
        scenario = {
            "player": {"pos": [3.5, 8]},
            "tables": [{"id": "T1", "pos": [5, 8]}],
            "stoves": [{"id": "B1", "state": "cooking", "cook_ticks_left": 2, "dish": cooked_dish()}],
            "customers": [customer(order_status="assigned")],
        }
        events, snapshots = self.play(scenario, 2, [{"tick": 0, "interact": True}])
        self.assertEqual([(e["tick"], e["name"]) for e in events], [(2, "dish_ready")])
        self.assertEqual(snapshots[2]["stoves"][0]["ready_ticks"], 0)

        scenario["stoves"] = []
        scenario["hand"] = cooked_dish()
        events, snapshots = self.play(scenario, 1, [{"tick": 0, "interact": True}])
        self.assertEqual(events, [])
        self.assertEqual(snapshots[-1]["hand"], cooked_dish())

    def test_serving_at_exact_radius_patience_and_closing_deadlines(self):
        events, _ = self.play({
            "player": {"pos": [10.5, 2]},
            "time_left_ticks": 1,
            "hand": cooked_dish(),
            "customers": [customer(order_status="assigned", patience_ticks_left=1)],
        }, 1, [{"tick": 0, "interact": True}])
        self.assertEqual(events[0]["name"], "served")
        self.assertEqual(events[0]["data"], {
            **cooked_dish(), "table_id": "T1", "patience_ticks_left": 0, "tip": 0,
        })

    def test_tip_threshold_uses_patience_after_decrement_and_payment_waits_for_eating(self):
        for patience, tip in ((1800, 0), (1801, 12)):
            with self.subTest(patience=patience):
                events, snapshots = self.play({
                    "player": {"pos": [9, 2]}, "random_customers": False,
                    "hand": cooked_dish(),
                    "customers": [customer(order_status="assigned", patience_ticks_left=patience)],
                }, 601, [{"tick": 0, "interact": True}])
                self.assertEqual([(e["tick"], e["name"]) for e in events],
                                 [(1, "served"), (601, "paid")])
                self.assertEqual(events[0]["data"]["tip"], tip)
                self.assertEqual(events[1]["data"], {
                    "order_id": "C1", "table_id": "T1", "base_price": 60, "tip": tip,
                    "amount": 60 + tip, "reason": "finished_eating",
                })
                self.assertEqual(snapshots[600]["money"], 0)
                self.assertEqual(snapshots[601]["earned"], 60 + tip)
                self.assertEqual(snapshots[601]["reputation"], 3.2 if tip else 3)
                self.assertEqual(snapshots[601]["customers"], [])

    def test_tip_floors_the_decimal_rate_applied_to_locked_price(self):
        self.tuning["quan"]["tip_rate"] = 0.58
        events, _ = self.play({
            "player": {"pos": [9, 2]}, "time_left_ticks": 1,
            "hand": cooked_dish(base_price=50),
            "customers": [customer(order_status="assigned")],
        }, 1, [{"tick": 0, "interact": True}])
        self.assertEqual(events[0]["data"]["tip"], 29)
        self.assertEqual(events[1]["data"]["amount"], 79)

    def test_waiting_customer_leaves_before_arrival_and_releases_raw_stock(self):
        events, snapshots = self.play({
            "stock": {"ca_loc": 1}, "customers": [customer(id="C9", patience_ticks_left=120)],
        }, 120)
        self.assertEqual([(e["tick"], e["name"]) for e in events],
                         [(120, "customer_left"), (120, "customer_arrived")])
        self.assertEqual(events[0]["data"], {
            "order_id": "C9", "table_id": "T1", "reason": "patience", "reputation": 2.5,
        })
        self.assertEqual(events[1]["data"]["order_id"], "C10")
        self.assertEqual(snapshots[120]["stock"], {"ca_loc": 1})
        self.assertEqual(snapshots[120]["customers"][0]["reserved"], {"ca_loc": 1})

    def test_closing_pays_eaters_and_clears_waiting_orders_in_table_order(self):
        self.tuning["quan"]["tables"].extend([
            {"id": "T10", "pos": [5, 8]}, {"id": "T2", "pos": [6, 8]},
        ])
        events, snapshots = self.play({
            "time_left_ticks": 1,
            "player": {"pos": [9, 2]},
            "hand": cooked_dish(),
            "stoves": [{"id": "B1", "state": "ready", "dish": cooked_dish("C2")}],
            "customers": [
                customer(id="C3", table_id="T10", state="eating", order_status="served",
                         eat_ticks_left=1, base_price=60, tip=12),
                customer(id="C2", table_id="T2", order_status="assigned", patience_ticks_left=1),
                customer(order_status="assigned"),
            ],
        }, 1, [{"tick": 0, "interact": True}])
        self.assertEqual([e["name"] for e in events], ["served", "paid", "customer_left", "paid", "quan_end"])
        self.assertEqual([(e["data"]["table_id"], e["data"]["reason"]) for e in events[1:4]],
                         [("T1", "closing"), ("T2", "closing"), ("T10", "finished_eating")])
        self.assertEqual(events[-1]["data"], {
            "reason": "time", "money": 144, "earned": 144, "shift_earned": 144, "reputation": 3.4,
        })
        final = snapshots[-1]
        self.assertEqual(final["customers"], [])
        self.assertEqual(final["stock"], {})
        self.assertIsNone(final["hand"])
        self.assertEqual(final["stoves"][0]["state"], "idle")
        self.assertIsNone(final["stoves"][0]["dish"])
        self.assertTrue(all(table["customer_id"] is None for table in final["tables"]))

    def test_reputation_uses_exact_whole_number_for_score_and_clamps(self):
        self.tuning["quan"]["tables"].extend([
            {"id": "T2", "pos": [5, 8]}, {"id": "T3", "pos": [6, 8]},
        ])
        customers = [
            customer(id=f"C{n}", table_id=f"T{n}", state="eating", order_status="served",
                     eat_ticks_left=1, base_price=60, tip=12)
            for n in range(1, 4)
        ]
        for start, reputation, score in ((1.4, 2, 416), (4.9, 5, 716)):
            with self.subTest(start=start):
                _, snapshots = self.play({"customers": customers, "reputation": start}, 1)
                self.assertEqual(snapshots[-1]["reputation"], reputation)
                self.assertEqual(snapshots[-1]["score"], score)

    def test_patience_drops_dish_without_refunding_used_ingredients(self):
        for location in (
            {"hand": cooked_dish()},
            {"stoves": [{"id": "B1", "state": "cooking", "cook_ticks_left": 2, "dish": cooked_dish()}]},
        ):
            with self.subTest(location=location):
                events, snapshots = self.play({
                    **location, "reputation": 0.2,
                    "customers": [customer(order_status="assigned", patience_ticks_left=1)],
                }, 1)
                self.assertEqual([e["name"] for e in events], ["customer_left"])
                self.assertEqual(events[0]["data"]["reputation"], 0)
                self.assertEqual(snapshots[-1]["stock"], {})
                self.assertIsNone(snapshots[-1]["hand"])
                self.assertEqual(snapshots[-1]["stoves"][0]["state"], "idle")
