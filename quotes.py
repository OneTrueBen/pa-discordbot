from models import Quote, Session
from discord.ext import commands
import discord
from sqlalchemy import desc
import random
import typing
from modrole import mod_only

session = Session()

class Quotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
    async def addquote(self, ctx, message_id):
        m = await ctx.channel.fetch_message(message_id)
        if m.guild.id == ctx.guild.id:
            q = Quote()
            q.author = m.author.id
            q.message = m.content
            q.time_sent = m.created_at
            q.server = m.guild.id
            q.added_by = ctx.author.id
            highest = session.query(Quote).filter(Quote.server==ctx.guild.id).order_by(desc(Quote.id)).first()
            q.number = highest.number+1 if highest else 1
            session.add(q)
            session.commit()
            await ctx.send(f'added. it\'s quote {q.number}')



