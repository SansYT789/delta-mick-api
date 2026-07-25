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
            tag = f"{crop['seed_cost']} mango/hạt (có {have})"
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

    scanner_owned = data["tools"].get("scanner", False)
    plucker_owned = data["tools"].get("mutation_plucker", False)
    embed.add_field(
        name="🔧 Dụng cụ",
        value=(
            f"**Kính lúp** — {'✅ Đã có' if scanner_owned else f'{farm_config.TOOL_PRICE_SCANNER} mango'}\n"
            f"**Đồ gắp** — {'✅ Đã có' if plucker_owned else f'{farm_config.TOOL_MUTATION_PLUCKER} mango'}"
        ),
        inline=False,
    )

    sprinkler_lines = []
    for sid in farm_config.SPRINKLER_ORDER:
        cfg = farm_config.SPRINKLERS[sid]
        have = data.get("sprinkler_inventory", {}).get(sid, 0)
        sprinkler_lines.append(f"**{cfg['name']}** — {cfg['price']} mango (có {have} trong kho)")
    embed.add_field(name="💦 Sprinkler", value="\n".join(sprinkler_lines), inline=False)

    view = FarmShopView(guild_id, user_id)
    return embed, view


class FarmShopView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=90)
        self.guild_id = guild_id
        self.user_id = user_id
        self.add_item(FarmShopCategoryDropdown(guild_id, user_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
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
        value_text = "🔒 Chưa mở khoá" if not unlocked else f"{crop['seed_cost']} mango/hạt — có {have} trong kho"
        embed.add_field(name=crop["name"], value=value_text, inline=False)
        if unlocked:
            view.add_item(_BuySeedBtn(guild_id, user_id, cid, crop["seed_cost"]))
    return embed, view


class _BuySeedBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, crop_id, price):
        super().__init__(
            label=f"Mua 1 hạt {farm_config.CROPS[crop_id]['name']} ({price} mango)",
            style=discord.ButtonStyle.success,
        )
        self.guild_id = guild_id
        self.user_id = user_id
        self.crop_id = crop_id
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return
        mango = farm_store.get_mango(self.guild_id, self.user_id)
        if mango < self.price:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return
        new_balance = farm_store.transaction_mango(self.guild_id, self.user_id, -self.price)
        if new_balance is None:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return

        def _buy(d):
            d.setdefault("seed_inventory", {})
            d["seed_inventory"][self.crop_id] = d["seed_inventory"].get(self.crop_id, 0) + 1
            return d

        farm_store.transaction_farm_data(self.guild_id, self.user_id, _buy)
        embed, view = _build_seed_shop(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)



def _build_can_shop(guild_id: int, user_id: int):
    data = farm_store.get_farm_data(guild_id, user_id)
    mango = farm_store.get_mango(guild_id, user_id)

    embed = discord.Embed(title="💧 Bình tưới", color=discord.Color.blue())
    embed.add_field(name="🥭 Mango", value=f"{mango}", inline=False)

    view = discord.ui.View(timeout=90)
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
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return
        mango = farm_store.get_mango(self.guild_id, self.user_id)
        if mango < self.price:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return
        new_balance = farm_store.transaction_mango(self.guild_id, self.user_id, -self.price)
        if new_balance is None:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return

        def _buy(d):
            d["watering_can"] = self.can_id
            return d

        farm_store.transaction_farm_data(self.guild_id, self.user_id, _buy)
        embed, view = _build_can_shop(self.guild_id, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)


def _build_tool_shop(guild_id: int, user_id: int):
    data = farm_store.get_farm_data(guild_id, user_id)
    mango = farm_store.get_mango(guild_id, user_id)

    embed = discord.Embed(title="🔧 Dụng cụ", color=discord.Color.blue())
    embed.add_field(name="🥭 Mango", value=f"{mango}", inline=False)
    embed.add_field(
        name="Kính lúp",
        value="Xem giá thị trường chính xác của bất kỳ trái nào trong kho.",
        inline=False,
    )
    embed.add_field(
        name="Đồ gắp",
        value="Gỡ bỏ 1 mutation cụ thể khỏi trái (trái mất mutation đó vĩnh viễn, không đổi sang mutation khác).",
        inline=False,
    )

    view = discord.ui.View(timeout=90)
    if not data["tools"].get("scanner"):
        view.add_item(_BuyToolBtn(guild_id, user_id, "scanner", farm_config.TOOL_PRICE_SCANNER, "Mua Soi giá"))
    if not data["tools"].get("mutation_plucker"):
        view.add_item(_BuyToolBtn(guild_id, user_id, "mutation_plucker", farm_config.TOOL_MUTATION_PLUCKER, "Mua Gắp đột biến"))
    return embed, view


class _BuyToolBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, tool_key, price, label):
        super().__init__(label=f"{label} ({price} mango)", style=discord.ButtonStyle.success)
        self.guild_id = guild_id
        self.user_id = user_id
        self.tool_key = tool_key
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return
        mango = farm_store.get_mango(self.guild_id, self.user_id)
        if mango < self.price:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return
        new_balance = farm_store.transaction_mango(self.guild_id, self.user_id, -self.price)
        if new_balance is None:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return

        def _buy(d):
            d["tools"][self.tool_key] = True
            return d

        farm_store.transaction_farm_data(self.guild_id, self.user_id, _buy)
        embed, view = _build_tool_shop(self.guild_id, self.user_id)
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
                f"+{cfg['progress_boost']} progress/tưới, {cfg['duration_min']}p hiệu lực\n"
                f"Tỉ lệ đột biến ngập nước: {cfg['flood_mutation_chance']*100:.0f}% — {cfg['price']} mango"
            ),
            inline=False,
        )
        view.add_item(_BuySprinklerBtn(guild_id, user_id, sid, cfg["price"]))
    return embed, view


class _BuySprinklerBtn(discord.ui.Button):
    def __init__(self, guild_id, user_id, sprinkler_id, price):
        super().__init__(
            label=f"Mua {farm_config.SPRINKLERS[sprinkler_id]['name']} ({price} mango)",
            style=discord.ButtonStyle.success,
        )
        self.guild_id = guild_id
        self.user_id = user_id
        self.sprinkler_id = sprinkler_id
        self.price = price

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Không phải phiên của bạn.", ephemeral=True)
            return
        mango = farm_store.get_mango(self.guild_id, self.user_id)
        if mango < self.price:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return
        new_balance = farm_store.transaction_mango(self.guild_id, self.user_id, -self.price)
        if new_balance is None:
            await interaction.response.send_message("Không đủ mango.", ephemeral=True)
            return

        def _buy(d):
            d.setdefault("sprinkler_inventory", {})
            d["sprinkler_inventory"][self.sprinkler_id] = d["sprinkler_inventory"].get(self.sprinkler_id, 0) + 1
            return d

        farm_store.transaction_farm_data(self.guild_id, self.user_id, _buy)
        embed, view = _build_sprinkler_shop(self.guild_id, self.user_id)
        await interaction.response.edit_message(
            content=f"✅ Đã mua **{farm_config.SPRINKLERS[self.sprinkler_id]['name']}**. Kích hoạt trong `/farm`.",
            embed=embed, view=view,
        )


# ==================== BÁN TRÁI (từ inventory) ====================

def build_sell_view_and_embed(guild_id: int, user_id: int):
    data = farm_store.get_farm_data(guild_id, user_id)
    inventory = data.get("inventory", {})
    has_scanner = data.get("tools", {}).get("scanner", False)
    has_plucker = data.get("tools", {}).get("mutation_plucker", False)

    embed = discord.Embed(title="💰 Kho nông sản", color=discord.Color.orange())
    if not inventory:
        embed.description = "Kho trống — chưa có gì để bán."
        return embed, discord.ui.View(timeout=90)

    lines = []
    for key, qty in inventory.items():
        produce, mutations = farm_store.parse_inventory_key(key)
        mut_text = f" ({', '.join(mutations)})" if mutations else ""
        if has_scanner:
            value = farm_logic.compute_produce_value(produce, mutations)
            price_text = f"{value} mango/trái"
        else:
            base = farm_config.PRODUCE_PRICES.get(produce, 0)
            price_text = f"~{base} mango/trái (giá chính xác cần Soi giá)" if mutations else f"{base} mango/trái"
        lines.append(f"**{produce}**{mut_text} x{qty} — {price_text}")
    embed.description = "\n".join(lines)
    if not has_scanner:
        embed.set_footer(text="Mua Soi giá ở /shop để xem chính xác giá trái có đột biến.")

    view = discord.ui.View(timeout=90)
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
        for key, qty in list(inventory.items())[:25]:  # Discord giới hạn 25 option
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

        total = value_per_unit * qty
        removed = farm_store.remove_from_inventory(self.guild_id, self.user_id, key, qty)
        if not removed:
            await interaction.response.send_message("Có lỗi khi bán, thử lại.", ephemeral=True)
            return

        farm_store.transaction_mango(self.guild_id, self.user_id, total)

        embed, view = build_sell_view_and_embed(self.guild_id, self.user_id)
        await interaction.response.edit_message(
            content=f"✅ Đã bán {qty}x **{produce}** nhận **{total} mango**.", embed=embed, view=view
        )


# ==================== GẮP ĐỘT BIẾN ====================

class PluckMutationDropdown(discord.ui.Select):
    """Bước 1: chọn trái (có mutation) muốn gắp bớt."""

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
    """Bước 2: chọn đúng 1 mutation trong trái đó để gỡ bỏ."""

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
        # Mutation bị gắp MẤT VĨNH VIỄN — không cộng vào đâu khác, không đổi sang mutation khác
        # (đúng yêu cầu: tránh lạm phát đột biến nếu gắp rồi tái sử dụng).
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
