import discord
from discord.ext import commands
from quotes import Quotes
from modrole import ModRoles
from mutes import Mutes
from aliases import Aliases
from models import Alias, Session

client = commands.Bot(command_prefix="*")
session = Session()

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        msg = ctx.message.content[1:]
        words = msg.split(' ')
        cmd = words[0]
        args = words[1:]
        aliased_command = session.query(Alias).filter(Alias.server_id == ctx.guild.id, Alias.alias == cmd).one_or_none()
        if not (aliased_command is None):
            new_msg = ' '.join([aliased_command.command] + args)
            ctx.message.content = new_msg
            await client.get_command(aliased_command.command).invoke(ctx)
        elif '*' in msg:
            # This was just someone using italics
            return
        else:
            await ctx.send(f"Unrecognized command: '{cmd}'")
    else:
        raise error

client.add_cog(Quotes(client))
client.add_cog(ModRoles(client))
client.add_cog(Mutes(client))
client.add_cog(Aliases(client))
