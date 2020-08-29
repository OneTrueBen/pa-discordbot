from discord.ext import commands
import discord

SPECLE_MUTED_ROLE_ID = 1035498783

class Mutes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def mute(self, ctx, user: discord.Member):
        muted_role = ctx.guild.get_role(SPECLE_MUTED_ROLE_ID)
        if muted_role is None:
            await ctx.guild.create_role(reason="Muted role that the bot needs to work did not previously exist.", name="Muted", colour=discord.Colour(0xff0000))
            muted_role = ctx.guild.get_role(SPECLE_MUTED_ROLE_ID)
        await add_roles()