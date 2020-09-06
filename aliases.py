from discord.ext import commands
import discord

from models import Alias, Session
from modrole import mod_only

session = Session()

class Aliases(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @mod_only()
    async def alias(self, ctx, original_command: str, new_alias: str):
        command = self.bot.get_command(original_command)
        if command is None:
            await ctx.send(f"{original_command} is not the name of a command, so you cannot add an alias to it")
            return
        else:
            alias_record = Alias()
            alias_record.server_id = ctx.guild.id
            alias_record.command = original_command
            alias_record.alias = new_alias
            session.add(alias_record)
            session.commit()
            
            await ctx.send(f"Added alias '{new_alias}' for command '{original_command}'")