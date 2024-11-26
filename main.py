'''
Two (three?) forms of currency:
- Points: for sending messages and playing easy games (karma, aura, social status)
- MONEY money: for leveling up, doing useful crap, etc. (money, stocks, economic crap)
(- REAL MONEY MONEY money: buy with USD lol)

EXTREME rewards for inviting people (automatic? manual?)

we make some sort of minigame per every 10 levels or what ever we decide our floors to be

each level has a cooler mini game then the last, and the rewards are better, but the difficulty could be higher

and the amount of points needed for each level is exponential, so even tho you have better games it will still take longer to level up

'''

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import os
import requests
import json
from datetime import datetime, timezone

from secret_const import TOKEN

from const import CACHE_DIR_PFP, LEADERBOARD_PIC, DEFUALT_PROFILE_PIC, LOG_CHANNEL_ID, ADMIN_LOG_CHANNEL_ID, CARD_DATA_JSON_PATH, CARD_DATA_IMAGES_PATH
from const import pool 
from const import xpToLevel, updateXpAndCheckLevelUp

from adminCommands.set import set
from adminCommands.stats import stats
from adminCommands.reset import reset
from adminCommands.vanity import vanity
from adminCommands.viewCard import viewCard

from floor10_game_concept import guess_the_number_command

from generateCardAI import genAiCard
from cardImageMaker import makeCardFromJson
from fight import ChallengeView, CardView

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=discord.Intents.all())

    async def setup_hook(self):
        # Add the imported command to the bot’s command tree
        self.tree.add_command(guess_the_number_command)
        await self.tree.sync()  # Sync commands with Discord

bot = MyBot()

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Bot is ready. Logged in as {bot.user}')

### ADMIN COMMANDS ###

bot.add_command(set)
bot.add_command(stats)
bot.add_command(reset)
bot.add_command(vanity)
bot.add_command(viewCard)

### ADMIN COMMANDS ###

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id
    username = message.author.name

    conn = pool.get_connection()
    cursor = conn.cursor()

    try:
        # Check if user exists in the database
        cursor.execute("SELECT xp, money FROM users WHERE userId = %s", (user_id,))
        result = cursor.fetchone()

        if result:
            # Directly call level-up update function and get level-up flag
            await updateXpAndCheckLevelUp(ctx=message, bot=bot, xp=1, add=True)
        else:
            # Insert new user record if they don't exist
            cursor.execute(
                "INSERT INTO users (userId, username, xp, money) VALUES (%s, %s, %s, %s)",
                (user_id, username, 1, 0)
            )
            conn.commit()

    finally:
        cursor.close()
        conn.close()

    # Continue processing other commands if any
    await bot.process_commands(message)

@bot.event
async def on_member_join(member: discord.Member):

    conn = pool.get_connection()
    cursor = conn.cursor()

    try:
        # see if the user is in the data base
        cursor.execute("SELECT xp, money FROM users WHERE userId = %s", (member.id,))
        result = cursor.fetchone()
        if result:
            xp = result[0]
            for i in range(xpToLevel(xp)):
                await member.add_roles(discord.utils.get(member.guild.roles, name=f"Level {i + 1}"))
    finally:
        cursor.close()
        conn.close()

    # Calculate account age
    now = datetime.now(timezone.utc)
    account_creation_date = member.created_at
    account_age = now - account_creation_date
    years = account_age.days // 365
    months = (account_age.days % 365) // 30
    days = (account_age.days % 365) % 30

    accountAgeStatus = 'normal'
    
    if years < 1:
        if months < 1:
            # account is brand new
            accountAgeStatus = 'brand new'
        else:
            # account is older than a month
            # and is new, but proably not dangerous
            accountAgeStatus = 'new'
        # account is older than a year old

    # test case for my alt
    #if member.id == 1000422804585451640:
    #    accountAgeStatus = 'brand new'

    # Embed setup
    match accountAgeStatus:
        case 'normal':
            discordColor = discord.Color.green()
        case 'new':
            discordColor = discord.Color.yellow()
        case 'brand new':
            discordColor = discord.Color.dark_orange()

    embed = discord.Embed(
            title="Member Joined",
            description=f"**Member:** \n{member.name}\n\n"
                        f"**Account Age:** \n{years} Years, {months} Months, {days} Days\n",
            color=discordColor,
            timestamp=now  # Automatically add the timestamp to the footer
        )
    embed.set_thumbnail(url=member.display_avatar.url)

    channel = bot.get_channel(LOG_CHANNEL_ID)

    # Send the embed to the server's system channel (or any specific channel)
    if channel:
        await channel.send(embed=embed)

@bot.event
async def on_member_remove(member: discord.Member):
    # Calculate account age
    now = datetime.now(timezone.utc)
    account_creation_date = member.created_at
    account_age = now - account_creation_date
    years = account_age.days // 365
    months = (account_age.days % 365) // 30
    days = (account_age.days % 365) % 30

    embed = discord.Embed(
            title="Member Left",
            description=f"**Member:** \n{member.name}\n\n"
                        f"**Account Age:** \n{years} Years, {months} Months, {days} Days\n",
            color=discord.Color.dark_magenta(),
            timestamp=now  # Automatically add the timestamp to the footer
        )
    embed.set_thumbnail(url=member.display_avatar.url)

    channel = bot.get_channel(LOG_CHANNEL_ID)

    # Send the embed to the server's system channel (or any specific channel)
    if channel:
        await channel.send(embed=embed)

@bot.event
async def on_user_update(before: discord.Member, after: discord.Member):

    # later if we run out of resources we can make it so that we check if the user is on the leaderboard or not
    # and if not we can just return

    # Check if the avatar has changed
    if before.avatar != after.avatar:
        print('check did not fail')
        user = await bot.fetch_user(after.id)
        # Ensure the directory exists
        profile_picture_dir = os.path.join(os.path.expanduser(CACHE_DIR_PFP))

        if not os.path.exists(profile_picture_dir):
            os.makedirs(profile_picture_dir)

        profile_picture_path = os.path.join(profile_picture_dir, f"{after.id}.png")

        if user and user.avatar:
            profile_picture_response = requests.get(user.avatar.url, stream=True)
            profile_picture_response.raise_for_status()
            profile_picture = Image.open(profile_picture_response.raw)
        else:
            profile_picture = Image.open(DEFUALT_PROFILE_PIC)

            # Save profile picture to cache
        profile_picture.save(profile_picture_path)

@bot.tree.command(name="leaderboard", description="Display the leaderboard based on level or money.")
@app_commands.describe(type="Choose between 'level' or 'money' for the leaderboard type.")
async def leaderboard(interaction: discord.Interaction, type: str = "level"):
    conn = pool.get_connection()
    cursor = conn.cursor()
    try:
        # Determine the query based on the selected type
        if type == "money":
            cursor.execute("SELECT userId, username, money FROM users ORDER BY money DESC, xp DESC LIMIT 10")
            leaderboard_data = cursor.fetchall()
        else:  # Default to "level"
            type = 'level' # handles edge case where the user types something other than 'money' or 'level'
            cursor.execute("SELECT userId, username, xp FROM users ORDER BY xp DESC, xp DESC LIMIT 10")
            leaderboard_data = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    # Create an image for the leaderboard
    image_width = 600
    image_height = 770
    background_color = (54, 57, 62)  # Dark grey background
    image = Image.new("RGB", (image_width, image_height), background_color)

    # Load font for text
    font_size = 30
    font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", font_size)

    # Initialize drawing context
    draw = ImageDraw.Draw(image)

    # Set up leaderboard rendering variables
    count = 0
    y_offset = 10
    for user_id, username, value in leaderboard_data:
        if user_id == 1175890644191957013:
            continue

        user = await bot.fetch_user(user_id)
        count += 1

        # Ensure the directory exists
        profile_picture_dir = os.path.join(os.path.expanduser(CACHE_DIR_PFP))
        if not os.path.exists(profile_picture_dir):
            os.makedirs(profile_picture_dir)

        # Check if profile picture is in cache
        profile_picture_path = os.path.join(profile_picture_dir, f"{user_id}.png")

        if os.path.exists(profile_picture_path):
            profile_picture = Image.open(profile_picture_path)
        else:
            if user and user.avatar:
                profile_picture_response = requests.get(user.avatar.url, stream=True)
                profile_picture_response.raise_for_status()
                profile_picture = Image.open(profile_picture_response.raw)
            else:
                profile_picture = Image.open(DEFUALT_PROFILE_PIC)

            # Save profile picture to cache
            profile_picture.save(profile_picture_path)

        # Resize profile picture and draw on the image
        profile_picture = profile_picture.resize((70, 70))
        image.paste(profile_picture, (10, y_offset))

        # Determine color based on rank
        if count == 1:
            rank_color = (255, 215, 0)  # Gold
        elif count == 2:
            rank_color = (192, 192, 192)  # Silver
        elif count == 3:
            rank_color = (205, 127, 50)  # Bronze
        else:
            rank_color = (255, 255, 255)  # White


        # what the fuck is value?

        value = xpToLevel(value) if type == "level" else value

        # Draw rank, username, and value (level or money)
        display_value = f"Level {value}" if type == "level" else f"${value:,}"
        draw.text((100, y_offset + 10), f"•  #{count} • {username}", fill=rank_color, font=font)
        draw.text((390, y_offset + 10), display_value, fill=(255, 255, 255), font=font)  # Value in white

        # Increment y_offset for next user
        y_offset += 75
        if count == 10:
            break

    # Save the leaderboard image
    image.save(LEADERBOARD_PIC)

    # Create an embed for the leaderboard
    embed = discord.Embed(title=f"{type.capitalize()} Leaderboard", color=0x282b30)
    embed.set_image(url="attachment://leaderboard.png")

    # Send the embed with the leaderboard image
    await interaction.response.send_message(embed=embed, file=discord.File(LEADERBOARD_PIC))


@bot.tree.command(name="challenge", description="Send a challenge to a user with accept or decline options.")
@app_commands.describe(member="The member to challenge")
async def challenge(interaction: discord.Interaction, member: discord.Member):
    conn = pool.get_connection()
    cursor = conn.cursor(dictionary=True)
    valid_cards = {}  # Store valid cards for each user

    try:
        # Check if both players have enough cards
        cursor.execute("SELECT COUNT(*) AS card_count FROM cards WHERE userId = %s", (interaction.user.id,))
        user_cards = cursor.fetchone()["card_count"]

        if user_cards < 3:
            await interaction.response.send_message("You need at least 3 cards to create a challenge.", ephemeral=True)
            return

        cursor.execute("SELECT COUNT(*) AS card_count FROM cards WHERE userId = %s", (member.id,))
        member_cards = cursor.fetchone()["card_count"]

        if member_cards < 3:
            await interaction.response.send_message(f"{member.mention} does not have enough cards to be challenged.", ephemeral=True)
            return

        # Proceed with the challenge
        await interaction.response.send_message(f"{member.mention}, you have been challenged! Choose an option below.")
        view = ChallengeView(member)
        message = await interaction.followup.send(content="Respond to the challenge:", view=view)
        view.message = message

        await view.wait()

        if not view.response:
            await interaction.followup.send("The challenge was cancelled due to no response.")
            return

        elif view.response == "Declined":
            await interaction.followup.send(f"{member.mention} has declined the challenge.")
            return

        elif view.response == "Accepted":
            thread = await interaction.channel.create_thread(
                name=f"{interaction.user.name} vs {member.name}",
                type=discord.ChannelType.public_thread,
            )

            card_view = CardView(pool=pool, member_id=None, valid_cards=valid_cards)
            await thread.send(
                content="Click this button to view your cards.",
                view=card_view,
            )

            # Track locked-in cards
            locked_in = {interaction.user.id: False, member.id: False}

            @bot.event
            async def on_message(message):
                # Only process messages in the thread
                if message.channel.id != thread.id:
                    return

                user_id = message.author.id

                # Check if this user is allowed to participate
                if user_id not in [interaction.user.id, member.id]:
                    try:
                        await message.delete()
                    except discord.errors.NotFound:
                        # Message was already deleted; ignore
                        pass
                    return

                # Validate card selection
                try:
                    selected_cards = list(map(int, message.content.split()))
                except ValueError:
                    try:
                        await message.delete()
                    except discord.errors.NotFound:
                        pass
                    await message.channel.send(
                        f"{message.author.mention}, please send the numbers of your cards in the format `1 2 3`.",
                        delete_after=5,
                    )
                    return

                # Ensure `valid_cards` retrieval is awaited if asynchronous
                valid_cards_for_user = await valid_cards.get(user_id)  # Assuming this function is async

                # Ensure the selection is valid
                if len(selected_cards) != 3 or len(set(selected_cards)) != 3:
                    try:
                        await message.delete()
                    except discord.errors.NotFound:
                        pass
                    await message.channel.send(
                        f"{message.author.mention}, you must select exactly 3 different cards.",
                        delete_after=5,
                    )
                    return

                if not all(1 <= card <= len(valid_cards_for_user) for card in selected_cards):
                    try:
                        await message.delete()
                    except discord.errors.NotFound:
                        pass
                    await message.channel.send(
                        f"{message.author.mention}, one or more selected cards are invalid. Please try again.",
                        delete_after=5,
                    )
                    return

                # Lock in cards
                card_view.locked_in_cards[user_id] = selected_cards
                locked_in[user_id] = True
                await message.channel.send(
                    f"{message.author.mention} has locked in their cards: {', '.join(map(str, selected_cards))}."
                )

                # Check if both players are locked in
                if all(locked_in.values()):
                    await thread.send("Both players have locked in their cards! Let the battle begin!")
                    bot.remove_listener(on_message)


    finally:
        cursor.close()
        conn.close()

bot.run(TOKEN)
