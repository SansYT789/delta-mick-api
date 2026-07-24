import datetime

import discord

import config
import logic
import store
import session_manager


def _is_owner(interaction: discord.Interaction, guild_id: int, user_id: int) -> bool:
    return interaction.user.id == user_id


def _cooldown_remaining(data: dict, car_id: str) -> int:
    """Giây còn lại của cooldown, 0 nếu đã hết."""
    cd = data.get("cooldowns", {}).get(car_id)
    if not cd:
        return 0
    until = store.parse_iso(cd)
    remaining = (until - datetime.datetime.utcnow()).total_seconds()
    return max(0, int(remaining))


# ==================== MAIN MENU ====================

class MainMenuView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Đây không phải phiên của bạn.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="▶️ Play", style=discord.ButtonStyle.success)
    async def play(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = store.get_user_data(self.guild_id, self.user_id)
        active_car = data.get("active_car")

        if not active_car or not data["cars"].get(active_car, {}).get("owned"):
            await interaction.response.send_message(
                "Bạn chưa có xe nào. Vào **🛒 Shop xe** để mua trước.", ephemeral=True
            )
            return

        car_entry = data["cars"][active_car]
        if car_entry.get("broken"):
            await interaction.response.send_message(
                "Xe hiện tại đang hỏng. Vào **🔧 Sửa xe** trước khi săn tiếp.", ephemeral=True
            )
            return

        remaining = _cooldown_remaining(data, active_car)
        if remaining > 0:
            await interaction.response.send_message(
                f"Xe đang hồi. Còn **{remaining // 60}p{remaining % 60}s** nữa.", ephemeral=True
            )
            return

        if session_manager.is_session_active(self.guild_id, self.user_id):
            await interaction.response.send_message("Bạn đang có 1 lượt săn đang chạy rồi.", ephemeral=True)
            return

        await interaction.response.defer()
        session_manager.start_session(
            self.guild_id,
            self.user_id,
            session_manager.run_hunt_session(interaction, active_car),
        )

    @discord.ui.button(label="🚗 Chọn xe", style=discord.ButtonStyle.primary)
    async def choose_car(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = store.get_user_data(self.guild_id, self.user_id)
        owned = [cid for cid, c in data["cars"].items() if c.get("owned")]
        if not owned:
            await interaction.response.send_message("Bạn chưa sở hữu xe nào.", ephemeral=True)
            return
        view = CarSelectView(self.guild_id, self.user_id, owned)
        await interaction.response.send_message("Chọn xe để dùng cho lượt săn tiếp theo:", view=view, ephemeral=True)

    @discord.ui.button(label="🛒 Shop xe", style=discord.ButtonStyle.secondary)
    async def shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, view = build_car_shop(self.guild_id, self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="⚙️ Nâng cấp", style=discord.ButtonStyle.secondary)
    async def upgrades(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, view = build_upgrade_menu(self.guild_id, self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🔧 Sửa xe", style=discord.ButtonStyle.secondary)
    async def repair(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed, view = build_repair_menu(self.guild_id, self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


def build_main_menu_embed(guild_id: int, user_id: int) -> discord.Embed:
    data = store.get_user_data(guild_id, user_id)
    active_car = data.get("active_car")

    embed = discord.Embed(title="🌪️ Trung tâm Săn Bão", color=discord.Color.blue())
    embed.add_field(name="💰 Money", value=f"${data.get('money', 0):,}", inline=True)
    embed.add_field(name="🥭 Mango", value=f"{data.get('mango', 0)}", inline=True)

    if active_car and data["cars"].get(active_car, {}).get("owned"):
        car_entry = data["cars"][active_car]
        stats = logic.get_car_stats(active_car, car_entry["durability_level"], car_entry["cooldown_level"])
        status = "🔴 Hỏng" if car_entry.get("broken") else "🟢 Sẵn sàng"
        remaining = _cooldown_remaining(data, active_car)
        if remaining > 0:
            status = f"🟡 Hồi ({remaining // 60}p{remaining % 60}s)"
        embed.add_field(
            name="Xe hiện tại",
            value=f"**{stats['name']}** — {status}\nĐộ bền tối đa: {stats['max_durability']} | Max EF{stats['max_ef']} | Cooldown {stats['cooldown_min']}p",
            inline=False,
        )
    else:
        embed.add_field(name="Xe hiện tại", value="Chưa có xe — vào Shop để mua.", inline=False)

    embed.set_footer(text=f"1 mango = {config.MONEY_PER_MANGO:,} money (quy đổi tham khảo)")
    return embed


# ==================== CHỌN XE ====================

class CarSelectView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int, owned_car_ids: list[str]):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.user_id = user_id
        self.add_item(CarSelectDropdown(guild_id, user_id, owned_car_ids))


class CarSelectDropdown(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int, owned_car_ids: list[str]):
        self.guild_id = guild_id
        self.user_id = user_id
        options = [
            discord.SelectOption(label=config.CARS[cid]["name"], value=cid)
            for cid in owned_car_ids
        ]
        super().__init__(placeholder="Chọn xe...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return
        car_id = self.values[0]
        store.update_user_data(self.guild_id, self.user_id, {"active_car": car_id})
        await interaction.response.edit_message(
            content=f"Đã chọn **{config.CARS[car_id]['name']}** làm xe săn bão.", view=None
        )


# ==================== SHOP XE ====================

def build_car_shop(guild_id: int, user_id: int):
    data = store.get_user_data(guild_id, user_id)
    money = data.get("money", 0)

    embed = discord.Embed(title="🛒 Shop xe", color=discord.Color.gold())
    lines = []
    for cid in config.CAR_ORDER:
        car = config.CARS[cid]
        owned = data["cars"].get(cid, {}).get("owned", False)
        tag = "✅ Đã sở hữu" if owned else f"${car['price']:,}"
        lines.append(
            f"**{car['name']}** — {tag}\n"
            f"　Durability {car['durability']} | Max EF{car['max_ef']} | Cooldown {car['cooldown_min']}p"
        )
    embed.description = "\n\n".join(lines)
    embed.set_footer(text=f"Bạn có ${money:,}")

    view = discord.ui.View(timeout=60)
    for cid in config.CAR_ORDER:
        car = config.CARS[cid]
        owned = data["cars"].get(cid, {}).get("owned", False)
        if not owned:
            view.add_item(BuyCarButton(guild_id, user_id, cid, car["price"]))
    return embed, view


class BuyCarButton(discord.ui.Button):
    def __init__(self, guild_id, user_id, car_id, price):
        super().__init__(label=f"Mua {config.CARS[car_id]['name']} (${price:,})", style=discord.ButtonStyle.success)
        self.guild_id = guild_id
        self.user_id = user_id
        self.car_id = car_id
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        def _buy(d):
            if d.get("money", 0) < self.price:
                return d  # không đủ tiền, không đổi gì
            d["money"] -= self.price
            d.setdefault("cars", {})[self.car_id] = {
                "durability_level": 0,
                "cooldown_level": 0,
                "owned": True,
            }
            return d

        result = store.transaction_user_data(self.guild_id, self.user_id, _buy)
        if not result["cars"].get(self.car_id, {}).get("owned"):
            await interaction.response.send_message("Không đủ money để mua xe này.", ephemeral=True)
            return

        embed, view = build_car_shop(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)


# ==================== NÂNG CẤP ====================

def build_upgrade_menu(guild_id: int, user_id: int):
    data = store.get_user_data(guild_id, user_id)
    active_car = data.get("active_car")
    money = data.get("money", 0)

    embed = discord.Embed(title="⚙️ Nâng cấp", color=discord.Color.purple())
    embed.add_field(name="💰 Money", value=f"${money:,}", inline=False)

    view = discord.ui.View(timeout=60)

    if active_car and data["cars"].get(active_car, {}).get("owned"):
        car_entry = data["cars"][active_car]
        dur_level = car_entry.get("durability_level", 0)
        cd_level = car_entry.get("cooldown_level", 0)
        dur_cost = logic.upgrade_cost("car", dur_level)
        cd_cost = logic.upgrade_cost("car", cd_level)

        embed.add_field(
            name=f"🚗 Độ bền xe (Lv.{dur_level})",
            value=f"+{config.CAR_UPGRADE['durability_per_level']} durability — ${dur_cost:,}",
            inline=False,
        )
        embed.add_field(
            name=f"⏱️ Cooldown xe (Lv.{cd_level})",
            value=f"-{config.CAR_UPGRADE['cooldown_reduction_per_level_min']} phút cooldown — ${cd_cost:,}",
            inline=False,
        )
        if dur_level < config.CAR_UPGRADE["max_level"]:
            view.add_item(UpgradeButton(guild_id, user_id, "car_durability", dur_cost, active_car))
        if cd_level < config.CAR_UPGRADE["max_level"]:
            view.add_item(UpgradeButton(guild_id, user_id, "car_cooldown", cd_cost, active_car))
    else:
        embed.add_field(name="Xe", value="Chưa chọn xe active.", inline=False)

    radar_level = data["upgrades"].get("radar_level", 0)
    armor_level = data["upgrades"].get("armor_level", 0)
    radar_cost = logic.upgrade_cost("radar", radar_level)
    armor_cost = logic.upgrade_cost("armor", armor_level)

    embed.add_field(
        name=f"📡 Radar dò bão (Lv.{radar_level})",
        value=f"Giảm thời gian chờ, tăng cơ hội gặp EF cao — ${radar_cost:,}",
        inline=False,
    )
    embed.add_field(
        name=f"🛡️ Giáp xe (Lv.{armor_level})",
        value=f"-{config.ARMOR_UPGRADE['dmg_reduction_per_level']*100:.0f}% sát thương mỗi tick — ${armor_cost:,}",
        inline=False,
    )
    if radar_level < config.RADAR_UPGRADE["max_level"]:
        view.add_item(UpgradeButton(guild_id, user_id, "radar", radar_cost, None))
    if armor_level < config.ARMOR_UPGRADE["max_level"]:
        view.add_item(UpgradeButton(guild_id, user_id, "armor", armor_cost, None))

    return embed, view


class UpgradeButton(discord.ui.Button):
    LABELS = {
        "car_durability": "🚗 Nâng độ bền xe",
        "car_cooldown": "⏱️ Giảm cooldown xe",
        "radar": "📡 Nâng radar",
        "armor": "🛡️ Nâng giáp",
    }

    def __init__(self, guild_id, user_id, kind, cost, car_id):
        super().__init__(label=f"{self.LABELS[kind]} (${cost:,})", style=discord.ButtonStyle.primary)
        self.guild_id = guild_id
        self.user_id = user_id
        self.kind = kind
        self.cost = cost
        self.car_id = car_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        def _upgrade(d):
            if d.get("money", 0) < self.cost:
                return d
            d["money"] -= self.cost
            if self.kind == "car_durability":
                d["cars"][self.car_id]["durability_level"] += 1
            elif self.kind == "car_cooldown":
                d["cars"][self.car_id]["cooldown_level"] += 1
            elif self.kind == "radar":
                d["upgrades"]["radar_level"] += 1
            elif self.kind == "armor":
                d["upgrades"]["armor_level"] += 1
            return d

        before = store.get_user_data(self.guild_id, self.user_id)
        if before.get("money", 0) < self.cost:
            await interaction.response.send_message("Không đủ money.", ephemeral=True)
            return

        store.transaction_user_data(self.guild_id, self.user_id, _upgrade)
        embed, view = build_upgrade_menu(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)


# ==================== SỬA XE ====================

def build_repair_menu(guild_id: int, user_id: int):
    data = store.get_user_data(guild_id, user_id)
    active_car = data.get("active_car")
    money = data.get("money", 0)

    embed = discord.Embed(title="🔧 Sửa xe", color=discord.Color.dark_orange())
    embed.add_field(name="💰 Money", value=f"${money:,}", inline=False)

    view = discord.ui.View(timeout=60)

    if active_car and data["cars"].get(active_car, {}).get("owned"):
        car_entry = data["cars"][active_car]
        broken = car_entry.get("broken", False)
        embed.add_field(
            name=config.CARS[active_car]["name"],
            value=(
                f"Trạng thái: {'🔴 Hỏng' if broken else '🟢 Bình thường'}\n"
                f"Chi phí: ${config.REPAIR_COST:,} / {config.REPAIR_AMOUNT} độ bền"
            ),
            inline=False,
        )
        if broken:
            view.add_item(RepairButton(guild_id, user_id, active_car))
    else:
        embed.add_field(name="Xe", value="Chưa chọn xe active.", inline=False)

    return embed, view


class RepairButton(discord.ui.Button):
    def __init__(self, guild_id, user_id, car_id):
        super().__init__(
            label=f"Sửa xe (${config.REPAIR_COST:,})",
            style=discord.ButtonStyle.success,
        )
        self.guild_id = guild_id
        self.user_id = user_id
        self.car_id = car_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        def _repair(d):
            if d.get("money", 0) < config.REPAIR_COST:
                return d
            d["money"] -= config.REPAIR_COST
            d["cars"][self.car_id]["broken"] = False
            return d

        before = store.get_user_data(self.guild_id, self.user_id)
        if before.get("money", 0) < config.REPAIR_COST:
            await interaction.response.send_message("Không đủ money để sửa xe.", ephemeral=True)
            return

        store.transaction_user_data(self.guild_id, self.user_id, _repair)
        embed, view = build_repair_menu(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)


# ==================== SAU KHI SĂN XONG ====================

class PostHuntView(discord.ui.View):
    """Hiện sau khi kết thúc 1 lượt săn, cho quay lại menu chính."""
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.user_id = user_id

    @discord.ui.button(label="🏠 Về menu chính", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return
        embed = build_main_menu_embed(self.guild_id, self.user_id)
        view = MainMenuView(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

