"""Buổi tối — Mở Quán theo Test Contract v1.0."""

import math
from decimal import Decimal

from ..errors import BadInput
from ..ids import id_key, sort_by_id
from ..inventory import validate_items
from ..scenario import _nonneg_int, _pos
from .ramp import ramp_velocity

STOVE_FIELDS = {"id", "pos", "state", "dish", "cook_ticks_left", "ready_ticks"}
CUSTOMER_FIELDS = {"id", "table_id", "dish_id", "order_tick", "state", "patience_ticks_left",
                   "eat_ticks_left", "order_status", "reserved", "base_price", "tip"}


class QuanSim:
    mode = "quan"
    phase = "quan"

    def __init__(self, tuning, scenario, streams, ids, inventory=None):
        t = tuning["quan"]
        self.t = t
        self.menu = tuning["menu"]
        self.rng = streams
        self.ids = ids
        self.tick_hz = tuning["tick_hz"]
        self.phase_tick = 0
        self.patience_ticks = self._ticks(t["patience_s"])
        self.eat_ticks = self._ticks(t["eat_s"])
        self.customer_interval = self._ticks(t["customer_interval_s"])
        self.random_customers = scenario.get("random_customers", True)
        if not isinstance(self.random_customers, bool):
            raise BadInput("random_customers phải là boolean")
        p = scenario.get("player", {})
        self.pos = list(p.get("pos", t["start_pos"]))
        vel = p.get("vel", [0.0, 0.0])
        if any(isinstance(c, float) and not math.isfinite(c) for c in vel):
            raise BadInput("player.vel phải hữu hạn")
        self.vel = [float(c) for c in vel]
        self._tgt = None
        self._ramp_left = 0
        # kho: --inventory HOẶC scenario.stock (cả hai -> cli đã báo mã 2)
        self.stock = dict(inventory if inventory is not None else scenario.get("stock", {}))
        self.hand = scenario.get("hand")
        self.time_left_ticks = scenario.get("time_left_ticks", self._ticks(t["duration_s"]))
        self.reputation = scenario.get("reputation", t["reputation_initial"])
        if (isinstance(self.reputation, bool) or not isinstance(self.reputation, (int, float))
                or not t["reputation_min"] <= self.reputation <= t["reputation_max"]):
            raise BadInput("reputation ngoài miền tuning")
        self.stoves = [dict(s, state=s.get("state", "idle"), dish=s.get("dish"),
                            cook_ticks_left=s.get("cook_ticks_left", 0), ready_ticks=s.get("ready_ticks", 0))
                       for s in self._merge(t["stoves"], scenario.get("stoves", []), STOVE_FIELDS)]
        self.tables = self._merge(t["tables"], scenario.get("tables", []), {"id", "pos"})
        self.customers = self._load_customers(scenario.get("customers", []))
        self._validate_dish_locations()
        self.money = 0
        self.earned = 0
        self.shift_earned = 0
        self.done = False
        self.reason = None

    def _ticks(self, seconds):
        return round(seconds * self.tick_hz)

    def _merge(self, defaults, updates, fields):
        by_id = {d["id"]: dict(d) for d in defaults}
        for u in updates:
            if u["id"] not in by_id:
                raise BadInput(f"id bếp/bàn không tồn tại: {u['id']}")
            if set(u) - fields:
                raise BadInput(f"{u['id']}: trường bếp/bàn chưa hỗ trợ")
            if "pos" in u:
                _pos(f"{u['id']}.pos", u["pos"], self.t["bounds"], axes=("x", "z"))
            by_id[u["id"]].update(u)
        return sort_by_id(list(by_id.values()))

    @staticmethod
    def _order_key(customer):
        return customer["order_tick"], id_key(customer["table_id"])

    def _load_customers(self, fixtures):
        customers = []
        available = self.stock.copy()
        for fixture in fixtures:
            if set(fixture) - CUSTOMER_FIELDS:
                raise BadInput(f"{fixture['id']}: trường khách chưa hỗ trợ")
            dish_id = fixture.get("dish_id")
            if not isinstance(dish_id, str) or dish_id not in self.menu:
                raise BadInput(f"{fixture['id']}: món gọi không hợp lệ")
            customer = dict(
                state="waiting", order_tick=0, order_status="reserved",
                patience_ticks_left=self.patience_ticks, eat_ticks_left=0, base_price=0, tip=0,
            )
            customer.update(fixture)
            for field in ("order_tick", "patience_ticks_left", "eat_ticks_left", "base_price", "tip"):
                _nonneg_int(f"{fixture['id']}.{field}", customer[field])
            state, status = customer["state"], customer["order_status"]
            if state == "eating":
                if (status != "served" or not customer["eat_ticks_left"]
                        or not customer["base_price"] or "tip" not in fixture):
                    raise BadInput(f"{fixture['id']}: khách đang ăn cần đơn served, giá, boa và timer ăn")
            elif (state != "waiting" or status not in ("reserved", "assigned", "unfulfillable")
                  or customer["eat_ticks_left"]):
                raise BadInput(f"{fixture['id']}: trạng thái khách và đơn mâu thuẫn")
            self.ids.reserve(customer["id"])
            customers.append(customer)

        for customer in sorted(customers, key=self._order_key):
            recipe = self.menu[customer["dish_id"]]["recipe"] if customer["order_status"] == "reserved" else {}
            reserved = validate_items(customer.get("reserved", recipe))
            if reserved != recipe or not self._can_reserve(reserved, available):
                raise BadInput(f"{customer['id']}: nguyên liệu giữ khác công thức hoặc quá tồn")
            customer["reserved"] = reserved
            for kind, count in reserved.items():
                available[kind] -= count
        return customers

    def _validate_dish_locations(self):
        dishes = [self.hand] if self.hand is not None else []
        for stove in self.stoves:
            state, dish = stove["state"], stove["dish"]
            cook, ready = stove["cook_ticks_left"], stove["ready_ticks"]
            _nonneg_int(f"{stove['id']}.cook_ticks_left", cook)
            _nonneg_int(f"{stove['id']}.ready_ticks", ready)
            if state == "idle" and dish is None and cook == ready == 0:
                continue
            if dish is None or not (
                (state == "cooking" and cook > 0 and ready == 0) or (state == "ready" and cook == 0)
            ):
                raise BadInput(f"{stove['id']}: trạng thái bếp, món và timer mâu thuẫn")
            dishes.append(dish)
        assigned = {c["id"]: c["dish_id"] for c in self.customers if c["order_status"] == "assigned"}
        for dish in dishes:
            if not isinstance(dish, dict) or set(dish) != {"order_id", "dish_id", "base_price"}:
                raise BadInput("payload món cần order_id, dish_id và base_price")
            order_id = dish["order_id"]
            _nonneg_int("dish.base_price", dish["base_price"])
            if (not isinstance(order_id, str) or order_id not in assigned
                    or dish["dish_id"] != assigned[order_id] or dish["base_price"] == 0):
                raise BadInput("món trong bếp hoặc trên tay không khớp đơn assigned")
            del assigned[order_id]
        if assigned:
            raise BadInput("đơn assigned phải có đúng một món ở bếp hoặc trên tay")

    @staticmethod
    def _can_reserve(recipe, available):
        return all(available.get(kind, 0) >= count for kind, count in recipe.items())

    def _try_arrival(self, events):
        elapsed = self.phase_tick - self.t["first_customer_tick"]
        if not self.random_customers or elapsed < 0 or elapsed % self.customer_interval:
            return
        occupied = {c["table_id"] for c in self.customers}
        table = next((table for table in self.tables if table["id"] not in occupied), None)
        if table is None:
            return
        available = self.stock.copy()
        for customer in self.customers:
            for kind, count in customer["reserved"].items():
                available[kind] -= count
        dishes = [dish_id for dish_id in sorted(self.menu)
                  if self._can_reserve(self.menu[dish_id]["recipe"], available)]
        if not dishes:
            events.append(("no_dish", {}))
            return
        dish_id = self.rng.get("quan_customer_dish").choice(dishes)
        order_id = self.ids.new("C")
        self.customers.append({
            "id": order_id, "table_id": table["id"], "dish_id": dish_id, "order_tick": self.phase_tick,
            "state": "waiting", "order_status": "reserved", "patience_ticks_left": self.patience_ticks,
            "eat_ticks_left": 0, "reserved": self.menu[dish_id]["recipe"].copy(), "base_price": 0, "tip": 0,
        })
        events.append(("customer_arrived", {"order_id": order_id, "table_id": table["id"], "dish_id": dish_id}))

    def snapshot(self) -> dict:
        occupied = {c["table_id"]: c["id"] for c in self.customers}
        return {
            "player": {"pos": self.pos.copy()},
            "stock": {k: self.stock[k] for k in sorted(self.stock) if self.stock[k] > 0},
            "hand": self.hand,
            "stoves": [{k: s.get(k) for k in ("id", "pos", "state", "dish", "cook_ticks_left", "ready_ticks")}
                       for s in self.stoves],
            "tables": [{"id": tb["id"], "pos": tb["pos"], "customer_id": occupied.get(tb["id"])} for tb in self.tables],
            "customers": [dict(c) for c in sort_by_id(self.customers)],
        }

    def step(self, inp):
        events = []
        self.phase_tick += 1
        self.time_left_ticks = max(0, self.time_left_ticks - 1)
        self._advance_timers(events)
        self._move(inp)
        if inp.pressed("interact"):
            self._interact(events)
        closing = self.time_left_ticks == 0
        self._resolve_customers(events, closing)
        if closing:
            self.done = True
            self.reason = "time"
            events.append(("quan_end", {"reason": "time", "money": self.money, "earned": self.earned,
                                        "shift_earned": self.shift_earned, "reputation": self.reputation}))
        else:
            self._try_arrival(events)
        return events

    def _advance_timers(self, events):
        for customer in self.customers:
            timer = "patience_ticks_left" if customer["state"] == "waiting" else "eat_ticks_left"
            customer[timer] = max(0, customer[timer] - 1)
        for stove in self.stoves:
            if stove["state"] == "ready":
                stove["ready_ticks"] += 1
            elif stove["state"] == "cooking":
                stove["cook_ticks_left"] -= 1
                if stove["cook_ticks_left"] == 0:
                    stove["state"] = "ready"
                    events.append(("dish_ready", self._stove_event(stove)))

    def _interact(self, events):
        candidates = []
        for priority, fixtures in enumerate((self.stoves, self.tables)):
            for fixture in fixtures:
                distance = math.dist(self.pos, fixture["pos"])
                if distance <= self.t["interact_radius"]:
                    candidates.append((distance, priority, id_key(fixture["id"]), fixture))
        if candidates:
            _, priority, _, fixture = min(candidates, key=lambda candidate: candidate[:3])
            if priority == 0:
                self._interact_stove(fixture, events)
            else:
                self._serve(fixture, events)

    @staticmethod
    def _stove_event(stove):
        dish = stove["dish"]
        return {"stove_id": stove["id"], "order_id": dish["order_id"], "dish_id": dish["dish_id"]}

    @staticmethod
    def _clear_stove(stove):
        stove.update(state="idle", dish=None, cook_ticks_left=0, ready_ticks=0)

    def _interact_stove(self, stove, events):
        if stove["state"] == "ready" and self.hand is None:
            self.hand = stove["dish"]
            events.append(("dish_picked", self._stove_event(stove)))
            self._clear_stove(stove)
        elif stove["state"] == "idle":
            pending = (c for c in self.customers if c["order_status"] == "reserved")
            customer = min(pending, key=self._order_key, default=None)
            if customer is None:
                return
            dish_id = customer["dish_id"]
            menu_entry = self.menu[dish_id]
            items = []
            for kind, count in sorted(customer["reserved"].items()):
                self.stock[kind] -= count
                items.extend([kind] * count)
            price = menu_entry["price"]
            customer.update(order_status="assigned", reserved={}, base_price=price)
            dish = {"order_id": customer["id"], "dish_id": dish_id, "base_price": price}
            stove.update(state="cooking", dish=dish, cook_ticks_left=self._ticks(menu_entry["cook_s"]))
            events.append(("cook_started", {**self._stove_event(stove), "items": items, "base_price": price}))

    def _serve(self, table, events):
        if self.hand is None:
            return
        customer = next((c for c in self.customers if c["table_id"] == table["id"]), None)
        if customer is None or customer["id"] != self.hand["order_id"]:
            return
        price = self.hand["base_price"]
        patience = customer["patience_ticks_left"]
        tip = 0
        if patience / self.patience_ticks >= self.t["tip_min_patience_ratio"]:
            tip = math.floor(price * Decimal(str(self.t["tip_rate"])))
        customer.update(state="eating", order_status="served", eat_ticks_left=self.eat_ticks,
                        base_price=price, tip=tip)
        events.append(("served", {**self.hand, "table_id": table["id"],
                                  "patience_ticks_left": patience, "tip": tip}))
        self.hand = None

    def _resolve_customers(self, events, closing):
        for customer in sort_by_id(self.customers, key=lambda c: c["table_id"]):
            if customer["state"] == "eating":
                if customer["eat_ticks_left"] == 0:
                    self._pay(customer, events, "finished_eating")
                elif closing:
                    self._pay(customer, events, "closing")
            elif closing or customer["patience_ticks_left"] == 0:
                if not closing:
                    self._adjust_reputation(self.t["left_reputation_delta"])
                events.append(("customer_left", {
                    "order_id": customer["id"], "table_id": customer["table_id"],
                    "reason": "closing" if closing else "patience", "reputation": self.reputation,
                }))
                self._remove_customer(customer)

    def _pay(self, customer, events, reason):
        price, tip = customer["base_price"], customer["tip"]
        amount = price + tip
        self.money += amount
        self.earned += amount
        self.shift_earned += amount
        if tip > 0:
            self._adjust_reputation(self.t["tip_reputation"])
        events.append(("paid", {
            "order_id": customer["id"], "table_id": customer["table_id"],
            "base_price": price, "tip": tip, "amount": amount, "reason": reason,
        }))
        self._remove_customer(customer)

    def _adjust_reputation(self, delta):
        # Điểm dùng floor(uy tín), nên cộng đúng thập phân tại các mốc nguyên.
        reputation = Decimal(str(self.reputation)) + Decimal(str(delta))
        self.reputation = float(max(self.t["reputation_min"], min(self.t["reputation_max"], reputation)))

    def _remove_customer(self, customer):
        order_id = customer["id"]
        for stove in self.stoves:
            if stove["dish"] is not None and stove["dish"]["order_id"] == order_id:
                self._clear_stove(stove)
        if self.hand is not None and self.hand["order_id"] == order_id:
            self.hand = None
        self.customers.remove(customer)

    def _move(self, inp):
        speed = self.t["walk_speed"]
        mx, mz = inp.move
        self.vel = ramp_velocity(self, (mx * speed, mz * speed), int(self.t.get("ramp_max_ticks", 6)))
        b = self.t["bounds"]
        for i, axis in enumerate(("x", "z")):
            self.pos[i] += self.vel[i] / self.tick_hz
            lo, hi = b[axis]
            if self.pos[i] <= lo:
                self.pos[i], self.vel[i] = lo, max(0.0, self.vel[i])
            elif self.pos[i] >= hi:
                self.pos[i], self.vel[i] = hi, min(0.0, self.vel[i])
