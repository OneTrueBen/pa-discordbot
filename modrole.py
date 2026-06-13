from models import Session, ModRole
from discord.ext import commands
import discord
from discord import app_commands
from settings import settings
import functools
session = Session()

# MAKE SURE ModRoles cog is LOADED. or you will DIE INSTANTLY

def owner_only():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.id != int(settings.get('owner')):
            await interaction.response.send_message('no!!!', ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

def mod_only():
    async def predicate(interaction: discord.Interaction):
        roleids = [r.id for r in interaction.user.roles]
        modroles = session.query(ModRole.role).filter(ModRole.server == interaction.guild_id, ModRole.role.in_(roleids)).all()
        modroles = [value for value, in modroles] #unpack it
        if len(modroles) <= 0:
            await interaction.response.send_message('no!! power hungry.....', ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

def server_owner_only():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.id == interaction.guild.owner_id:
            return True
        await interaction.response.send_message('no!!!!', ephemeral=True)
        return False
    return app_commands.check(predicate)

class ModRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="addmodrole", description="Add a moderator role (server owner only)")
    @app_commands.describe(role="Role to add as moderator role")
    @server_owner_only()
    async def slash_addmodrole(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        match = session.query(ModRole).filter(ModRole.server == interaction.guild_id, ModRole.role == str(role.id)).first()
        if match:
            await interaction.followup.send(f'{role.name} is already a moderator role', ephemeral=True)
            return

        m = ModRole()
        m.server = interaction.guild_id
        m.role = str(role.id)
        session.add(m)
        session.commit()
        await interaction.followup.send(f'{role.name} was added as a moderator role', ephemeral=True)
    
    @app_commands.command(name="delmodrole", description="Remove a moderator role (bot owner only)")
    @app_commands.describe(role="Role to remove as moderator role")
    @owner_only()
    async def slash_delmodrole(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        match = session.query(ModRole).filter(ModRole.server == interaction.guild_id, ModRole.role == str(role.id)).first()
        if match:
            session.delete(match)
            session.commit()
            await interaction.followup.send(f'{role.name} was removed from moderator roles', ephemeral=True)
        else:
            await interaction.followup.send(f'{role.name} is not a moderator role', ephemeral=True)

    @app_commands.command(name="modroles", description="List all moderator roles")
    async def slash_modroles(self, interaction: discord.Interaction):
        await interaction.response.defer()
        matches = session.query(ModRole).filter(ModRole.server == interaction.guild_id).all()
        if not matches:
            await interaction.followup.send("No moderator roles configured", ephemeral=True)
            return
            
        msg = "Moderator Roles:\n"
        for m in matches:
            role = interaction.guild.get_role(int(m.role))
            if role:
                msg += f"- {role.name}\n"
        
        await interaction.followup.send(f'```{msg}```')


        
 