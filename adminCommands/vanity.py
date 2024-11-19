import os
import discord
from discord.ext import commands

from const import ROOT_DIR

@commands.command()
async def vanity(ctx):
    """Get the total number of lines in the project files."""
    total_files, total_commands, total_lines = count_lines_of_code_in_python_files(ROOT_DIR)
    total_lines = "{:,}".format(total_lines)
    total_files = "{:,}".format(total_files)
    total_commands = "{:,}".format(total_commands)
    embed = discord.Embed(
    title="📊 Bot Statistics",
    description="Here’s a breakdown of the bot’s code and commands:",
    color=0x5865F2  # Use a more vibrant color
    )

    embed.add_field(
        name="🔢 Total Lines of Code",
        value=f"```yaml\n{total_lines}\n```",
        inline=False
    )
    embed.add_field(
        name="🛠️ Total Commands",
        value=f"```yaml\n{total_commands}\n```",
        inline=False
    )
    embed.add_field(
        name="📁 Total Files",
        value=f"```yaml\n{total_files}\n```",
        inline=False
    )

    embed.set_footer(
        text="Generated by Eli Bot, Powered by 404",
        icon_url=ctx.bot.user.avatar.url  if ctx.bot.user.avatar else '' # Replace with your bot's avatar URL
    )
    embed.set_thumbnail(
        url=""  # Replace with your bot's logo URL
    )

    await ctx.send(embed=embed)

def count_lines_of_code_in_python_files(root_dir):
    total_files = 0
    total_py_files = 0
    total_lines = 0

    # Walk through the directory recursively
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip hidden directories (those starting with a dot) and __pycache__
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '__pycache__']
        
        for filename in filenames:
            total_files += 1  # Count all files
            
            if filename.endswith('.py'):  # Check if the file is a Python file
                total_py_files += 1
                file_path = os.path.join(dirpath, filename)
                
                # Open the Python file and count its lines
                with open(file_path, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
                    total_lines += len(lines)

    return total_files, total_py_files, total_lines