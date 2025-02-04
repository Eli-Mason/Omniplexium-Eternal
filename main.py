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
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFont
import os
import requests
from datetime import datetime, timezone
import time
import sqlite3
import traceback
import asyncio

from secret_const import TOKEN

from const import CACHE_DIR_PFP, COLORS, LEADERBOARD_PIC, DEFUALT_PROFILE_PIC, DATABASE_PATH, MAIN_CENSORSHIP_MODEL, BACKUP_CENSORSHIP_MODEL
from const import SERVER_ID, ADMIN_LOG_CHANNEL_ID, MODEL_ERROR_LOG_CHANNEL_ID, CENSORSHIP_CHANNEL_ID, LOG_CHANNEL_ID

from helperFunctions.main import xpToLevel, updateXpAndCheckLevelUp, copyCard, censorMessage, checkLoginRemindersAndSend, logModelError, logError, logWarning
from helperFunctions.database import checkDatabase

from adminCommands.set import set
from adminCommands.stats import stats
from adminCommands.reset import reset
from adminCommands.vanity import vanity
from adminCommands.levelToXp import create_level_to_xp_command
from adminCommands.makeLogin import makeloginrewards
from adminCommands.copyCard import copycard
from adminCommands.viewCard import viewcard
from adminCommands.viewCardStats import viewcardstats

from slashCommands.login import slashCommandLogin
from slashCommands.setLoginReminders import slashCommandSetLoginReminders
from slashCommands.credits import slashCommandCredits
from slashCommands.stats import slashCommandStats
#from slashCommands.generateCard import slashCommandGenerateCard

from commands.killme import killme
from commands.credits import credits

from floor10_game_concept import guess_the_number_command

from fight import ChallengeView

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=discord.Intents.all())

    async def setup_hook(self):
        # Add the imported command to the bot’s command tree
        self.tree.add_command(guess_the_number_command)
        self.tree.add_command(slashCommandLogin)
        self.tree.add_command(slashCommandSetLoginReminders)
        self.tree.add_command(slashCommandCredits)
        self.tree.add_command(slashCommandStats)
        #self.tree.add_command(slashCommandGenerateCard)

        await self.tree.sync()  # Sync commands with Discord

bot = MyBot()

@bot.event
async def on_ready():
    checkDatabaseStartTime = time.time()
    await checkDatabase(bot)
    print(f'The database check took {round(time.time() - checkDatabaseStartTime, 2)} seconds')

    if not loginReminderTask.is_running():
        try:
            loginReminderTask.start()
            print(f"{COLORS['blue']}Login reminder task started{COLORS['reset']}")
        
        except Exception as e:
            print(f"{COLORS['red']}Login reminder task failed to start: {e}{COLORS['reset']}")
            await logError(bot, e, traceback.format_exc(), 'Login reminder task failed to start')

    botTreeSyncStartTime = time.time()
    await bot.tree.sync()
    print(f'Bot tree sync took {round(time.time() - botTreeSyncStartTime, 2)} seconds')

    print(f'Bot is ready. Logged in as {bot.user}')

# Define the task outside of the bot class
@tasks.loop(hours=1)
async def loginReminderTask():
    await checkLoginRemindersAndSend(bot)


### ADMIN COMMANDS ###

bot.add_command(set)
bot.add_command(stats)
bot.add_command(reset)
bot.add_command(vanity)
create_level_to_xp_command(bot)
bot.add_command(makeloginrewards)
bot.add_command(copycard)
#bot.add_command(leveltoxp)
bot.add_command(viewcard)
bot.add_command(viewcardstats)

### ADMIN COMMANDS ###



### Normal commands ###

bot.add_command(killme)
bot.add_command(credits)

### Normal commands ###



@bot.event
async def on_message(message):
    if message.author.bot:
        return

    userId = message.author.id
    username = message.author.name

    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            # Check if user exists in the database
            cursor.execute("SELECT * FROM users WHERE userId = ?", (userId,))
            result = cursor.fetchone()
            
            if not result:
                cursor.execute(
                    "INSERT INTO users (userId, username, xp, money, lastLogin, daysLoggedInInARow) VALUES (?, ?, ?, ?, ?, ?)",
                    (userId, username, 1, 0, None, 0)
                )
                conn.commit()
            
            if result:
                await updateXpAndCheckLevelUp(ctx=message, bot=bot, xp=1, add=True)
    except sqlite3.Error as e:
        print(f"Database error in on_message: {e}")
        channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
        await channel.send(f'''```ansi{COLORS['red']}Database error in on_message: ```{e}```{COLORS['reset']}```''')

    finally:
        # Continue processing other commands regardless of database operation success
        await bot.process_commands(message)

        async def tryCensorMessageWithModel(message: str) -> str:
            censoredMessage = None
            try:
                try:
                    censoredMessage = await asyncio.wait_for(censorMessage(message), timeout=1.0)
                except asyncio.TimeoutError as e:
                    messageId = await logModelError(
                                    bot, e, traceback.format_exc(), 
                                    f"""{username} sent a message: {message}\nWhich was not censored in time!""", 'on_message event'
                                    )
                    channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
                    await channel.send(f"https://discord.com/channels/{SERVER_ID}/{MODEL_ERROR_LOG_CHANNEL_ID}/{messageId}")

                    await logWarning(
                                    bot, f"""{username} sent a message: {message}\nWhich was not censored in time!""", 'on_message event'
                                    )
                    #return await tryCensorMessageWithModel(message, model=BACKUP_CENSORSHIP_MODEL)

            except Exception as e:
                messageId = await logModelError(bot, e, traceback.format_exc(), 'on_message event')
                channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
                await channel.send(f"https://discord.com/channels/{SERVER_ID}/{MODEL_ERROR_LOG_CHANNEL_ID}/{messageId}")
                
                await logWarning(
                                bot, f"""{username} sent a message: {message} Which was not censored.""", 'on_message event'
                                )
                #return await tryCensorMessageWithModel(message, model=BACKUP_CENSORSHIP_MODEL)
            
            return 'false' if censoredMessage is None else censoredMessage

        censoredMessage = 'false'

        if message.content is not None and message.content.strip() != '':
            censoredMessage = await tryCensorMessageWithModel(message.content)
        
        if censoredMessage.strip() not in ['false', "'false'", '"false"', 'False', "'False'", '"False"'] and username != '404_5971':
            channel = bot.get_channel(CENSORSHIP_CHANNEL_ID)
            await channel.send(f'`{username}` sent a message: ```{message.content}```Which was censored to: ```{censoredMessage}```')
            await message.delete()
            await message.channel.send(f'`{username}:` {censoredMessage}')

@bot.command()
async def login(ctx, day: float = None) -> None:
    if not ctx.author.guild_permissions.administrator:
        day = 0

    if day is not None:
        # everything is a string
        float(day)

    if day is None:
        day = 0

    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT lastLogin, daysLoggedInInARow FROM users WHERE userId = ?", (ctx.author.id,))
        result = cursor.fetchone()
        
        if result is not None:
            lastLogin = result[0]
            daysLoggedInInARow = result[1]
        else:
            lastLogin = None
            daysLoggedInInARow = 0
        
        if lastLogin is None:
            await ctx.send("You have made your first daily login!")
            cursor.execute("UPDATE users SET lastLogin = ? WHERE userId = ?", (time.time(), ctx.author.id))
            cursor.execute("UPDATE users SET daysLoggedInInARow = ? WHERE userId = ?", (1, ctx.author.id))
            conn.commit()
        else:
            if time.time() - lastLogin > 172800 or (day * 86400) > 172800:
                await ctx.send("You have lost your daily login streak!")
                cursor.execute("UPDATE users SET daysLoggedInInARow = ? WHERE userId = ?", (1, ctx.author.id))
                cursor.execute("UPDATE users SET lastLogin = ? WHERE userId = ?", (time.time(), ctx.author.id))
                conn.commit()
            elif time.time() - lastLogin > 86400 or (day * 86400) > 86400:
                await ctx.send("You have made your daily login!")
                cursor.execute("UPDATE users SET lastLogin = ? WHERE userId = ?", (time.time(), ctx.author.id))
                cursor.execute("UPDATE users SET daysLoggedInInARow = ? WHERE userId = ?", (daysLoggedInInARow + 1, ctx.author.id))
                conn.commit()
            else:
                await ctx.send("You have already logged in today!")
                return
        
        cursor.execute("SELECT daysLoggedInInARow FROM users WHERE userId = ?", (ctx.author.id,))
        result = cursor.fetchone()
        daysLoggedInInARow = result[0]

        cursor.execute("SELECT rewardType, amountOrCardId FROM loginRewards WHERE level = ?", (daysLoggedInInARow,))
        result = cursor.fetchone()
        type, amount = result

        match type:
            case "xp":
                await updateXpAndCheckLevelUp(ctx=ctx, bot=bot, xp=amount, add=True)
                await ctx.send(f"Congratulations! You have received {amount} XP for logging in {daysLoggedInInARow} days in a row!")
            case "money":
                cursor.execute("UPDATE users SET money = money + ? WHERE userId = ?", (amount, ctx.author.id))
                conn.commit()
                await ctx.send(f"Congratulations! You have received ${amount} for logging in {daysLoggedInInARow} days in a row!")
            case "card":
                copyCard(amount, ctx.author.id)
                
                cursor.execute("SELECT itemName FROM cards WHERE itemId = ?", (amount,))
                cardName = cursor.fetchone()[0]
                
                await ctx.send(f"Congratulations! You have received {cardName} for logging in {daysLoggedInInARow} days in a row!")


@bot.event
async def on_member_join(member: discord.Member):
    memberId = member.id
    memberName = member.name
    
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        # see if the user is in the data base
        cursor.execute("SELECT xp FROM users WHERE userId = ?", (memberId,))
        result = cursor.fetchone()
        if result:
            xp = result[0]
            for i in range(xpToLevel(xp)):
                await member.add_roles(discord.utils.get(member.guild.roles, name=f"Level {i + 1}"))

        if not result:
            cursor.execute(
                "INSERT INTO users (userId, username, xp, money, lastLogin, daysLoggedInInARow) VALUES (?, ?, ?, ?, ?, ?)",
                (memberId, memberName, 0, 0, None, 0)
            )
            conn.commit()


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
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        # Determine the query based on the selected type
        if type == "money":
            cursor.execute("SELECT userId, username, money FROM users ORDER BY money DESC, xp DESC LIMIT 10")
            leaderboard_data = cursor.fetchall()
        else:  # Default to "level"
            type = 'level' # handles edge case where the user types something other than 'money' or 'level'
            cursor.execute("SELECT userId, username, xp FROM users ORDER BY xp DESC, xp DESC LIMIT 10")
            leaderboard_data = cursor.fetchall()

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
    if member.id == interaction.user.id:
        await interaction.response.send_message("You can't challenge yourself to a duel!", ephemeral=True)
        return

    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor(dictionary=True)

        userId = interaction.user.id  # The ID of the user who used the command
        opponent_id = member.id  # The ID of the opponent

        # Query to count the number of cards for the user
        cursor.execute("SELECT COUNT(*) as card_count FROM cards WHERE userId = ?", (userId,))
        user_card_count = cursor.fetchone()["card_count"]

        # Check if the user has at least three cards
        if user_card_count < 3:
            await interaction.response.send_message("You need at least 3 cards to send a challenge.", ephemeral=True)
            return

        # Query to count the number of cards for the opponent
        cursor.execute("SELECT COUNT(*) as card_count FROM cards WHERE userId = ?", (opponent_id,))
        opponent_card_count = cursor.fetchone()["card_count"]

        # Check if the opponent has at least three cards
        if opponent_card_count < 3:
            await interaction.response.send_message(f"{member.mention} needs at least 3 cards to accept a challenge.", ephemeral=True)
            return

        # If both players have enough cards, send the challenge with buttons
        await interaction.response.send_message(
            f"{member.mention}, {interaction.user.mention} has challenged you to a duel! Do you accept?",
            ephemeral=False
        )

        # Use followup to get the message object for editing
        challenge_message = await interaction.followup.send(
            f"{member.mention}, you have been challenged to a duel by {interaction.user.mention}!",
            view=ChallengeView(challenger=interaction.user, challenged=member, timeout_message=None),
            ephemeral=False,
        )

        # Attach the challenge message to the view for timeout handling
        challenge_view = ChallengeView(challenger=interaction.user, challenged=member, timeout_message=challenge_message)
        challenge_view.timeout_message = challenge_message
        await challenge_message.edit(view=challenge_view)

bot.run(TOKEN)
