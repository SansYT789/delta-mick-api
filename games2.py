import discord
import re
from discord.ext import commands

class AutoBanNuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.NUKE_BOT_ID = 1529927693313769654
        
        self.BAD_CHANNEL_PATTERNS = [
            r'「.*?」.*?𝑯𝒊𝒅𝒅𝒆𝒏',
            r'maya',
            r'nuke',
        ]
        
        self.BAD_EMOJI_PATTERNS = [
            r'hidden',
            r'maya',
            r'nuke',
        ]
        
        self.BAD_MESSAGE_PATTERNS = [
            r'Nuke By Hidden',
            r'discord\.gg/onlyfann',
            r'discord\.gg/.*nuke',
            r'@everyone.*nuke',
            r'nuke.*server',
            r'🔨.*nuke',
            r'💀.*nuke',
        ]
        
        self.BAD_EVENT_PATTERNS = [
            r'hidden',
            r'maya',
            r'nuke',
            r'raid',
            r'@everyone',
        ]
        
        self.BAD_AUTOMOD_PATTERNS = [
            r'Hidden On The Top',
            r'hidden',
            r'maya',
            r'nuke',
            r'raid',
        ]

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.id == self.NUKE_BOT_ID and member.bot:
            guild = member.guild
            
            try:
                await guild.ban(member, reason="Bot nuke", delete_message_days=7)
                await guild.unban(member, reason="Ban complete")
                print(f"✅ Đã softban {member.name} tại {guild.name}")
            except Exception as e:
                print(f"❌ Lỗi ban: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        for pattern in self.BAD_CHANNEL_PATTERNS:
            if re.search(pattern, channel.name, re.IGNORECASE):
                try:
                    await channel.delete(reason="Auto-delete kênh bot nuke")
                    print(f"🗑️ Đã xóa kênh: {channel.name}")
                except:
                    pass

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        new_emojis = [emoji for emoji in after if emoji not in before]
        
        for emoji in new_emojis:
            for pattern in self.BAD_EMOJI_PATTERNS:
                if re.search(pattern, emoji.name, re.IGNORECASE):
                    try:
                        await guild.delete_emoji(emoji)
                        print(f"🗑️ Đã xóa emoji: {emoji.name} (ID: {emoji.id})")
                    except discord.Forbidden:
                        print(f"❌ Không có quyền xóa emoji {emoji.name}")
                    except Exception as e:
                        print(f"❌ Lỗi xóa emoji {emoji.name}: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        
        if message.author.guild_permissions.administrator:
            return
        
        for pattern in self.BAD_MESSAGE_PATTERNS:
            if re.search(pattern, message.content, re.IGNORECASE):
                try:
                    await message.delete()
                    print(f"🗑️ Đã xóa tin nhắn spam từ {message.author}: {message.content[:50]}...")
                    
                    warn_msg = await message.channel.send(
                        f"⚠️ Tin nhắn của {message.author.mention} đã bị xóa do chứa nội dung spam/nuke!"
                    )
                    await warn_msg.delete(delay=5)
                    
                    if message.author.bot:
                        try:
                            await message.author.ban(reason="Bot spam/nuke", delete_message_days=1)
                            print(f"✅ Đã ban bot spam: {message.author}")
                        except:
                            pass
                except Exception as e:
                    print(f"❌ Lỗi xóa tin nhắn: {e}")

    @commands.Cog.listener()
    async def on_scheduled_event_create(self, event):
        for pattern in self.BAD_EVENT_PATTERNS:
            if re.search(pattern, event.name, re.IGNORECASE):
                try:
                    await event.delete()
                    print(f"🗑️ Đã xóa sự kiện: {event.name} (tạo bởi {event.creator})")
                    
                    if event.creator and event.creator.bot:
                        try:
                            await event.guild.ban(event.creator, reason="Bot tạo sự kiện nuke", delete_message_days=1)
                            print(f"✅ Đã ban bot tạo sự kiện: {event.creator}")
                        except:
                            pass
                except discord.Forbidden:
                    print(f"❌ Không có quyền xóa sự kiện {event.name}")
                except Exception as e:
                    print(f"❌ Lỗi xóa sự kiện {event.name}: {e}")

    @commands.Cog.listener()
    async def on_automod_rule_create(self, rule):
        for pattern in self.BAD_AUTOMOD_PATTERNS:
            if re.search(pattern, rule.name, re.IGNORECASE):
                try:
                    await rule.delete(reason="Auto-delete AutoMod rule từ bot nuke")
                    print(f"🗑️ Đã xóa AutoMod rule: {rule.name} (tạo bởi {rule.creator_id})")

                    if rule.creator_id:
                        creator = rule.guild.get_member(rule.creator_id)
                        if creator and creator.bot:
                            try:
                                await rule.guild.ban(creator, reason="Bot tạo AutoMod rule nuke", delete_message_days=1)
                                print(f"✅ Đã ban bot tạo AutoMod: {creator}")
                            except:
                                pass
                except discord.Forbidden:
                    print(f"❌ Không có quyền xóa AutoMod rule {rule.name}")
                except Exception as e:
                    print(f"❌ Lỗi xóa AutoMod rule {rule.name}: {e}")

    @commands.command(name='add_pattern')
    @commands.has_permissions(administrator=True)
    async def add_pattern(self, ctx, target: str, *, pattern: str):
        try:
            re.compile(pattern)
            
            if target.lower() == 'channel':
                self.BAD_CHANNEL_PATTERNS.append(pattern)
                await ctx.send(f"✅ Đã thêm pattern cho KÊNH: `{pattern}`")
            elif target.lower() == 'emoji':
                self.BAD_EMOJI_PATTERNS.append(pattern)
                await ctx.send(f"✅ Đã thêm pattern cho EMOJI: `{pattern}`")
            elif target.lower() == 'message':
                self.BAD_MESSAGE_PATTERNS.append(pattern)
                await ctx.send(f"✅ Đã thêm pattern cho TIN NHẮN: `{pattern}`")
            elif target.lower() == 'event':
                self.BAD_EVENT_PATTERNS.append(pattern)
                await ctx.send(f"✅ Đã thêm pattern cho SỰ KIỆN: `{pattern}`")
            elif target.lower() == 'automod':
                self.BAD_AUTOMOD_PATTERNS.append(pattern)
                await ctx.send(f"✅ Đã thêm pattern cho AUTOMOD: `{pattern}`")
            else:
                await ctx.send("❌ target phải là `channel`, `emoji`, `message`, `event` hoặc `automod`")
        except re.error:
            await ctx.send(f"❌ Pattern regex không hợp lệ!")

    @commands.command(name='list_patterns')
    @commands.has_permissions(administrator=True)
    async def list_patterns(self, ctx):
        channel_patterns = '\n'.join(self.BAD_CHANNEL_PATTERNS) or "(trống)"
        emoji_patterns = '\n'.join(self.BAD_EMOJI_PATTERNS) or "(trống)"
        message_patterns = '\n'.join(self.BAD_MESSAGE_PATTERNS) or "(trống)"
        event_patterns = '\n'.join(self.BAD_EVENT_PATTERNS) or "(trống)"
        automod_patterns = '\n'.join(self.BAD_AUTOMOD_PATTERNS) or "(trống)"
        
        embed = discord.Embed(title="📋 Danh sách Pattern Auto-Delete", color=discord.Color.blue())
        embed.add_field(name="Kênh", value=f"```{channel_patterns}```", inline=False)
        embed.add_field(name="Emoji", value=f"```{emoji_patterns}```", inline=False)
        embed.add_field(name="Tin nhắn", value=f"```{message_patterns}```", inline=False)
        embed.add_field(name="Sự kiện", value=f"```{event_patterns}```", inline=False)
        embed.add_field(name="AutoMod", value=f"```{automod_patterns}```", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='remove_pattern')
    @commands.has_permissions(administrator=True)
    async def remove_pattern(self, ctx, target: str, index: int):
        try:
            if target.lower() == 'channel':
                if 0 <= index < len(self.BAD_CHANNEL_PATTERNS):
                    removed = self.BAD_CHANNEL_PATTERNS.pop(index)
                    await ctx.send(f"✅ Đã xóa pattern KÊNH: `{removed}`")
                else:
                    await ctx.send("❌ Index không hợp lệ!")
            elif target.lower() == 'emoji':
                if 0 <= index < len(self.BAD_EMOJI_PATTERNS):
                    removed = self.BAD_EMOJI_PATTERNS.pop(index)
                    await ctx.send(f"✅ Đã xóa pattern EMOJI: `{removed}`")
                else:
                    await ctx.send("❌ Index không hợp lệ!")
            elif target.lower() == 'message':
                if 0 <= index < len(self.BAD_MESSAGE_PATTERNS):
                    removed = self.BAD_MESSAGE_PATTERNS.pop(index)
                    await ctx.send(f"✅ Đã xóa pattern TIN NHẮN: `{removed}`")
                else:
                    await ctx.send("❌ Index không hợp lệ!")
            elif target.lower() == 'event':
                if 0 <= index < len(self.BAD_EVENT_PATTERNS):
                    removed = self.BAD_EVENT_PATTERNS.pop(index)
                    await ctx.send(f"✅ Đã xóa pattern SỰ KIỆN: `{removed}`")
                else:
                    await ctx.send("❌ Index không hợp lệ!")
            elif target.lower() == 'automod':
                if 0 <= index < len(self.BAD_AUTOMOD_PATTERNS):
                    removed = self.BAD_AUTOMOD_PATTERNS.pop(index)
                    await ctx.send(f"✅ Đã xóa pattern AUTOMOD: `{removed}`")
                else:
                    await ctx.send("❌ Index không hợp lệ!")
            else:
                await ctx.send("❌ target phải là `channel`, `emoji`, `message`, `event` hoặc `automod`")
        except Exception as e:
            await ctx.send(f"❌ Lỗi: {e}")

    @commands.command(name='clear_all_events')
    @commands.has_permissions(administrator=True)
    async def clear_all_events(self, ctx):
        guild = ctx.guild
        events = await guild.fetch_scheduled_events()
        
        if not events:
            await ctx.send("📭 Server không có sự kiện nào.")
            return
        
        deleted = 0
        for event in events:
            try:
                await event.delete()
                deleted += 1
            except:
                pass
        
        await ctx.send(f"🗑️ Đã xóa {deleted}/{len(events)} sự kiện.")

    @commands.command(name='clear_all_automod')
    @commands.has_permissions(administrator=True)
    async def clear_all_automod(self, ctx):
        guild = ctx.guild
        
        try:
            rules = await guild.fetch_automod_rules()
        except:
            await ctx.send("❌ Bot không có quyền xem AutoMod rules!")
            return
        
        if not rules:
            await ctx.send("📭 Server không có AutoMod rule nào.")
            return
        
        deleted = 0
        for rule in rules:
            try:
                await rule.delete()
                deleted += 1
            except:
                pass
        
        await ctx.send(f"🗑️ Đã xóa {deleted}/{len(rules)} AutoMod rule.")

    @commands.command(name='toggle_message_auto_delete')
    @commands.has_permissions(administrator=True)
    async def toggle_message_auto_delete(self, ctx):
        if not hasattr(self, 'message_auto_delete_enabled'):
            self.message_auto_delete_enabled = True
        
        self.message_auto_delete_enabled = not self.message_auto_delete_enabled
        status = "BẬT" if self.message_auto_delete_enabled else "TẮT"
        await ctx.send(f"✅ Auto-delete tin nhắn đã {status}")

async def setup(bot):
    await bot.add_cog(AutoBanNuke(bot))