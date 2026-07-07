import discord
from discord import app_commands
from discord.ext import commands
from models import Quote, Session
from sqlalchemy import desc
import random
import typing
from modrole import mod_only, server_owner_only
from datetime import datetime

session = Session()

class Quotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @classmethod
    async def insert_quote(cls, interaction: discord.Interaction, author: discord.Member, content: str, created_at: datetime, server_id: int, added_by_id: int):
        q = Quote()
        q.author = author.id
        q.message = content
        q.time_sent = created_at
        q.server = server_id
        q.added_by = added_by_id
        highest = session.query(Quote).filter(Quote.server==server_id).order_by(desc(Quote.id)).first()
        q.number = highest.number+1 if highest else 1
        session.add(q)
        session.commit()
        await interaction.followup.send(f'added. it\'s quote {q.number}\n"{q.message}"\n—{author.display_name} (Quote #{q.number})')

    @app_commands.command(name="quote", description="Get a random quote, a quote by number, or a random quote by user")
    @app_commands.describe(
        number="Quote number to retrieve",
        user="User whose quotes to retrieve"
    )
    async def slash_quote(self, interaction: discord.Interaction, number: typing.Optional[int] = None, user: typing.Optional[discord.Member] = None):
        await interaction.response.defer()
        q = None
        server = interaction.guild_id
        quotes = session.query(Quote).filter(Quote.server == server)
        
        if number is not None:
            q = quotes.filter(Quote.number == number).one_or_none()
        elif user is not None:
            user_quotes = quotes.filter(Quote.author == user.id).all()
            if user_quotes:
                q = random.choice(user_quotes)
        else:
            all_quotes = quotes.all()
            if all_quotes:
                q = random.choice(all_quotes)
        
        if q is None:
            await interaction.followup.send('No quote found matching your criteria')
            return
            
        # get the user
        try:
            author = await self.bot.fetch_user(q.author)
            author_name = author.display_name
        except:
            author_name = f"Unknown User ({q.author})"
            
        response = f'"{q.message}"\n—{author_name} (Quote #{q.number})'
        await interaction.followup.send(response)
    
    @app_commands.command(name="sq", description="Search for a quote containing specific text")
    @app_commands.describe(search_text="Text to search for in quotes")
    async def slash_sq(self, interaction: discord.Interaction, search_text: str):
        await interaction.response.defer()
        server = interaction.guild_id
        quotes = session.query(Quote).filter(Quote.server == server)

        q = quotes.filter(Quote.message.like(f"%{search_text}%")).first()
        
        if q is None:
            await interaction.followup.send('nothing was found')
            return
            
        try:
            author = await self.bot.fetch_user(q.author)
            author_name = author.display_name
        except:
            author_name = f"Unknown User ({q.author})"
            
        response = f'"{q.message}"\n—{author_name} (Quote #{q.number})'
        await interaction.followup.send(response)
    
    @app_commands.command(name="addquote", description="Add a quote from a message ID or from a specific user")
    @app_commands.describe(
        message_id_or_text="Message ID or quote text",
        user="User who said the quote (if providing text)"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def slash_addquote(self, interaction: discord.Interaction, message_id_or_text: str, user: typing.Optional[discord.Member] = None):
        await interaction.response.defer()
        
        try:
            # Try to parse as message ID first
            message_id = int(message_id_or_text)
            try:
                m = await interaction.channel.fetch_message(message_id)
                if m.guild.id == interaction.guild_id:
                    await self.insert_quote(interaction, m.author, m.content, datetime.now(), m.guild.id, interaction.user.id)
                    return
            except (ValueError, discord.NotFound):
                pass
        except ValueError:
            pass
            
        # If not a valid message ID or message not found, treat as text
        if user is not None:
            await self.insert_quote(interaction, user, message_id_or_text, datetime.now(), interaction.guild_id, interaction.user.id)
        else:
            await interaction.followup.send("You must specify a user when adding a quote by text")
    
    @app_commands.command(name="rmquote", description="Remove a quote by number")
    @app_commands.describe(number="Quote number to remove")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def slash_rmquote(self, interaction: discord.Interaction, number: int):
        await interaction.response.defer()
        server = interaction.guild_id
        quotes = session.query(Quote).filter(Quote.server == server)

        # heaven help you if you manage to have two quotes with the same number
        q = quotes.filter(Quote.number == number).first()

        if not q:
            await interaction.followup.send("it is NOT. THERE.")
            return

        session.delete(q)

        # then decrement all greater quote numbers by 1
        largerquotes = quotes.filter(Quote.number > number)
        for qq in largerquotes:
            qq.number = qq.number - 1

        session.commit()
        await interaction.followup.send("ok")
    
    @app_commands.command(name="lsquotes", description="List all quotes in the server")
    async def slash_lsquotes(self, interaction: discord.Interaction):
        await interaction.response.defer()
        server = interaction.guild_id
        quotes = session.query(Quote).filter(Quote.server == server).order_by(Quote.number).all()
        names = {}

        if not quotes:
            await interaction.followup.send("No quotes found in this server")
            return

        message_chunks = []
        current_chunk = "```number    sent by                           message\n"

        for q in quotes:
            name = names.get(q.author)
            if not name:
                try:
                    author = await self.bot.fetch_user(q.author)
                    names[q.author] = author.display_name
                    name = author.display_name
                except:
                    name = f"Unknown User ({q.author})"
                    names[q.author] = name
            
            message = q.message.replace("\n", "")[:55]
            add = f'{q.number:3d}      {name:32s}   {message:10}\n'

            if len(current_chunk) + len(add) > 1900:  # Leave room for closing ```
                message_chunks.append(current_chunk + '```')
                current_chunk = "```number    sent by                           message\n"
                
            current_chunk += add
            
        message_chunks.append(current_chunk + '```')
        
        for i, chunk in enumerate(message_chunks):
            if i == 0:
                await interaction.followup.send(chunk)
            else:
                await interaction.channel.send(chunk)
