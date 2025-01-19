import discord
import sqlite3

from discord.ext import commands
from pathlib import Path

from const import CARD_DATA_IMAGES_PATH, COLORS, DATABASE_PATH

# Ensure CARD_DATA_IMAGES_PATH is a Path object
CARD_DATA_IMAGES_PATH = Path(CARD_DATA_IMAGES_PATH)

@commands.command()
async def viewcardstats(ctx, *, query: str = '') -> None:
    if not ctx.author.guild_permissions.administrator:
        await ctx.send(f'''```ansi\n{COLORS['yellow']}You do not have the required permissions to use this command.{COLORS['reset']}```''')
        return
    
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        try:
            if not query or query == '':
                await ctx.send(f'''```ansi\n{COLORS['yellow']}Please specify a valid card name or ID to view.{COLORS['reset']}```''')
                return

            cardData = None

            # Try to find by itemId if the query is numeric
            if query.isdigit():
                cursor.execute("SELECT * FROM cards WHERE cardId = ?", (int(query),))
                cardData = cursor.fetchone()
            else:
                # Otherwise, find by itemName (case-insensitive)
                cursor.execute("SELECT * FROM cards WHERE LOWER(itemName) = LOWER(?)", (query.lower(),))
                cardData = cursor.fetchone()
            
            if cardData is None:
                await ctx.send(f'''```ansi\n{COLORS['yellow']}No card found for '{query}'.{COLORS['reset']}```''')
                return

            # Extract the itemId and construct the image path
            item_id = cardData['itemId']
            image_path = CARD_DATA_IMAGES_PATH / f"{item_id}.png"

            # Check if the image file exists
            if not image_path.exists():
                await ctx.send(f'''```ansi\n{COLORS['red']}Image for card with ID {item_id} not found.{COLORS['reset']}```''')
                return

            # Send the image
            await ctx.send(file=discord.File(image_path))

        except Exception as e:
            await ctx.send(f'''```ansi\n{COLORS['red']}An error occurred: {e}\u001b[0m{COLORS['reset']}```''')
            return