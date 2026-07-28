import datetime
import io

import discord

import farm_config
import farm_logic
import farm_render
import store


def _fmt_td(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m}p"
    if m:
        return f"{m}p{s}s"
    return f"{s}s"


def _slot_water_remaining_sec(slot: dict, water_speed_level: int) -> int:
    if not slot.get("last_water_at"):
        return 0
    last = store.parse_iso(slot["last_water_at"])
    cd_min = farm_logic.water_cooldown_min(water_speed_level)
    elapsed = (datetime.datetime.utcnow() - last).total_seconds()
    remaining = cd_min * 60 - elapsed
    return max(0, int(remaining))


def _slot_sprinkler_active(slot: dict) -> tuple[bool, str | None]:
    if not slot.get("active_sprinkler_tier") or not slot.get("active_sprinkler_until"):
        return False, None
    until = store.parse_iso(slot["active_sprinkler_until"])
    if datetime.datetime.utcnow() < until:
        return True, slot["active_sprinkler_tier"]
    return False, None


def _apply_passive_growth_to_slot(slot: dict, now: datetime.datetime) -> dict:
    """Cộng progress tự tăng thụ động từ last_passive_tick_at đến now, cập nhật mốc tick mới."""
    if not slot.get("planted"):
        slot["last_passive_tick_at"] = now.isoformat()
        return slot

    crop_type = slot["seed_type"]
    last_tick = slot.get("last_passive_tick_at")
    last_tick_dt = store.parse_iso(last_tick) if last_tick else now

    needed = farm_config.CROPS[crop_type]["grow_progress_needed"]
    gain = farm_logic.compute_passive_progress_gain(crop_type, last_tick_dt, now)
    slot["progress"] = min(needed, slot.get("progress", 0.0) + gain)
    slot["last_passive_tick_at"] = now.isoformat()
    return slot


def _farmer_status_text(farmer: dict, now: datetime.datetime) -> str:
    if not farmer.get("hired"):
        return "❌ Chưa thuê"
    if farmer.get("permanent"):
        return "✅ Vĩnh viễn"
    hired_until = farmer.get("hired_until")
    if not hired_until:
        return "❌ Chưa thuê"
    until = store.parse_iso(hired_until)
    if now >= until:
        return "❌ Đã hết hạn"
    remaining = int((until - now).total_seconds())
    return f"✅ Còn {_fmt_td(remaining)}"


# ==================== PASSIVE GROWTH + FARMER AUTO-WATER (lazy-calc) ====================
def _process_seller(guild_id: int, user_id: int, data: dict, now: datetime.datetime) -> tuple[list[str], bool]:
    """
    Người bán nông sản: tự động bán TOÀN BỘ kho nông sản hiện có mỗi chu kỳ (catch-up theo elapsed time).
    Chỉ xử lý khoảng thời gian user KHÔNG mở /farm (lazy-calc) — nếu user tự bán tay trước khi
    tick này chạy, kho đã trống thì seller không có gì để bán, không phạt gì thêm.
    Trả về (logs, changed) — changed=True nếu có ghi Firebase (cần đọc lại data ở tầng gọi).
    """
    seller = data.get("seller", {})
    if not farm_logic.is_npc_active(seller, now):
        return [], False

    last_processed = (
        store.parse_iso(seller["last_processed_at"])
        if seller.get("last_processed_at") else now
    )
    stats = farm_logic.seller_stats(seller.get("level", 0))
    cycle_sec = stats["cycle_min"] * 60

    hired_until_dt = None
    if not seller.get("permanent") and seller.get("hired_until"):
        hired_until_dt = store.parse_iso(seller["hired_until"])

    elapsed_sec = (now - last_processed).total_seconds()
    if hired_until_dt is not None and hired_until_dt < now:
        elapsed_sec = (hired_until_dt - last_processed).total_seconds()

    if cycle_sec <= 0 or elapsed_sec < cycle_sec:
        return [], False

    ticks = min(int(elapsed_sec // cycle_sec), 50)  # trần an toàn: tối đa 50 lần bán/lần catch-up
    if ticks <= 0:
        return [], False

    total_sold_mango = 0
    total_sold_qty = 0

    def _sell_all(d):
        nonlocal total_sold_mango, total_sold_qty
        inventory = dict(d.get("inventory", {}))
        for key, qty in list(inventory.items()):
            if qty <= 0:
                continue
            produce, mutations = store.parse_inventory_key(key)
            value = farm_logic.compute_produce_value(produce, mutations)
            value = int(value * stats["price_multiplier"])
            total_sold_mango += value * qty
            total_sold_qty += qty
        d["inventory"] = {}
        d["seller"]["last_processed_at"] = now.isoformat()
        return d

    store.transaction_farm_data(user_id, _sell_all)
    if total_sold_qty > 0:
        store.transaction_mango(user_id, total_sold_mango)
        return [f"💰 Người bán đã tự bán {total_sold_qty} trái trong kho, thu về {total_sold_mango} 🥭."], True

    # không có gì để bán nhưng vẫn cần cập nhật mốc tick để tránh dồn ticks vô hạn
    def _touch(d):
        d.setdefault("seller", {})
        d["seller"]["last_processed_at"] = now.isoformat()
        return d
    store.transaction_farm_data(user_id, _touch)
    return [], True


def _process_collector(guild_id: int, user_id: int, data: dict, now: datetime.datetime) -> tuple[list[str], bool]:
    """
    Người thu thập hạt giống: tự động mua MIỄN PHÍ 1-N hạt giống mỗi chu kỳ (catch-up),
    chỉ mua loại hạt mà level Collector cho phép VÀ đã được unlock.
    Trả về (logs, changed) — changed=True nếu có ghi Firebase.
    """
    collector = data.get("collector", {})
    if not farm_logic.is_npc_active(collector, now):
        return [], False

    last_processed = (
        store.parse_iso(collector["last_processed_at"])
        if collector.get("last_processed_at") else now
    )
    stats = farm_logic.collector_stats(collector.get("level", 0))
    cycle_sec = stats["cycle_min"] * 60

    hired_until_dt = None
    if not collector.get("permanent") and collector.get("hired_until"):
        hired_until_dt = store.parse_iso(collector["hired_until"])

    elapsed_sec = (now - last_processed).total_seconds()
    if hired_until_dt is not None and hired_until_dt < now:
        elapsed_sec = (hired_until_dt - last_processed).total_seconds()

    if cycle_sec <= 0 or elapsed_sec < cycle_sec:
        return [], False

    ticks = min(int(elapsed_sec // cycle_sec), 50)
    if ticks <= 0:
        return [], False

    allowed_crops = farm_logic.collector_allowed_crops(collector.get("level", 0), data.get("unlocked_crops", {}))
    if not allowed_crops:
        def _touch(d):
            d.setdefault("collector", {})
            d["collector"]["last_processed_at"] = now.isoformat()
            return d
        store.transaction_farm_data(user_id, _touch)
        return [], True

    import random as _random
    lo, hi = stats["seeds_range"]
    gained_summary: dict[str, int] = {}

    def _collect(d):
        d.setdefault("seed_inventory", {})
        for _ in range(ticks):
            crop_id = _random.choice(allowed_crops)
            qty = _random.randint(lo, hi)
            d["seed_inventory"][crop_id] = d["seed_inventory"].get(crop_id, 0) + qty
            gained_summary[crop_id] = gained_summary.get(crop_id, 0) + qty
        d["collector"]["last_processed_at"] = now.isoformat()
        return d

    store.transaction_farm_data(user_id, _collect)

    if gained_summary:
        parts = [f"{qty} {farm_config.CROPS[cid]['name']}" for cid, qty in gained_summary.items()]
        return [f"🧺 Người thu thập đã mua miễn phí: {', '.join(parts)} hạt giống."], True
    return [], True


def _process_offline_growth_and_farmer(guild_id: int, user_id: int) -> tuple[list[str], dict]:
    data = store.get_farm_data(user_id)
    now = datetime.datetime.utcnow()
    logs: list[str] = []

    unlocked_plots = data.get("unlocked_plots", {})
    plots = dict(data.get("plots", {}))
    farmer = data.get("farmer", {})
    farmer_active = farm_logic.is_farmer_active(farmer, now)
    farmer_level = farmer.get("level", 0)
    water_speed_level = data.get("upgrades", {}).get("water_speed_level", 0)
    watering_can = data.get("watering_can", "basic")

    changed = False
    farmer_watered_count = 0

    for pid in farm_config.PLOT_ORDER:
        pid_str = str(pid)
        if not unlocked_plots.get(pid_str):
            continue
        plot = plots.get(pid_str) or {"slots": []}
        slots = plot.get("slots", [])

        can_farmer_work_here = farmer_active and farm_logic.farmer_can_work_plot(
            pid, farmer_level, unlocked_plots.get(pid_str, False)
        )

        for slot in slots:
            before_progress = slot.get("progress", 0.0)
            _apply_passive_growth_to_slot(slot, now)
            if slot.get("progress", 0.0) != before_progress:
                changed = True

            if not slot.get("planted"):
                continue

            needed = farm_config.CROPS[slot["seed_type"]]["grow_progress_needed"]
            if can_farmer_work_here and farmer.get("auto_water") and slot["progress"] < needed:
                remaining = _slot_water_remaining_sec(slot, water_speed_level)
                if remaining <= 0:
                    sprinkler_active, sprinkler_tier = _slot_sprinkler_active(slot)
                    gain = farm_logic.roll_water_progress(watering_can, sprinkler_active, sprinkler_tier)
                    slot["progress"] = min(needed, slot["progress"] + gain)
                    slot["last_water_at"] = now.isoformat()
                    changed = True
                    farmer_watered_count += 1

        plot["slots"] = slots
        plots[pid_str] = plot

    if farmer_watered_count > 0:
        logs.append(f"🚜💧 Nông dân đã tự tưới {farmer_watered_count} cây trong lúc bạn vắng mặt.")

    if changed:
        def _apply(d):
            d["plots"] = plots
            return d
        store.transaction_farm_data(user_id, _apply)
        # Cập nhật lại data trong bộ nhớ khớp với những gì vừa ghi, tránh đọc lại Firebase.
        data["plots"] = plots

    # Seller/Collector dùng lại `data` hiện có trong bộ nhớ để CHECK điều kiện (không tốn round-trip).
    # Nếu chúng thực sự có ghi (bán hàng / mua hạt), chỉ khi đó mới cần đọc lại 1 lần để đồng bộ.
    seller_logs, seller_changed = _process_seller(guild_id, user_id, data, now)
    collector_logs, collector_changed = _process_collector(guild_id, user_id, data, now)
    logs.extend(seller_logs)
    logs.extend(collector_logs)

    if seller_changed or collector_changed:
        data = store.get_farm_data(user_id)  # chỉ đọc lại khi thực sự có thay đổi cần đồng bộ

    return logs, data


# ==================== MAIN FARM EMBED ====================
def build_farm_embed_and_view(guild_id: int, user_id: int, extra_logs: list[str] | None = None):
    offline_logs, data = _process_offline_growth_and_farmer(guild_id, user_id)

    mango = store.get_mango(user_id)
    weather = store.get_current_weather(guild_id)
    now = datetime.datetime.utcnow()

    unlocked_plots = data.get("unlocked_plots", {})
    plots = data.get("plots", {})
    farmer = data.get("farmer", {})
    has_wrench = data.get("gear", {}).get("wrench", False)
    has_net = data.get("gear", {}).get("net", False)

    embed = discord.Embed(title="🌾 Nông trại", color=discord.Color.green())
    embed.add_field(name="🥭 Mango", value=f"{mango}", inline=True)
    embed.add_field(name="🌤️ Thời tiết", value=farm_config.WEATHER_TYPES[weather]["name"], inline=True)
    embed.add_field(name="🚜 Nông dân", value=_farmer_status_text(farmer, now), inline=True)

    plot_lines = []
    render_data = []
    for pid in farm_config.PLOT_ORDER:
        pid_str = str(pid)
        unlocked = unlocked_plots.get(pid_str, False)
        plot = plots.get(pid_str, {"slots": []})
        slots = plot.get("slots", [])

        if not unlocked:
            cost_info = farm_logic.plot_unlock_cost(pid)
            currency_label = "🥭" if cost_info["currency"] == "mango" else "🥭+"
            plot_lines.append(f"🔒 **Ô {pid}** — Khoá ({cost_info['cost']}{currency_label} để mở)")
            render_data.append({"plot_id": pid, "unlocked": False, "slots": []})
            continue

        planted_count = sum(1 for s in slots if s.get("planted"))
        ready_count = 0
        for s in slots:
            if s.get("planted"):
                needed = farm_config.CROPS[s["seed_type"]]["grow_progress_needed"]
                if s["progress"] >= needed:
                    ready_count += 1

        status = f"{planted_count}/{farm_config.SLOTS_PER_PLOT} đang trồng"
        if ready_count > 0:
            status += f" — ✅ {ready_count} sẵn sàng thu hoạch"
        plot_lines.append(f"🌱 **Ô {pid}** — {status}")

        slot_render = []
        for s in slots:
            if not s.get("planted"):
                slot_render.append({"planted": False})
                continue
            sprinkler_active, _ = _slot_sprinkler_active(s)
            needed = farm_config.CROPS[s["seed_type"]]["grow_progress_needed"]
            ready = s["progress"] >= needed
            stage_preview = None
            if ready:
                stage_preview = farm_config.PRODUCE_STAGES[s["seed_type"]]["stages"][1]
            slot_render.append({
                "planted": True,
                "crop_type": s["seed_type"],
                "progress": s["progress"],
                "needed": needed,
                "stage_preview": stage_preview,
                "sprinkler_active": sprinkler_active,
            })
        render_data.append({"plot_id": pid, "unlocked": True, "slots": slot_render})

    embed.add_field(name="🗺️ Các ô trồng", value="\n".join(plot_lines), inline=False)

    seed_lines = [
        f"{farm_config.CROPS[cid]['name']}: {data.get('seed_inventory', {}).get(cid, 0)} hạt"
        for cid in farm_config.CROP_ORDER if data.get("unlocked_crops", {}).get(cid)
    ]
    if seed_lines:
        embed.add_field(name="🌱 Hạt giống trong kho", value=" | ".join(seed_lines), inline=False)

    if offline_logs:
        embed.add_field(name="📋 Trong lúc bạn vắng mặt", value="\n".join(offline_logs), inline=False)
    if extra_logs:
        embed.add_field(name="Vừa xong", value="\n".join(extra_logs), inline=False)

    image_bytes = farm_render.render_multi_plot_image(render_data)
    file = discord.File(fp=io.BytesIO(image_bytes), filename="farm.png")
    embed.set_image(url="attachment://farm.png")

    view = FarmView(guild_id, user_id, show_shop_button=has_wrench, show_net_button=has_net)
    return embed, view, file


class FarmView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int, show_shop_button: bool = False, show_net_button: bool = False):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.user_id = user_id

        if show_net_button:
            self.add_item(HarvestAllButton(guild_id, user_id))
        if show_shop_button:
            self.add_item(OpenShopButton(guild_id, user_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải nông trại của bạn.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🗂️ Quản lý ô trồng", style=discord.ButtonStyle.success)
    async def manage_plots(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = store.get_farm_data(self.user_id)
        unlocked_plots = data.get("unlocked_plots", {})
        available = [pid for pid in farm_config.PLOT_ORDER if unlocked_plots.get(str(pid))]

        view = discord.ui.View(timeout=90)
        view.add_item(PlotChooseDropdown(self.guild_id, self.user_id, available))
        await interaction.response.send_message("Chọn ô trồng để quản lý:", view=view, ephemeral=True)

    @discord.ui.button(label="⚙️ Nâng cấp", style=discord.ButtonStyle.secondary)
    async def upgrades(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, view = build_upgrade_menu(self.guild_id, self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="👥 Thuê nhân công", style=discord.ButtonStyle.secondary)
    async def hire_worker_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View(timeout=90)
        view.add_item(WorkerChooseDropdown(self.guild_id, self.user_id))
        await interaction.response.send_message("Chọn loại nhân công để thuê/quản lý:", view=view, ephemeral=True)

    @discord.ui.button(label="💦 Kích hoạt sprinkler", style=discord.ButtonStyle.secondary)
    async def activate_sprinkler(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = store.get_farm_data(self.user_id)
        inventory = data.get("sprinkler_inventory", {})
        owned = [sid for sid in farm_config.SPRINKLER_ORDER if inventory.get(sid, 0) > 0]

        if not owned:
            await interaction.response.send_message("Bạn chưa sở hữu sprinkler nào. Mua ở `/shop`.", ephemeral=True)
            return

        unlocked_plots = data.get("unlocked_plots", {})
        available = [pid for pid in farm_config.PLOT_ORDER if unlocked_plots.get(str(pid))]

        view = discord.ui.View(timeout=90)
        view.add_item(SprinklerPlotChooseDropdown(self.guild_id, self.user_id, available, owned))
        await interaction.response.send_message("Chọn ô để kích hoạt sprinkler:", view=view, ephemeral=True)


class WorkerChooseDropdown(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int):
        self.guild_id = guild_id
        self.user_id = user_id
        options = [
            discord.SelectOption(label="🚜 Nông dân — tự tưới cây", value="farmer"),
            discord.SelectOption(label="💰 Người bán — tự bán kho lúc offline", value="seller"),
            discord.SelectOption(label="🧺 Người thu thập — tự mua hạt giống miễn phí", value="collector"),
        ]
        super().__init__(placeholder="Chọn loại nhân công...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        worker_kind = self.values[0]
        embed, view = build_worker_menu(self.guild_id, self.user_id, worker_kind)
        await interaction.response.edit_message(content=None, embed=embed, view=view)


_WORKER_CONFIG = {
    "farmer": {
        "field": "farmer",
        "name": "Nông dân",
        "emoji": "🚜",
        "hire_cost": lambda: farm_config.FARMER_HIRE_COST_MANGO,
        "hire_duration_min": lambda: farm_config.FARMER_HIRE_DURATION_MIN,
        "permanent_cost": lambda: farm_config.FARMER_PERMANENT_COST_MANGO,
        "upgrade_kind": "farmer",
        "max_level": lambda: farm_config.FARMER_UPGRADE["max_level"],
        "hire_desc": "Tự động tưới cây ở các ô mà cấp độ nông dân cho phép.",
    },
    "seller": {
        "field": "seller",
        "name": "Người bán nông sản",
        "emoji": "💰",
        "hire_cost": lambda: farm_config.SELLER_HIRE_COST_MANGO,
        "hire_duration_min": lambda: farm_config.SELLER_HIRE_DURATION_MIN,
        "permanent_cost": lambda: farm_config.SELLER_HIRE_COST_MANGO * 40,
        "upgrade_kind": "seller",
        "max_level": lambda: farm_config.SELLER_UPGRADE["max_level"],
        "hire_desc": "Tự động bán TOÀN BỘ kho nông sản mỗi chu kỳ — CHỈ khi bạn không mở /farm.",
    },
    "collector": {
        "field": "collector",
        "name": "Người thu thập hạt giống",
        "emoji": "🧺",
        "hire_cost": lambda: farm_config.COLLECTOR_HIRE_COST_MANGO,
        "hire_duration_min": lambda: farm_config.COLLECTOR_HIRE_DURATION_MIN,
        "permanent_cost": lambda: farm_config.COLLECTOR_HIRE_COST_MANGO * 40,
        "upgrade_kind": "collector",
        "max_level": lambda: farm_config.COLLECTOR_UPGRADE["max_level"],
        "hire_desc": "Tự động mua MIỄN PHÍ hạt giống theo loại cây đã unlock và level cho phép.",
    },
}


def build_worker_menu(guild_id: int, user_id: int, worker_kind: str):
    cfg = _WORKER_CONFIG[worker_kind]
    data = store.get_farm_data(user_id)
    worker = data.get(cfg["field"], {})
    now = datetime.datetime.utcnow()
    is_active = farm_logic.is_npc_active(worker, now)

    embed = discord.Embed(title=f"{cfg['emoji']} {cfg['name']}", color=discord.Color.dark_green())
    embed.add_field(name="Trạng thái", value=_farmer_status_text(worker, now), inline=True)
    embed.add_field(name="Cấp độ", value=f"Lv.{worker.get('level', 0)}", inline=True)

    view = discord.ui.View(timeout=90)

    if not is_active:
        cost = cfg["hire_cost"]()
        duration_min = cfg["hire_duration_min"]()
        embed.description = f"{cfg['hire_desc']}\n\nGiá thuê: **{cost} mango** — hiệu lực **{duration_min} phút**."
        view.add_item(_HireWorkerBtn(guild_id, user_id, worker_kind, cost, duration_min))
        return embed, view

    embed.description = cfg["hire_desc"]

    if worker_kind == "farmer":
        unlocked_plots = data.get("unlocked_plots", {})
        level = worker.get("level", 0)
        working_plots = [
            pid for pid in farm_config.PLOT_ORDER
            if farm_logic.farmer_can_work_plot(pid, level, unlocked_plots.get(str(pid), False))
        ]
        embed.add_field(
            name="Đang làm việc tại",
            value=", ".join(f"Ô {p}" for p in working_plots) if working_plots else "Chưa đủ điều kiện ở ô nào",
            inline=False,
        )
        embed.add_field(name="Tự động tưới", value="✅ Bật" if worker.get("auto_water") else "❌ Tắt", inline=True)
        view.add_item(_FarmerToggleAutoWaterBtn(guild_id, user_id, worker.get("auto_water", False)))
    elif worker_kind == "seller":
        stats = farm_logic.seller_stats(worker.get("level", 0))
        embed.add_field(name="Chu kỳ bán", value=f"{stats['cycle_min']:.1f} phút/lần", inline=True)
        embed.add_field(name="Bonus giá bán", value=f"+{(stats['price_multiplier']-1)*100:.0f}%", inline=True)
    elif worker_kind == "collector":
        stats = farm_logic.collector_stats(worker.get("level", 0))
        allowed = farm_logic.collector_allowed_crops(worker.get("level", 0), data.get("unlocked_crops", {}))
        allowed_names = ", ".join(farm_config.CROPS[c]["name"] for c in allowed) if allowed else "Chưa có loại nào"
        embed.add_field(name="Chu kỳ mua", value=f"{stats['cycle_min']:.1f} phút/lần", inline=True)
        embed.add_field(name="Số hạt/lần", value=f"{stats['seeds_range'][0]}-{stats['seeds_range'][1]}", inline=True)
        embed.add_field(name="Loại hạt được mua", value=allowed_names, inline=False)

    level = worker.get("level", 0)
    max_level = cfg["max_level"]()
    if level < max_level:
        cost = farm_logic.upgrade_cost(cfg["upgrade_kind"], level)
        embed.add_field(name="Nâng cấp tiếp theo", value=f"{cost} mango", inline=False)
        view.add_item(_WorkerUpgradeBtn(guild_id, user_id, worker_kind, cost))

    if not worker.get("permanent"):
        perm_cost = cfg["permanent_cost"]()
        embed.add_field(name="⭐ Nâng cấp vĩnh viễn", value=f"Không cần thuê lại — {perm_cost:,} mango", inline=False)
        view.add_item(_WorkerPermanentBtn(guild_id, user_id, worker_kind, perm_cost))

    return embed, view


class _HireWorkerBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, worker_kind, cost, duration_min):
        cfg = _WORKER_CONFIG[worker_kind]
        super().__init__(label=f"Thuê {cfg['name']} ({cost} mango)", style=discord.ButtonStyle.success)
        self.guild_id = guild_id
        self.user_id = user_id
        self.worker_kind = worker_kind
        self.cost = cost
        self.duration_min = duration_min

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        cfg = _WORKER_CONFIG[self.worker_kind]
        now = datetime.datetime.utcnow()
        hired_until = (now + datetime.timedelta(minutes=self.duration_min)).isoformat()

        def _hire(d):
            d.setdefault(cfg["field"], {})
            d[cfg["field"]]["hired"] = True
            d[cfg["field"]]["hired_until"] = hired_until
            d[cfg["field"]]["last_processed_at"] = now.isoformat()
            return d

        ok, msg = store.spend_mango_and_apply(
            self.user_id, self.cost, _hire,
            label=f"Thuê {cfg['name']}",
        )
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed, view = build_worker_menu(self.guild_id, self.user_id, self.worker_kind)
        await interaction.response.edit_message(
            content=f"✅ Đã thuê **{cfg['name']}** ({self.duration_min} phút)!",
            embed=embed, view=view,
        )


class _WorkerUpgradeBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, worker_kind, cost):
        cfg = _WORKER_CONFIG[worker_kind]
        super().__init__(label=f"Nâng cấp ({cost} mango)", style=discord.ButtonStyle.primary)
        self.guild_id = guild_id
        self.user_id = user_id
        self.worker_kind = worker_kind
        self.cost = cost

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        cfg = _WORKER_CONFIG[self.worker_kind]

        def _upgrade(d):
            d.setdefault(cfg["field"], {})
            d[cfg["field"]]["level"] = d[cfg["field"]].get("level", 0) + 1
            return d

        ok, msg = store.spend_mango_and_apply(
            self.user_id, self.cost, _upgrade,
            label=f"Nâng cấp {cfg['name']}",
        )
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed, view = build_worker_menu(self.guild_id, self.user_id, self.worker_kind)
        await interaction.response.edit_message(embed=embed, view=view)


class _WorkerPermanentBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, worker_kind, cost):
        super().__init__(label=f"⭐ Vĩnh viễn ({cost:,} mango)", style=discord.ButtonStyle.success)
        self.guild_id = guild_id
        self.user_id = user_id
        self.worker_kind = worker_kind
        self.cost = cost

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        cfg = _WORKER_CONFIG[self.worker_kind]

        def _make_permanent(d):
            d.setdefault(cfg["field"], {})
            d[cfg["field"]]["permanent"] = True
            d[cfg["field"]]["hired"] = True
            d[cfg["field"]]["hired_until"] = None
            return d

        ok, msg = store.spend_mango_and_apply(
            self.user_id, self.cost, _make_permanent,
            label=f"Vĩnh viễn {cfg['name']}",
        )
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed, view = build_worker_menu(self.guild_id, self.user_id, self.worker_kind)
        await interaction.response.edit_message(embed=embed, view=view)


class OpenShopButton(discord.ui.Button):
    """Xuất hiện khi có gear Cờ lê — mở /shop ngay trong /farm không cần gõ lệnh riêng."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(label="🔧 Shop", style=discord.ButtonStyle.primary)
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        import farm_shop
        embed, view = farm_shop.build_farm_shop_embed_and_view(self.guild_id, self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class HarvestAllButton(discord.ui.Button):
    """Xuất hiện khi có gear Vợt — thu hoạch toàn bộ trái sẵn sàng ở mọi ô/mọi cây."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(label="🥅 Thu hoạch tất cả", style=discord.ButtonStyle.success)
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        guild_id, user_id = self.guild_id, self.user_id
        data = store.get_farm_data(user_id)
        weather = store.get_current_weather(guild_id)
        yield_level = data.get("upgrades", {}).get("yield_level", 0)
        has_lightning_rod = data.get("gear", {}).get("lightning_rod", False)

        unlocked_plots = data.get("unlocked_plots", {})
        plots = dict(data.get("plots", {}))
        harvested_summary: dict[str, int] = {}
        total_harvested = 0

        for pid in farm_config.PLOT_ORDER:
            pid_str = str(pid)
            if not unlocked_plots.get(pid_str):
                continue
            plot = plots.get(pid_str, {"slots": []})
            slots = plot.get("slots", [])

            for slot in slots:
                if not slot.get("planted"):
                    continue
                crop_type = slot["seed_type"]
                needed = farm_config.CROPS[crop_type]["grow_progress_needed"]
                if slot["progress"] < needed:
                    continue

                stage = farm_logic.roll_produce_stage(crop_type)
                sprinkler_active, sprinkler_tier = _slot_sprinkler_active(slot)
                mutations = farm_logic.roll_mutations(weather, sprinkler_active, sprinkler_tier)
                if has_lightning_rod and weather == "storm" and "electrified" not in mutations:
                    bonus = farm_config.GEAR["lightning_rod"]["electrified_bonus_chance"]
                    import random as _random
                    if _random.random() < bonus:
                        mutations.append("electrified")
                qty = farm_logic.roll_harvest_quantity(crop_type, yield_level)

                key = store.inventory_key(stage, mutations)
                harvested_summary[key] = harvested_summary.get(key, 0) + qty
                total_harvested += qty

                slot["planted"] = False
                slot["seed_type"] = None
                slot["progress"] = 0.0
                slot["last_water_at"] = None
                slot["last_passive_tick_at"] = None

            plot["slots"] = slots
            plots[pid_str] = plot

        if total_harvested == 0:
            await interaction.response.send_message("Chưa có trái nào sẵn sàng thu hoạch.", ephemeral=True)
            return

        def _apply(d):
            d["plots"] = plots
            d.setdefault("inventory", {})
            for key, qty in harvested_summary.items():
                d["inventory"][key] = d["inventory"].get(key, 0) + qty
            return d

        store.transaction_farm_data(user_id, _apply)

        summary_lines = [f"{qty}x {key.split('|')[0]}" for key, qty in harvested_summary.items()]
        embed, view, file = build_farm_embed_and_view(
            guild_id, user_id,
            extra_logs=[f"🥅 Đã thu hoạch tất cả: {', '.join(summary_lines)} (tổng {total_harvested} trái)."],
        )
        await interaction.response.edit_message(embed=embed, view=view, attachments=[file])


# ==================== QUẢN LÝ Ô (dropdown 2 tầng) ====================
class PlotChooseDropdown(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int, plot_ids: list[int]):
        self.guild_id = guild_id
        self.user_id = user_id
        options = [discord.SelectOption(label=f"Ô {pid}", value=str(pid)) for pid in plot_ids]
        super().__init__(placeholder="Chọn ô...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        plot_id = int(self.values[0])
        embed, view = build_plot_detail(self.guild_id, self.user_id, plot_id)
        await interaction.response.edit_message(content=None, embed=embed, view=view)


def build_plot_detail(guild_id: int, user_id: int, plot_id: int):
    data = store.get_farm_data(user_id)
    plot = data.get("plots", {}).get(str(plot_id), {"slots": []})
    slots = plot.get("slots", [])
    water_speed_level = data.get("upgrades", {}).get("water_speed_level", 0)

    embed = discord.Embed(title=f"🗂️ Ô {plot_id} — Chi tiết", color=discord.Color.dark_green())

    for i, slot in enumerate(slots):
        if not slot.get("planted"):
            embed.add_field(name=f"Slot {i + 1}", value="🟫 Đất trống", inline=True)
            continue

        crop_type = slot["seed_type"]
        needed = farm_config.CROPS[crop_type]["grow_progress_needed"]
        progress = slot["progress"]
        ready = progress >= needed
        bar_len = 10
        filled = int(bar_len * progress / needed) if needed else 0
        bar = "🟩" * filled + "⬛" * (bar_len - filled)

        remaining = _slot_water_remaining_sec(slot, water_speed_level)
        water_text = f"\n⏱️ Tưới lại sau {_fmt_td(remaining)}" if remaining > 0 and not ready else ""

        embed.add_field(
            name=f"Slot {i + 1}: {farm_config.CROPS[crop_type]['name']}",
            value=f"{bar}\n{progress:.1f}/{needed}{' — ✅ SẴN SÀNG' if ready else ''}{water_text}",
            inline=True,
        )

    view = discord.ui.View(timeout=120)
    view.add_item(SlotActionDropdown(guild_id, user_id, plot_id, slots))
    return embed, view


class SlotActionDropdown(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int, plot_id: int, slots: list[dict]):
        self.guild_id = guild_id
        self.user_id = user_id
        self.plot_id = plot_id
        options = []
        for i, slot in enumerate(slots):
            if slot.get("planted"):
                crop_name = farm_config.CROPS[slot["seed_type"]]["name"]
                label = f"Slot {i + 1}: {crop_name}"
            else:
                label = f"Slot {i + 1}: (trống — trồng cây mới)"
            options.append(discord.SelectOption(label=label, value=str(i)))
        super().__init__(placeholder="Chọn slot để thao tác...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        slot_index = int(self.values[0])
        embed, view = build_slot_action_menu(self.guild_id, self.user_id, self.plot_id, slot_index)
        await interaction.response.edit_message(embed=embed, view=view)


def build_slot_action_menu(guild_id: int, user_id: int, plot_id: int, slot_index: int):
    data = store.get_farm_data(user_id)
    plot = data.get("plots", {}).get(str(plot_id), {"slots": []})
    slots = plot.get("slots", [])
    slot = slots[slot_index] if slot_index < len(slots) else {"planted": False}

    embed = discord.Embed(title=f"Ô {plot_id} — Slot {slot_index + 1}", color=discord.Color.blurple())
    view = discord.ui.View(timeout=90)

    if not slot.get("planted"):
        embed.description = "Đất trống. Chọn hạt giống để trồng."
        view.add_item(SeedChooseDropdown(guild_id, user_id, plot_id, slot_index))
        return embed, view

    crop_type = slot["seed_type"]
    needed = farm_config.CROPS[crop_type]["grow_progress_needed"]
    progress = slot["progress"]
    ready = progress >= needed
    water_speed_level = data.get("upgrades", {}).get("water_speed_level", 0)

    embed.description = (
        f"🌱 **{farm_config.CROPS[crop_type]['name']}**\n"
        f"Tiến độ: {progress:.1f}/{needed}{' — ✅ SẴN SÀNG THU HOẠCH' if ready else ''}\n"
        f"Cây tự lớn theo thời gian (không cần tưới) — tưới chỉ giúp nhanh hơn."
    )

    if ready:
        view.add_item(HarvestSlotButton(guild_id, user_id, plot_id, slot_index))
    else:
        remaining = _slot_water_remaining_sec(slot, water_speed_level)
        if remaining <= 0:
            view.add_item(WaterSlotButton(guild_id, user_id, plot_id, slot_index))
        else:
            embed.add_field(name="⏱️ Tưới lại sau", value=_fmt_td(remaining), inline=False)

    return embed, view


class SeedChooseDropdown(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int, plot_id: int, slot_index: int):
        self.guild_id = guild_id
        self.user_id = user_id
        self.plot_id = plot_id
        self.slot_index = slot_index

        data = store.get_farm_data(user_id)
        seed_inv = data.get("seed_inventory", {})
        options = []
        for cid in farm_config.CROP_ORDER:
            if not data.get("unlocked_crops", {}).get(cid):
                continue
            have = seed_inv.get(cid, 0)
            label = f"{farm_config.CROPS[cid]['name']} (có {have} hạt)"
            options.append(discord.SelectOption(label=label, value=cid))

        super().__init__(placeholder="Chọn loại hạt giống để trồng...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        crop_id = self.values[0]
        data = store.get_farm_data(self.user_id)
        have_seeds = data.get("seed_inventory", {}).get(crop_id, 0)
        if have_seeds <= 0:
            seed_cost = farm_config.CROPS[crop_id]["seed_cost"]
            await interaction.response.send_message(
                f"Bạn không có hạt giống **{farm_config.CROPS[crop_id]['name']}**. "
                f"Mua ở `/shop` — {seed_cost} mango/hạt.",
                ephemeral=True,
            )
            return

        now = datetime.datetime.utcnow()

        def _plant(d):
            plot = d["plots"].setdefault(
                str(self.plot_id),
                {"slots": [store._empty_slot() for _ in range(farm_config.SLOTS_PER_PLOT)]},
            )
            slot = plot["slots"][self.slot_index]
            slot["planted"] = True
            slot["seed_type"] = crop_id
            slot["progress"] = 0.0
            slot["last_water_at"] = None
            slot["last_passive_tick_at"] = now.isoformat()
            d["seed_inventory"][crop_id] = d["seed_inventory"].get(crop_id, 0) - 1
            return d

        store.transaction_farm_data(self.user_id, _plant)

        embed, view = build_slot_action_menu(self.guild_id, self.user_id, self.plot_id, self.slot_index)
        await interaction.response.edit_message(
            content=f"🌱 Đã trồng **{farm_config.CROPS[crop_id]['name']}** tại Ô {self.plot_id} - Slot {self.slot_index + 1}.",
            embed=embed, view=view,
        )


class WaterSlotButton(discord.ui.Button):
    def __init__(self, guild_id: int, user_id: int, plot_id: int, slot_index: int):
        super().__init__(label="💧 Tưới cây (boost thêm progress)", style=discord.ButtonStyle.primary)
        self.guild_id = guild_id
        self.user_id = user_id
        self.plot_id = plot_id
        self.slot_index = slot_index

    async def callback(self, interaction: discord.Interaction):
        data = store.get_farm_data(self.user_id)
        plot = data["plots"].get(str(self.plot_id), {"slots": []})
        slot = plot["slots"][self.slot_index]

        if not slot.get("planted"):
            await interaction.response.send_message("Slot này không có cây.", ephemeral=True)
            return

        needed = farm_config.CROPS[slot["seed_type"]]["grow_progress_needed"]
        if slot["progress"] >= needed:
            await interaction.response.send_message("Cây đã sẵn sàng thu hoạch.", ephemeral=True)
            return

        sprinkler_active, sprinkler_tier = _slot_sprinkler_active(slot)
        gain = farm_logic.roll_water_progress(data["watering_can"], sprinkler_active, sprinkler_tier)
        now = datetime.datetime.utcnow()

        def _water(d):
            s = d["plots"][str(self.plot_id)]["slots"][self.slot_index]
            s["progress"] = min(needed, s["progress"] + gain)
            s["last_water_at"] = now.isoformat()
            return d

        store.transaction_farm_data(self.user_id, _water)

        embed, view = build_slot_action_menu(self.guild_id, self.user_id, self.plot_id, self.slot_index)
        await interaction.response.edit_message(
            content=f"💧 Đã tưới (+{gain} progress).", embed=embed, view=view,
        )


class HarvestSlotButton(discord.ui.Button):
    def __init__(self, guild_id: int, user_id: int, plot_id: int, slot_index: int):
        super().__init__(label="🧺 Thu hoạch", style=discord.ButtonStyle.success)
        self.guild_id = guild_id
        self.user_id = user_id
        self.plot_id = plot_id
        self.slot_index = slot_index

    async def callback(self, interaction: discord.Interaction):
        data = store.get_farm_data(self.user_id)
        plot = data["plots"].get(str(self.plot_id), {"slots": []})
        slot = plot["slots"][self.slot_index]

        if not slot.get("planted"):
            await interaction.response.send_message("Slot này không có cây.", ephemeral=True)
            return

        crop_type = slot["seed_type"]
        needed = farm_config.CROPS[crop_type]["grow_progress_needed"]
        if slot["progress"] < needed:
            await interaction.response.send_message(
                f"Cây chưa đủ tiến độ ({slot['progress']:.1f}/{needed}).", ephemeral=True
            )
            return

        weather = store.get_current_weather(self.guild_id)
        stage = farm_logic.roll_produce_stage(crop_type)
        sprinkler_active, sprinkler_tier = _slot_sprinkler_active(slot)
        mutations = farm_logic.roll_mutations(weather, sprinkler_active, sprinkler_tier)

        has_lightning_rod = data.get("gear", {}).get("lightning_rod", False)
        if has_lightning_rod and weather == "storm" and "electrified" not in mutations:
            bonus = farm_config.GEAR["lightning_rod"]["electrified_bonus_chance"]
            import random as _random
            if _random.random() < bonus:
                mutations.append("electrified")

        yield_level = data.get("upgrades", {}).get("yield_level", 0)
        qty = farm_logic.roll_harvest_quantity(crop_type, yield_level)

        def _harvest(d):
            s = d["plots"][str(self.plot_id)]["slots"][self.slot_index]
            key = store.inventory_key(stage, mutations)
            d.setdefault("inventory", {})
            d["inventory"][key] = d["inventory"].get(key, 0) + qty
            s["planted"] = False
            s["seed_type"] = None
            s["progress"] = 0.0
            s["last_water_at"] = None
            s["last_passive_tick_at"] = None
            s["active_sprinkler_tier"] = None
            s["active_sprinkler_until"] = None
            return d

        store.transaction_farm_data(self.user_id, _harvest)

        mut_names = [
            farm_config.MUTATIONS_STACKABLE.get(m, farm_config.MUTATIONS_EXCLUSIVE.get(m, {})).get("name", m)
            for m in mutations
        ]
        mut_text = f" ({', '.join(mut_names)})" if mut_names else ""

        embed, view = build_slot_action_menu(self.guild_id, self.user_id, self.plot_id, self.slot_index)
        await interaction.response.edit_message(
            content=f"🧺 Thu hoạch {qty}x **{stage}**{mut_text}!", embed=embed, view=view,
        )


# ==================== SPRINKLER (chọn ô để kích hoạt) ====================
class SprinklerPlotChooseDropdown(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int, plot_ids: list[int], owned_sprinkler_ids: list[str]):
        self.guild_id = guild_id
        self.user_id = user_id
        self.owned_sprinkler_ids = owned_sprinkler_ids
        options = [discord.SelectOption(label=f"Ô {pid}", value=str(pid)) for pid in plot_ids]
        super().__init__(placeholder="Chọn ô để kích hoạt sprinkler...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        plot_id = int(self.values[0])
        view = discord.ui.View(timeout=60)
        view.add_item(SprinklerTierDropdown(self.guild_id, self.user_id, plot_id, self.owned_sprinkler_ids))
        await interaction.response.edit_message(content=f"Chọn loại sprinkler cho Ô {plot_id}:", view=view)


class SprinklerTierDropdown(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int, plot_id: int, owned_sprinkler_ids: list[str]):
        self.guild_id = guild_id
        self.user_id = user_id
        self.plot_id = plot_id
        data = store.get_farm_data(user_id)
        inventory = data.get("sprinkler_inventory", {})
        options = [
            discord.SelectOption(label=f"{farm_config.SPRINKLERS[sid]['name']} (còn {inventory.get(sid, 0)})", value=sid)
            for sid in owned_sprinkler_ids
        ]
        super().__init__(placeholder="Chọn sprinkler...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        sprinkler_id = self.values[0]
        cfg = farm_config.SPRINKLERS[sprinkler_id]
        now = datetime.datetime.utcnow()
        until = (now + datetime.timedelta(minutes=cfg["duration_min"])).isoformat()

        result_holder = {"ok": False}

        def _activate(d):
            inv = d.setdefault("sprinkler_inventory", {})
            have = inv.get(sprinkler_id, 0)
            if have <= 0:
                result_holder["ok"] = False
                return d
            inv[sprinkler_id] = have - 1
            if inv[sprinkler_id] <= 0:
                inv.pop(sprinkler_id, None)

            plot = d["plots"].setdefault(
                str(self.plot_id),
                {"slots": [store._empty_slot() for _ in range(farm_config.SLOTS_PER_PLOT)]},
            )
            for slot in plot["slots"]:
                slot["active_sprinkler_tier"] = sprinkler_id
                slot["active_sprinkler_until"] = until
            result_holder["ok"] = True
            return d

        store.transaction_farm_data(self.user_id, _activate)

        if not result_holder["ok"]:
            await interaction.response.send_message("Sprinkler này đã hết trong kho.", ephemeral=True)
            return

        await interaction.response.edit_message(
            content=f"💦 Đã kích hoạt **{cfg['name']}** cho toàn bộ Ô {self.plot_id} trong {cfg['duration_min']} phút.",
            view=None,
        )


# ==================== NÂNG CẤP MENU ====================
def build_upgrade_menu(guild_id: int, user_id: int):
    data = store.get_farm_data(user_id)
    mango = store.get_mango(user_id)

    embed = discord.Embed(title="⚙️ Nâng cấp nông trại", color=discord.Color.purple())
    embed.add_field(name="🥭 Mango", value=f"{mango}", inline=False)

    yield_lvl = data["upgrades"]["yield_level"]
    water_lvl = data["upgrades"]["water_speed_level"]
    yield_cost = farm_logic.upgrade_cost("yield", yield_lvl)
    water_cost = farm_logic.upgrade_cost("water_speed", water_lvl)

    embed.add_field(
        name=f"📈 Năng suất (Lv.{yield_lvl})",
        value=f"+{farm_config.YIELD_UPGRADE['double_fruit_chance_per_level']*100:.0f}% cơ hội x2 trái — {yield_cost}🥭",
        inline=False,
    )
    embed.add_field(
        name=f"⏱️ Tốc độ tưới (Lv.{water_lvl})",
        value=f"-{farm_config.WATER_SPEED_UPGRADE['cooldown_reduction_min_per_level']} phút cooldown tưới — {water_cost}🥭",
        inline=False,
    )

    view = discord.ui.View(timeout=90)
    if yield_lvl < farm_config.YIELD_UPGRADE["max_level"]:
        view.add_item(_UpgradeBtn(guild_id, user_id, "yield", yield_cost, "📈 Nâng năng suất"))
    if water_lvl < farm_config.WATER_SPEED_UPGRADE["max_level"]:
        view.add_item(_UpgradeBtn(guild_id, user_id, "water_speed", water_cost, "⏱️ Nâng tốc độ tưới"))

    unlocked_crops = data.get("unlocked_crops", {})
    next_crop = None
    for cid in farm_config.CROP_ORDER:
        if not unlocked_crops.get(cid):
            next_crop = cid
            break

    if next_crop:
        cost = farm_config.CROPS[next_crop]["unlock_cost"]
        embed.add_field(
            name=f"🌿 Mở khoá cây: {farm_config.CROPS[next_crop]['name']}",
            value=f"{cost} mango",
            inline=False,
        )
        view.add_item(_UnlockCropBtn(guild_id, user_id, next_crop, cost))

    unlocked_plots = data.get("unlocked_plots", {})
    next_plot = farm_logic.next_locked_plot({pid for pid in farm_config.PLOT_ORDER if unlocked_plots.get(str(pid))})
    if next_plot:
        cost_info = farm_logic.plot_unlock_cost(next_plot)
        currency_label = "mango" if cost_info["currency"] == "mango" else "mango+"
        embed.add_field(
            name=f"🗺️ Mở khoá Ô {next_plot}",
            value=f"{cost_info['cost']} {currency_label}",
            inline=False,
        )
        view.add_item(_UnlockPlotBtn(guild_id, user_id, next_plot, cost_info["cost"], cost_info["currency"]))

    return embed, view


class _UpgradeBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, kind, cost, label):
        super().__init__(label=f"{label} ({cost} mango)", style=discord.ButtonStyle.primary)
        self.guild_id = guild_id
        self.user_id = user_id
        self.kind = kind
        self.cost = cost
        self.upgrade_label = label

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        field = "yield_level" if self.kind == "yield" else "water_speed_level"

        def _upgrade(d):
            d["upgrades"][field] += 1
            return d

        ok, msg = store.spend_mango_and_apply(
            self.user_id, self.cost, _upgrade,
            label=self.upgrade_label,
        )
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed, view = build_upgrade_menu(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)


class _UnlockCropBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, crop_id, cost):
        super().__init__(label=f"Mở khoá {farm_config.CROPS[crop_id]['name']} ({cost} mango)", style=discord.ButtonStyle.success)
        self.guild_id = guild_id
        self.user_id = user_id
        self.crop_id = crop_id
        self.cost = cost

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        def _unlock(d):
            d["unlocked_crops"][self.crop_id] = True
            return d

        ok, msg = store.spend_mango_and_apply(
            self.user_id, self.cost, _unlock,
            label=f"Mở khoá cây {farm_config.CROPS[self.crop_id]['name']}",
        )
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed, view = build_upgrade_menu(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)


class _UnlockPlotBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, plot_id, cost, currency):
        currency_label = "mango" if currency == "mango" else "mango+"
        super().__init__(label=f"Mở khoá Ô {plot_id} ({cost} {currency_label})", style=discord.ButtonStyle.success)
        self.guild_id = guild_id
        self.user_id = user_id
        self.plot_id = plot_id
        self.cost = cost
        self.currency = currency

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        def _unlock(d):
            d["unlocked_plots"][str(self.plot_id)] = True
            d["plots"].setdefault(
                str(self.plot_id),
                {"slots": [store._empty_slot() for _ in range(farm_config.SLOTS_PER_PLOT)]},
            )
            return d

        label = f"Mở khoá Ô {self.plot_id}"
        if self.currency == "mango":
            ok, msg = store.spend_mango_and_apply(self.user_id, self.cost, _unlock, label=label)
        else:
            new_balance = store.transaction_mango(self.user_id, -self.cost, use_plus=True)
            if new_balance is None:
                ok, msg = False, "Không đủ mango+."
            else:
                try:
                    store.transaction_farm_data(self.user_id, _unlock)
                    ok, msg = True, ""
                    store.log_purchase(self.user_id, label, self.cost, "mango_plus")
                except Exception:
                    store.transaction_mango(self.user_id, self.cost, use_plus=True)  # rollback
                    ok, msg = False, "Có lỗi xảy ra, giao dịch đã được hoàn tác."

        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed, view = build_upgrade_menu(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)


class _FarmerToggleAutoWaterBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, current_state: bool):
        label = "🔕 Tắt tự động tưới" if current_state else "💧 Bật tự động tưới"
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.guild_id = guild_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        def _toggle(d):
            d["farmer"]["auto_water"] = not d["farmer"].get("auto_water", False)
            return d

        store.transaction_farm_data(self.user_id, _toggle)
        embed, view = build_worker_menu(self.guild_id, self.user_id, "farmer")
        await interaction.response.edit_message(embed=embed, view=view)
