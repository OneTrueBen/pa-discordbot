from typing import Optional
from datetime import datetime, timedelta
from threading import Timer
import asyncio

from discord.ext import commands
import discord

from models import Server, Mute, Session

session = Session()

SPECLE_MUTED_ROLE_ID = 1035498783

class Mutes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # discord API is dumb so we need to manually suppress role events we caused ourselves (why can't I just see the author of the edit)
        self.suppress_role_update_events = False

        # a dictionary of member id -> pending unmute tasks so that we can avoid double-unmuting
        self.pending_unmutes = {}

    # GENERAL NOTE: we use "guild" to refer to the discord API's model of a guild/server and "server" to refer to our own server info as stored in the db

    @commands.command()
    async def mute(self, ctx, user: discord.Member, time_amount: int, time_units: str, reason: Optional[str]):
        if user.id in self.pending_unmutes:
            await ctx.send(f"{user.display_name} is already muted!")
            return

        time_units = time_units.lower()
        if time_units == 'seconds':
            duration_in_seconds = time_amount
        elif time_units == 'minutes':
            duration_in_seconds = time_amount * 60
        elif time_units == 'hours':
            duration_in_seconds = time_amount * 360
        else:
            await ctx.send("Invalid time unit. Please use seconds, minutes, or hours.")
            return

        expiration_time = datetime.now() + timedelta(seconds=duration_in_seconds)

        if len(session.query(Mute).filter(Mute.muted_id == user.id).all()) > 0:
            await ctx.send(f"{user.display_name} is already muted.")
            return

        server = await self.getServerFromGuild(ctx.guild)
        unmuted_role, muted_role = await self.getMutedRoles(ctx.guild, server)
            
        # Add a record of the mute to the database
        mute_record = Mute()
        mute_record.server_id = ctx.guild.id
        mute_record.muted_id = user.id
        mute_record.muter_id = ctx.author.id
        mute_record.expiration_time = expiration_time
        mute_record.channel_id = ctx.channel.id
        session.add(mute_record)
        session.commit()

        # Add the muted role to the user and remove the unmuted role (but only if necessary)
        if not (muted_role in user.roles):
            await user.add_roles(muted_role, reason=reason if not (reason is None) else "Goka")
        if unmuted_role in user.roles:
            await user.remove_roles(unmuted_role, reason=reason if not (reason is None) else "Goka")
        
        # Send confirmation message
        if reason is None:
            await ctx.send(f"{user.display_name} was muted by {ctx.author.display_name}")
        else:
            await ctx.send(f"{user.display_name} was muted by {ctx.author.display_name} because {reason}")

        # Schedule the user to be unmuted
        unmute_task = self.bot.loop.create_task(self.timedUnmute(user, ctx.author, ctx.guild.id, ctx.channel, duration_in_seconds), name=f"unmute {user.display_name}")
        self.pending_unmutes[user.id] = unmute_task

    # the guts of the unmute command, which has a couple different wrappers
    async def unmuteLogic(self, unmuted, unmuter, server_id, channel):
        # if there was an unmute pending for this user, cancel it 
        if unmuted.id in self.pending_unmutes:
            pending_unmute = self.pending_unmutes.pop(unmuted.id)
            pending_unmute.cancel()

        server = session.query(Server).filter(Server.server_id == server_id).one_or_none()

        # Unknown Server
        if server is None:
            print("Tried to unmute somebody but literally nobody has ever been muted on this server")
            await channel.send("You can't unmute somebody when nobody has ever been muted on this server before.")
            return

        unmuted_role, muted_role = await self.getMutedRoles(self.bot.get_guild(server_id), server)

        # Remove mute record from the database. There should only ever be one, but we'll get rid of all of them just in case.
        mute_records = session.query(Mute).filter(Mute.muted_id == unmuted.id).all()
        for record in mute_records:
            session.delete(record)
        session.commit()

        # Add the muted role to the user and remove the unmuted role (but only if necessary)
        if not (unmuted_role in unmuted.roles):
            await unmuted.add_roles(unmuted_role)
        if muted_role in unmuted.roles:
            await unmuted.remove_roles(muted_role)

        
        await channel.send(f"{unmuted.display_name} was unmuted by {unmuter.display_name}")

    # the unmute command itself, which pulls the info for the unmute primarily from the context
    @commands.command()
    async def unmute(self, ctx, user: discord.Member):
        await self.unmuteLogic(user, ctx.author, ctx.guild.id, ctx.channel)

    # A little wrapper of a wrapper that allows us to use unmute with threading timers
    async def timedUnmute(self, unmuted, unmuter, server_id, channel, delay_in_seconds):
        await asyncio.sleep(delay_in_seconds)
        await self.unmuteLogic(unmuted, unmuter, server_id, channel)

    @commands.Cog.listener()
    async def on_ready(self):
        # Resume all of our mute timers and account for those that should have gone off while we were shut down
        current_time = datetime.now()
        for mute_record in session.query(Mute).all():
            guild = self.bot.get_guild(mute_record.server_id)
            unmuted = guild.get_member(mute_record.muted_id)
            unmuter = guild.get_member(mute_record.muter_id)
            channel = guild.get_channel(mute_record.channel_id)

            if mute_record.expiration_time < current_time:
                # Immediately unmute the user and apologize for the missed expiration time 
                await self.unmuteLogic(unmuted, unmuter, mute_record.server_id, channel)
                await channel.send(f"Apologies for the delay {unmuted.mention}, the mods disconnected me so I couldn't unmute you earlier.")
            else:
                # Schedule the user to be unmuted
                remaining_time = mute_record.expiration_time - current_time
                unmute_task = self.bot.loop.create_task(self.timedUnmute(unmuted, unmuter, guild.id, channel, remaining_time.total_seconds()), name=f"unmute {unmuted.display_name}")
                self.pending_unmutes[unmuted.id] = unmute_task

        
        
        for guild in self.bot.guilds:
            server = await self.getServerFromGuild(guild)
            unmuted_role, muted_role = await self.getMutedRoles(guild, server)

            # Make sure none of the roles under our jursidiction other than the unmuted role grant talking privileges
            for role in guild.roles:
                if (guild.default_role.position < role.position and role.position < guild.me.top_role.position and
                (role.id != unmuted_role.id) and (role.permissions.speak or role.permissions.send_messages)):
                    self.suppress_role_update_events = True
                    await role.edit(permissions=discord.Permissions(role.permissions.value & 2145384447))
                    self.suppress_role_update_events = False

            # Make sure that anyone who is not muted has the unmuted role so they can talk
            for member in guild.members:
                if not muted_role in member.roles:
                    await member.add_roles(
                        unmuted_role,
                        reason="This user did not have the muted role or the unmuted role. We will assume they joined while the bot was disconnected and should be unmuted."
                    )

    # Whenever a new user joins, give them unmuted role so they can speak
    @commands.Cog.listener()
    async def on_member_join(self, member):
        server = await self.getServerFromGuild(guild)
        unmuted_role, muted_role = await self.getMutedRoles(guild, server)
        await member.add_roles(
            unmuted_role,
            reason="All new users need the unmuted role to speak."
        )

    # Whenever a new role is added, if it is within the bots jurisdiction, make sure it doesn't have speaking or messaging perms or mutes won't work
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        if not self.suppress_role_update_events and (role.permissions.speak or role.permissions.send_messages):
            # ideally we would send a message to the person who created the role but apparently thats not possible thanks discord
            # if the bot knows what a mods channel is, we can send a message there
            if role.guild.default_role.position < role.position and role.position < role.guild.me.top_role.position:
                self.suppress_role_update_events = True
                await role.edit(permissions=discord.Permissions(role.permissions.value & 2145384447))
                self.suppress_role_update_events = False

    # Likewise when an existing role is modified
    @commands.Cog.listener()
    async def on_guild_role_update(self, _, updated_role):
        if not self.suppress_role_update_events and (updated_role.permissions.speak or updated_role.permissions.send_messages):
            # ideally we would send a message to the person who created the role but apparently thats not possible thanks discord
            # if the bot knows what a mods channel is, we can send a message there
            if updated_role.guild.default_role.position < updated_role.position and updated_role.position < updated_role.guild.me.top_role.position:
                self.suppress_role_update_events = True
                await updated_role.edit(permissions=discord.Permissions(updated_role.permissions.value & 2145384447))
                self.suppress_role_update_events = False

    async def getServerFromGuild(self, guild):
        server = session.query(Server).filter(Server.server_id == guild.id).one_or_none()
        if server is None:
            server = await self.registerServer
        return server

    async def registerServer(self, guild):
        muted_role = await self.makeMutedRole(guild)
        unmuted_role = await self.makeUnmutedRole(guild)
        
        # Add the new server, now with new muted and unmuted roles, to the database
        server = Server()
        server.server_id = guild.id
        server.name = guild.name
        server.muted_role_id = muted_role.id
        server.unmuted_role_id = unmuted_role.id
        session.add(server)
        session.commit()
        
        return server

    # Create a muted role for aesthetic purposes. It doesn't actually do much of anything.
    async def makeMutedRole(self, guild):
        muted_role = await guild.create_role(
            reason="Muted role changes name color to show who is muted.",
            name="Muted",
            colour=discord.Colour(0xff0000))

        # muted role should have the priority just under the bot's highest permission, shifting other roles down as necessary
        role_position_updates = {role:role.position-1 for role in guild.roles if (muted_role.position < role.position and role.position < guild.me.top_role.position)}
        role_position_updates[muted_role] = guild.me.top_role.position-1
        self.suppress_role_update_events = True
        await guild.edit_role_positions(role_position_updates, reason="Muted role needs to have high precdence to show color")
        self.suppress_role_update_events = False

        return muted_role

    # Create unmuted role, and change existing roles so that only those with the unmuted role can speak and send messages
    async def makeUnmutedRole(self, guild):
        # remove talking permissions from all existing roles, so that users need the unmuted role to talk
        for role in guild.roles:
                if role.position < guild.me.top_role.position:
                    # using a bitmask to remove only speaking and message-sending
                    self.suppress_role_update_events = True
                    await role.edit(permissions=discord.Permissions(role.permissions.value & 2145384447))
                    self.suppress_role_update_events = False
        unmuted_role = await guild.create_role(
            reason="Unmuted role that the bot needs to work did not previously exist. Users will now be unable to talk without this role.",
            name="Unmuted",
            permissions=discord.Permissions(2099200))

        # unmued role should be just above @everyone
        self.suppress_role_update_events = True
        await unmuted_role.edit(position=min([role.position for role in guild.roles])+1, reason="We don't want unmuted to have precedence over anything")
        self.suppress_role_update_events = False

        # give everyone the unmuted role
        for member in guild.members:
            await member.add_roles(
                unmuted_role,
                reason="Assigning unmuted role to everyone. Users will no longer be able to speak or message unless they have this role, though this can be overwritten by channel-specific settings."
            )
        return unmuted_role

    async def getMutedRoles(self, guild, server):
        muted_role = guild.get_role(server.muted_role_id)
        unmuted_role = guild.get_role(server.unmuted_role_id)
        if muted_role is None:
            print(f"The server {server.name} deleted their muted role. Now we have to make a new one >:(.")
            muted_role = await self.makeMutedRole(guild)
            server.muted_role_id = muted_role.id
            session.commit()
        if unmuted_role is None:
            print(f"The server {server.name} deleted their unmuted role. Now we have to make a new one >:(.")
            unmuted_role = await self.makeUnmutedRole(guild)
            server.unmuted_role_id = unmuted_role.id
            session.commit()

        return (unmuted_role, muted_role)