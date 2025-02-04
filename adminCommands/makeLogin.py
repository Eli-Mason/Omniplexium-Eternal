import sqlite3

from discord.ext import commands
from const import DATABASE_PATH, COLORS

@commands.command()
async def makeloginrewards(ctx, numberOfLevels: int = None) -> None:
    if ctx.author.guild_permissions.administrator != True:
        await ctx.send(f'''```ansi
{COLORS['yellow']}You do not have the required permissions to use this command.{COLORS['reset']}
```''')
        return

    if numberOfLevels is None:
        await ctx.send(f'''```ansi
{COLORS['red']}Please provide the number of levels for which to create login rewards.{COLORS['reset']}
```''')
        return

    with sqlite3.connect(DATABASE_PATH) as conn:
        try:
            cursor = conn.cursor()
            
            # Prepare data for insertion
            rewards = []
            xp_amount = 10
            xp_increment = 20

            for level in range(1, numberOfLevels + 1):
                if level == 10:
                    rewards.append((level, "card", 6))
                elif level % 5 == 0:  # Money reward every 5 levels
                    rewards.append((level, "money", level * 2))
                    xp_increment += 10  # Increase XP increment every 5 levels
                else:
                    if level == 1:
                        rewards.append((level, "xp", xp_amount))
                    else:
                        xp_amount += xp_increment
                        rewards.append((level, "xp", xp_amount))
            
            # Insert rewards into the database
            cursor.executemany("""
                INSERT INTO loginRewards (level, rewardType, amountOrCardId)
                VALUES (?, ?, ?)
                ON CONFLICT(level) DO UPDATE SET
                    rewardType=excluded.rewardType,
                    amountOrCardId=excluded.amountOrCardId
            """, rewards)

            conn.commit()
            await ctx.send(f'''```ansi
{COLORS['blue']}Login rewards for {numberOfLevels} levels have been successfully created.{COLORS['reset']}
```''')

        except Exception as e:
            await ctx.send(f'''```ansi
{COLORS['red']}An error occurred: {e}\u001b[0m{COLORS['reset']}
```''')
            return