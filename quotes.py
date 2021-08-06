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
    async def insert_quote(cls, ctx, author, content, created_at, server_id, added_by_id):
        q = Quote()
        q.author = author.id
        q.message = content
        q.time_sent = created_at
        q.server = server_id
        q.added_by = added_by_id
        highest = session.query(Quote).filter(Quote.server==ctx.guild.id).order_by(desc(Quote.id)).first()
        q.number = highest.number+1 if highest else 1
        session.add(q)
        session.commit()
        await ctx.send(f'added. it\'s quote {q.number}\n"{q.message}"\n—{author.name} (Quote #{q.number})')

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
    async def sq(self, ctx, *, arg):
        server = ctx.guild.id
        quotes = session.query(Quote).filter(Quote.server == server)

        q = quotes.filter(Quote.message.like(f"%{arg}%")).first()
        if q is None:
            await ctx.send('nothing was found')
        author = await self.bot.fetch_user(q.author)
        r = f'"{q.message}"\n—{author.name} (Quote #{q.number})'
        await ctx.send(r)
    
    @commands.command()
    @mod_only()
    async def addquote(self, ctx, message: typing.Union[int, str], from_user: typing.Optional[discord.Member]):
        if type(message) is int:
            m = await ctx.channel.fetch_message(message)
            if m.guild.id == ctx.guild.id:
                await self.insert_quote(ctx, m.author, m.content, datetime.now(), m.guild.id, ctx.author.id)
        else:
            await self.insert_quote(ctx, from_user, message, datetime.now(), ctx.guild.id, ctx.author.id)
    
    @commands.command()
    @mod_only()
    async def rmquote(self, ctx, number):
            server = ctx.guild.id
            quotes = session.query(Quote).filter(Quote.server == server)

            # heaven help you if you manage to have two quotes with the same number
            q = quotes.filter(Quote.number == number).first()

            if not q:
                await ctx.send("it is NOT. THERE.")

            

            session.delete(q)

            #then decrement all greater quote numbers by 1

            largerquotes = quotes.filter(Quote.number > number)


            for qq in largerquotes:
                qq.number = qq.number-1


            session.commit()
            await ctx.send("ok")
    @commands.command()
    async def lsquotes(self, ctx):
        server = ctx.guild.id
        quotes = session.query(Quote).filter(Quote.server == server)

        messenge = "```number    sent by                           message\n"

        for q in quotes:
            author = await self.bot.fetch_user(q.author)
            message = q.message.replace("\n", "")[:55]
            add = f'{q.number:3d}      {author.name:32s}   {message:10}\n'

            if len(messenge) + len(add) > 1717: #this is a magic number that is very cool and makes  the code run faster
                await ctx.send(messenge + '```')
                messenge = "```"
            messenge += add
        await ctx.send(messenge + '```') 









