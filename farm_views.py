import datetime

import discord

import farm_config
import farm_logic
import farm_store

def _fmt_td(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m}p"
    if m:
        return f"{m}p{s}s"
    return f"{s}s"

def _water_remaining_sec(data: dict, guild_id: int, user_id: int) -> int:
    plot = data["plot"]
    if not plot["last_water_at"]:
        return 0
    last = farm_store.parse_iso(plot["last_water_at"])
    cd_min = farm_logic.water_cooldown_min(data["upgrades"]["water_speed_level"])
    elapsed = (datetime.datetime.utcnow() - last).total_seconds()
    remaining = cd_min * 60 - elapsed
    return max(0, int(remaining))

def _sprinkler_active(plot: dict) -> tuple[bool, str | None]:
    if not plot.get("active_sprinkler_tier") or not plot.get("active_sprinkler_until"):
        return False, None
    until = farm_store.parse_iso(plot["active_sprinkler_until"])
    if datetime.datetime.utcnow() < until:
        return True, plot["active_sprinkler_tier"]
    return False, None

def _farmer_status_text(farmer: dict, now: datetime.datetime) -> str:
    if not farmer.get("hired"):
        return "❌ Chưa thuê"
    if farmer.get("permanent"):
        return "✅ Vĩnh viễn"
    hired_until = farmer.get("hired_until")
    if not hired_until:
        return "❌ Chưa thuê"
    until = farm_store.parse_iso(hired_until)
    if now >= until:
        return "❌ Đã hết hạn"
    remaining = int((until - now).total_seconds())
    return f"✅ Còn {_fmt_td(remaining)}"

# ==================== FARMER LAZY-CALC ====================
def _process_farmer_offline_work(guild_id: int, user_id: int) -> list[str]:
    """
    Tính bù việc farmer đã làm khi user vắng mặt.
    Mỗi vòng: farmer tự mua hạt (trừ mango) + trồng, hoặc tưới, hoặc thu hoạch.
    Nếu farmer thuê tạm thời đã hết hạn, việc chỉ tính tới đúng mốc hired_until rồi dừng,
    farmer coi như đã rời đi (hired=False) sau khi xử lý xong phần việc còn lại.
    """
    data = farm_store.get_farm_data(guild_id, user_id)
    farmer = data["farmer"]
    if not farmer.get("hired"):
        return []

    now = datetime.datetime.utcnow()
    last_processed = (
        farm_store.parse_iso(farmer["last_processed_at"])
        if farmer.get("last_processed_at")
        else now
    )

    hired_until_dt = None
    will_expire = False
    if not farmer.get("permanent"):
        hired_until = farmer.get("hired_until")
        if hired_until:
            hired_until_dt = farm_store.parse_iso(hired_until)
            will_expire = now >= hired_until_dt
        else:
            farm_store.update_farm_data(guild_id, user_id, {"farmer/hired": False})
            return ["🚜 Hợp đồng nông dân đã hết hạn — anh ta đã rời đi."]

    stats = farm_logic.farmer_stats(farmer.get("level", 0))
    ticks = farm_logic.simulate_farmer_ticks(
        last_processed, now, stats["work_duration_min"], stats["job_wait_sec"],
        hired_until=hired_until_dt,
    )
    ticks = min(ticks, 200)  # trần an toàn

    if ticks <= 0:
        return []

    crop_type = data["crop_type"]
    mango_available = farm_store.get_mango(guild_id, user_id)
    total_seed_cost = 0
    plot = dict(data["plot"])
    inventory_delta: dict[str, int] = {}
    logs: list[str] = []

    for _ in range(ticks):
        if not plot["planted"]:
            seed_cost = farm_config.CROPS[crop_type]["seed_cost"]
            if seed_cost > 0 and mango_available - total_seed_cost < seed_cost:
                logs.append("⚠️ Nông dân hết Mango🥭 để mua hạt giống, tạm dừng.")
                break
            total_seed_cost += seed_cost
            plot["planted"] = True
            plot["seed_type"] = crop_type
            plot["progress"] = 0.0
            plot["last_water_at"] = None
            logs.append(f"🌱 Nông dân đã mua hạt ({seed_cost}🥭) và trồng cây mới.")
            continue

        needed = farm_config.CROPS[plot["seed_type"] or crop_type]["grow_progress_needed"]

        if plot["progress"] < needed:
            sprinkler_active, sprinkler_tier = _sprinkler_active(plot)
            gain = farm_logic.roll_water_progress(data["watering_can"], sprinkler_active, sprinkler_tier)
            plot["progress"] = min(needed, plot["progress"] + gain)
            plot["last_water_at"] = now.isoformat()
            logs.append(f"💧 Nông dân đã tưới cây (+{gain} progress).")
        else:
            type = plot["seed_type"] or crop_type
            stage = farm_logic.roll_produce_stage(type)
            sprinkler_active, sprinkler_tier = _sprinkler_active(plot)
            weather = farm_store.get_current_weather(guild_id)
            mutations = farm_logic.roll_mutations(weather, sprinkler_active, sprinkler_tier)
            qty = farm_logic.roll_harvest_quantity(type, data["upgrades"]["yield_level"])

            key = farm_store.inventory_key(stage, mutations)
            inventory_delta[key] = inventory_delta.get(key, 0) + qty

            plot["planted"] = False
            plot["seed_type"] = None
            plot["progress"] = 0.0
            plot["last_water_at"] = None

            mut_text = f" ({', '.join(mutations)})" if mutations else ""
            logs.append(f"🧺 Nông dân đã thu hoạch {qty}x {stage}{mut_text}.")

    if will_expire:
        logs.append("🚜 Hợp đồng nông dân đã hết hạn — anh ta đã rời đi.")

    if total_seed_cost > 0:
        farm_store.transaction_mango(guild_id, user_id, -total_seed_cost)

    def _apply(d):
        d["plot"] = plot
        d.setdefault("inventory", {})
        for key, qty in inventory_delta.items():
            d["inventory"][key] = d["inventory"].get(key, 0) + qty
        d["farmer"]["last_processed_at"] = now.isoformat()
        if will_expire:
            d["farmer"]["hired"] = False
        return d

    farm_store.transaction_farm_data(guild_id, user_id, _apply)
    return logs[-6:]

# ==================== MAIN FARM ====================
def build_farm_embed_and_view(guild_id: int, user_id: int, extra_logs: list[str] | None = None):
    offline_logs = _process_farmer_offline_work(guild_id, user_id)

    data = farm_store.get_farm_data(guild_id, user_id)
    mango = farm_store.get_mango(guild_id, user_id)
    weather = farm_store.get_current_weather(guild_id)
    now = datetime.datetime.utcnow()

    plot = data["plot"]
    crop_type = data["crop_type"]
    crop_stats = farm_logic.get_crop_stats(plot["seed_type"] or crop_type)

    embed = discord.Embed(title="🌾 Nông trại", color=discord.Color.green())
    embed.add_field(name="🥭 Mango", value=f"{mango}", inline=True)
    embed.add_field(name="🌤️ Thời tiết", value=farm_config.WEATHER_TYPES[weather]["name"], inline=True)
    embed.add_field(name="🚜 Nông dân", value=_farmer_status_text(data["farmer"], now), inline=True)

    seed_count = data.get("seed_inventory", {}).get(crop_type, 0)
    embed.add_field(
        name=f"🌱 Hạt {farm_config.CROPS[crop_type]['name']} trong kho",
        value=f"{seed_count} hạt",
        inline=True,
    )

    sprinkler_inv = data.get("sprinkler_inventory", {})
    if sprinkler_inv:
        inv_text = ", ".join(f"{farm_config.SPRINKLERS[sid]['name']} x{qty}" for sid, qty in sprinkler_inv.items())
        embed.add_field(name="💦 Sprinkler trong kho", value=inv_text, inline=True)

    if plot["planted"]:
        needed = crop_stats["grow_progress_needed"]
        progress = plot["progress"]
        bar_len = 15
        filled = int(bar_len * progress / needed) if needed else 0
        bar = "🟩" * filled + "⬛" * (bar_len - filled)
        ready = progress >= needed

        sprinkler_active, sprinkler_tier = _sprinkler_active(plot)
        sprinkler_text = ""
        if sprinkler_active:
            sprinkler_name = farm_config.SPRINKLERS[sprinkler_tier]["name"]
            sprinkler_text = f"\n💦 {sprinkler_name} đang hoạt động"

        embed.add_field(
            name=f"Cây trồng: {farm_config.CROPS[plot['seed_type'] or crop_type]['name']}",
            value=f"{bar}\n{progress:.1f}/{needed} progress{' — ✅ SẴN SÀNG THU HOẠCH' if ready else ''}{sprinkler_text}",
            inline=False,
        )

        remaining = _water_remaining_sec(data, guild_id, user_id)
        if remaining > 0 and not ready:
            embed.add_field(name="⏱️ Tưới lại sau", value=_fmt_td(remaining), inline=True)
    else:
        embed.add_field(name="Đất trống", value="Chưa trồng cây nào. Bấm **Trồng cây** để bắt đầu.", inline=False)

    if offline_logs:
        embed.add_field(name="📋 Trong lúc bạn vắng mặt", value="\n".join(offline_logs), inline=False)
    if extra_logs:
        embed.add_field(name="Vừa xong", value="\n".join(extra_logs), inline=False)

    view = FarmView(guild_id, user_id)
    return embed, view

class FarmView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải nông trại của bạn.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🌱 Trồng cây", style=discord.ButtonStyle.success)
    async def plant(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = farm_store.get_farm_data(self.guild_id, self.user_id)
        if data["plot"]["planted"]:
            await interaction.response.send_message("Đất đang có cây trồng rồi.", ephemeral=True)
            return

        crop_type = data["crop_type"]
        have_seeds = data.get("seed_inventory", {}).get(crop_type, 0)
        if have_seeds <= 0:
            seed_cost = farm_config.CROPS[crop_type]["seed_cost"]
            await interaction.response.send_message(
                f"Bạn không có hạt giống **{farm_config.CROPS[crop_type]['name']}**. "
                f"Mua ở `/shop` — {seed_cost} mango/hạt.",
                ephemeral=True,
            )
            return

        def _plant(d):
            d["seed_inventory"][crop_type] = d["seed_inventory"].get(crop_type, 0) - 1
            d["plot"]["planted"] = True
            d["plot"]["seed_type"] = crop_type
            d["plot"]["progress"] = 0.0
            d["plot"]["last_water_at"] = None
            return d

        farm_store.transaction_farm_data(self.guild_id, self.user_id, _plant)
        embed, view = build_farm_embed_and_view(self.guild_id, self.user_id, extra_logs=["🌱 Bạn đã trồng cây mới."])
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="💧 Tưới cây", style=discord.ButtonStyle.primary)
    async def water(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = farm_store.get_farm_data(self.guild_id, self.user_id)
        if not data["plot"]["planted"]:
            await interaction.response.send_message("Chưa trồng cây nào để tưới.", ephemeral=True)
            return

        remaining = _water_remaining_sec(data, self.guild_id, self.user_id)
        if remaining > 0:
            await interaction.response.send_message(
                f"Phải chờ **{_fmt_td(remaining)}** nữa mới tưới tiếp được.", ephemeral=True
            )
            return

        needed = farm_logic.get_crop_stats(data["plot"]["seed_type"] or data["crop_type"])["grow_progress_needed"]
        if data["plot"]["progress"] >= needed:
            await interaction.response.send_message("Cây đã sẵn sàng thu hoạch, không cần tưới nữa.", ephemeral=True)
            return

        sprinkler_active, sprinkler_tier = _sprinkler_active(data["plot"])
        gain = farm_logic.roll_water_progress(data["watering_can"], sprinkler_active, sprinkler_tier)

        def _water(d):
            new_progress = min(needed, d["plot"]["progress"] + gain)
            d["plot"]["progress"] = new_progress
            d["plot"]["last_water_at"] = datetime.datetime.utcnow().isoformat()
            return d

        farm_store.transaction_farm_data(self.guild_id, self.user_id, _water)
        embed, view = build_farm_embed_and_view(
            self.guild_id, self.user_id, extra_logs=[f"💧 Đã tưới cây (+{gain} progress)."]
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🧺 Thu hoạch", style=discord.ButtonStyle.success)
    async def harvest(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = farm_store.get_farm_data(self.guild_id, self.user_id)
        plot = data["plot"]
        if not plot["planted"]:
            await interaction.response.send_message("Chưa trồng cây nào để thu hoạch.", ephemeral=True)
            return

        crop_type = plot["seed_type"] or data["crop_type"]
        needed = farm_logic.get_crop_stats(crop_type)["grow_progress_needed"]
        if plot["progress"] < needed:
            await interaction.response.send_message(
                f"Cây chưa đủ progress ({plot['progress']:.1f}/{needed}).", ephemeral=True
            )
            return

        stage = farm_logic.roll_produce_stage(crop_type)
        sprinkler_active, sprinkler_tier = _sprinkler_active(plot)
        weather = farm_store.get_current_weather(self.guild_id)
        mutations = farm_logic.roll_mutations(weather, sprinkler_active, sprinkler_tier)
        qty = farm_logic.roll_harvest_quantity(crop_type, data["upgrades"]["yield_level"])

        def _harvest(d):
            key = farm_store.inventory_key(stage, mutations)
            d.setdefault("inventory", {})
            d["inventory"][key] = d["inventory"].get(key, 0) + qty
            d["plot"] = {
                "planted": False,
                "seed_type": None,
                "progress": 0.0,
                "last_water_at": None,
                "active_sprinkler_tier": d["plot"].get("active_sprinkler_tier"),
                "active_sprinkler_until": d["plot"].get("active_sprinkler_until"),
            }
            return d

        farm_store.transaction_farm_data(self.guild_id, self.user_id, _harvest)

        mut_text = f" ({', '.join(farm_config.MUTATIONS_STACKABLE.get(m, farm_config.MUTATIONS_EXCLUSIVE.get(m, {})).get('name', m) for m in mutations)})" if mutations else ""
        embed, view = build_farm_embed_and_view(
            self.guild_id, self.user_id,
            extra_logs=[f"🧺 Thu hoạch {qty}x **{stage}**{mut_text}!"],
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="⚙️ Nâng cấp", style=discord.ButtonStyle.secondary)
    async def upgrades(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, view = build_upgrade_menu(self.guild_id, self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🚜 Thuê nông dân", style=discord.ButtonStyle.secondary)
    async def hire_farmer(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = farm_store.get_farm_data(self.guild_id, self.user_id)
        now = datetime.datetime.utcnow()
        farmer = data["farmer"]
        is_active = farm_logic.is_farmer_active(farmer, now)

        if is_active:
            embed, view = build_farmer_menu(self.guild_id, self.user_id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return

        mango = farm_store.get_mango(self.guild_id, self.user_id)
        if mango < farm_config.FARMER_HIRE_COST_MANGO:
            await interaction.response.send_message(
                f"Cần **{farm_config.FARMER_HIRE_COST_MANGO} mango** để thuê nông dân (bạn có {mango}).",
                ephemeral=True,
            )
            return

        new_balance = farm_store.transaction_mango(self.guild_id, self.user_id, -farm_config.FARMER_HIRE_COST_MANGO)
        if new_balance is None or new_balance < 0:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return

        hired_until = (now + datetime.timedelta(minutes=farm_config.FARMER_HIRE_DURATION_MIN)).isoformat()

        def _hire(d):
            d["farmer"]["hired"] = True
            d["farmer"]["hired_until"] = hired_until
            d["farmer"]["last_processed_at"] = now.isoformat()
            return d

        farm_store.transaction_farm_data(self.guild_id, self.user_id, _hire)
        embed, view = build_farm_embed_and_view(
            self.guild_id, self.user_id,
            extra_logs=[f"🚜 Đã thuê nông dân ({farm_config.FARMER_HIRE_DURATION_MIN} phút)! Anh ta sẽ tự làm việc kể cả khi bạn offline."],
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="💦 Kích hoạt sprinkler", style=discord.ButtonStyle.secondary)
    async def activate_sprinkler(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = farm_store.get_farm_data(self.guild_id, self.user_id)
        inventory = data.get("sprinkler_inventory", {})
        owned = [sid for sid in farm_config.SPRINKLER_ORDER if inventory.get(sid, 0) > 0]

        if not owned:
            await interaction.response.send_message(
                "Bạn chưa sở hữu sprinkler nào. Mua ở `/shop`.", ephemeral=True
            )
            return

        active, _ = _sprinkler_active(data["plot"])
        if active:
            await interaction.response.send_message("Đang có 1 sprinkler hoạt động rồi.", ephemeral=True)
            return

        view = discord.ui.View(timeout=60)
        view.add_item(SprinklerActivateDropdown(self.guild_id, self.user_id, owned))
        await interaction.response.send_message("Chọn sprinkler để kích hoạt:", view=view, ephemeral=True)

class SprinklerActivateDropdown(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int, owned_sprinkler_ids: list[str]):
        self.guild_id = guild_id
        self.user_id = user_id
        data = farm_store.get_farm_data(guild_id, user_id)
        inventory = data.get("sprinkler_inventory", {})
        options = [
            discord.SelectOption(
                label=f"{farm_config.SPRINKLERS[sid]['name']} (còn {inventory.get(sid, 0)})",
                value=sid,
            )
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
            d["plot"]["active_sprinkler_tier"] = sprinkler_id
            d["plot"]["active_sprinkler_until"] = until
            result_holder["ok"] = True
            return d

        farm_store.transaction_farm_data(self.guild_id, self.user_id, _activate)

        if not result_holder["ok"]:
            await interaction.response.send_message("Sprinkler này đã hết trong kho.", ephemeral=True)
            return

        await interaction.response.edit_message(
            content=f"💦 Đã kích hoạt **{cfg['name']}** trong {cfg['duration_min']} phút.", view=None
        )

# ==================== NÂNG CẤP MENU ====================
def build_upgrade_menu(guild_id: int, user_id: int):
    data = farm_store.get_farm_data(guild_id, user_id)
    mango = farm_store.get_mango(guild_id, user_id)

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

    current_crop = data["crop_type"]
    next_crop = farm_config.CROPS[current_crop].get("next_unlock")

    view = discord.ui.View(timeout=90)
    if yield_lvl < farm_config.YIELD_UPGRADE["max_level"]:
        view.add_item(_UpgradeBtn(guild_id, user_id, "yield", yield_cost, "📈 Nâng năng suất"))
    if water_lvl < farm_config.WATER_SPEED_UPGRADE["max_level"]:
        view.add_item(_UpgradeBtn(guild_id, user_id, "water_speed", water_cost, "⏱️ Nâng tốc độ tưới"))

    if next_crop and not data["unlocked_crops"].get(next_crop):
        cost = farm_config.CROPS[next_crop]["unlock_cost"]
        embed.add_field(
            name=f"🌿 Mở khoá cây: {farm_config.CROPS[next_crop]['name']}",
            value=f"{cost} mango",
            inline=False,
        )
        view.add_item(_UnlockCropBtn(guild_id, user_id, next_crop, cost))

    return embed, view

class _UpgradeBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, kind, cost, label):
        super().__init__(label=f"{label} ({cost} mango)", style=discord.ButtonStyle.primary)
        self.guild_id = guild_id
        self.user_id = user_id
        self.kind = kind
        self.cost = cost

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        mango = farm_store.get_mango(self.guild_id, self.user_id)
        if mango < self.cost:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return

        new_balance = farm_store.transaction_mango(self.guild_id, self.user_id, -self.cost)
        if new_balance is None:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return

        field = "yield_level" if self.kind == "yield" else "water_speed_level"

        def _upgrade(d):
            d["upgrades"][field] += 1
            return d

        farm_store.transaction_farm_data(self.guild_id, self.user_id, _upgrade)
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

        mango = farm_store.get_mango(self.guild_id, self.user_id)
        if mango < self.cost:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return

        new_balance = farm_store.transaction_mango(self.guild_id, self.user_id, -self.cost)
        if new_balance is None:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return

        def _unlock(d):
            d["unlocked_crops"][self.crop_id] = True
            d["crop_type"] = self.crop_id  # tự chuyển sang cây mới sau khi unlock
            return d

        farm_store.transaction_farm_data(self.guild_id, self.user_id, _unlock)
        embed, view = build_upgrade_menu(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

# ==================== FARMER MENU (khi đã thuê) ====================
def build_farmer_menu(guild_id: int, user_id: int):
    data = farm_store.get_farm_data(guild_id, user_id)
    mango = farm_store.get_mango(guild_id, user_id)
    farmer = data["farmer"]
    level = farmer["level"]
    stats = farm_logic.farmer_stats(level)
    cost = farm_logic.upgrade_cost("farmer", level)
    now = datetime.datetime.utcnow()

    embed = discord.Embed(title="🚜 Nông dân", color=discord.Color.dark_green())
    embed.add_field(name="Trạng thái", value=_farmer_status_text(farmer, now), inline=True)
    embed.add_field(name="Cấp độ", value=f"Lv.{level}", inline=True)
    embed.add_field(name="Thời gian/vòng việc", value=f"{stats['work_duration_min']} phút", inline=True)
    embed.add_field(name="Chờ giữa việc", value=f"{stats['job_wait_sec']}s", inline=True)
    embed.add_field(
        name="Nâng cấp tiếp theo (giảm thời gian làm việc)",
        value=f"{cost} mango",
        inline=False,
    )
    if not farmer.get("permanent"):
        embed.add_field(
            name="⭐ Nâng cấp vĩnh viễn",
            value=f"Không cần thuê lại nữa — {farm_config.FARMER_PERMANENT_COST_MANGO:,} mango",
            inline=False,
        )

    view = discord.ui.View(timeout=90)
    if level < farm_config.FARMER_UPGRADE["max_level"]:
        view.add_item(_FarmerUpgradeBtn(guild_id, user_id, cost))
    if not farmer.get("permanent"):
        view.add_item(_FarmerPermanentBtn(guild_id, user_id))
    return embed, view

class _FarmerUpgradeBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, cost):
        super().__init__(label=f"Nâng cấp nông dân ({cost} mango)", style=discord.ButtonStyle.primary)
        self.guild_id = guild_id
        self.user_id = user_id
        self.cost = cost

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        mango = farm_store.get_mango(self.guild_id, self.user_id)
        if mango < self.cost:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return

        new_balance = farm_store.transaction_mango(self.guild_id, self.user_id, -self.cost)
        if new_balance is None:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return

        def _upgrade(d):
            d["farmer"]["level"] += 1
            return d

        farm_store.transaction_farm_data(self.guild_id, self.user_id, _upgrade)
        embed, view = build_farmer_menu(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

class _FarmerPermanentBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id):
        cost = farm_config.FARMER_PERMANENT_COST_MANGO
        super().__init__(label=f"⭐ Nâng cấp vĩnh viễn ({cost:,} mango)", style=discord.ButtonStyle.success)
        self.guild_id = guild_id
        self.user_id = user_id
        self.cost = cost

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải cửa hàng của bạn.", ephemeral=True)
            return

        mango = farm_store.get_mango(self.guild_id, self.user_id)
        if mango < self.cost:
            await interaction.response.send_message(
                f"Cần {self.cost:,} mango (bạn có {mango:,}).", ephemeral=True
            )
            return

        new_balance = farm_store.transaction_mango(self.guild_id, self.user_id, -self.cost)
        if new_balance is None:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return

        def _make_permanent(d):
            d["farmer"]["permanent"] = True
            d["farmer"]["hired"] = True
            d["farmer"]["hired_until"] = None
            return d

        farm_store.transaction_farm_data(self.guild_id, self.user_id, _make_permanent)
        embed, view = build_farmer_menu(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)