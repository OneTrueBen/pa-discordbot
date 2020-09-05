from discord.ext import commands
import discord

from models import Server, Session

session = Session()

SPECLE_MUTED_ROLE_ID = 1035498783

class Mutes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def mute(self, ctx, *args):
        if len(args) < 1:
            return
        user: discord.Member = args[0]
        server = session.query(Server).filter(Server.server_id == ctx.guild.id).one_or_none()

        # Unknown Server
        if server is None:
            # Create a muted role on this new server and move it to the top of the priority list
            muted_role = await ctx.guild.create_role(reason="Muted role that the bot needs to work did not previously exist.", name="Muted", colour=discord.Colour(0xff0000))
            await muted_role.edit(position=1, reason="Muted role needs to have high precdence to work")

            # Add the new server, now with a muted role, to the database
            server = Server()
            server.server_id = ctx.guild.id
            server.name = ctx.guild.name
            server.muted_role_id = muted_role.id
            session.add(server)
            session.commit()

        # Known Server
        else:
            muted_role = ctx.guild.get_role(server.muted_role_id)
            if muted_role is None:
                print(f"The server {server.name} deleted their muted role. Now we have to make a new one >:(.")
                muted_role = await ctx.guild.create_role(reason="Muted role that the bot needs to work did not previously exist.", name="Muted", colour=discord.Colour(0xff0000))
                await muted_role.edit(position=1, reason="Muted role needs to have high precdence to work")
                server.muted_role_id = muted_role.id
                session.commit()

        # Add the muted role to the user
        await user.add_roles(muted_role, reason=args[1] if len(args)>0 else "Goka")
            