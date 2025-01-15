# This file is a template - it must be renamed to apitoken.py and all fields filled out with the proper information.
# Discord token for bot account
token = ''
# Twitch Client-ID and Client Secret keys, used for Twitch API calls
clientid = ''
clientsecret = ''
# twitch header with token - Automatically set with the clientid provided above, no editing needed.
twitchheader = {"Client-ID": clientid}

# Server ID of your dev server. Slash commands get synced here during setup_hook for testing purposes.
devserver = 0

# User ID of the bot developer to limit debug commands to only them.
devuser = 0

# The name of the bot role that is always present, eg PicartoBot. Used to provide the role name during role management
# permission checking.
botname = ''