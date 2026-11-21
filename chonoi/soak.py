"""Chạy một Session qua nhiều Ngày với bot đầu vào tất định."""

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

from .contract import load_contract
from .errors import BadInput
from .inputs import InputState
from .runner import Session


class Bot:
    def __init__(self):
        self.interacting = False

    def _toward(self, position, target, radius):
        dx, dy = (target[0] - position[0], target[1] - position[1])
        distance = math.hypot(dx, dy)
        close = distance <= radius / 3
        move = (0.0, 0.0) if close else (dx / distance, dy / distance)
        edge = close and not self.interacting
        self.interacting = edge
        return InputState(move, {"interact": edge}, {"interact"} if edge else set())

    def _gather(self, session):
        sim = session.sim
        plants = {node["kind"] for node in sim.nodes}
        plans = session.day.plan
        recipes = [session.tuning["menu"][dish]["recipe"] for dish in sorted(plans["dishes"])]
        goals = next((recipe for recipe in recipes if recipe.keys() <= plants), None)
        if goals is None:
            available = sorted(plants & plans["ingredients"].keys())
            goals = {available[0]: 1} if available else {}
        have = Counter(item["kind"] for item in sim.hold)
        missing = next((kind for kind, amount in goals.items() if have[kind] < amount), None)
        if missing and len(sim.hold) < sim.t["hold_capacity"]:
            nodes = [node for node in sim.nodes if node["kind"] == missing]
            node = min(nodes, key=lambda n: (n["regrow_ticks"] != 0, math.dist(sim.pos, n["pos"]), n["id"]))
            return self._toward(sim.pos, node["pos"], sim.t["interact_radius"])
        return self._toward(sim.pos, sim.t["dock_pos"], sim.t["dock_radius"])

    def _quan(self, sim):
        if sim.hand:
            customer = next(c for c in sim.customers if c["id"] == sim.hand["order_id"])
            table = next(t for t in sim.tables if t["id"] == customer["table_id"])
            return self._toward(sim.pos, table["pos"], sim.t["interact_radius"])
        if any(c["order_status"] == "reserved" for c in sim.customers) or any(
                stove["state"] != "idle" for stove in sim.stoves):
            stove = next((st for st in sim.stoves if st["state"] != "idle"), sim.stoves[0])
            return self._toward(sim.pos, stove["pos"], sim.t["interact_radius"])
        self.interacting = False
        return InputState((0.0, 0.0), {}, set())

    def actions(self, session):
        sim = session.sim
        if sim.phase == "gather":
            return self._gather(session)
        if sim.phase == "quan":
            return self._quan(sim)
        self.interacting = False
        for kind in ("oxygen", "hp"):
            levels = sim.tuning["upgrades"][kind]
            level = sim.upgrades.get(kind, 0)
            if level < len(levels) and levels[level]["price"] <= sim.money:
                return InputState((0.0, 0.0), {}, set(), buy=kind)
        return InputState((0.0, 0.0), {"shop_done": True}, {"shop_done"})


def run_soak(tuning, seed, days):
    started = time.perf_counter()
    results, crashes = [], 0
    try:
        session = Session("day", tuning, {}, seed, days=days)
        bot = Bot()
        max_per_day = sum(round(tuning[phase]["duration_s"] * tuning["tick_hz"])
                          for phase in ("gather", "quan")) + tuning["shop"]["max_ticks"]
        for _ in range(days * max_per_day):
            events = session.step(bot.actions(session))
            closed = next((row for row in events if row["name"] == "shop_end"), None)
            if closed:
                state = session.end_row()
                results.append({"day": closed["day"], "earned": state["earned"],
                                "reputation": state["reputation"], "score": state["score"]})
            if session.done:
                break
        if not session.done or len(results) != days:
            raise RuntimeError("vượt giới hạn mô phỏng trước khi đủ Ngày")
    except Exception as error:
        crashes += 1
        print(f"soak: {error}", file=sys.stderr)
    return {"days": days, "days_completed": len(results), "crashes": crashes, "results": results,
            "duration_s": time.perf_counter() - started}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Chạy soak headless qua nhiều Ngày.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.days <= 0:
        parser.error("--days phải là số nguyên dương")
    try:
        contract = load_contract()
        result = run_soak(contract["tuning"], args.seed, args.days)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    except (BadInput, OSError) as error:
        parser.exit(1, f"soak: {error}\n")
    return int(bool(result["crashes"]))


if __name__ == "__main__":
    raise SystemExit(main())
