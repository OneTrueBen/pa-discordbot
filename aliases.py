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
            await ctx.send(f"'{original_command}' is not the name of a command, so you cannot add an alias to it")
            return
        elif not (self.bot.get_command(new_alias) is None):
            await ctx.send(f"'{new_alias}' is already a command. You cannot use it as an alias.")
            return
        else:
            existing_alias = session.query(Alias).filter(Alias.alias == new_alias).one_or_none()
            if existing_alias is None:
                # We actually create the new alias
                alias_record = Alias()
                alias_record.server_id = ctx.guild.id
                alias_record.command = original_command
                alias_record.alias = new_alias
                session.add(alias_record)
                session.commit()
                
                await ctx.send(f"Added alias '{new_alias}' for command '{original_command}'")
            else:
                await ctx.send(f"'{new_alias}' already exists as an alias for command '{existing_alias.command}'")
            

    @commands.command()
    @mod_only()
    async def removealias(self, ctx, alias_to_remove: str):
        # there should only ever be one, but just in case we'll wipe all matching aliases.
        for alias_record in session.query(Alias).filter(Alias.alias == alias_to_remove).all():
            await ctx.send(f"Removed alias '{alias_to_remove}' for command '{alias_record.command}'")
            session.delete(alias_record)
        session.commit()

        