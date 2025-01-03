from discord.ext import commands
import discord

from const import pool 

@commands.command()
async def makeloginrewards(ctx, numberOfLevels: int):
    if ctx.author.guild_permissions.administrator != True:
        await ctx.send("You do not have the required permissions to use this command.")
        return

    try:
        # Connect to the MariaDB server
        conn = pool.get_connection()
        cursor = conn.cursor()
        
        # Create the loginRewards table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS loginRewards (
                level INT PRIMARY KEY,
                rewardType VARCHAR(10) NOT NULL,
                amountOrCardId INT NOT NULL
            )
        """)
        
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
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                rewardType=VALUES(rewardType),
                amountOrCardId=VALUES(amountOrCardId)
        """, rewards)

        # Commit changes
        conn.commit()
        await ctx.send(f"Login rewards for {numberOfLevels} levels have been successfully created.")

    except Exception as e:
        await ctx.send(f"An error occurred: {e}")
    finally:
            cursor.close()
            conn.close()