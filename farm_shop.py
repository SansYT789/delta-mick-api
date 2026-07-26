import datetime

import discord

import farm_config
import farm_logic
import farm_store

# ==================== SHOP FARM MODE ====================
def build_farm_shop_embed_and_view(guild_id: int, user_id: int):
    data = farm_store.get_farm_data(guild_id, user_id)
    mango = farm_store.get_mango(guild_id, user_id)

    embed = discord.Embed(title="🛒 Shop — Nông trại", color=discord.Color.gold())
    embed.add_field(name="🥭 Mango", value=f"{mango}", inline=False)

    seed_lines = []
    for cid in farm_config.CROP_ORDER:
        crop = farm_config.CROPS[cid]
        unlocked = data["unlocked_crops"].get(cid, False)
        have = data.get("seed_inventory", {}).get(cid, 0)
        if unlocked:
            tag = f"{crop['seed_cost']} 🥭/hạt (có {have})"
        else:
            tag = "🔒 Chưa mở khoá"
        seed_lines.append(f"**{crop['name']}** — {tag}")
    embed.add_field(name="🌱 Hạt giống", value="\n".join(seed_lines), inline=False)

    can_lines = []
    for cid, cfg in farm_config.WATERING_CANS.items():
        owned = data["watering_can"] == cid
        tag = "✅ Đang dùng" if owned else (f"{cfg['price']} mango" if cfg["price"] > 0 else "🆓")
        can_lines.append(f"**{cfg['name']}** — {tag}")
    embed.add_field(name="💧 Bình tưới", value="\n".join(can_lines), inline=False)

    scanner_owned = data["gear"].get("scanner", False)
    plucker_owned = data["gear"].get("mutation_plucker", False)
    scanner_price = farm_config.GEAR["scanner"]["price"]
    plucker_price = farm_config.GEAR["mutation_plucker"]["price"]
    scanner_text = "✅ Đã có" if scanner_owned else f"{scanner_price}🥭"
    plucker_text = "✅ Đã có" if plucker_owned else f"{plucker_price}🥭"
    embed.add_field(
        name="🔧 Dụng cụ (gear)",
        value=(
            f"**Kính lúp** — {scanner_text}\n"
            f"**Đồ gắp** — {plucker_text}\n"
            f"Xem thêm Cờ lê / Vợt / Cột thu lôi trong danh mục Dụng cụ."
        ),
        inline=False,
    )

    sprinkler_lines = []
    for sid in farm_config.SPRINKLER_ORDER:
        cfg = farm_config.SPRINKLERS[sid]
        have = data.get("sprinkler_inventory", {}).get(sid, 0)
        sprinkler_lines.append(f"**{cfg['name']}** — {cfg['price']}🥭 (có {have} trong kho)")
    embed.add_field(name="💦 Sprinkler", value="\n".join(sprinkler_lines), inline=False)

    view = FarmShopView(guild_id, user_id)
    return embed, view

class FarmShopView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=200)
        self.guild_id = guild_id
        self.user_id = user_id
        self.add_item(FarmShopCategoryDropdown(guild_id, user_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải cửa hàng của bạn.", ephemeral=True)
            return False
        return True

class FarmShopCategoryDropdown(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int):
        self.guild_id = guild_id
        self.user_id = user_id
        options = [
            discord.SelectOption(label="Hạt giống", value="seeds", emoji="🌱"),
            discord.SelectOption(label="Bình tưới", value="cans", emoji="💧"),
            discord.SelectOption(label="Dụng cụ", value="tools", emoji="🔧"),
            discord.SelectOption(label="Sprinkler", value="sprinklers", emoji="💦"),
            discord.SelectOption(label="Mở khoá ô trồng", value="plots", emoji="🗺️"),
        ]
        super().__init__(placeholder="Chọn danh mục để mua...", options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        if category == "seeds":
            embed, view = _build_seed_shop(self.guild_id, self.user_id)
        elif category == "cans":
            embed, view = _build_can_shop(self.guild_id, self.user_id)
        elif category == "tools":
            embed, view = _build_tool_shop(self.guild_id, self.user_id)
        elif category == "plots":
            embed, view = _build_plot_shop(self.guild_id, self.user_id)
        else:
            embed, view = _build_sprinkler_shop(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

# ==================== HẠT GIỐNG ====================
def _build_seed_shop(guild_id: int, user_id: int):
    data = farm_store.get_farm_data(guild_id, user_id)
    mango = farm_store.get_mango(guild_id, user_id)

    embed = discord.Embed(title="🌱 Hạt giống", color=discord.Color.blue())
    embed.add_field(name="🥭 Mango", value=f"{mango}", inline=False)

    view = discord.ui.View(timeout=90)
    for cid in farm_config.CROP_ORDER:
        crop = farm_config.CROPS[cid]
        unlocked = data["unlocked_crops"].get(cid, False)
        have = data.get("seed_inventory", {}).get(cid, 0)
        value_text = "🔒 Chưa mở khoá" if not unlocked else f"{crop['seed_cost']}🥭/hạt — có {have} trong kho"
        embed.add_field(name=crop["name"], value=value_text, inline=False)
        if unlocked:
            view.add_item(_BuySeedBtn(guild_id, user_id, cid, crop["seed_cost"]))
    return embed, view

class _BuySeedBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, crop_id, price):
        super().__init__(
            label=f"Mua 1 hạt {farm_config.CROPS[crop_id]['name']} ({price}🥭)",
            style=discord.ButtonStyle.success,
        )
        self.guild_id = guild_id
        self.user_id = user_id
        self.crop_id = crop_id
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải cửa hàng của bạn.", ephemeral=True)
            return
        def _buy(d):
            d.setdefault("seed_inventory", {})
            d["seed_inventory"][self.crop_id] = d["seed_inventory"].get(self.crop_id, 0) + 1
            return d

        ok, msg = farm_store.spend_mango_and_apply(self.guild_id, self.user_id, self.price, _buy)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed, view = _build_seed_shop(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

def _build_can_shop(guild_id: int, user_id: int):
    data = farm_store.get_farm_data(guild_id, user_id)
    mango = farm_store.get_mango(guild_id, user_id)

    embed = discord.Embed(title="💧 Bình tưới", color=discord.Color.blue())
    embed.add_field(name="🥭 Mango", value=f"{mango}", inline=False)

    view = discord.ui.View(timeout=200)
    for cid, cfg in farm_config.WATERING_CANS.items():
        owned = data["watering_can"] == cid
        lo, hi = cfg["progress_range"]
        price_text = "Đang dùng" if owned else f"{cfg['price']} mango"
        embed.add_field(
            name=cfg["name"],
            value=f"+{lo}-{hi} progress/lần tưới — {price_text}",
            inline=False,
        )
        if not owned:
            view.add_item(_BuyCanBtn(guild_id, user_id, cid, cfg["price"]))
    return embed, view

class _BuyCanBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, can_id, price):
        super().__init__(label=f"Mua {farm_config.WATERING_CANS[can_id]['name']} ({price} mango)", style=discord.ButtonStyle.success)
        self.guild_id = guild_id
        self.user_id = user_id
        self.can_id = can_id
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải cửa hàng của bạn.", ephemeral=True)
            return
        def _buy(d):
            d["watering_can"] = self.can_id
            return d

        ok, msg = farm_store.spend_mango_and_apply(self.guild_id, self.user_id, self.price, _buy)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed, view = _build_can_shop(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

def _build_tool_shop(guild_id: int, user_id: int):
    data = farm_store.get_farm_data(guild_id, user_id)
    mango = farm_store.get_mango(guild_id, user_id)

    embed = discord.Embed(title="🔧 Dụng cụ (Gear)", color=discord.Color.blue())
    embed.add_field(name="🥭 Mango", value=f"{mango}", inline=False)

    view = discord.ui.View(timeout=90)
    for gear_id, cfg in farm_config.GEAR.items():
        owned = data.get("gear", {}).get(gear_id, False)
        price_text = "✅ Đã có" if owned else f"{cfg['price']}🥭"
        embed.add_field(name=cfg["name"], value=f"{cfg['desc']}\n{price_text}", inline=False)
        if not owned:
            view.add_item(_BuyGearBtn(guild_id, user_id, gear_id, cfg["price"]))
    return embed, view

class _BuyGearBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, gear_id, price):
        super().__init__(label=f"Mua {farm_config.GEAR[gear_id]['name']} ({price} mango)", style=discord.ButtonStyle.success)
        self.guild_id = guild_id
        self.user_id = user_id
        self.gear_id = gear_id
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải cửa hàng của bạn.", ephemeral=True)
            return

        def _buy(d):
            d.setdefault("gear", {})
            d["gear"][self.gear_id] = True
            return d

        ok, msg = farm_store.spend_mango_and_apply(self.guild_id, self.user_id, self.price, _buy)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed, view = _build_tool_shop(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

# ==================== MỞ KHOÁ Ô TRỒNG ====================
def _build_plot_shop(guild_id: int, user_id: int):
    import farm_logic
    import economy_store

    data = farm_store.get_farm_data(guild_id, user_id)
    mango = farm_store.get_mango(guild_id, user_id)
    mango_plus = economy_store.get_mango_plus(user_id)

    embed = discord.Embed(title="🗺️ Mở khoá ô trồng", color=discord.Color.dark_teal())
    embed.add_field(name="🥭 Mango", value=f"{mango}", inline=True)
    embed.add_field(name="🥭+ Mango Plus", value=f"{mango_plus}", inline=True)

    unlocked_plots = data.get("unlocked_plots", {})
    view = discord.ui.View(timeout=200)

    for pid in farm_config.PLOT_ORDER:
        unlocked = unlocked_plots.get(str(pid), False)
        cost_info = farm_logic.plot_unlock_cost(pid)
        currency_label = "mango" if cost_info["currency"] == "mango" else "mango+"
        status = "✅ Đã mở khoá" if unlocked else f"{cost_info['cost']} {currency_label}"
        embed.add_field(name=f"Ô {pid}", value=status, inline=True)

    next_plot = farm_logic.next_locked_plot({pid for pid in farm_config.PLOT_ORDER if unlocked_plots.get(str(pid))})
    if next_plot:
        cost_info = farm_logic.plot_unlock_cost(next_plot)
        view.add_item(_BuyPlotBtn(guild_id, user_id, next_plot, cost_info["cost"], cost_info["currency"]))
    else:
        embed.set_footer(text="Bạn đã mở khoá toàn bộ ô trồng!")

    return embed, view

class _BuyPlotBtn(discord.ui.Button):
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
            await interaction.response.send_message("Không phải cửa hàng của bạn.", ephemeral=True)
            return

        def _unlock(d):
            d["unlocked_plots"][str(self.plot_id)] = True
            d["plots"].setdefault(
                str(self.plot_id),
                {"slots": [farm_store._empty_slot() for _ in range(farm_config.SLOTS_PER_PLOT)]},
            )
            return d

        if self.currency == "mango":
            ok, msg = farm_store.spend_mango_and_apply(self.guild_id, self.user_id, self.cost, _unlock)
        else:
            import economy_store
            new_balance = economy_store.transaction_mango_plus(self.user_id, -self.cost)
            if new_balance is None:
                ok, msg = False, "Không đủ mango+."
            else:
                try:
                    farm_store.transaction_farm_data(self.guild_id, self.user_id, _unlock)
                    ok, msg = True, ""
                except Exception:
                    economy_store.transaction_mango_plus(self.user_id, self.cost)
                    ok, msg = False, "Có lỗi xảy ra, giao dịch đã được hoàn tác."

        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed, view = _build_plot_shop(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

def _build_sprinkler_shop(guild_id: int, user_id: int):
    data = farm_store.get_farm_data(guild_id, user_id)
    mango = farm_store.get_mango(guild_id, user_id)

    embed = discord.Embed(title="💦 Sprinkler", color=discord.Color.blue())
    embed.add_field(name="🥭 Mango", value=f"{mango}", inline=False)

    view = discord.ui.View(timeout=90)
    for sid in farm_config.SPRINKLER_ORDER:
        cfg = farm_config.SPRINKLERS[sid]
        embed.add_field(
            name=cfg["name"],
            value=(
                f"+{cfg['progress_boost']} tiến trình/tưới, {cfg['duration_min']}p hiệu lực\n"
                f"Tỉ lệ đột biến ngập nước: {cfg['flood_mutation_chance']*100:.0f}% — Giá {cfg['price']}🥭"
            ),
            inline=False,
        )
        view.add_item(_BuySprinklerBtn(guild_id, user_id, sid, cfg["price"]))
    return embed, view

class _BuySprinklerBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, sprinkler_id, price):
        super().__init__(
            label=f"Mua {farm_config.SPRINKLERS[sprinkler_id]['name']} ({price}🥭)",
            style=discord.ButtonStyle.success,
        )
        self.guild_id = guild_id
        self.user_id = user_id
        self.sprinkler_id = sprinkler_id
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải cửa hàng của bạn.", ephemeral=True)
            return
        def _buy(d):
            d.setdefault("sprinkler_inventory", {})
            d["sprinkler_inventory"][self.sprinkler_id] = d["sprinkler_inventory"].get(self.sprinkler_id, 0) + 1
            return d

        ok, msg = farm_store.spend_mango_and_apply(self.guild_id, self.user_id, self.price, _buy)
        if not ok:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        embed, view = _build_sprinkler_shop(self.guild_id, self.user_id)
        await interaction.response.edit_message(
            content=f"✅ Đã mua **{farm_config.SPRINKLERS[self.sprinkler_id]['name']}**. Kích hoạt trong `/farm`.",
            embed=embed, view=view,
        )

# ==================== BÁN TRÁI (từ inventory) ====================
def build_sell_view_and_embed(guild_id: int, user_id: int):
    data = farm_store.get_farm_data(guild_id, user_id)
    inventory = data.get("inventory", {})
    has_scanner = data.get("gear", {}).get("scanner", False)
    has_plucker = data.get("gear", {}).get("mutation_plucker", False)

    embed = discord.Embed(title="💰 Kho nông sản", color=discord.Color.orange())
    if not inventory:
        embed.description = "Kho trống — chưa có gì để bán."
        return embed, discord.ui.View(timeout=60)

    lines = []
    for key, qty in inventory.items():
        produce, mutations = farm_store.parse_inventory_key(key)
        mut_text = f" ({', '.join(mutations)})" if mutations else ""
        price_text = ""
        if has_scanner:
            value = farm_logic.compute_produce_value(produce, mutations)
            price_text = f"{value} 🥭/trái"
        lines.append(f"**{produce}**{mut_text} x{qty} ({price_text})")
    embed.description = "\n".join(lines)
    if not has_scanner:
        embed.set_footer(text="Mua Kính Lúp ở /shop để xem chính xác giá trái có đột biến.")

    view = discord.ui.View(timeout=200)
    view.add_item(SellItemDropdown(guild_id, user_id, inventory))
    if has_plucker:
        pluckable = {k: v for k, v in inventory.items() if farm_store.parse_inventory_key(k)[1]}
        if pluckable:
            view.add_item(PluckMutationDropdown(guild_id, user_id, pluckable))
    return embed, view

class SellItemDropdown(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int, inventory: dict):
        self.guild_id = guild_id
        self.user_id = user_id
        options = []
        for key, qty in list(inventory.items())[:25]:
            produce, mutations = farm_store.parse_inventory_key(key)
            mut_text = f" ({', '.join(mutations)})" if mutations else ""
            options.append(discord.SelectOption(label=f"{produce}{mut_text} x{qty}"[:100], value=key))
        super().__init__(placeholder="Chọn loại để bán tất cả...", options=options)

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        produce, mutations = farm_store.parse_inventory_key(key)
        value_per_unit = farm_logic.compute_produce_value(produce, mutations)

        data = farm_store.get_farm_data(self.guild_id, self.user_id)
        qty = data.get("inventory", {}).get(key, 0)
        if qty <= 0:
            await interaction.response.send_message("Không còn gì để bán.", ephemeral=True)
            return

        total_mango = value_per_unit * qty
        removed = farm_store.remove_from_inventory(self.guild_id, self.user_id, key, qty)
        if not removed:
            await interaction.response.send_message("Có lỗi khi bán, thử lại.", ephemeral=True)
            return

        farm_store.transaction_mango(self.guild_id, self.user_id, total_mango)

        # cây cao cấp (cam, táo) bán ra thêm mango+ ngoài mango thường
        crop_type = produce.split("_")[0]
        bonus_plus_text = ""
        if crop_type in farm_config.CROPS and farm_config.CROPS[crop_type].get("sells_mango_plus"):
            import economy_store
            plus_gained = max(1, int(total_mango * 0.05))  # 5% giá trị quy đổi thêm sang mango+
            economy_store.transaction_mango_plus(self.user_id, plus_gained)
            bonus_plus_text = f" + **{plus_gained} 🥭+**"

        embed, view = build_sell_view_and_embed(self.guild_id, self.user_id)
        await interaction.response.edit_message(
            content=f"✅ Đã bán {qty}x **{produce}** nhận **{total_mango} mango**{bonus_plus_text}.", embed=embed, view=view
        )

# ==================== Đồ Gắp ====================
class PluckMutationDropdown(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int, pluckable_inventory: dict):
        self.guild_id = guild_id
        self.user_id = user_id
        options = []
        for key, qty in list(pluckable_inventory.items())[:25]:
            produce, mutations = farm_store.parse_inventory_key(key)
            mut_text = f" ({', '.join(mutations)})"
            options.append(discord.SelectOption(label=f"{produce}{mut_text} x{qty}"[:100], value=key))
        super().__init__(placeholder="✂️ Gắp đột biến từ trái nào...", options=options)

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        produce, mutations = farm_store.parse_inventory_key(key)

        view = discord.ui.View(timeout=60)
        view.add_item(PluckChooseMutationDropdown(self.guild_id, self.user_id, key, produce, mutations))
        await interaction.response.send_message(
            f"Chọn đột biến muốn gắp khỏi **{produce}**:", view=view, ephemeral=True
        )

class PluckChooseMutationDropdown(discord.ui.Select):
    def __init__(self, guild_id: int, user_id: int, source_key: str, produce: str, mutations: list[str]):
        self.guild_id = guild_id
        self.user_id = user_id
        self.source_key = source_key
        self.produce = produce
        self.mutations = mutations

        all_mut_cfg = {**farm_config.MUTATIONS_STACKABLE, **farm_config.MUTATIONS_EXCLUSIVE}
        options = [
            discord.SelectOption(label=all_mut_cfg.get(m, {}).get("name", m), value=m)
            for m in mutations
        ]
        super().__init__(placeholder="Chọn 1 đột biến để gắp...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return

        mutation_to_remove = self.values[0]
        remaining_mutations = [m for m in self.mutations if m != mutation_to_remove]

        # gắp = chuyển 1 đơn vị từ key cũ (đủ mutation) sang key mới (thiếu 1 mutation đã gắp).
        removed = farm_store.remove_from_inventory(self.guild_id, self.user_id, self.source_key, 1)
        if not removed:
            await interaction.response.send_message("Trái này không còn trong kho nữa.", ephemeral=True)
            return

        farm_store.add_to_inventory(self.guild_id, self.user_id, self.produce, remaining_mutations, qty=1)

        all_mut_cfg = {**farm_config.MUTATIONS_STACKABLE, **farm_config.MUTATIONS_EXCLUSIVE}
        mut_name = all_mut_cfg.get(mutation_to_remove, {}).get("name", mutation_to_remove)
        await interaction.response.edit_message(
            content=f"✂️ Đã gắp đột biến **{mut_name}** khỏi **{self.produce}**. Đột biến này đã biến mất vĩnh viễn.",
            view=None,
        )