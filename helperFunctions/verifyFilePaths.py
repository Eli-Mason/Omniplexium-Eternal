import os
from helperFunctions.main import logWarning
from const import FILE_PATHS, COLORS


async def verifyFilePaths(bot):
    for filePath in FILE_PATHS:
        if not os.path.isdir(filePath) and not os.path.exists(filePath):
            os.makedirs(filePath)
            print(f"{COLORS['yellow']}Created {filePath}{COLORS['reset']}")
            await logWarning(bot, f"File path {filePath} did not exist, so it was created.")
        else:
            if not os.path.exists(filePath):
                print(f"{COLORS['red']}Error: {filePath} does not exist{COLORS['reset']}")
                await logWarning(bot, f"Error: {filePath} does not exist")
    
    print(f"{COLORS['blue']}Verified all file paths{COLORS['reset']}")