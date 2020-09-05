from typing import Optional

from discord.ext import commands
import discord

from models import Server, Session

session = Session()

SPECLE_MUTED_ROLE_ID = 1035498783

class Mutes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Create muted and unmuted roles, and change existing roles so that only those with the unmuted role can speak and send messages
    async def makeMutedRole(self, ctx):
        muted_role = await ctx.guild.create_role(
            reason="Muted role changes name color to show who is muted.",
            name="Muted",
            colour=discord.Colour(0xff0000))
        # muted role should be positioned as high as the bot can make them (just under the bot's own highest role)
        await muted_role.edit(position=max([role.position for role in ctx.guild.me.roles])-1, reason="Muted role needs to have high precdence to show color")
        # unmued role should be just above @everyone
        return muted_role

    # Create muted and unmuted roles, and change existing roles so that only those with the unmuted role can speak and send messages
    async def makeUnmutedRole(self, ctx):
        # this is the position of the bots highest role. It cannot affect any roles that are higher.
        bot_authority_position = max([role.position for role in ctx.guild.me.roles])
        # remove talking permissions from all existing roles, so that users need the unmuted role to talk
        for role in ctx.guild.roles:
                print(f"{role.name}: {role.position}")
                if role.position < bot_authority_position:
                    # using a bitmask to remove only speaking and message-sending
                    await role.edit(permissions=discord.Permissions(role.permissions.value & 2145384447))
        unmuted_role = await ctx.guild.create_role(
            reason="Unmuted role that the bot needs to work did not previously exist. Users will now be unable to talk without this role.",
            name="Unmuted",
            permissions=discord.Permissions(2099200))
        # unmued role should be just above @everyone
        print(f"About to try to move unmuted role to position {min([role.position for role in ctx.guild.roles])+1}")
        await unmuted_role.edit(position=min([role.position for role in ctx.guild.roles])+1, reason="We don't want unmuted to have precedence over anything")
        return unmuted_role

    @commands.command()
    async def mute(self, ctx, user: discord.Member, reason: Optional[str]):
        server = session.query(Server).filter(Server.server_id == ctx.guild.id).one_or_none()

        # Unknown Server
        if server is None:
            unmuted_role = await self.makeUnmutedRole(ctx)
            muted_role = await self.makeMutedRole(ctx)
            
            # Add the new server, now with new muted and unmuted roles, to the database
            server = Server()
            server.server_id = ctx.guild.id
            server.name = ctx.guild.name
            server.muted_role_id = muted_role.id
            server.unmuted_role_id = unmuted_role.id
            session.add(server)
            session.commit()

        # Known Server
        else:
            unmuted_role = ctx.guild.get_role(server.unmuted_role_id)
            muted_role = ctx.guild.get_role(server.muted_role_id)
            if unmuted_role is None:
                print(f"The server {server.name} deleted their unmuted role. Now we have to make a new one >:(.")
                muted_role = await self.makeUnmutedRole(ctx)
                server.unmuted_role_id = muted_role.id
                session.commit()
            if muted_role is None:
                print(f"The server {server.name} deleted their muted role. Now we have to make a new one >:(.")
                muted_role = await self.makeMutedRole(ctx)
                server.muted_role_id = muted_role.id
                session.commit()
            
        # Add the muted role to the user
        await user.add_roles(muted_role, reason=reason if not (reason is None) else "Goka")
        await user.remove_roles(unmuted_role, reason=reason if not (reason is None) else "Goka")
            