from models import Quote, Session
from discord.ext import commands
import discord
from sqlalchemy import desc
import random
import typing
from modrole import mod_only
from datetime import datetime

session = Session()

class Quotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @classmethod
    async def insert_quote(cls, ctx, author_id, content, created_at, server_id, added_by_id):
        q = Quote()
        q.author = author_id
        q.message = content
        q.time_sent = created_at
        q.server = server_id
        q.added_by = added_by_id
        highest = session.query(Quote).filter(Quote.server==ctx.guild.id).order_by(desc(Quote.id)).first()
        q.number = highest.number+1 if highest else 1
        session.add(q)
        session.commit()
        await ctx.send(f'added. it\'s quote {q.number}')

    @commands.command()
    async def quote(self, ctx, arg: typing.Union[int, discord.Member, None]):
        q = None
        server = ctx.guild.id
        quotes = session.query(Quote).filter(Quote.server == server)
        if arg:
            if type(arg) is int:
                q = quotes.filter(Quote.number == arg).one()
            elif type(arg) is discord.Member:
                q = random.choice(quotes.filter(Quote.author == arg.id).all())
        else:
            q = random.choice(quotes.all())
        if q is None: return
        # get the user
        author = await self.bot.fetch_user(q.author)
        r = f'"{q.message}"\n—{author.name} (Quote #{q.number})'
        
        await ctx.send(r)
    
    @commands.command()
    @mod_only()
    async def addquote(self, ctx, message: typing.Union[int, str], from_user: typing.Optional[discord.Member]):
        if type(message) is int:
            m = await ctx.channel.fetch_message(message)
            if m.guild.id == ctx.guild.id:
                await self.insert_quote(ctx, m.author.id, m.content, datetime.now(), m.guild.id, ctx.author.id)
        else:
            await self.insert_quote(ctx, from_user.id, message, datetime.now(), ctx.guild.id, ctx.author.id)
            



