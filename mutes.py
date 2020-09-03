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

        # muted role should have the priority just under the bot's highest permission, shifting other roles down as necessary
        bot_authority_position = max([role.position for role in ctx.guild.me.roles])
        role_position_updates = {role:role.position-1 for role in ctx.guild.roles if (muted_role.position < role.position and role.position < bot_authority_position)}
        role_position_updates[muted_role] = max([role.position for role in ctx.guild.me.roles])-1
        await ctx.guild.edit_role_positions(role_position_updates, reason="Muted role needs to have high precdence to show color")

        return muted_role

    # Create muted and unmuted roles, and change existing roles so that only those with the unmuted role can speak and send messages
    async def makeUnmutedRole(self, ctx):
        # this is the position of the bots highest role. It cannot affect any roles that are higher.
        bot_authority_position = max([role.position for role in ctx.guild.me.roles])
        # remove talking permissions from all existing roles, so that users need the unmuted role to talk
        for role in ctx.guild.roles:
                if role.position < bot_authority_position:
                    # using a bitmask to remove only speaking and message-sending
                    await role.edit(permissions=discord.Permissions(role.permissions.value & 2145384447))
        unmuted_role = await ctx.guild.create_role(
            reason="Unmuted role that the bot needs to work did not previously exist. Users will now be unable to talk without this role.",
            name="Unmuted",
            permissions=discord.Permissions(2099200))

        # unmued role should be just above @everyone
        await unmuted_role.edit(position=min([role.position for role in ctx.guild.roles])+1, reason="We don't want unmuted to have precedence over anything")

        # give everyone the unmuted role
        for member in ctx.guild.members:
            await member.add_roles(
                unmuted_role,
                reason="Assigning unmuted role to everyone. Users will no longer be able to speak or message unless they have this role, though this can be overwritten by channel-specific settings."
            )
        return unmuted_role

    async def getMutedRoles(self, ctx, server):
        unmuted_role = ctx.guild.get_role(server.unmuted_role_id)
        muted_role = ctx.guild.get_role(server.muted_role_id)
        if unmuted_role is None:
            print(f"The server {server.name} deleted their unmuted role. Now we have to make a new one >:(.")
            unmuted_role = await self.makeUnmutedRole(ctx)
            server.unmuted_role_id = unmuted_role.id
            session.commit()
        if muted_role is None:
            print(f"The server {server.name} deleted their muted role. Now we have to make a new one >:(.")
            muted_role = await self.makeMutedRole(ctx)
            server.muted_role_id = muted_role.id
            session.commit()

        return (unmuted_role, muted_role)

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
            unmuted_role, muted_role = await self.getMutedRoles(ctx, server)
            
        # Add the muted role to the user and remove the unmuted role (but only if necessary)
        if not (muted_role in user.roles):
            await user.add_roles(muted_role, reason=reason if not (reason is None) else "Goka")
        if unmuted_role in user.roles:
            await user.remove_roles(unmuted_role, reason=reason if not (reason is None) else "Goka")
        
        if reason is None:
            await ctx.send(f"{user.nick} was muted by {ctx.author.nick}")
        else:
            await ctx.send(f"{user.nick} was muted by {ctx.author.nick} because {reason}")

    @commands.command()
    async def unmute(self, ctx, user: discord.Member):
        server = session.query(Server).filter(Server.server_id == ctx.guild.id).one_or_none()

        # Unknown Server
        if server is None:
            print("Tried to unmute somebody but literally nobody has ever been muted on this server")
            await ctx.send("You can't unmute somebody when nobody has ever been muted on this server before.")
            return

        unmuted_role, muted_role = await self.getMutedRoles(ctx, server)

        # Add the muted role to the user and remove the unmuted role (but only if necessary)
        if not (unmuted_role in user.roles):
            await user.add_roles(unmuted_role)
        if muted_role in user.roles:
            await user.remove_roles(muted_role)

        await ctx.send(f"{user.nick} was unmuted by {ctx.author.nick}")