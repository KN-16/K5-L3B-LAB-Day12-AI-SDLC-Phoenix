"""Buổi sáng — Lặn & Hái (`gather`). KHUNG: bơi, chặn mép, đồng hồ, cập bến, xuất kho.

Mặt cắt dòng sông nhìn NGANG: vị trí `[x, d]` (x sang phải, `d` độ sâu hướng xuống, d = 0 là mặt nước).
`move = [x, d]`: thành phần thứ hai DƯƠNG = bơi xuống. Hướng mặt là góc từ +x, dương = xuống.

Đã làm sẵn để smoke test chạy được: bơi + tăng/giảm tốc, chặn mép (d không âm), đồng hồ và hết giờ,
cập bến (`interact` trong vùng bến -> `gather_end` reason `docked`), xuất kho, snapshot đầy đủ trường gather.

Luật của nhóm theo DocsPhase.txt (PRD-0 mục F "Gather", payload event theo mục E), đúng thứ tự một bước:
  - đã làm: dive / surface khi đổi phía biên mặt nước giữa đầu và cuối bước (pos sau di chuyển); oxy theo d
    CUỐI bước (mặt nước hồi oxygen_refill_per_tick + reset ngạt, dưới nước -1, kẹp [0, max]), oxygen_empty,
    đếm ngạt kể cả bước vừa chạm 0 -> đủ choke_interval_ticks thì -1 Máu (choke)
  - đã làm: cập bến xét TRƯỚC hái; hái nút ready gần nhất trong interact_radius chỉ ở mặt nước (gather /
    hold_full, đặt regrow_ticks); bắt đúng đàn gần nhất trong catch_radius khi hết hồi và dưới nước
    (fish_caught / hold_full, đặt hồi chiêu); hòa khoảng cách theo id; lấy đủ yield hoặc giữ nguyên, không thử
    ứng viên khác; giỏ theo thứ tự nhặt, sức chứa hold_capacity; ghi kho đúng một lần do runner lo
  TODO(nhóm, lát 1): Máu về 0 -> bỏ giỏ LIFO, faint, gather_end reason `fainted` với kho rỗng, dừng bước
Các tính năng của phase sau chưa nằm trong khung này.
"""

import math
from itertools import repeat

from ..ids import id_key, sort_by_id
from ..inventory import hold_to_items
from .ramp import ramp_velocity

TICK = 60.0
AXES = ("x", "d")


class GatherSim:
    mode = "gather"
    phase = "gather"

    def __init__(self, tuning, scenario, streams, ids):
        t = tuning["gather"]
        self.t = t
        self.rng = streams
        self.ids = ids
        p = scenario.get("player", {})
        self.pos = [float(c) for c in p.get("pos", t["start_pos"])]
        self.vel = [float(c) for c in p.get("vel", [0.0, 0.0])]
        self._tgt = None
        self._ramp_left = 0
        self.heading = float(p.get("heading_deg", t["start_heading_deg"]))
        self.oxygen_max = int(round(t["oxygen_max_s"] * TICK))
        self.oxygen_ticks = p.get("oxygen_ticks", self.oxygen_max)
        self.hp = p.get("hp", t["hp_max"])
        self.zero_oxy_ticks = p.get("zero_oxy_ticks", 0)
        self.invuln_ticks = p.get("invuln_ticks", 0)
        self.catch_cd_ticks = p.get("catch_cd_ticks", 0)
        self.hold = list(scenario.get("hold", []))  # thứ tự nhặt, cuối mảng là mới nhất
        self.time_left_ticks = scenario.get("time_left_ticks", int(round(t["duration_s"] * TICK)))
        # nút và đàn cá: scenario THAY THẾ danh sách mặc định; random_fish=false tắt cá mặc định
        src_nodes = scenario["nodes"] if "nodes" in scenario else t["nodes"]
        self.nodes = [{"id": n["id"], "kind": n["kind"], "pos": [float(c) for c in n["pos"]],
                       "regrow_ticks": n.get("regrow_ticks", 0)} for n in src_nodes]
        if "fish" in scenario:
            src_fish = scenario["fish"]
        elif scenario.get("random_fish", True):
            src_fish = t["fish_initial"]
        else:
            src_fish = []
        # Đàn cá đứng yên ở phase này. Cá bơi / sinh thêm là việc của phase sau.
        self.fish = [{"id": f["id"], "kind": f["kind"], "pos": [float(c) for c in f["pos"]],
                      "heading_deg": f.get("heading_deg", 0)} for f in src_fish]
        for coll in (self.nodes, self.fish):
            for e in coll:
                ids.reserve(e["id"])
        self.money = 0
        self.earned = 0
        self.reputation = tuning["quan"]["reputation_initial"]
        self.done = False
        self.reason = None
        # hằng luật đọc từ contract MỘT lần (không literal, không tra lại mỗi tick)
        self._refill = t["oxygen_refill_per_tick"]
        self._choke_every = t["choke_interval_ticks"]
        self._cap = t["hold_capacity"]
        self._node_yield = t["node_yield"]
        self._fish_yield = t["fish_yield"]
        self._r_interact = t["interact_radius"]
        self._r_catch = t["catch_radius"]
        self._regrow_full = int(round(t["regrow_s"] * TICK))
        self._catch_cd_full = int(round(t["catch_cooldown_s"] * TICK))

    # --- giao diện cho runner -------------------------------------------------
    def inventory_items(self) -> dict:
        return hold_to_items(self.hold)

    def snapshot(self) -> dict:
        return {
            "player": {"pos": self.pos, "vel": self.vel, "heading_deg": self.heading,
                       "oxygen_ticks": self.oxygen_ticks, "oxygen_max_ticks": self.oxygen_max,
                       "hp": self.hp, "hp_max": self.t["hp_max"], "zero_oxy_ticks": self.zero_oxy_ticks,
                       "invuln_ticks": self.invuln_ticks, "catch_cd_ticks": self.catch_cd_ticks,
                       "at_surface": self._at_surface()},
            "hold": self.hold, "hold_count": len(self.hold),
            "hold_capacity": self.t["hold_capacity"],
            "nodes": [{"id": n["id"], "pos": n["pos"], "kind": n["kind"],
                       "ready": n["regrow_ticks"] == 0, "regrow_ticks": n["regrow_ticks"]}
                      for n in sort_by_id(self.nodes)],
            "fish": [{"id": f["id"], "pos": f["pos"], "kind": f["kind"], "heading_deg": f["heading_deg"]}
                     for f in sort_by_id(self.fish)],
        }

    # --- một bước ---------------------------------------------------------------
    def step(self, inp):
        events = []
        # 1. đồng hồ và hàng có sẵn: giảm bộ đếm, nút mọc lại
        self.time_left_ticks = max(0, self.time_left_ticks - 1)
        self.invuln_ticks = max(0, self.invuln_ticks - 1)
        self.catch_cd_ticks = max(0, self.catch_cd_ticks - 1)
        for n in sort_by_id(self.nodes):
            if n["regrow_ticks"] > 0:
                n["regrow_ticks"] -= 1
                if n["regrow_ticks"] == 0:
                    events.append(("node_regrown", {"node_id": n["id"]}))
        # 2. bơi + chặn mép; so phía biên mặt nước đầu/cuối bước -> dive / surface (pos sau di chuyển)
        was_surface = self._at_surface()
        self._move(inp)
        surface = self._at_surface()
        if surface != was_surface:
            # chép giá trị: self.pos đổi tại chỗ ở bước sau, chonoi.live giữ event theo tham chiếu
            events.append(("surface" if surface else "dive", {"pos": list(self.pos)}))
        # oxy theo d CUỐI bước -> oxygen_empty, ngạt (choke)
        self._breathe(surface, events)
        # TODO(nhóm, lát 1): Máu 0 -> bỏ giỏ LIFO, faint + gather_end("fainted") với kho rỗng, return.
        # 3. interact: bến trước, rồi hái
        if inp.pressed("interact"):
            if self._in_dock():
                self._finish("docked", events)
                return events
            if surface:  # ngoài bến chỉ hái khi ở mặt nước
                self._gather_node(events)
        # 4. bắt cá: chỉ khi hết hồi và đang dưới nước
        if inp.pressed("catch") and self.catch_cd_ticks == 0 and not surface:
            self._catch_fish(events)
        # 5. hết giờ
        if self.time_left_ticks <= 0:
            self._finish("time", events)
        return events

    # --- tiện ích ---------------------------------------------------------------
    def _at_surface(self) -> bool:
        return self.pos[1] <= self.t["surface_depth"]

    def _in_dock(self) -> bool:
        return math.dist(self.pos, self.t["dock_pos"]) <= self.t["dock_radius"]

    def _finish(self, reason, events):
        self.done = True
        self.reason = reason
        events.append(("gather_end", {"reason": reason, "inventory": {"items": self.inventory_items()}}))

    def _breathe(self, surface, events):
        """Oxy theo d CUỐI bước (PRD-0 mục F): mặt nước hồi và reset ngạt; dưới nước trừ 1, kẹp 0.

        Mỗi bước dưới nước kết thúc với oxy 0, kể cả bước vừa chạm 0, tăng zero_oxy_ticks; đủ
        choke_interval_ticks thì đặt lại về 0, trừ 1 Máu, phát choke. Chạm 0 ở t -> ngạt lần đầu ở t+59.
        """
        if surface:
            self.oxygen_ticks = min(self.oxygen_max, self.oxygen_ticks + self._refill)
            self.zero_oxy_ticks = 0
            return
        if self.oxygen_ticks > 0:
            self.oxygen_ticks -= 1
            if self.oxygen_ticks > 0:
                self.zero_oxy_ticks = 0  # còn oxy thì không có nhịp ngạt (v1.1: reset khi oxy > 0)
                return
            events.append(("oxygen_empty", {"oxygen_ticks": 0}))
        self.zero_oxy_ticks += 1
        if self.zero_oxy_ticks >= self._choke_every:
            self.zero_oxy_ticks = 0
            self.hp -= 1
            events.append(("choke", {"hp": self.hp}))

    def _nearest(self, coll, radius):
        """Thực thể gần nhất trong `radius` (tính cả đúng mép), hòa khoảng cách theo id; None nếu không có.

        Một lượt qua `coll`, chọn bằng min (lõi C). Thực thể gần nhất ngoài tầm thì mọi thực thể đều ngoài tầm.
        id duy nhất trong mỗi danh sách nên tuple không bao giờ phải so tới dict.
        """
        best = min(((math.dist(self.pos, e["pos"]), id_key(e["id"]), e) for e in coll), default=None)
        return best[2] if best is not None and best[0] <= radius else None

    def _room(self) -> int:
        return self._cap - len(self.hold)

    def _put(self, kind, n):
        """Thêm n nguyên liệu `kind` vào cuối giỏ (thứ tự nhặt, mới nhất cuối)."""
        self.hold.extend(repeat(kind, n))

    def _gather_node(self, events):
        """Hái nút ready gần nhất trong interact_radius: đủ chỗ thì lấy và đặt mọc lại, thiếu chỗ giữ nguyên nút."""
        node = self._nearest((n for n in self.nodes if n["regrow_ticks"] == 0), self._r_interact)
        if node is None:
            return
        need, free = self._node_yield, self._room()
        if free < need:
            events.append(("hold_full", {"action": "gather", "node_id": node["id"], "required": need, "free": free}))
            return
        self._put(node["kind"], need)
        node["regrow_ticks"] = self._regrow_full
        events.append(("gather", {"node_id": node["id"], "kind": node["kind"], "amount": need}))

    def _catch_fish(self, events):
        """Bắt đúng đàn gần nhất trong catch_radius: lấy cả yield, xoá đàn, đặt hồi chiêu.

        Thiếu chỗ: hold_full, giữ đàn và cooldown, không thử đàn khác. Không đàn trong tầm: không event, không hồi.
        """
        fish = self._nearest(self.fish, self._r_catch)
        if fish is None:
            return
        need, free = self._fish_yield[fish["kind"]], self._room()
        if free < need:
            events.append(("hold_full", {"action": "catch", "fish_id": fish["id"], "required": need, "free": free}))
            return
        self._put(fish["kind"], need)
        self.fish.remove(fish)
        self.catch_cd_ticks = self._catch_cd_full
        events.append(("fish_caught", {"fish_id": fish["id"], "kind": fish["kind"], "yield": need}))

    def _move(self, inp):
        speed = self.t["swim_speed"]
        mx, md = inp.move
        self.vel = ramp_velocity(self, (mx * speed, md * speed), int(self.t["ramp_max_ticks"]))
        if (mx, md) != (0.0, 0.0):
            self.heading = math.degrees(math.atan2(md, mx)) % 360
        b = self.t["bounds"]
        for i, axis in enumerate(AXES):
            self.pos[i] += self.vel[i] / TICK
            lo, hi = b[axis]
            if self.pos[i] <= lo:
                self.pos[i] = lo
                self.vel[i] = max(0.0, self.vel[i])
            elif self.pos[i] >= hi:
                self.pos[i] = hi
                self.vel[i] = min(0.0, self.vel[i])
