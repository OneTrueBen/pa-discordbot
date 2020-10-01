from models import Session, ModRole
from discord.ext import commands
import discord
from settings import settings
import functools
session = Session()

# MAKE SURE ModRoles cog is LOADED. or you will DIE INSTANTLY
def owner_only():
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args):
            ctx = next(a for a in args if type(a) is commands.context.Context)
            if ctx.author.id != int(settings.get('owner')):
                await ctx.send('no!!!')
                return
            return await func(*args)
        return wrapped
    return wrapper

def mod_only():
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args):
            ctx = next(a for a in args if type(a) is commands.context.Context)
            roleids = [r.id for r in ctx.author.roles]
            modroles = session.query(ModRole.role).filter(ModRole.server == ctx.guild.id, ModRole.role.in_(roleids)).all()
            modroles = [value for value, in modroles] #unpack it
            if len(modroles) <= 0:
                await ctx.send('no!!')
                return
            return await func(*args)
        return wrapped
    return wrapper

def server_owner_only():
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args):
            ctx = next(a for a in args if type(a) is commands.context.Context)
            if ctx.author.id == ctx.guild.owner_id:
                return await func(*args)
            else:
                await ctx.send('no!!!!')
                return
        return wrapped
    return wrapper

    

class ModRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @server_owner_only()
    async def addmodrole(self, ctx, role_id):
        match = session.query(ModRole).filter(ModRole.server == ctx.guild.id, ModRole.role == role_id).first()
        if match:
            return
        r = [ role for role in ctx.guild.roles if role.id == int(role_id) ]


        if r is not None:
            m = ModRole()
            m.server = ctx.guild.id
            m.role = r[0].id
            session.add(m)
            session.commit()
            await ctx.send(f'{r[0].name} was added')
    @owner_only()
    @commands.command()
    async def delmodrole(self, ctx, role_id):
        match = session.query(ModRole).filter(ModRole.server == ctx.guild.id, ModRole.role == role_id).first()
        if match:
            session.delete(match)
            session.commit()
            name = ctx.guild.get_role(int(match.role)).name
            await ctx.send(f'{name} was deleted')

    @commands.command()
    async def modroles(self, ctx):
        matches = session.query(ModRole).filter(ModRole.server == ctx.guild.id).all()
        msg = ""
        for m in matches:
            name = ctx.guild.get_role(int(m.role)).name
            msg += name + '\n'
        await ctx.send(f'```{msg}```')


        
