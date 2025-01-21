import discord
import sqlite3
import numpy as np
from datetime import datetime, timezone, timedelta
import traceback

from const import HUGGING_FACE_API_KEY_CLIENT, MAIN_CENSORSHIP_MODEL, BACKUP_CENSORSHIP_MODEL
from const import DATABASE_PATH, LOG_CHANNEL_ID, ADMIN_LOG_CHANNEL_ID, LOGIN_REMINDERS_CHANNEL_ID, COLORS, WARNING_LOG_CHANNEL_ID

async def censorMessage(message: str, model: str = MAIN_CENSORSHIP_MODEL) -> str:
    messages = [
        { "role": "system", "content": """You are a profanity filter. It is your goal to:

Use whichever of these methods that is necessary:
A) Respond \"false\" to non-explicit or barely explicit messages.
B) Respond with a slightly altered version by changing the explicit words.
C) Completely rewrite the message with a jokingly sarcastic rewrite if the message is entirely explicit and completely profane.

Misspelled profanity is still profanity. Words like \"fuck, shit, pussy, cock, dick, cunt\" are bad and should be removed either through B or C methods.

Some barely explicit words that are ok include \"damn, shit, sexy\"

Remember, DO NOT RESPOND TO THE MESSAGE YOU ARE GIVEN. REWRITE IT. THAT IS YOUR PURPOSE.

Here are some examples:

Input: \"Hello bro, what's up?\"
Output: \"false\"
Method Used: A

Input: \"Bro fuck you. I dislike you, yk?\"
Output: \"Bro frick you. I dislike you, yk?\"
Method Used: B

Input: \"Hey bro what's good? Looking sexy.\"
Output: \"false\"
Method Used: A

Input: \"Cum in my ass daddy\"
Output: \"Please release your population pudding into my bottom father\"
Method Used: C

Input: \"heyyy bro fuccck you lmao\"
Output: \"heyyy bro duck you lmao\"
Method Used: B

Input: \"fuckkk dude I hate life\"
Output: \"flip dude I hate life\"
Method Used: B

Input: \"oh nigger imma fuck you in the ass\"
Output: \"oh black person, imma shove my receptacle into your behind's opening\"
Method Used: C

Input: \"I\'m so shit at this game\"
Output: \"false\"
Method Used: A

Input: \"fucking cunts kill yourselves\"
Output: \"trucking harm yourselves\"
Method Used: C

Input: \"Do an example with it then\"
Output: \"false\"
Mehtod Used: A

DO NOT OUTPUT THE METHOD USED. ONLY OUTPUT \"false\" OR THE CENSORED MESSAGE.""" },
        { "role": "user", "content": message }
    ]

    completion = HUGGING_FACE_API_KEY_CLIENT.chat.completions.create(
        model=model, 
        messages=messages, 
        temperature=0,
        max_tokens=128,
        top_p=0.7
    )

    return completion.choices[0].message.content

def xpToLevel(xp: any) -> int:
    # Constants
    TOTAL_LEVELS = 100
    XP_LEVEL_10 = 100
    XP_LEVEL_100 = 10e12  # 1 trillion

    # Calculate the exponential growth factor
    base = (XP_LEVEL_100 / XP_LEVEL_10) ** (1 / (TOTAL_LEVELS - 10))
    
    # Ensure xp is treated as a int
    xp = int(xp)

    # Calculate the level using logarithmic transformation
    if xp <= XP_LEVEL_10:
        # every muiltply of 10 xp is a level
        return int(xp // 10)
    elif xp >= XP_LEVEL_100:
        return TOTAL_LEVELS

    # Reverse-engineer the level based on the xp input
    level = 10 + np.log(xp / XP_LEVEL_10) / np.log(base)
    return int(level)



def levelToXp(level: int) -> int:
    # Constants
    TOTAL_LEVELS = 100
    XP_LEVEL_10 = 100
    XP_LEVEL_100 = 10e12  # 1 trillion

    # Calculate the exponential growth factor
    base = (XP_LEVEL_100 / XP_LEVEL_10) ** (1 / (TOTAL_LEVELS - 10))
    
    if level <= 10:
        # XP grows linearly for levels <= 10
        return level * 10
    elif level >= TOTAL_LEVELS:
        # XP caps at XP_LEVEL_100 for level 100
        return int(XP_LEVEL_100)

    # Calculate XP required for the level
    xp = XP_LEVEL_10 * (base ** (level - 10))
    return int(xp)



async def checkLoginRemindersAndSend(bot) -> None:
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT userId, lastLogin FROM users WHERE loginReminders = TRUE")
            users = cursor.fetchall()
            
            # I'm breaking one of my rules here and adding a print statement
            #print(users)
            #channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
            #await channel.send(f"```ansi\n{COLORS['yellow']}{users}{COLORS['reset']}```")

            for user in users:
                userId, lastLogin = user
                # Calculate time since last login
                now = datetime.now()
                last_login_time = datetime.fromtimestamp(lastLogin)
                time_diff = now - last_login_time

                # Check if it's been approximately 40 hours since last login
                if timedelta(hours=40) <= time_diff <= timedelta(hours=41):
                    try:
                        userObj = await bot.fetch_user(userId)
                        await userObj.send("Hey! You have 4 hours until you lose your login streak. Don't forget to login in!")
                    
                    except discord.errors.NotFound:
                        channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
                        await channel.send(f"```ansi\n{COLORS['red']}User `{userId}` not found while checking login reminders.{COLORS['reset']}```")
                    
                    except discord.errors.Forbidden:
                        channel = bot.get_channel(LOGIN_REMINDERS_CHANNEL_ID)
                        await channel.send(f"{userObj.mention} You have 4 hours until you lose your login streak. Don't forget to login in!")

    except sqlite3.Error as e:
        print(f"Database error while checking login reminders: {e}")

async def updateXpAndCheckLevelUp(ctx, bot, xp: int, add: bool = True) -> None:
    # Input validation
    if isinstance(xp, float):
        xp = int(xp)
    elif isinstance(xp, str):
        try:
            xp = int(xp)
        except ValueError:
            raise ValueError("argument 'xp' must be an int, float, or a string that can be converted to an integer.")

    if not isinstance(add, bool):
        raise ValueError("argument 'add' must be a boolean.")

    # Get discord author
    try:
        discordAuthor = ctx.author
    except AttributeError:
        discordAuthor = ctx.user

    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()

            # Get current XP
            cursor.execute("SELECT xp FROM users WHERE userId = ?", (discordAuthor.id,))
            database = cursor.fetchone()

            if not database:
                raise ValueError(f"User {discordAuthor.id} not found in database")

            current_xp = database[0]
            current_level = xpToLevel(current_xp)

            # Update XP based on add flag
            new_xp = current_xp + xp if add else current_xp - xp
            cursor.execute("UPDATE users SET xp = ? WHERE userId = ?", (new_xp, discordAuthor.id))
            conn.commit()

            # Calculate new level after XP update
            newLevel = xpToLevel(new_xp)

            levelUp = current_level < newLevel
            levelDown = current_level > newLevel

            if levelUp or levelDown:
                # Get the appropriate channel
                try:
                    channel = bot.get_channel(LOG_CHANNEL_ID)
                except AttributeError:
                    channel = bot.client.get_channel(LOG_CHANNEL_ID)

                # Determine if we should mention the user
                doMention = (newLevel == 1 or newLevel > 9) if levelUp else True

                # Handle level up
                if levelUp:
                    for i in range(current_level, newLevel):
                        now = datetime.now(timezone.utc)
                        embed = discord.Embed(
                            title="Member Leveled Up",
                            description=f"**Member:** \n{discordAuthor}\n\n"
                                        f"**Account Level:** \n{i + 1}\n",
                            color=discord.Color.green(),
                            timestamp=now
                        )
                        embed.set_thumbnail(url=discordAuthor.display_avatar.url)

                        await channel.send(
                            discordAuthor.mention if doMention else '', 
                            embed=embed
                        )

                        # Handle role assignment
                        role = discord.utils.get(ctx.guild.roles, name=f"Level {i + 1}")
                        if role is None:
                            await logError(bot, ValueError(f"Role Level {i + 1} does not exist."), traceback.format_exc(), 
                                            f'Role Level {i + 1} does not exist.', ctx)
                            continue

                        if role in discordAuthor.roles:
                            await logError(bot, ValueError(f"{discordAuthor.name} already has the Level {i + 1} role, but we tried to give it to them again."), 
                                            traceback.format_exc(), f"{discordAuthor.name} already has the Level {i + 1} role, but we tried to give it to them again.", 
                                            ctx)
                            continue

                        await discordAuthor.add_roles(role)

                # Handle level down
                if levelDown:
                    for i in range(current_level, newLevel, -1):
                        now = datetime.now(timezone.utc)
                        embed = discord.Embed(
                            title="Member Leveled Down",
                            description=f"**Member:** \n{discordAuthor}\n\n"
                                        f"**Account Level:** \n{i - 1}\n",
                            color=discord.Color.red(),
                            timestamp=now
                        )
                        embed.set_thumbnail(url=discordAuthor.display_avatar.url)

                        await channel.send(
                            discordAuthor.mention if doMention else '', 
                            embed=embed
                        )

                        # Handle role removal
                        role = discord.utils.get(ctx.guild.roles, name=f"Level {i}")
                        if role is None:
                            await logError(bot, ValueError(f"Role Level {i} does not exist."), traceback.format_exc(), 
                                            f'Role Level {i} does not exist.', ctx)
                            continue

                        if role not in discordAuthor.roles:
                            await logError(bot, ValueError(f"{discordAuthor.name} does not have the Level {i} role, but we tried to remove it."), 
                                            traceback.format_exc(), f"{discordAuthor.name} does not have the Level {i} role, but we tried to remove it.", 
                                            ctx)
                            continue

                        await discordAuthor.remove_roles(role)

    except sqlite3.Error as e:
        await logError(bot, e, traceback.format_exc(), f"Database error in updateXpAndCheckLevelUp", ctx)
    except Exception as e:
        await logError(bot, e, traceback.format_exc(), f"Error in updateXpAndCheckLevelUp", ctx)


def copyCard(cardId: int, userId: int) -> None:
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT itemName FROM cards WHERE itemId = ?", (cardId,))
        cardName = cursor.fetchone()[0]

        if cardName is None:
            raise ValueError(f"Card with ID {cardId} does not exist.")

        cursor.execute("INSERT INTO cards (itemName, userId, cardId) VALUES (?, ?, ?)", (cardName, userId, cardId)) # card name is a tuple
        conn.commit()

        # get the current max itemId
        cursor.execute("SELECT MAX(itemId) FROM cards")
        maxItemId = cursor.fetchone()[0]

    return None

async def logError(bot, error: Exception, traceback: traceback, errorMessage: str = '', ctx: discord.Message = None) -> None:
    try:
        channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
    except AttributeError:
        channel = bot.client.get_channel(ADMIN_LOG_CHANNEL_ID)
    
    now = datetime.now(timezone.utc)
    embed = discord.Embed(
        title="Error Log",
        description=f"**Error Message:**\n```{errorMessage}```\n\n"
                    f"**Error:**\n```{error}```\n\n"
                    f"**Traceback:**\n```{traceback}```\n"
                    f"**Context:**\n```{ctx}```",
        color=discord.Color.red(),
        timestamp=now
    )

    await channel.send(embed=embed)

    return None

async def logWarning(bot, warning: str, ctx: discord.Message = None) -> None:
    try:
        channel = bot.get_channel(WARNING_LOG_CHANNEL_ID)
    except AttributeError:
        channel = bot.client.get_channel(WARNING_LOG_CHANNEL_ID)
    
    now = datetime.now(timezone.utc)
    embed = discord.Embed(
        title="Warning Log",
        description=f"**Warning:**\n```{warning}```\n\n"
                    f"**Context:**\n```{ctx}```",
        color=discord.Color.orange(),
        timestamp=now
    )

    await channel.send(embed=embed)

    return None