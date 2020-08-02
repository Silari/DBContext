# discord bot with module based functionality.
# Now based on discord.py version 1.3.3

# DONT UPDATE APIS IF BOT ISNT CONNECTED
#  No way to find this out?
#  Maybe via 'if client.user' - will be None if not logged in?

# TESTING NOTES

# notifyon notes
# Optionally include a channel mention to ensure role has permission to view? Seems unneccessary.
# Though I'm putting this message where the notifyon is given, so hey
# maybe it is useful.

# Need some way to say that an API doesn't support an option, like twitch for adult
# Thought about getoption=None but that's the fallback if it doesn't exist.
# Maybe 'NA' or something.
#  Might be best to keep a dict of valid options {name:group}, and if it's not in
#  there it doesn't apply to that API.
#   Pretty big rewrite, hold till next. I can redo all of the option command though
#   if I do this, and have it check a dict of possible options for the category.
# HIGHLY RELATED
# Maybe give contexts a 'commands' list so that it's easier to see what are valid?
# help could use this to see what contexts have a particular command.

# SIMILAR TO ABOVE: maybe a dict with the allowed option TYPES? Then again that
# could be gotten from the defaultopts list maybe? Except that's global! so mods
# can't access it directly.
#  Maybe a dict with {'OptName':set(val1,val2,val3),'OptName2':set(True,False)}
#  Then I have an easy to access and change list of groups and their allowed
# values
# There's options that don't follow like that though - Notify being a big one,
# but that's already special case handled via global so maybe not a big deal.

# Something to move a savedmsg to a new channel if the channel
# gets changed. So 'add stream <channel>' would delete the old message and make a
# new one in the proper channel.
#  Can't move, would need to send new and delete old. Not sure it's worth it
# # I could probably do it for streamoption at least, so it's not a ton at once.

# Maybe check on_message_deleted if it was one of our savedmsg? Then could clear
# it from our list immediately to allow re-announcing.
# Only relevant if you delete then <module> announce right after.
# Could have module announce check if msg is deleted instead?
#  for context in contdict.values() :
#      for key,value in context.mydata['SavedMSG'][guild_id] :
#          if value == message_id :
#              del context.mydata['SavedMSG'][guild_id][key]
#              break
#   Easier to just have announce <stream> announce a stream regardless if it was
#   already? NO.
# TODO Revisit this. We would just need to see if the message id is in our cache now, which is a lot quicker.
#   Also we could possibly watch for edit events and edit our cached version appropriately.

# Import module and setup our client and token.
from typing import Dict, Union

import discord
import copy  # Needed to deepcopy contexts for periodic saving
import asyncio  # Async wait command
import aiohttp  # used for ClientSession which is passed to modules.
import traceback  # Used to print traceback on uncaught exceptions.
import os  # Used by loadtemps to delete the loaded files
import pickle  # Save/load contexts data
import signal  # Used to make SIGTERM shut down our bot cleanly.
# Modules that hold our context classes.
import picartoclass
import piczelclass
import twitchclass
# This holds the needed API keys. You may want to use other methods for storing these.
import apitoken

# token is the Discord API
token = apitoken.token
if not token:
    raise Exception("You must provide a valid Discord API token for use!")

version = "1.2"  # Current bot version
changelogurl = "https://github.com/Silari/DBContext/wiki/ChangeLog"
# We're not keeping the changelog in here anymore - it's too long to reliably send
# as a discord message, so it'll just be kept on the wiki. Latest version will be
# here solely as an organizational thing, until it's ready for upload to the wiki
# proper.
changelog = '''1.2 Changelog:
Added custom message cache and disabled discord.py's. This saves RAM and ensures the messages we use are cached.
Added rmmsg and updated setmsgid to handle added/removing SavedMSG and the cache.
Added savednames async generator to iterate over all unique stream names with a saved message ID. 
 Used by updatewrapper to find SavedMSGs to verify.
Added savedids async generator to iterate over all saved message IDs, optionally only those for the given stream name.
 Used in removemsg and updatemsg to find the oldest ID for a stream.'''

myloop = asyncio.get_event_loop()
client = discord.Client(loop=myloop, fetch_offline_members=False, max_messages=None)
# Invite link for the PicartoBot. Allows adding to a server by a server admin.
# This is the official version of the bot, running the latest stable release.
invite = "https://discordapp.com/api/oauth2/authorize?client_id=553335277704445953&scope=bot&permissions=268921920"
# The old version lacks manage_messages, which we need now to pin our reaction messages in notifyon
# invite = "https://discordapp.com/api/oauth2/authorize?client_id=553335277704445953&scope=bot&permissions=268913728"
# The old invite does not have manage roles permission, needed for the manage module
# oldinvite = "https://discordapp.com/api/oauth2/authorize?client_id=553335277704445953&scope=bot&permissions=478272"
# URL to the github wiki for DBContext, which has a help page
helpurl = "https://github.com/Silari/DBContext/wiki"

# Timeout used for our aiohttp instance
conntimeout = 30

# Role names for the manage module
managerolename = "StreamManage"
notifyrolename = "StreamNotify"

calledstop = False  # Did we intentionally stop the bot?

taskmods = []
tasks = []

# Keep a dict of Contexts
# Contexts
#   |-Picarto
#     |name
#     |handler
#     |Data
#       |AnnounceDict
#       |Servers
#       |Listens
#   |-Twitch
#       |AnnounceDict
#       |Servers
#       |Listens

contexts = {}
# Try to load a previously saved contexts dict
try:
    with open('dbcontexts.bin', mode='rb') as f:
        contexts = pickle.load(f)
except FileNotFoundError:
    pass
print("Initial Contexts:", contexts)
newcont = {}
contfuncs = {}


async def resolveuser(userid, guild=None):
    """Resolves a Member or User instance from the given id. The ID can be in 'username#0000' format or a user
    mention or the discord ID.

    :type userid: str
    :type guild: discord.Guild
    :rtype: discord.Member | discord.User | None
    :param userid: A string with the username and discriminator in 'username#0000' format, or a user mention string, or
     the user id.
    :param guild: discord Guild instance to search in. If not provided return can only be a User instance.
    :return: If guild is provided, searches the guild for the given userid and returns their Member instance, or None if
     not found. If guild is not provided, searches the Client users list and returns the found User instance, or None if
     not found.
    """
    # This is a mention string so we need to remove the mention portion of it.
    if userid.startswith('<@!'):
        userid = userid[3:-1]
    elif userid.startswith('<@'):
        userid = userid[2:-1]
    if guild:
        if '#' in userid:
            founduser = discord.utils.find(lambda m: str(m) == userid, guild.members)
        else:
            founduser = discord.utils.find(lambda m: str(m.id) == userid, guild.members)
    else:
        if '#' in userid:
            founduser = discord.utils.find(lambda m: str(m) == userid, client.users)
        else:
            founduser = discord.utils.find(lambda m: str(m.id) == userid, client.users)
    return founduser


class LimitedClient:
    """Allows modules limited access to needed Client functionality."""

    def __init__(self, parentclient):
        """Allows modules limited access to needed Client functionality.

        :type parentclient: discord.Client
        :param parentclient: A Client instance we use to create our LimitedClient.
        """
        # get_channel, wait_until_ready, and is_closed()
        self.get_channel = parentclient.get_channel
        self.wait_until_ready = parentclient.wait_until_ready
        self.is_closed = parentclient.is_closed
        # This is a custom function that helps resolve a Member/User instance from the username#0000 or ID. It uses the
        # users property of client which we don't want exposed.
        self.resolveuser = resolveuser
        # Stores Message instances into a cache. More selectful than the discord.py one, and keeps messages until they
        # are explicitly removed from it, rather than having a limit.
        self.messagecache: Dict[int, discord.Message] = {}

    async def cacheadd(self, message):
        """Adds the given Message instance to the cache.

        :type message: discord.Message
        :param message: The discord.Message instance to add to the cache.
        """
        self.messagecache[message.id] = message

    async def cacheget(self, messageid):
        """Gets the given message id from the cache.

        :type messageid: int
        :param messageid: An integer representing the discord ID of the message to remove.
        :rtype: None | discord.Message
        :return: The discord.Message instance matching the given id, or None if it is not cached.
        """
        return self.messagecache.get(messageid, None)

    async def cacheremove(self, *, message=None, messageid=None):
        """Removes the given Message or id from the cache. messageid is ignored if message is provided.

        :type message: discord.Message
        :param message: The discord.Message instance to add to the cache.
        :type messageid: int
        :param messageid: An integer representing the discord ID of the message to remove.
        :rtype: discord.Message | None
        :return: The cached Message instance, or None if that id was not cached.
        """
        if message:
            messageid = message.id
        elif messageid is None:
            raise ValueError("cacheremove requires either a Message instance or a message ID!")
        return self.messagecache.pop(messageid, None)


fakeclient = LimitedClient(client)


async def getglobal(guildid, option):
    """Gets the value for the option given in the global namespace, set in the
    manage context. This allows for setting an option once for all contexts
    which read from global.

    :type guildid: int
    :type option: str
    :rtype: None | object
    :param guildid: Integer representing the snowflake of the Guild we're retrieving this option for.
    :param option:  String with the name of the option to retrieve.
    :return: None if no option with that name, or the value of option-dependant type that represents its current setting
    """
    mydata = contexts["manage"]["Data"]
    if option == 'Notify':  # Special handling for notify option
        try:
            # print('getglobal',guildid,option)
            guild = client.get_guild(guildid)
            # print(guild.get_role(mydata["notifymsg"][mydata['notifyserver'][guildid]]))
            return guild.get_role(mydata["notifymsg"][mydata["notifyserver"][guildid]])
        except KeyError:
            # print('getglobal',repr(e))
            return False
    try:  # Try to read this guild's option from the manage contexts data.
        return mydata[guildid][option]
    except KeyError:  # Either server has no options, or doesn't have this option
        pass  # None found, so continue to next location.
    try:  # Lets see if the option is in the default options dict.
        return defaultopts[option]
    except KeyError:
        pass
    return None  # No option of that type found in any location.


def convertcontexts():
    """Deprecated: Used to convert old contexts to new system for 0.5 due to discord.py changes. Kept in case we need
    to make a similar change again at some point, though the setup for data has changed since then so it will need
    rewriting. """
    global newcont
    newcont = copy.deepcopy(contexts)
    for module in newcont:
        if 'AnnounceDict' in contexts[module]['Data']:
            for item in contexts[module]['Data']['AnnounceDict']:
                newcont[module]['Data']['AnnounceDict'][item] = set(
                    [int(x) for x in contexts[module]['Data']['AnnounceDict'][item]])
        if 'Servers' in contexts[module]['Data']:
            for item in contexts[module]['Data']['Servers']:
                newcont[module]['Data']['Servers'].pop(item)
                newcont[module]['Data']['Servers'][int(item)] = contexts[module]['Data']['Servers'][item]
                if 'AnnounceChannel' in newcont[module]['Data']['Servers'][int(item)]:
                    newcont[module]['Data']['Servers'][int(item)]['AnnounceChannel'] = int(
                        newcont[module]['Data']['Servers'][int(item)]['AnnounceChannel'])


# Function to setup new context handler - handles the dbcontext side of adding.
# This should only be used directly by the builtin contexts of dbcontext.py.
# All other contexts should use newmodcontext or newclasscontext.
def newcontext(name, handlefunc, data):
    """Registers a new context for the bot to handle."""
    if not (name in contexts):
        # Context doesn't exist, create and init with default data and function
        contexts[name] = {"name": name, "Data": data}
        contfuncs[name] = handlefunc
    else:
        # Context exists, update handler function
        # contexts[name]["function"] = handlefunc
        contfuncs[name] = handlefunc
        # If data wasn't created, add it
        if not contexts[name]["Data"]:
            contexts[name]["Data"] = data
        else:  # If it was, merge it with saved data overwriting defaults
            contexts[name]["Data"] = {**data, **contexts[name]["Data"]}
    return


contdict = {}


# Function to setup a module as a context - handles the module side of adding.
def newmodcontext(contextmodule):
    """Registers a module as a context holder."""
    # Module needs the following:
    # Name - a string that acts as the command to activate and the name data is stored under
    # handler - the function to call with the command requested, the message event, and a reference to the modules data
    # defaultdata - a dict to populate the modules contexts[name]["Data"] with
    newcontext(contextmodule.name,
               contextmodule.handler,
               contextmodule.defaultdata)
    contextmodule.client = fakeclient
    contextmodule.mydata = contexts[contextmodule.name]["Data"]
    contextmodule.getglobal = getglobal
    contdict[contextmodule.name] = contextmodule  # Keep a reference to it around
    try:  # If it has an updatewrapper, add it to the list of tasks to start
        if contextmodule.updatewrapper:
            taskmods.append(contextmodule)
    except AttributeError:
        pass


def newclasscontext(classinst):
    """Function to setup a class as a context - handles the instance side of adding.

    :param classinst: Instance of a class that provides the minimum needed functions for a context, like APIContext.
    """
    contdict[classinst.name] = classinst  # Keep a reference to it around
    # Instance needs the following:
    # Name - a string that acts as the command to activate and the name data is stored under
    # handler - the function to call with the command requested, the message event, and a reference to the modules data
    newcontext(classinst.name, classinst.handler, classinst.defaultdata)
    classinst.client = fakeclient
    classinst.mydata = contexts[classinst.name]["Data"]
    classinst.getglobal = getglobal
    try:
        if classinst.updatewrapper:
            taskmods.append(classinst)
    except AttributeError:
        pass


newclasscontext(picartoclass.PicartoContext())
newclasscontext(piczelclass.PiczelContext())
newclasscontext(twitchclass.TwitchContext())


async def getcontext(name, message):
    """Grabs the context handler associated with name and calls the registered
    function, providing the command and the data dict.

    :type name: str
    :type message: discord.Message
    :param name: String with the context name to call
    :param message: The discord.Message instance that invoked the context.
    """
    try:
        await contfuncs[name](message.content.split()[2:], message)
    except (discord.Forbidden, asyncio.CancelledError):
        raise
    except BaseException as e:
        print("Caught exception in getcontext", repr(e))
        traceback.print_tb(e.__traceback__)
        print("Message:", message.id, message.channel.id, message.channel.name,
              repr(message.author))
        print("Content:", message.content)


# noinspection PyUnusedLocal
async def handler(command, message, handlerdata):
    """A generic handler function for a context. It should accept a string list
    representing the command string AFTER the context identifier, the message
    and a dict that stores all it's relevant data. It should return the
    message to send to the originating channel, or None for no message."""
    # This is also used as the default init function - essentially does nothing
    return


async def helphandler(command, message):
    """Handler function which is called by getcontext when invoked by a user. Parses the command and responds as needed.

    :type command: list
    :type message: discord.Message
    :param command: List of strings which represent the contents of the message, split by the spaces.
    :param message: discord.Message instance of the message which invoked this handler.
    """
    if len(command) > 0:  # We were given additional paramters
        # Let's see if it's a command we understand.
        if command[0] == 'invite':
            msg = "I can be invited to join a server by an administrator of the server using the following links\n"
            msg += "\nNote that the link includes the permissions that I will be granted when joined.\n"
            msg += "\nThe current link is: <" + invite + ">"
            msg += "\nIf the bot is already in your server, re-inviting will NOT change the current permissions."
            await message.channel.send(msg)
            return
        elif command[0] in contfuncs:  # User asking for help with a context.
            # Redirect the command to the given module.
            # print("cont help", ["help"] + command[1:])
            await contfuncs[command[0]](["help"] + command[1:], message)
            return
    msg = "PicartoWatch bot version " + str(version)
    msg += "\nThe following commands are available for 'help': help, invite"
    msg += "\nOnline help, and bug reporting are available at: <https://github.com/Silari/DBContext/wiki>"
    msg += "\nThe complete changelog can be found at <" + changelogurl + ">"
    msg += "\nPlease use '<module> help' for help with specific modules"
    msg += "\nThe following modules are available for use: " + ", ".join(contexts)
    msg += "\nI listen to commands on any channel from users with the Manage Server permission."
    msg += " Additionally, I will listen to commands from users with a role named " + str(managerolename)
    await message.channel.send(msg)
    return


newcontext("help", helphandler, {})

defaultopts: Dict[str, Union[str, bool, None, object]] = {
    'Type': 'default',  # Type of announcement to use, default= embed with preview.
    'MSG': 'edit',  # Should messages be edited and/or removed after announcement?
    'Stop': False,  # Should no new announcements be made?
    'Channel': None,  # Default channel to announce in is no channel.
    'Adult': 'showadult'  # Should streams marked adult be shown normally?
}

globalops = {}


async def addglobal(optname, validate=None):
    """Adds a new option name to the list of options that manage will allow
    setting via 'manage setopt <optname>'. optname must be a str or evalute
    properly when compared to a string using ==. If validate is passed it
    should be a function handle which is called when the value is set as
    validate(optname,value). If the function return evalutes False, the user
    will receive a message the value is not appropriate and the value is not
    set. This system is not complete.

    :type optname: str
    :type validate: function
    :rtype: None
    :param optname: String with the name of the option to add to the global list.
    :param validate: A function that will be called in order to validate the setting of the option before it is set.
     Should return False if the data is not appropriate for this option.
    """
    defaultopts[optname] = validate


async def getuserrole(guild):
    """Find the manage role in the server

    :type guild: discord.Guild
    :rtype: None | discord.Role
    :param guild: Guild instance to find the role in.
    :return: The found role, possibly None if the role does not exist.
    """
    return discord.utils.find(lambda m: m.name == managerolename, guild.roles)


async def makeuserrole(guild):
    """Make the manage role in the given guild.

    :type guild: discord.Guild
    :rtype: None | discord.Role
    :param guild: Guild instance to create the role in.
    :return: The created role, possibly None if the creation failed.
    """
    # Find the bot role in the server
    userrole = discord.utils.find(lambda m: m.name == managerolename, guild.roles)
    # Doesn't exist, so we need to make it.
    if not userrole:
        # No permissions, no color, non-hoist, non-mentionable.
        try:
            userrole = await guild.create_role(reason="Role created for bot management", name=managerolename)
        except discord.Forbidden:  # May not have permission
            pass  # This should leave userrole empty
    return userrole


async def hasrole(member, rolename):
    """Checks if the given Member has the management role. Includes a shim for interoperability with the old role name.

    :type member: discord.Member
    :type rolename: str
    :rtype: bool
    :param member: discord.Member instance to check for a role with the given name.
    :param rolename: String with the role name to look for.
    :return: Boolean indicating if the Member has a role with the rolename.
    """
    for item in member.roles:
        # print(hasrole, item.name, client.user.name)
        if rolename == item.name:
            # print(hasrole, item.name, client.user.name)
            return True
    return False


async def hasmanagerole(member):
    """Checks if the given Member has the management role. Includes a shim for interoperability with the old role name.

    :type member: discord.Member
    :rtype: bool
    :param member: discord.Member instance to check for the roles.
    :return: Boolean indicating if the Member has the management role.
    """
    # Second half of this is a shim for 1.0 to allow the old role name to work.
    return await hasrole(member, managerolename) or await hasrole(member, client.user.name)


async def renamerole(guild):
    """Deprecated. Function to handle the name change of the management role."""
    oldrole = discord.utils.find(lambda m: m.name == client.user.name, guild.roles)
    if not oldrole:
        return "Old role was not found, can not rename."
    if await getuserrole(guild):
        return "Renaming failed, " + managerolename + " already exists."
    try:
        await oldrole.edit(reason="Adjust role to new name", name=managerolename)
        return "Role edited successfully."
    except discord.Forbidden:
        return "Bot does not have permission to rename role!"
    except discord.HTTPException:
        return "Renaming failed due to unknown reason."


async def getnotifyrole(guild):
    """Find the notify role in the server

    :type guild: discord.Guild
    :rtype: None | discord.Role
    :param guild: Guild instance to find the role in.
    :return: The found role, possibly None if the role does not exist.
    """
    userrole = discord.utils.find(lambda m: m.name == notifyrolename, guild.roles)
    return userrole  # Return the found role, or None if it failed


async def makenotifyrole(guild):
    """Make the notify role in the given guild.

    :type guild: discord.Guild
    :rtype: None | discord.Role
    :param guild: Guild instance to create the role in.
    :return: The created role, possibly None if the creation failed.
    """
    userrole = None
    try:
        # The bot should have the ping any role perm, so the role doesn't need to be mentionable
        userrole = await guild.create_role(reason="Role created for notification", name=notifyrolename)
    except discord.Forbidden:  # May not have permission
        pass  # This should leave userrole as none
    return userrole  # Return the role we made, or None if it failed


async def findmsg(guild, msgid, channel=None):
    """Attempts to find a message with just the ID and the guild it came from

    :type guild: discord.Guild
    :type msgid: int
    :type channel: discord.TextChannel
    :rtype: discord.Message
    :param guild: The guild to try and find the message in.
    :param msgid: The int representing the Discord snowflake for the message to find.
    :param channel: Channel to try and find the message in, which can help to find the message but isn't required.
    :return: The Message instance for the message id, or None if the message was not found.
    """
    # Step 1: Search given channel for message, if given
    if channel:  # Acts as a hint for where we're most likely to find the message
        try:  # Try to find the message in the channel
            return await channel.fetch_message(msgid)
        except (discord.NotFound, discord.Forbidden):
            pass  # Message wasn't here, or can't access channel. Ignore
    for chan in guild.text_channels:
        if chan != channel:  # Don't search again in our hint channel
            try:  # Try to find the message in the channel
                return await chan.fetch_message(msgid)  # If it worked, return it
            except (discord.NotFound, discord.Forbidden):
                pass  # Message wasn't here, or can't access channel. Ignore


async def managehandler(command, message):
    """Handler function which is called by getcontext when invoked by a user. Parses the command and responds as needed.

    :type command: list
    :type message: discord.Message
    :param command: List of strings which represent the contents of the message, split by the spaces.
    :param message: discord.Message instance of the message which invoked this handler.
    """
    if len(command) == 0 or command[0] == 'help':
        msg = "The following commands are available for manage. Separate multiple usernames with a single space.:"
        msg += "\nperms: Has the bot check for missing permissions, and replies with any that are missing and what " \
               "they are needed for. "
        msg += "\nnotifyon: Creates a message in the channel that users can react to to be granted a role that is " \
               "@mentioned in announcements. "
        msg += "\nnotifyoff: Turns off the notification system. Users with the role will keep it, but announcements " \
               "will not include the @mention and reactions to add/remove are ignored. "
        msg += "\nsetupchan <#channels>: Creates the user role to manage the bot, and adds an override to allow them " \
               "to send messages in the given #channels. Each #channel MUST be a channel mention. "
        msg += "\ncheck <username#0000>: Check if given user(s) have access to bot commands. Separate user names " \
               "with spaces."
        msg += "\nadd <username#0000>: Gives permission to one or more users to access bot commands. Note that bot " \
               "accounts are ALWAYS ignored. "
        msg += "\nremove <username#0000>: Revokes permission to one or more users to access bot commands. Note that " \
               "server admins ALWAYS have bot access! "
        if not message.channel.permissions_for(message.guild.me).manage_roles:
            msg += "\n**Bot does not** have permission to manage user roles. Only help, check, notifyoff, and perms " \
                   "commands will work. "
            msg += "\nPlease manually add the 'manage roles' permission to make use of additional features."
        await message.channel.send(msg)
        return
    validcommands = ('help', 'check', 'add', 'remove', 'setupchan', 'notifyon', 'notifyoff', 'perms')
    if not command[0] in validcommands:
        await message.channel.send("Please provide one of the following commands: " +
                                   ",".join(validcommands))
        return
    # We check what permissions are missing and inform the user why we need them
    if command[0] == 'perms':
        # print("manage perms")
        msg = ''
        # Perms we need: Manage roles, mention_everyone, read_message_history, embed links
        # manage messages (pinning), add reactions, read (view channels)+send messages
        # Seems to be it for now. External Emojis MIGHT be needed for future use.
        myperms = message.channel.permissions_for(message.guild.me)
        if not myperms.manage_roles:
            msg += "\nMissing 'Manage Roles' perm. This permission is needed for the bot to manage announce " \
                   "notifications and give users permission to use this bot. "
        managerole = await getuserrole(message.guild)
        if managerole:
            if message.guild.me.top_role.position < managerole.position:
                msg += "\n**Bot does not** have permission to add/remove " + managerole.name + " due to role position."
                msg += " Please ensure the " + managerole.name + " role is below the bots role."
        notifyrole = await getnotifyrole(message.guild)
        if notifyrole:
            if message.guild.me.top_role.position < notifyrole.position:
                msg += "\n**Bot does not** have permission to add/remove " + notifyrole.name + " due to role position."
                msg += " Please ensure the " + notifyrole.name + " role is below the bots role."
        if not myperms.mention_everyone:
            msg += "\nMissing 'Mention Everyone' perm. This permission is needed for the announcement notification " \
                   "feature. "
        if not myperms.read_message_history:
            msg += "\nMissing 'Read Message History' perm. This permission is needed to find old announcements for " \
                   "editing if the bot restarts. "
        if not myperms.embed_links:
            msg += "\nMissing 'Embed Links' perm. This permission is needed for announcements (except 'simple') to " \
                   "display properly. "
        if not myperms.manage_messages:
            msg += "\nMissing 'Manage Messages' perm. This permission is needed for the notification system to pin " \
                   "the message users react to to be notified. "
        if not myperms.add_reactions:
            msg += "\nMissing 'Add Reactions' perm. This permission is needed for the notification system to add the " \
                   "reaction users use to be notified. "
        # External emojis aren't used for anything - might be used for custom
        # emoji for the reaction to add/remove notification role.
        #        if not myperms.external_emojis :
        #            msg += "\nMissing 'External Emojis' perm. This permission is needed for nothing right now."
        # Check for send message permission. This MUST BE DONE LAST due to the PM
        # if we can't send messages to the channel.
        # If a channel was mentioned check send permissions there, unless it was
        # the same channel the message was sent in.
        if (len(message.channel_mentions) > 0 and
                message.channel_mentions[0] != message.channel):
            if not message.channel_mentions[0].permissions_for(
                    message.guild.me).send_messages:  # Only on the mentioned channel
                msg += "\nMissing 'Send Messages' perm for #" + message.channel_mentions[
                    0].name + ". This permission is needed to send messages to the channel. "
        # We're checking send perms for the message channel
        else:
            if not myperms.send_messages:
                # We can't send messages to the channel the command came from
                msg += "\nMissing 'Send Messages' perm for #" + message.channel.name + \
                       ". This permission is needed to send messages to the channel. "
                # So instead of responding in channel, we PM it to the user
                await message.author.send(msg)
                return  # And return so we don't try to send it twice
        if msg:  # We had at least one permission missing
            await message.channel.send(msg)
        else:
            await message.channel.send("Bot has no missing permissions.")
        return
    if command[0] == 'check':
        hasperm = set()
        noperm = set()
        msg = ""
        notfound = set()
        managerole = await getuserrole(message.guild)
        for username in command[1:]:
            founduser = await resolveuser(username, message.guild)
            if founduser:
                if founduser.bot:
                    noperm.add(username + ":bot")  # User is a bot, never allowed
                # If the user has permission, add them to the list with why
                elif founduser.guild_permissions.manage_guild:
                    hasperm.add(username + ":manage")  # User can manage guild, they have permission
                elif managerole and await hasmanagerole(founduser):
                    hasperm.add(username + ":role")  # User has the role.
                else:
                    noperm.add(username)  # User has neither
            else:
                notfound.add(username)
        if hasperm:  # We had at least one permitted user: list them
            msg += "Permitted users: " + ", ".join(hasperm)
        if noperm:  # We had at least one not permitted user: list them
            msg += "\nNot permitted users: " + ", ".join(noperm)
        if notfound:
            msg += "\nThe following users were not found in the server: " + ", ".join(notfound)
        if not msg:  # Should never happen, but maybe no user names were provided.
            msg += "Unable to check any users due to unknown error. Please ensure you provided a list of usernames " \
                   "with discriminator to check. "
        await message.channel.send(msg)
        return
    mydata = contexts['manage']['Data']  # Keep a reference to our module data
    # notify off is the only one of these that DOESNT require permissions.
    # We can just turn it off.
    if command[0] == 'notifyoff':
        # Turning off our notification feature for this server.
        # Remove the stored info from the server and message dicts
        unpinned = False
        if message.guild.id in mydata['notifyserver']:  # Is notify on?
            try:
                foundmsg = await findmsg(message.guild, mydata['notifyserver'][message.guild.id], message.channel)
                await foundmsg.unpin()
                unpinned = True
            except discord.Forbidden:
                pass  # If we don't have permission to unpin, ignore it.
            except Exception as e:
                print("notifyoff", repr(e))  # For debugging log any other error
            # Remove the dict entries for this server.
            mydata["notifymsg"].pop(mydata['notifyserver'].pop(message.guild.id))
            msg = "Notification system has been disabled."
            if unpinned:
                msg += " I have also attempted to unpin the old reaction message."
            else:
                msg += " The old reaction message is no longer needed and can be unpinned."
            await message.channel.send(msg)
            return
        await message.channel.send("Notifications are currently off for this server.")
        return
    # See if we have permission to add/remove user roles. If not, say so
    if not message.channel.permissions_for(message.guild.me).manage_roles:
        await message.channel.send(
            "Bot does not have permission to manage user roles, requested command can not be completed without it.")
        return  # We can't do any of the following things without it, so quit
    if command[0] == 'notifyon':
        # Step 1 - Find/Create the role
        notifyrole = await getnotifyrole(message.guild)
        if not notifyrole:  # We couldn't find the role, make it
            notifyrole = await makenotifyrole(message.guild)
        if not notifyrole:
            # We couldn't find or make the role. We already checked for permissions, so this shouldn't happen, but JIC
            await message.channel.send(
                "Unable to create/find the necessary role. Please ensure the bot has the manage_roles permission.")
            return
        # Check if role is assignable by the bot.
        if message.guild.me.top_role.position < notifyrole.position:
            await message.channel.send("Notify role position is higher than the bots highest role. Please move the "
                                       "notify role below the " + message.guild.me.top_role.name + " role.")
            return
        # Step 2 - Check if we already are on
        if message.guild.id in mydata['notifyserver']:  # Is notify on?
            msg = "Notifications have already been enabled on this server."
            savedmsgid = mydata['notifyserver'][message.guild.id]
            foundmsg = await findmsg(message.guild, savedmsgid, message.channel)
            if foundmsg:  # The old reaction message still exists.
                msg += " Reaction message is at " + foundmsg.jump_url
                # Check if the notifyrole id has changed. Might happen if recreated by a user or the bot.
                if notifyrole.id != mydata['notifymsg'][savedmsgid]:
                    mydata['notifymsg'][savedmsgid] = notifyrole.id
                    msg += " . The stored notify role ID did not match the found role. It has been reset."
                await message.channel.send(msg)
                if not foundmsg.pinned:  # Try to pin the message if it isn't.
                    try:
                        await foundmsg.pin()
                    except discord.Forbidden:
                        pass
                return
            # Notify system should be on, but the message is gone, so we're going to reactivate it.
            try:  # At this point we need to clean up the old remnants, cause we're going to redo everything.
                del mydata['notifyserver'][message.guild.id]  # This one must exist, we used it above.
                # This one SHOULD exist, and needs to be removed as that ID is invalid and we don't want to leave junk.
                del mydata['notifymsg'][savedmsgid]
            except KeyError:
                pass
        # If notifyon was already on, the message was removed (or unfindable) so we just treat it like it was off.
        # Step 3 - Send message to channel with info, request it be pinned/try to pin it?
        sentmsg = await message.channel.send(
            "Notifications are enabled for this server. To receive a notification when stream announcements are set, "
            "please react to this message with :sound:. To stop receiving notifications, unreact the :sound: "
            "reaction.\nIt is HIGHLY recommended this message be left pinned for users to find!")
        # Step 4 - Add the server+msgid and msgid+roleid to the dicts.
        mydata['notifyserver'][message.guild.id] = sentmsg.id
        mydata['notifymsg'][sentmsg.id] = notifyrole.id
        # Step 5 - Add the :sound: reaction to the message to make it easier to
        # react to it for others. One click, no mistakes.
        try:
            await sentmsg.pin()  # Try to pin the message
        except discord.Forbidden:  # Possibly a permission failure here, if so ignore.
            pass
        await sentmsg.add_reaction("\U0001f509")  # Unicode value for :sound:
        return
    managerole = await getuserrole(message.guild)
    if not managerole:  # Manage role doesn't exist, make it now as we'll need it
        managerole = await makeuserrole(message.guild)
    if not managerole:  # This isn't due to permissions issues, as we check that above
        await message.channel.send("Unable to obtain/create the necessary role for an unknown reason.")
        return
    if managerole and (message.guild.me.top_role.position < managerole.position):
        msg = "Bot does not have permission to manage the " + managerole.name + " role due to the role's position."
        msg += "\nPlease ensure the " + managerole.name + " role is below the bots role."
        msg += "\n" + managerole.name + " position: " + str(managerole.position) + ". Bots highest position: " + str(
            message.guild.me.top_role.position)
        await message.channel.send(msg)
        return
    if command[0] == 'setupchan':
        if message.channel_mentions:  # We can't do anything if they didn't include a channel
            # We need to set this channel to be talkable by anyone with the role.
            for channel in message.channel_mentions:
                # Validate the mentions are in this guild. It SEEMS either Discord or discord.py doesn't include them
                # anyway, but just to be sure we're still gonna check it.
                if channel.guild != message.guild:
                    await message.channel.send("I could not find " + channel.name + " in this server.")
                    continue
                msg = channel.name + ": "
                # Set everyone role to be able to read but not send in the channel
                try:
                    await channel.set_permissions(message.guild.default_role, read_messages=True, send_messages=False)
                    msg += "@everyone role set to read only permission for channel."
                except discord.Forbidden:
                    msg += "Failed to set read only permission for @everyone role for channel."
                newoverride = discord.PermissionOverwrite(**{"send_messages": True, "read_messages": True})
                # Set the bot user to be able to read and send messages
                try:
                    await channel.set_permissions(message.guild.me, overwrite=newoverride,
                                                  reason="Added read/send permissions to bot")
                    msg += "\nRead+Write permissions given to bot for channel."
                except discord.Forbidden:
                    msg += "\nFailed to give read+write permissions to bot for channel."
                # Set the manage role to be able to read and send messages
                try:
                    await channel.set_permissions(managerole, overwrite=newoverride,
                                                  reason="Added read/send message permission to bot user role.")
                    msg += "\nRead+Send permissions given to role for channel " + channel.name
                except discord.Forbidden:
                    msg += "\nFailed to give read+write permissions to management role for channel."
                await message.channel.send(msg)
            return
        await message.channel.send("You must mention one or more channels to be setup.")
        return
    if command[0] == 'add':
        added = set()
        msg = ""
        notfound = set()
        for username in command[1:]:
            founduser = await resolveuser(username, message.guild)
            if founduser:
                await founduser.add_roles(managerole, reason="Added user to bot management.")
                added.add(username)
            else:
                notfound.add(username)
        if added:
            msg += "Ok, the following users were given the role for bot commands: " + ", ".join(added)
        if notfound:
            msg += "\nThe following users were not found and could not be added: " + ", ".join(notfound)
        if not msg:
            msg += "Unable to add any users due to unknown error."
        await message.channel.send(msg)
    if command[0] == 'remove':
        removed = set()
        msg = ""
        notfound = set()
        for username in command[1:]:
            founduser = await resolveuser(username, message.guild)
            if founduser:
                await founduser.remove_roles(managerole, reason="Removed user from bot management.")
                removed.add(username)
            else:
                notfound.add(username)
        if removed:
            msg += "Ok, removed the bot command role from the following users: " + ", ".join(removed)
        if notfound:
            msg += "\nThe following users were not found: " + ", ".join(notfound)
        if not msg:
            msg += "Unable to remove roles from any users due to unknown error."
        await message.channel.send(msg)


# Add our context, default data is to have two empty dicts: notifyserver and notifymsg
newcontext("manage", managehandler, {'notifyserver': {}, 'notifymsg': {}})


async def debughandler(command, message):
    """Handler function which is called by getcontext when invoked by a user. Parses the command and responds as needed.

    :type command: list
    :type message: discord.Message
    :param command: List of strings which represent the contents of the message, split by the spaces.
    :param message: discord.Message instance of the message which invoked this handler.
    """
    # 'safe' commands like help can go up here
    # If there wasn't a command given, or the command was help
    if len(command) == 0 or command[0] == 'help':
        msg = "Debug module. This module is used for debugging/testing and notifying servers of updates/downtimes/etc."
        msg += "\nIt can not be used by anyone other than the bot developer."
        await message.channel.send(msg)
        return
    # Unsafe commands go down here
    if not (message.author.id == 273076937474441218):
        # print("Not GP, do not run",command[1:])
        await message.channel.send("Sorry, this command is limited to the bot developer.")
        return
    if command[0] == 'embed':
        # Debug to create detail embed from picarto stream
        record = await contdict["picarto"].agetstream(command[1])
        description = record['title']
        myembed = discord.Embed(title=record['name'] + " has come online!", url="https://picarto.tv/" + record['name'],
                                description=description)
        value = "Multistream: No"
        if record['multistream']:
            value = "\nMultistream: Yes"
        myembed.add_field(name="Adult: " + ("Yes" if record['adult'] else "No"),
                          value="Viewers: " + str(record['viewers']),
                          inline=True)
        myembed.add_field(name=value, value="Gaming: " + ("Yes" if record['gaming'] else "No"), inline=True)
        # myembed.set_footer(text=picartourl + record['name'])
        myembed.set_image(url=record['thumbnails']['web'])
        myembed.set_thumbnail(url="https://picarto.tv/user_data/usrimg/" + record['name'].lower() + "/dsdefault.jpg")
        msg = record['name'] + " has come online! Watch them at <https://picarto.tv/" + record['name'] + ">"
        await message.channel.send(msg, embed=myembed)
    elif command[0] == 'eval':
        if command[1] == 'await':
            await eval(" ".join(command[2:]))
        else:
            eval(" ".join(command[1:]))
    elif command[0] == 'reply':
        msg = " ".join(command[1:])
        await message.channel.send(msg)
    elif command[0] == 'replyeval':
        msg = eval(" ".join(command[1:]))
        # print(msg)
        await message.channel.send(msg)
    elif command[0] == 'sendall':
        await sendall(" ".join(command[1:]))
    elif command[0] == 'updatenotice':
        msg = "The bot has been restarted and updated to version " + str(version)
        msg += ". Please use 'help changelog' to see a list of the additions/changes/fixes to this version."
        await sendall(msg)
    elif command[0] in ('quit', 'restart'):
        global calledstop
        if command[0] == 'quit':
            calledstop = True
        else:
            calledstop = 'restart'  # Still counts as True for testing
        await message.channel.send("Client exiting. Goodbye.")
        await client.logout()
    elif command[0] == 'checkupdate':
        # This lets us see if the last update API call for our stream classes worked
        # print(picartoclass.lastupdate,piczelclass.lastupdate,twitchclass.lastupdate)
        await message.channel.send(
            "Pica: " + picartoclass.lastupdate + "Picz: " + piczelclass.lastupdate + "Twit: " + twitchclass.lastupdate)
    elif command[0] == 'checkstreams':
        streams = 0
        for module in contdict.values():
            try:
                for server in module.mydata['SavedMSG']:
                    streams += len(module.mydata['SavedMSG'][server])
            except KeyError:
                pass
        await message.channel.send("Total online streams: " + str(streams))
    elif command[0] == 'checkservers':
        # debug replyeval repr(client.guilds)
        # above gives details on servers
        await message.channel.send("I am currently in " + str(len(client.guilds)) + " servers.")
    elif command[0] == 'channelperms':
        # Gets the effective permissions for the bot in the given channel id
        if len(command) > 0:
            foundchan = client.get_channel(command[1])
            print(foundchan.permissions_for(foundchan.guild.me))
    elif command[0] == 'getmessage':
        print(await message.channel.fetch_message(command[1]))
    elif command[0] == 'editmessage':
        msg = await message.channel.fetch_message(command[1])
        await msg.edit(content=" ".join(command[2:]), suppress=False)
    elif command[0] == 'purge' and len(command[0]) > 1:
        # Attempt to delete messages after the given message id
        if message.guild.id == 318253682485624832:  # ONLY in my server
            await message.channel.purge(after=discord.Object(int(command[1])))
    elif command[0] == 'clearsaved':
        for module in contdict.values():
            try:
                module.mydata['SavedMSG'].clear()
            except KeyError:
                pass
    elif command[0] == 'listguilds':
        await message.channel.send(repr(client.guilds))
    elif command[0] == 'rename':
        for guild in client.guilds:
            msg = await renamerole(guild)
            print(msg)  # await message.channel.send(msg)
        return
    elif command[0] == 'testresolve':
        ret = []
        for comm in command[1:]:
            found = await resolveuser(comm)
            ret.append(found)
            found = await resolveuser(comm, message.guild)
            ret.append(found)
        print("testresolve", ret)
        return
    elif command[0] == 'testtop':
        msg = "Roles:"
        for myrole in message.guild.me.roles:
            msg += " Name: " + myrole.name + " Position:" + str(myrole.position)
        print(msg)
        msg = "Top Role: " + message.guild.me.top_role.name + " " + str(message.guild.me.top_role.position)
        print(msg)


newcontext("debug", debughandler, {})


async def sendall(msg):
    """Sends a message to all servers. Generally used when updates are pushed."""
    msgset = set()
    msgcontexts = ('picarto', 'twitch', 'piczel')
    for thiscon in msgcontexts:
        mydata = contexts[thiscon]['Data']
        for serverid in mydata['Servers']:
            # Find their set announcement channel and add it to the list
            try:
                msgset.add(mydata['Servers'][serverid]["AnnounceChannel"])
                continue  # Move to the next server, we got one
            except KeyError:
                pass  # Server has no announcement channel set
            # Find a channel to use via stream overrides
            if serverid in mydata['COver']:
                for stream in mydata['COver'][serverid]:
                    try:
                        msgset.add(mydata['COver'][serverid][stream]['Channel'])
                        continue
                    except KeyError:
                        pass
    # print("sendall:",msgset)
    for channelid in msgset:
        try:
            channel = client.get_channel(channelid)
            if channel:  # We may no longer be in the server which would mean no channel
                await asyncio.sleep(1)  # Sleep to avoid hitting rate limit
                await channel.send(msg)
        except (KeyError, Exception):
            pass


# Message contains:
# author - Member that sent message, or User if PM
# content - string with message
# channel - Channel it was sent from, or None if PM.
# server - Server message was sent on, or None if PM

# Server contains:
# name - server name - not unique
# id - server ID - this is unique
# owner - the server owner's Member

# Member contains:
# roles - list of Role objects member has
# top_role - highest role
# server_permissions - Returns permissions.


@client.event
async def on_member_update(before, after):
    """This is used in one specific server to prevent the Patreon bot from removing the patreon roles from users after
     they stop their pledge. He prefers to let users keep those roles if they've given him money.

     :type before: discord.Member
     :type after: discord.Member
     :param before: discord.Member with the state before the change that prompted the event.
     :param after: discord.Member with the state after the change that prompted the event.
     """
    if before.guild.id != 253682347420024832:
        return
    # print(repr(before.roles))
    # print(repr(after.roles))
    # If roles are the same, do nothing
    if before.roles == after.roles:
        return
    # 256408573397958656 - Sponsor
    # 336063609815826444 - Patron
    addspon = False
    addpat = False
    if discord.utils.find(lambda m: m.id == 256408573397958656, before.roles):
        if not discord.utils.find(lambda m: m.id == 256408573397958656, after.roles):
            addspon = True
    if discord.utils.find(lambda m: m.id == 336063609815826444, before.roles):
        if not discord.utils.find(lambda m: m.id == 336063609815826444, after.roles):
            # print("user no longer has PWDpatron")
            addpat = True
    if addspon:
        userrole = discord.utils.find(lambda m: m.id == 256408573397958656, after.guild.roles)
        await after.add_roles(userrole, reason="Re-adding removed patreon role")
    if addpat:
        userrole = discord.utils.find(lambda m: m.id == 336063609815826444, after.guild.roles)
        await after.add_roles(userrole, reason="Re-adding removed patreon role")
    return


@client.event
async def on_raw_reaction_add(rawreact):
    """Part of the manage function to add users to be notified. Checks if this is a reaction on a message we are
    watching for. If it is, calls managenotify to handle the add/removal of the role.

    :type rawreact: discord.RawReactionActionEvent
    :param rawreact: Payload for the discord.Client event that called this event.
    """
    # member - only on ADD, use if available.
    # user_id - would need to get member from this and guild_id
    # emoji - PartialEmoji - name may work? otherwise use id
    if rawreact.user_id == client.user.id:
        return  # This is us, do nothing
    # Is this a message we're monitoring for reacts? If not, exit
    if not (rawreact.message_id in contexts['manage']['Data']["notifymsg"]):
        return
    # print("RawReactAdd",repr(rawreact.member),rawreact.user_id)
    # print(rawreact.emoji.name.encode('unicode-escape').decode('ASCII'))
    # Is this an add of the sound emoji? If it is, we need to call managenotify
    if rawreact.emoji.name == '\U0001f509':
        # print("RawReactAdd sound!")
        # We get the guild for this reaction now, as managenotify expects it
        guild = client.get_guild(rawreact.guild_id)
        await managenotify(rawreact, guild)
    # Adding the :mute: emote acts as if you removed the sound emote, as a fallback
    if rawreact.emoji.name == '\U0001f507':
        # print("RawReactAdd mute!")
        rawreact.event_type = 'REACTION_REMOVE'
        # We get the guild for this reaction now, as managenotify expects it
        guild = client.get_guild(rawreact.guild_id)
        await managenotify(rawreact, guild)
    # print(rawreact.event_type)
    return


@client.event
async def on_raw_reaction_remove(rawreact):
    """Part of the manage function to remove users to be notified. Checks if this is a reaction on a message we are
    watching for. If it is, calls managenotify to handle the add/removal of the role.

    :type rawreact: discord.RawReactionActionEvent
    :param rawreact: Payload for the discord.Client event that called this event.
    """
    if rawreact.user_id == client.user.id:
        return  # This is us, do nothing
    # Is this a message we're monitoring for reacts? If not, exit
    if not (rawreact.message_id in contexts['manage']['Data']["notifymsg"]):
        return
    # We should set up member and add to rawreact, then move to handle function. Getting the member requires getting the
    # guild, so we keep that reference and pass it on to save time regetting it.
    if rawreact.emoji.name == '\U0001f509':
        # print("RawReactRemove sound!")
        guild = client.get_guild(rawreact.guild_id)
        rawreact.member = guild.get_member(rawreact.user_id)
        if not rawreact.member:  # Something bad happened
            # print("RawReactRemove was unable to find the user Member")
            return
        await managenotify(rawreact, guild)
    return


async def managenotify(rawreact, guild):
    """This should add/remove the notification role from the Member. This should only be called if the server has
    notifications enabled, so we don't need to check that.

    :type rawreact: discord.RawReactionActionEvent
    :type guild: discord.Guild
    :param rawreact: RawReactionActionEvent we need to parse to determine if we add or remove the notification role.
    :param guild: discord.Guild instance where the reaction took place.
    """
    mydata = contexts['manage']['Data']  # Has our contexts data in it
    # We need to find our role in the server.
    notifyrole = None  # ID of the notify role
    try:
        # mydata["notify"] has a dict of MSGID:RoleID. If no message id, no role
        # The server owner has to have used the 'manage notify' command to set it up
        notifyrole = guild.get_role(mydata["notifymsg"][rawreact.message_id])
    except Exception as e:  # If we fail for any reason, ignore it
        # For debugging reasons, we print the error
        print("Failed to find role?", repr(e))  # Possible the server isn't using it anymore?
    if not notifyrole:  # We couldn't find the id of the notify role for this guild
        return
    # Now we need to see if we have to add or remove that role
    if rawreact.event_type == "REACTION_ADD":  # Add the role
        await rawreact.member.add_roles(notifyrole, reason="Adding user to notify list")
    elif rawreact.event_type == "REACTION_REMOVE":  # Remove the role
        await rawreact.member.remove_roles(notifyrole, reason="Removing user from notify list")
    return


@client.event
async def on_message(message):
    """The main event handler: handles all incoming messages and assigns them to the proper context/replies to DMs.

    :param message: The message that prompted the event.
    :type message: discord.Message
    """
    # print("on_message",message.role_mentions)
    # Ignore messages we sent - this could be removed as we'd always fail the next test anyway?
    if message.author == client.user:
        return
    # We ignore any messages from other bots. Could lead to bad things.
    elif message.author.bot:
        return
    # print("not us or a bot")
    if not message.guild:  # PMs just get a help dialog and then we're done.
        msg = client.user.name + " bot version " + str(version)
        msg += "\nPlease use '@" + client.user.name + " help' in a server channel for help on using the bot."
        msg += "\nOnline help is also available at <" + helpurl + ">."
        await message.channel.send(msg)
        return
    # print("not a PM")
    # print("hasrole", await hasmanagerole(message.author),":",message.author.guild_permissions.administrator)
    # The bot listens to anyone who can manage the guild, or has the management role
    # Administrator is the old check, and is left in for legacy reasons, but they
    # should always have manage_guild in any case.
    if (message.author.guild_permissions.administrator
            or message.author.guild_permissions.manage_guild
            or await hasmanagerole(message.author)):
        # print("passed check",message.content)
        # print('<@!' + str(client.user.id) + ">",":",client.user.mention)
        # Checks if message starts with a user or nickname mention of the bot
        if (message.content.startswith('<@!' + str(client.user.id) + ">") or
                message.content.startswith('<@' + str(client.user.id) + ">")):
            command = message.content.split()
            # print("Listening for message", len(command))
            if len(command) < 2:
                msg = client.user.name + " bot version " + str(version)
                msg += "\nPlease use '@" + client.user.name + " help' for help on using the bot."
                msg += "\nOnline help is available at <" + helpurl + ">."
                await message.channel.send(msg)
            elif command[1] in contexts:
                # print("calling module",command[1], command[2:])
                # If we don't have permission to send messages in the channel, don't use
                # the typing function as that would throw Forbidden.
                if not message.channel.permissions_for(message.guild.me).send_messages:
                    msg = "I do not have permission to respond in the channel you messaged me in. While I will still " \
                          "attempt to perform the command, any error or success messages will fail. "
                    try:
                        await message.author.send(msg)
                    except discord.Forbidden:  # We aren't allowed to DM the user
                        pass  # nothing to do here
                    # This is a separate block because we need to do both even if
                    # the first fails, and we still need to ignore Forbidden in
                    # the second part.
                    try:
                        await getcontext(command[1], message)
                    except discord.Forbidden:  # Chances are we're going to fail
                        pass  # still nothing to do here
                else:
                    # If we can send messages, use the context manager
                    async with message.channel.typing():
                        await getcontext(command[1], message)
            else:
                msg = "Unknown module '" + command[
                    1] + "'. Remember, you must specify the module name before the command - e.g. 'picarto " + " ".join(
                    command[1:]) + "'"
                await message.channel.send(msg)


# Used when joining a server. Might want something for this.
# @client.event
# async def on_guild_join(server) :
#    pass

@client.event
async def on_resumed():
    """Ensure our activity is set when resuming and add a log that it resumed."""
    # print("Client resumed")
    await client.change_presence(activity=discord.Game(name="@" + client.user.name + " help"))


@client.event
async def on_ready():
    """Fires when the bot is up and running. Sets our presence and logs the connection."""
    print("------\nLogged in as", client.user.name, client.user.id, "\n------")
    # We set our activity here - we can't do it in the client creation because
    # we didn't have the user name yet
    await client.change_presence(activity=discord.Game(name="@" + client.user.name + " help"))


# Old method to close tasks and log out
def closebot():
    myloop.run_until_complete(client.logout())
    for t in asyncio.Task.all_tasks(loop=client.loop):
        if t.done():
            t.exception()
            continue
        t.cancel()
        try:
            myloop.run_until_complete(asyncio.wait_for(t, 5, loop=client.loop))
            t.exception()
        except asyncio.InvalidStateError:
            pass
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            pass
    myloop.run_until_complete(asyncio.sleep(0.25))


# Logs the bot out and ends all tasks
async def aclosebot():
    await client.logout()
    for t in asyncio.Task.all_tasks(loop=client.loop):
        if t.done():  # Task is finished, we can skip it
            # t.exception() #This would show the exception, but we don't care
            continue
        t.cancel()  # Cancels the task by raising CancelledError
        try:
            myloop.run_until_complete(asyncio.wait_for(t, 5, loop=client.loop))
            t.exception()
        except asyncio.InvalidStateError:
            pass
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            pass
    # Wait for a small delay to allow for all tasks to finish
    await asyncio.sleep(0.25)


async def savecontexts():
    """Saves the data for all contexts to a file."""
    # It'd be nice to have this only save if data changed, but considering how little data we have it seems it'd be more
    # trouble to try and track that than to just let it go.
    # A simpler method may be to hash the buffer and compare that, then save if different?
    # Pickle-ing the exact same data can load to different results, so that doesn't work.
    try:
        # Copy the current contexts into a new dictionary
        contdata = copy.deepcopy(contexts)
    except asyncio.CancelledError:  # Task was cancelled, so quit.
        return
    except Exception as e:
        # Any errors, log them as that's a serious problem.
        print("Error in deepcopy:", repr(e))
        # print(contexts)
        return
    try:
        # Dump contexts to a Bytes object - if it fails our file isn't touched
        buff = pickle.dumps(contdata, pickle.HIGHEST_PROTOCOL)
        with open('dbcontexts.bin', mode='wb') as g:
            # Now we actually write the data to the file
            g.write(buff)
    except asyncio.CancelledError:  # Task was cancelled, so quit.
        # Note that closing will save the contexts elsewhere, so we don't care
        # that we're potentially skipping a save here.
        return
    except Exception as e:
        # Again, log errors as those are potentially serious.
        print("error in savecontext", repr(e))
        # print(newcont)


async def savetask():
    """Calls savecontext every five minutes. Stops immediately if client is closed so it won't interfere with the save
     on close."""
    while not client.is_closed():
        try:
            # These were broken up into minute chunks to avoid a hang when closing
            # The try:except CancelledError SHOULD have resolved that now.
            if not client.is_closed():
                await asyncio.sleep(60)
            if not client.is_closed():
                await asyncio.sleep(60)
            if not client.is_closed():
                await asyncio.sleep(60)
            if not client.is_closed():
                await asyncio.sleep(60)
            if not client.is_closed():
                await asyncio.sleep(60)
            # We've waited five minutes, save data
            if not client.is_closed():
                # If there's some kind of error, we mostly ignore it and try again later
                try:
                    await savecontexts()
                except asyncio.CancelledError:  # Task was cancelled, so quit.
                    return
                except Exception as e:
                    print("Error in savetask:", repr(e))
        except asyncio.CancelledError:
            # Task was cancelled, so immediately exit. Bot is likely closing.
            return


def savetemps():
    """Saves temporary data for registered module and class contexts, to be loaded on restart."""
    for name, context in contdict.items():  # Iterate over all our contexts
        buff = False  # Clear buffer to remove any old data
        try:
            buff = context.savedata()  # Grab temp data from the context
        except Exception as e:
            print("Error getting savedata for", name, repr(e))
            pass
        if buff:  # We got some data to save for the context
            print("Saving data for", name, "context.")
            try:
                # Attempt to pickle the data - may fail if it's non-pickleable.
                pbuff = pickle.dumps(buff, pickle.HIGHEST_PROTOCOL)
                # Since it didn't error, time to write the pickled buffer to a file
                with open(name + '.dbm', mode='xb') as output:
                    # Now we actually write the data to the file
                    output.write(pbuff)
            except Exception as e:
                print("Save failed for", name, repr(e))
                print(buff)
                pass


def loadtemps():
    """Loads saved temp data into their modules via their loaddata function"""
    for name, context in contdict.items():  # Iterate over all our contexts
        data = False  # Clear data
        dname = name + ".dbm"  # Name is the context name, plus .dbm
        try:
            # print("Loading",dname)
            # Try to open the file and unpickle it's contents
            with open(dname, mode='rb') as g:
                data = pickle.load(g)
                # print("Found",dname, repr(data))
        except FileNotFoundError:
            continue  # No file, so we can move to the next one
        except Exception as e:
            print("Error loading data for", name, repr(e))
        try:
            if data:  # Assuming unpickling worked, send it to the context
                context.loaddata(data)
        except Exception as e:
            print("Error in loaddata!", repr(e))
        try:  # Try to remove the old file, as these aren't meant to be saved
            os.remove(dname)
        except Exception as e:
            print("Error removing file!", repr(e))


# This section should cause the bot to shutdown and exit properly on SIGTERM
# It should cause the threads to shut down, which ends client.run and then runs
# the finally block below to save the data.
# It's recommended to send SIGINT instead - systemd can do this if you're on
# Linux and using it to start/stop the bot. Ctrl+C also sends SIGINT.
# SIGINT is handled automatically by Python and works extremely well.
signal.signal(signal.SIGTERM, closebot)


async def makesession():
    """Creates an aiohttp.ClientSession instance, shared among all modules.

    :rtype: aiohttp.ClientSession
    :return: Returns an aiohttp.ClientSession to be used by any context which needs to make HTTP calls.
    """
    # We create a timeout instance to allow a max of conntimeout seconds per call
    mytime = aiohttp.ClientTimeout(total=conntimeout)
    # Note that individual requests CAN still override this, but for most APIs it
    # shouldn't take that long.
    myconn = aiohttp.ClientSession(timeout=mytime)
    return myconn


async def startbot():
    """Handles starting the bot, making the session, and starting tasks."""
    loadtemps()  # Load any saved temporary data into modules that have it
    myconn = await makesession()  # The shared aiohttp clientsession
    # Saves our context data periodically
    tasks.append(client.loop.create_task(savetask()))
    # Start our context modules' updatewrapper task, if they had one when adding.
    for modname in taskmods:
        # print("Starting task for:",modname.name)
        # This starts the modules updatewrapper and passes the connection to it.
        tasks.append(client.loop.create_task(modname.updatewrapper(myconn)))
    try:
        # Starts the discord.py client with our discord token.
        await client.start(token)
    # On various kinds of errors, close our background tasks, the bot, and the loop
    except SystemExit:
        print("SystemExit, closing")
        for task in tasks:  # Mark all tasks as cancelled
            task.cancel()
        # Logs out bot and ensures tasks were properly stopped before moving on.
        await aclosebot()
    except KeyboardInterrupt:
        print("KBInt, closing")
        for task in tasks:  # Mark all tasks as cancelled
            task.cancel()
        # Logs out bot and ensures tasks were properly stopped before moving on.
        await aclosebot()
    await myconn.close()


# noinspection PyBroadException
def startupwrapper():
    """Starts the async loop and handles exceptions that propagate outside of it, and cleanup."""
    try:
        # client.run(token)
        myloop.run_until_complete(startbot())
    # On various kinds of errors, close our background tasks, the bot, and the loop
    except Exception as e:
        # These we want to note so we can catch them where it happened
        print("Uncaught exception, closing", repr(e))
        traceback.print_tb(e.__traceback__)
    except BaseException:
        # There shouldn't be many of these, as SystemExit and KBInt are the two big ones
        # so note them so we can see what we might need to do specifically for them.
        # OR it could completely ignore our try:catch in startbot and immediately go
        # here. OK then.
        # print("Uncaught base exception, closing", repr(e))
        pass
    finally:
        try:
            for task in tasks:
                task.cancel()
            closebot()
        except Exception:
            # print(repr(e))
            pass
        # Save the handler data whenever we close for any reason.
        # Dump contexts to a Bytes object - if it fails our file isn't touched
        buff = pickle.dumps(contexts, pickle.HIGHEST_PROTOCOL)
        with open('dbcontexts.bin', mode='wb') as g:
            # pickle.dump(contexts,f,pickle.HIGHEST_PROTOCOL)
            # Actually write the data to the buffer
            g.write(buff)
        # Close our ClientSession properly to avoid an annoying message.
        # client.loop.run_until_complete(myconn.close())
        client.loop.close()  # Ensure loop is closed
    # Did someone use the debug quit option? If not, raise an error
    if not calledstop:
        raise Exception("Bot ended without being explicitly stopped!")
    else:
        # for each module, save the resume data.
        savetemps()
        if calledstop == 'restart':
            raise Exception("Restart requested.")
        else:
            # Log that the quit was requested.
            print("Called quit")


# This section is needed for Python 3.7 to 3.7.3 only.
import ssl
import sys

SSL_PROTOCOLS = (asyncio.sslproto.SSLProtocol,)


def ignore_aiohttp_ssl_error(loop):
    """Ignore aiohttp #3535 / cpython #13548 issue with SSL data after close

    There is an issue in Python 3.7 up to 3.7.3 that over-reports a
    ssl.SSLError fatal error (ssl.SSLError: [SSL: KRB5_S_INIT] application data
    after close notify (_ssl.c:2609)) after we are already done with the
    connection. See GitHub issues aio-libs/aiohttp#3535 and
    python/cpython#13548.

    Given a loop, this sets up an exception handler that ignores this specific
    exception, but passes everything else on to the previous exception handler
    this one replaces.

    Checks for fixed Python versions, disabling itself when running on 3.7.4+
    or 3.8.

    """
    if sys.version_info >= (3, 7, 4):
        return

    orig_handler = loop.get_exception_handler()

    def ignore_ssl_error(lop, context):
        if context.get("message") in {
            "SSL error in data received",
            "Fatal error on transport",
        }:
            # validate we have the right exception, transport and protocol
            exception = context.get('exception')
            protocol = context.get('protocol')
            if (
                    isinstance(exception, ssl.SSLError)
                    and exception.reason == 'KRB5_S_INIT'
                    and isinstance(protocol, SSL_PROTOCOLS)
            ):
                # print("Ignored bad exception")
                if lop.get_debug():
                    asyncio.log.logger.debug('Ignoring asyncio SSL KRB5_S_INIT error')
                return
        if orig_handler is not None:
            orig_handler(lop, context)
        else:
            lop.default_exception_handler(context)

    loop.set_exception_handler(ignore_ssl_error)


ignore_aiohttp_ssl_error(myloop)
# END 3.7 to 3.7.3 only section

# If the module was run, call our startup wrapper
if __name__ == "__main__":
    startupwrapper()
