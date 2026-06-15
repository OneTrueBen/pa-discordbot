import discord
from discord.ext import commands
from quotes import Quotes
from modrole import ModRoles
from mutes import Mutes
from ranked_polls import RankedChoicePolls
from models import Session

intents = discord.Intents.default()
intents.members = True


client = commands.Bot(command_prefix="*", intents=intents)
session = Session()

@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')
    
    # Sync application commands
    try:
        synced = await client.tree.sync()
        print(f'Synced {len(synced)} application commands')
    except Exception as e:
        print(f'Error syncing commands: {e}')

# Remove on_command_error handler as slash commands use interaction.response

async def setup_cogs():
    await client.add_cog(Quotes(client))
    await client.add_cog(ModRoles(client))
    await client.add_cog(Mutes(client))
    await client.add_cog(RankedChoicePolls(client))

client.setup_cogs = setup_cogs
