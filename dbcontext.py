#discord bot with module based functionality.
#Now based on discord.py version 1.2.5

#Todo for 0.8:
#Add in "streamoption streamname <options>" for overriding options per stream?
#getoption supports reading if set in ['COver'][guildid][rec]['Option'][option]
#Done, not at all tested. Added new setstreamoption which handles the setting,
#including making the nested dicts.

#Add messages when using certain commands if the API is currently down - ie failed last update
##Done, test? add/addmult, detailannounce when failed, 

#Todo for 0.9:
#VERY IMPORTANT
#Start using getoption for anything that needs to get an option. That provides
#free support for any of the overrides/global options/etc. Especially announce
#stuff - creation/editing.

#If set to listen in a channel, via listen or listen <chan>, PM the user setting
#the message if the bot does not have view, or send message permission in the
#channel given.

#Rewrite the messages so they're marked offline quicker, with the message being
#reused if it comes back within 10 minutes. Basically just change the edit message
#part to note that it is currently offline?

#Clean up various uses of server to guild, to match discord.py/Discord usage
#instead of server.
##Likewise, should ensure I always use stream to refer to a stream from picarto/etc
##and not channel, to avoid confusing the discord term with it.
###getchannel when i wanted resolvechannel already got me once, ffs
####This means doing a lot of find/replace, so I'm holding off until next version

#maybe rewrite stop to not clear the listen channel. Instead things would check
#COver for the stop, possibly in getchannel

#Need some way to say that an API doesn't support an option, like twitch for adult
#Thought about getoption=None but that's the fallback if it doesn't exist.
#Maybe 'NA' or something.
##Might be best to keep a dict of valid options {name:group}, and if it's not in
##there it doesn't apply to that API.
###Pretty big rewrite, hold till next. I can redo all of the option command though
###if I do this, and have it check a dict of possible options for the category.
#HIGHLY RELATED
#Maybe give contexts a 'commands' list so that it's easier to see what are valid?
#help could use this to see what contexts have a particular command.

##Can also allow "PWNotify" role that can get @'d if proper option is set.
###Do this via reacting to a message sent by the bot. Can unreact to unset?

#Add a module named Global for handling global settings - pretty simple data layout
#ServerID->['Channel'],['MSG'],['Type'], etc.
#Need to add a way for modules to READ but not WRITE this - getglobal(globalname)?
#Reading done, but still need a way to set this.
##See below, module options instead

#Similar to parsechannel, add a getoption(Type) to resolve an option setting
#Probably add a defaultoptions dict to basecontext to control what to return
#when there isn't one set. defaultopts = {'Type':'default','MSG':'edit'}
#Again, this can handle getting the global value via getglobal if needed.
#Done, apart from global. global ALSO done, just need to be able to set it
##ALSO need a way to delete options. Both from the global store and context store
###Previously this was going to be through manage setopt, but thinking about it
###I'd rather make a new module for it, options, and direct things to use that
###whenever possible, rather than invoking it for each APIContext. Simpler.
####Deleting options is done in streamoption with the 'clear' option, which deletes em all.__call__

#General TODO list/ideas:
#maybe have it announce online channels if it hasn't announced them before -
#ie was offline when they came online, rather than only when they first come online
##This would require either constantly going through the entire online list and finding
##which don't have a saved channel, or modifying updatewrapper to hold off on
##the first update until it can use that to add any messages it needs to.
###On the other hand, doing it that way would mean that I could save the savedmsgs
###onto disk in case of shutdown, then on load match those back up automatically
###to still running streams/edit them to offline if needed. That'd be nice.
#Maybe a way to permalink a message to a stream so that it always edits that one
#message instead, never making a new one. Seems kinda pointless, but easy enough
#New option - 'single', that says to do this? ###Don't think I will cause you want
###the new message so people get notified.

#Kinda similarly, something to move a savedmsg to a new channel if the channel
#gets changed. So 'add stream <channel>' would delete the old message and make a
#new one in the proper channel.

#Should look and see if it's easy to determine stream length for picarto/twitch/piczel
#The current version works ok, but if I do end up moving messages like above then
#that'll reset the msgid, which resets the start time. If it's already present in
#the record in parsed, should be easy enough to grab it. If not, then msgid is fine

#Holdover from 0.5:
#Add role management permission - DONE

#@Bot announce - announces here for all?
#@Bot announce <channel> - announce in <channel> for all?

#All modules TODO
#Option to @here - probably better handled by channel notifications user side
##Adding in the notify role instead, so that'd handle it just fine.

#Redo detail announce so that it responds in the channel it was requested in?

version = 0.8 #Current bot version
changelog = {}
changelog["0.8"] = '''0.8 from 0.7 Changelog:
GENERAL
Added adult/noadult option. Will hide streams that are marked as adult, if the API supports it.
  Please note that this is based on the streamer setting that option appropriately, and that previews may be cached from non-safe periods both on the API and user side.
  Do not rely on this option to perfectly shield your users from potentially NSFW content.
  list command will state if adult streams are enabled or not.
'manage check' command now explicitly lists if members are a bot: bots never have permission to address the bot.
'manage create <channelmention>' command added - will create the bot role if necessary, and then add a permission override for the given channel for read + send messages.
stop command now unsets announcement channel and prevents new announcements from being made, even if they have an overridden announcement channel.
  Using listen will start announcements again. Old announcements will still be edited/removed when applicable.
  list command will state if the stop command is currently active.
list command now shows channel overrides when present.
announce command will cause the bot to announce any live streams that have not been announced.
calling the help module with a context name will pass the help command to that module.
Fixed an error in basecontext that prevented help from working.
twitch streams now handle not having a game id set.
'streamoption <streamname> <option>' command added, which sets an option only for the given stream.
PICZEL
Modified code for API change to avatar url location
Please see the github for further items.'''
changelog["0.7"] = '''0.7 from 0.6 Changelog:
GENERAL
Added stream length to edited announcement messages.
listen command changed to allow mentioning a channel to make it the announcement channel. If none given, it is still the channel the command was given in.
add command now allows mentioning a channel after the stream name to make that stream announce in the mentioned channel, rather than the default listen channel.
addmult also now allows mentioning a channel to set a channel override for all the channels given. It can be anywhere in the command.
addmult now strips a trailing comma from channel names if present, to allow for copy/pasting the output of the list command without modification.
remove and removemult commands now deletes/stops editing current announcement for the deleted stream.
Fixed an issue where streams were marked as offline before the proper wait time.
Quitting using the debug quit command now exits with status code 42, to allow for checking of intentional stoppage.
  Bot exit due to other reasons (SIGINT/SIGTERM/etc) is handled better, but still needs work.
API based modules now track if the last API update succeeded. Failure will be noted in the list command.
Please see the github for further items.'''
changelog["0.6"] = '''0.6 from 0.5 Changelog:
GENERAL
Data saving made more robust, and most errors should be found before attempting to save data.
Activity is re-set when resuming connection.
list command for all modules links to the set announcement channel, instead of just saying the name.
API based modules rewritten to be classes, inheriting from a common basecontext class.
basecontext caches record IDs to avoid needing multiple calls.
basecontext handles attempting announcement in a server it is not a member of.
basecontext handles attempting editing announcement when no announcement was saved.
basecontext uses more specific exceptions for error catching, to avoid hiding unexpected errors.
Closing the bot is handled more gracefully.
Twitch module now uses properly aiohttp for all connections.
Added a small purpose-built module for one server to handle unwanted role changes.'''
changelog["0.5"] = '''0.5 from 0.4 Changelog:
GENERAL
Updated for discord.py current version: 1.1.1.
  This should make the bot considerably more reliable in case of internet or server outages.
Link to online version of help on the github page added.
Added removemult command - removes multiple streams, separated by space, same as addmult.
Bot nows shows the typing status while responding to commands.
Updated API parsing to handle 0-byte returns. Update will be skipped for that cycle.
  Both picarto and piczel were updated. Twitch has not due to differences in the API.
Changed internal handling of module data - no longer passed to the handler.
Fixed list command for all modules not checking if server options exist.
Fixed addmult command for all modules failing if channel was already added.
Changed data storage name to dbcontexts.bin.
MANAGE MODULE - NEW
Added. Allows for easier managing of roles allowing bot usage. Requires Manage Roles permission!'''
changelog["0.4"] = '''0.4 from 0.3 Changelog:
GENERAL
Add piczel.tv support.
Renamed code files.
All API keys moved to a separate file for security.
All modules support setting multiple options at once. Later options overwrite previous options if conflicting.
Periodic saving of data ACTUALLY running.
Minor internal code changes to better support context framework.
Background tasks are now properly cancelled on exit, refactored task creation.
Important messages are sent to any server which has registered a listening channel.
  Typically these are announcements of update rollouts, or possibly downtimes
PICZEL MODULE - NEW
Added. Commands are identical to picarto module, minor output differences.
PICARTO MODULE
Split into own module, instead of inline with discordbot code.
Detail command now returns a message if a user was not provided.
Now supports editing of announcement messages with current info, including if stream is offline
  Optionally, can delete the announcement when channel goes offline
TWITCH MODULE
Detail command now returns a message if a user was not provided.
Now supports editing of announcement messages with current info, including if stream is offline
  Optionally, can delete the announcement when channel goes offline'''
changelog["0.3"] = '''0.3 from 0.2 Changelog:
GENERAL
Added Twitch.tv stream support.
context data is now merged onto default data rather than replacing it entirely.
Context data now saves regularly, as well as at shutdown.
Bot now shows a Playing message with the command for help.
PICARTO MODULE
Add commands now verify stream names during adding. Avoids issues with mismatched capitalizations/misspellings.
Added option for how announcements are displayed - default, no preview (noprev), and simple.
List command now shows currently online streams in bold.
Added addmult command to add multiple streams at once.
Refactor update thread to catch errors and resume updates afterwards.
Refactor help to show when help command OR no command.
TWITCH MODULE
Added. Commands are identical to picarto module, minor output differences.'''
changelog["0.2"] = '''0.2 from 0.1 Changelog:
GENERAL
Change trigger to be an @mention
Bot now ignores all bot users.
Users with a Role named <Bot Discord Name> have permission to use bot commands.
  Administrators on the server will always have permission to use commands.
Removed some debug stuff.
Added code to hopefully save data if process is SIGTERMd. Periodic saves coming soon.
PICARTO MODULE
Added limit of 100 listens per server.
Changed announce method to a media-rich embed with channel avatar and preview.
Added 'detail' command which responds with announce-style window with more info.
Adding a watched channel will announce that channel immediately if online.
Updated help to current functionality.
Changed Request module to aiohttp to avoid blocking.
Small refactor on update thread to not run an unneeded final update when shutting down.
HELP MODULE
Added version and changelog commands.'''
changelog["0.1"] = "0.1 Changelog:\nInitial Version."

#Import module and setup our client and token.
import discord
import copy #Needed to deepcopy contexts for periodic saving
import asyncio #Async wait command
import aiohttp #used for ClientSession which is passed to modules.
import traceback #Used to print traceback on uncaught exceptions.

myloop = asyncio.get_event_loop()
client = discord.Client(loop=myloop)
#Invite link for the PicartoBot. Allows adding to a server by a server admin.
#This is the official version of the bot, running the latest stable release.
invite = "https://discordapp.com/api/oauth2/authorize?client_id=553335277704445953&scope=bot&permissions=268913728"
#The old invite does not have manage roles permission, needed for the manage module
oldinvite = "https://discordapp.com/api/oauth2/authorize?client_id=553335277704445953&scope=bot&permissions=478272"
#URL to the github wiki for DBContext, which has a help page
helpurl = "https://github.com/Silari/DBContext/wiki"

calledstop = False #Did we intentionally stop the bot?

#This holds the needed API keys. You may want to use other methods for storing these.
import apitoken
#token is the Discord API
token = apitoken.token
if not token :
    raise Exception("You must provide a valid Discord API token for use!")

import pickle #Save/load contexts data

taskmods = []
tasks = []

#Keep a dict of Contexts
#Contexts
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
#Try to load a previously saved contexts dict
try :
    with open('dbcontexts.bin',mode='rb') as f:
        contexts = pickle.load(f)
except FileNotFoundError :
    pass
print("Initial Contexts:",contexts)
newcont = {}
contfuncs = {}

async def getglobal(guildid,option,rec=None) :
    '''Gets the value for the option given in the global namespace, set in the
       manage context. This allows for setting an option once for all contexts
       which read from global.'''
    try : #Try to read this guild's option from the manage contexts data.
        return contexts["manage"]["Data"][guildid][option]
    except KeyError : #Either server has no options, or doesn't have this option
        pass #None found, so continue to next location.
    try : #Lets see if the option is in the default options dict.
        return defaultopts[option]
    except KeyError :
        pass
    return None #No option of that type found in any location.

#Used to convert old contexts to new one for 0.5 due to discord.py changes
def convertcontexts() :
    global newcont
    newcont = copy.deepcopy(contexts)
    for module in newcont :
        if 'AnnounceDict' in contexts[module]['Data'] :
            for item in contexts[module]['Data']['AnnounceDict'] :
                newcont[module]['Data']['AnnounceDict'][item] = set([int(x) for x in contexts[module]['Data']['AnnounceDict'][item]])
        if 'Servers' in contexts[module]['Data'] :
            for item in contexts[module]['Data']['Servers'] :
                newcont[module]['Data']['Servers'].pop(item)
                newcont[module]['Data']['Servers'][int(item)] = contexts[module]['Data']['Servers'][item]
                if 'AnnounceChannel' in newcont[module]['Data']['Servers'][int(item)] :
                    newcont[module]['Data']['Servers'][int(item)]['AnnounceChannel'] = int(newcont[module]['Data']['Servers'][int(item)]['AnnounceChannel'])

#Function to setup new context handler - handles the dbcontext side of adding.
#This should only be used directly by the builtin contexts of dbcontext.py.
#All other contexts should use newmodcontext or newclasscontext.                   
def newcontext(name,handlefunc,data) :
    '''Registers a new context for the bot to handle.'''
    if not (name in contexts) :
        #Context doesn't exist, create and init with default data and function
        contexts[name] = {"name":name,"Data":data}
        contfuncs[name] = handlefunc
    else :
        #Context exists, update handler function
        #contexts[name]["function"] = handlefunc
        contfuncs[name] = handlefunc
        #If data wasn't created, add it
        if not contexts[name]["Data"] :
            contexts[name]["Data"] = data
        else : #If it was, merge it with saved data overwriting defaults
            contexts[name]["Data"] = {**data, **contexts[name]["Data"]}
    return

#Function to setup a module as a context - handles the module side of adding.
def newmodcontext(modname) :
    '''Registers a module as a context holder.'''
    #Module needs the following:
    #Name - a string that acts as the command to activate and the name data is stored under
    #handler - the function to call with the command requested, the message event, and a reference to the modules data
    newcontext(modname.name, modname.handler, modname.defaultdata)
    modname.client = client
    modname.mydata = contexts[modname.name]["Data"]
    modname.getglobal = getglobal
    try :
        if modname.updatewrapper :
            taskmods.append(modname)
    except :
        pass

#No longer used, switched to class based contexts.
##import twitchcontext
##newmodcontext(twitchcontext)
##import piczelcontext
##newmodcontext(piczelcontext)
##import picartocontext
##newmodcontext(picartocontext)

#Function to setup a class as a context - handles the instance side of adding.
classcontexts = []
def newclasscontext(classinst) :
    classcontexts.append(classinst) #Keep a reference to it around
    #Instance needs the following:
    #Name - a string that acts as the command to activate and the name data is stored under
    #handler - the function to call with the command requested, the message event, and a reference to the modules data
    newcontext(classinst.name, classinst.handler, classinst.defaultdata)
    classinst.client = client
    classinst.mydata = contexts[classinst.name]["Data"]
    classinst.getglobal = getglobal
    try :
        if classinst.updatewrapper :
            taskmods.append(classinst)
    except :
        pass

import picartoclass
newclasscontext(picartoclass.PicartoContext())
import piczelclass
newclasscontext(piczelclass.PiczelContext())
import twitchclass
newclasscontext(twitchclass.TwitchContext())

async def getcontext(name,message) :
    '''Grabs the context handler associated with name and calls the registered
       function, providing the command and the data dict.'''
    thiscontext = contexts[name]
    await contfuncs[name](message.content.split()[2:],message)

async def handler(command, message, handlerdata) :
    '''A generic handler function for a context. It should accept a string list
       representing the command string AFTER the context identifier, the message
       and a dict that stores all it's relevant data. It should return the
       message to send to the originating channel, or None for no message.'''
    #This is also used as the default init function - essentially does nothing
    return

async def helphandler(command, message) :
##    if command :
##        msg = 'For help with a specific context, please use "<context> help"'
##        await message.channel.send(msg)
##    else :
    #print("help", command)
    if len(command) > 0 :
        if command[0] == "version" :
            msg = client.user.name + " bot version " + str(version)
            msg += ". Please use the 'help changelog' command for update details."
            await message.channel.send(msg)
        elif command[0] == "versions" :
            msg = "The following versions of PicartoWatch exist: "
            msg += ", ".join(changelog)
            await message.channel.send(msg)
        elif command[0] == "changelog" :
            #print(len(command))
            if len(command) == 1 :
                command.append(version)
            try :
                msg = changelog[str(command[1])]
                await message.channel.send(msg)
            except (KeyError, ValueError) as e :
                msg = "No changelog exists for version " + str(command[1])
                await message.channel.send(msg)
        elif command[0] == "help" :
            msg = "PicartoWatch bot version " + str(version)
            msg += "\nThe following commands are available for 'help':"
            msg += "\nhelp, changelog, invite, version, versions"
            await message.channel.send(msg)
        elif command[0] == 'invite' :
            msg = "I can be invited to join a server by an administrator of the server using the following links\n"
            msg += "\nNote that the link includes the permissions that I will be granted when joined.\n"
            msg += "\nIf you do not wish to use the manage module: <" + invite + ">"
            msg += "\nIf you wish to use the manage module: <" + roleinvite + ">"
            msg += "\nNote that if the bot is already in your server, re-inviting will NOT reset permissions."
            await message.channel.send(msg)
        elif command[0] in contfuncs : #User asking for help with a context.
            #Redirect the command to the given module.
            #print("cont help", ["help"] + command[1:])
            await contfuncs[command[0]](["help"] + command[1:],message)
    else :
        msg = "PicartoWatch bot version " + str(version)
        msg += "\nOnline help and bug reporting are available at: <https://github.com/Silari/DBContext/wiki>"
        msg += "\nPlease use '<module> help' for help with specific modules"
        msg += "\nThe following modules are available for use: " + ", ".join(contexts)
        msg += "\nI listen to commands on any channel from users with the Administrator role in channel."
        msg += "\nAdditionally, I will listen to commands from users with a role named " + str(client.user.name)
        await message.channel.send(msg)

newcontext("help",helphandler,{})

defaultopts = {
    'Type':'default', #Type of announcement to use, default= embed with preview.
    'MSG':'edit', #Should messages be edited and/or removed after announcement?
    'Stop':False, #Should no new announcements be made?
    'Channel':None, #Default channel to announce in is no channel.
    'Adult':True #Should streams marked adult be shown normally?
}

globalops = {}

async def addglobal(optname,validate=None) :
    '''Adds a new option name to the list of options that manage will allow
       setting via 'manage setopt <optname>'. optname must be a str or evalute
       properly when compared to a string using ==. If validate is passed it
       should be a function handle which is called when the value is set as
       validate(optname,value). If the function return evalutes False, the user
       will receive a message the value is not appropriate and the value is not
       set.'''
    defaultopts[optname] = validate

async def getuserrole(guild) :
    #Find the bot role in the server
    userrole = discord.utils.find(lambda m: m.name == client.user.name, guild.roles)
    #Doesn't exist, so we need to make it.
    if not userrole :
        #Named after the bot, no permissions, no color, non-hoist, non-mentionable.
        try :
            userrole = await guild.create_role(reason="Role created for bot management",name=client.user.name)
        except : #May not have permission, dunno what else.
            pass #This should leave userrole as none
    return userrole

#Checks if the Member has a role with the specified name
async def hasrole(member, rolename) :
    for item in member.roles :
        #print(hasrole, item.name, client.user.name)
        if rolename == item.name :
            return True
            #print(hasrole, item.name, client.user.name)
    return False

async def managehandler(command, message) :
    #Commands: check (if user can use bot), help, (Check for manage_role here!)
    #add, remove
    if len(command) == 0 or not (command[0] in ('help','check','add','remove','create')) :
        await message.channel.send("Please provide one of the following commands: help, check, add, remove")
        return
    userrole = await getuserrole(message.guild)
    message.guild.me.top_role.position
    if command[0] == 'help' :
        msg = "The following commands are available for manage. Separate multiple usernames with a single space.:"
        msg += "\ncheck <username#0000>: Check if given user(s) have access to bot commands."
        msg += "\nadd <username#0000>: Gives permission to one or more users to access bot commands. Note that bot accounts are ALWAYS ignored."
        msg += "\nremove <username#0000>: Revokes permission to one or more users to access bot commands. Note that channel admins ALWAYS have bot access!"
        if not message.channel.permissions_for(message.guild.me).manage_roles :
            msg += "\n**Bot does not** have permission to manage user roles. Only check and help commands are active."
            msg += "\Please manually add the 'manage roles' permission to make use of additional features."
        if message.guild.me.top_role.position < userrole.position :
            msg += "\n**Bot does not** have permission to add/remove " + userrole.name + " due to role position."
            msg += "\nPlease ensure the " + userrole.name + " role is below the bots role."
            msg += "\n" + userrole.name + " position: " + str(userrole.position) + ". Bots highest position: " + str(message.guild.me.top_role.position)
        await message.channel.send(msg)
        return
    if command[0] == 'check' :
        hasperm = set()
        noperm = set()
        msg = ""
        notfound = set()
        for username in command[1:] :
            founduser = discord.utils.find(lambda m: str(m) == username, message.channel.guild.members)
            if founduser :
                if founduser.bot :
                    noperm.add(username + ":bot") #User is a bot, never allowed
                #If the user has permission, add them to the list with why
                elif founduser.guild_permissions.administrator :
                    hasperm.add(username + ":admin") #User is an admin, they always have permission
                elif userrole and await hasrole(founduser,userrole.name) :
                    hasperm.add(username + ":role") #User has the role.
                else :
                    noperm.add(username) #User has neither
            else :
                notfound.add(username)
        if hasperm : #We had at least one permitted user: list them
            msg += "Permitted users: " + ", ".join(hasperm)
        if noperm : #We had at least one not permitted user: list them
            msg += "\nNot permitted users: " + ", ".join(noperm)
        if notfound :
            msg += "\nThe following users were not found in the server: " + ", ".join(notfound)
        if not msg : #Should never happen, but maybe no user names were provided.
            msg += "Unable to check any users due to unknown error. Please ensure you provided a list of usernames to check."
        await message.channel.send(msg)
        return
    if not (command[0] in ['add','remove','create']) :
        await message.channel.send("Unknown command Please use 'manage help' to see available commands.")
        return
    #See if we have permission to add/remove user roles
    if not message.channel.permissions_for(message.guild.me).manage_roles :
        await message.channel.send("Bot does not have permission to manage user roles.")
        return
    if message.guild.me.top_role.position < userrole.position :
        msg = "Bot does not have permission to add/remove " + userrole.name + " due to role position."
        msg += "\nPlease ensure the " + userrole.name + " role is below the bots role."
        msg += "\n" + userrole.name + " position: " + str(userrole.position) + ". Bots highest position: " + str(message.guild.me.top_role.position)
        await message.channel.send(msg)
        return
    if command[0] == 'create' :
        if not userrole : #This isn't due to permissions issues, as we check that above
            await message.channel.send("Unable to obtain/create the necessary role for unknown reason.")
            return
        if message.channel_mentions : #We can't do anything if they didn't include a channel
            #We need to set this channel to be talkable by anyone with the role.
            channel = message.channel_mentions[0]
            newoverride = discord.PermissionOverwrite(**{"send_messages":True,"read_messages":True})
            try :
                await channel.set_permissions(userrole,overwrite=newoverride,reason="Added send message permission to bot user role.")
                msg = "Role has been created and an override for read+send set in channel " + channel.name
                await message.channel.send(msg)
            except discord.Forbidden :
                msg = "Bot does not have permission to set read+send override in channel " + channel.name + ". Please ensure it has the read message and write message permissions in that channel."
                await message.channel.send(msg)
    if command[0] == 'add' :
        if not userrole :
            await message.channel.send("Unable to obtain/create the necessary role for unknown reason.")
            return
        added = set()
        msg = ""
        notfound = set()
        for username in command[1:] :
            founduser = discord.utils.find(lambda m: str(m) == username, message.channel.guild.members)
            if founduser :
                await founduser.add_roles(userrole,reason="Added user to bot management.")
                added.add(username)
            else :
                notfound.add(username)
        if added :
            msg += "Ok, the following users were given the role for bot commands: " + ", ".join(added)
        if notfound :
            msg += "\nThe following users were not found and could not be added: " + ", ".join(notfound)
        if not msg :
            msg += "Unable to add any users due to unknown error."
        await message.channel.send(msg)
    if command[0] == 'remove' :
        userrole = await getuserrole(message.guild)
        if not userrole :
            await message.channel.send("Unable to obtain/create the necessary role for unknown reason.")
            return
        removed = set()
        msg = ""
        notfound = set()
        for username in command[1:] :
            founduser = discord.utils.find(lambda m: str(m) == username, message.channel.guild.members)
            if founduser :
                await founduser.remove_roles(userrole,reason="Removed user from bot management.")
                removed.add(username)
            else :
                notfound.add(username)
        if removed :
            msg += "Ok, removed the bot command role from the following users: " + ", ".join(removed)
        if notfound :
            msg += "\nThe following users were not found: " + ", ".join(notfound)
        if not msg :
            msg += "Unable to remove roles from any users due to unknown error."
        await message.channel.send(msg)

newcontext("manage",managehandler,{})

async def debughandler(command, message) :
    #'safe' commands like help can go up here
    if len(command) > 0 and command[0] == 'help' :
        msg = "Debug module. This module is used for debugging/testing and notifying servers of updates/downtimes/etc."
        msg += "\nIt can not be used by anyone other than the bot developer."
        await message.channel.send(msg)
        return
    if not (message.author.id == 273076937474441218) :
        #print("Not GP, do not run",command[1:])
        await message.channel.send("Sorry, this command is limited to the bot developer.")
        #await message.channel.send("Sorry, you are not the developer and do not have access to this command.\nThe debug feature should not be loaded into the public version of PicartoWatch.")
        return
    if len(command) == 0 :
        return
    if command[0] == 'embed' :
        rec = await picartocontext.agetchannel(command[1])
        description = rec['title']
        myembed = discord.Embed(title=rec['name'] + " has come online!",url="https://picarto.tv/" + rec['name'],description=description)
        value = "Multistream: No"
        if rec['multistream'] :
            value = "\nMultistream: Yes"
        myembed.add_field(name="Adult: " + ("Yes" if rec['adult'] else "No"),value="Viewers: " + str(rec['viewers']),inline=True)
        myembed.add_field(name=value,value="Gaming: " + ("Yes" if rec['gaming'] else "No"),inline=True)
        #myembed.set_footer(text=picartourl + rec['name'])
        myembed.set_image(url=rec['thumbnails']['web'])
        myembed.set_thumbnail(url="https://picarto.tv/user_data/usrimg/" + rec['name'].lower() + "/dsdefault.jpg")
        msg = rec['name'] + " has come online! Watch them at <https://picarto.tv/" + rec['name'] + ">"
        await message.channel.send(msg,embed=myembed)
    elif command[0] == 'eval' :
        if command[1] == 'await' :
            await eval(" ".join(command[2:]))
        else :
            eval(" ".join(command[1:]))
    elif command[0] == 'reply' :
        msg = " ".join(command[1:])
        await message.channel.send(msg)
    elif command[0] == 'replyeval' :
        msg = eval(" ".join(command[1:]))
        await message.channel.send(msg)
    elif command[0] == 'sendall' :
        await sendall(" ".join(command[1:]))
    elif command[0] == 'updatenotice' :
        msg = "The bot has been restarted and updated to version " + str(version)
        msg += ". Please use 'help changelog' to see a list of the additions/changes/fixes to this version."
        await sendall(msg)
    elif command[0] == 'quit' :
        global calledstop
        calledstop = True
        await message.channel.send("Client exiting. Goodbye.")
        await client.logout()
        #client.loop.close() #This is closed later
    elif command[0] == 'checkupdate' :
        #This lets us see if the last update API call for our stream classes worked
        #print(picartoclass.lastupdate,piczelclass.lastupdate,twitchclass.lastupdate)
        await message.channel.send("Pica: " + picartoclass.lastupdate + "Picz: " + piczelclass.lastupdate + "Twit: " + twitchclass.lastupdate)
    elif command[0] == 'channelperms' :
        #Gets the effective permissions for the bot in the given channel id
        if len(command) > 0 :
            foundchan = client.get_channel(command[1])
            print(foundchan.permissions_for(foundchan.guild.me))
    elif command[0] == 'getmessage' :
        print(await message.channel.fetch_message(command[1]))


newcontext("debug",debughandler,{})

#Sends a message to all servers
async def sendall(msg) :
    msgset = set()
    msgcontexts = ('picarto','twitch','piczel')
    for thiscon in msgcontexts :
        mydata = contexts[thiscon]['Data']
        for server in mydata['Servers'] :
            try :
                msgset.add(mydata['Servers'][server]["AnnounceChannel"])
            except KeyError :
                pass #Server has no announcement channel set
    #print("sendall:",msgset)
    for servchan in msgset :
            channel = client.get_channel(servchan)
            #channel = client.get_channel(mydata['Servers'][server]["AnnounceChannel"])
            if channel : #We may no longer be in the server which would mean no channel
                await channel.send(msg)

#I don't remember what this was for.
#I think it was a debug thing which isn't needed due to the debug context
def sendmessage(channel,chanid) :
    pass

#Message contains:
#author - Member that sent message, or User if PM
#content - string with message
#channel - Channel it was sent from, or None if PM.
#server - Server message was sent on, or None if PM

#Server contains:
#name - server name - not unique
#id - server ID - this is unique
#owner - the server owner's Member

#Member contains:
#roles - list of Role objects member has
#top_role - highest role
#server_permissions - Returns permissions.


#This is used in one specific server to prevent the Patreon bot from removing
#the patreon roles from users after they stop their pledge. He prefers to let
#users keep those roles if they've given him money.
@client.event
async def on_member_update(before, after) :
    if before.guild.id != 253682347420024832 :
        return
    #print(repr(before.roles))
    #print(repr(after.roles))
    #If roles are the same, do nothing
    if before.roles == after.roles :
        return
    #256408573397958656 - Sponsor
    #336063609815826444 - Patron
    addspon = False
    addpat = False
    if discord.utils.find(lambda m: m.id == 256408573397958656, before.roles) :
        if not discord.utils.find(lambda m: m.id == 256408573397958656, after.roles) :
            addspon = True
    if discord.utils.find(lambda m: m.id == 336063609815826444, before.roles) :
        if not discord.utils.find(lambda m: m.id == 336063609815826444, after.roles) :
            #print("user no longer has PWDpatron")
            addpat = True
    if addspon :
        userrole = discord.utils.find(lambda m: m.id == 256408573397958656, after.guild.roles)
        await after.add_roles(userrole,reason="Re-adding removed patreon role")
    if addpat :
        userrole = discord.utils.find(lambda m: m.id == 336063609815826444, after.guild.roles)
        await after.add_roles(userrole,reason="Re-adding removed patreon role")

@client.event
async def on_message(message):
    #Ignore messages we sent
    if message.author == client.user :
        return
    else :
        pass
    #We ignore any messages from other bots. Could lead to bad things.
    if message.author.bot :
        return
    #Currently we ignore PMs. Later, this will prompt the basic help dialog.
    if not message.guild : #PMs just get a help dialog and then we're done.
        msg = client.user.name + " bot version " + str(version)
        msg += "\nPlease use '@" + client.user.name + " help' in a server channel for help on using the bot."
        msg += "\nOnline help is also available at <" + helpurl + ">."
        await message.channel.send(msg)
        return
    hasrole = False
    #Check if one of the users roles matches the bot's name
    for item in message.author.roles :
        #print(hasrole, item.name, client.user.name)
        if client.user.name == item.name :
            hasrole = True
            #print(hasrole, item.name, client.user.name)
    #The bot listens to anyone who is an admin, or has a role named after the bot
    if message.author.guild_permissions.administrator or hasrole :
        if message.content.startswith('<@!' + str(client.user.id) + ">") :
            command = message.content.split()
            #print("Listening for message", len(command))
            if len(command) < 2 :
                msg = client.user.name + " bot version " + str(version)
                msg += "\nPlease use '@" + client.user.name + " help' for help on using the bot."
                msg += "\nOnline help is available at <" + helpurl + ">."
                await message.channel.send(msg)
            elif command[1] in contexts :
                async with message.channel.typing() :
                    await getcontext(command[1],message)
            else :
                msg = "Unknown command '" + command[1] + "'."
                await message.channel.send(msg)

#Used when joining a server. Might want something for this.        
#@client.event
#async def on_guild_join(server) :
#    pass

@client.event
async def on_resumed() :
    #Ensure our activity is set when resuming.
    print("Client resumed")
    await client.change_presence(activity=discord.Game(name="@" + client.user.name + " help"))

@client.event
async def on_ready() :
    print("------\nLogged in as")
    print(client.user.name)
    print(client.user.id)
    print("------")
    #We set our activity here - we can't do it in the client creation because we don't have the user name yet
    await client.change_presence(activity=discord.Game(name="@" + client.user.name + " help"))

def closebot() :
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

async def aclosebot() :
    await client.logout()
    for t in asyncio.Task.all_tasks(loop=client.loop):
        if t.done(): #Task is finished, we can skip it
            #t.exception() #This would show the exception, but we don't care
            continue
        t.cancel() #Cancels the task by raising CancelledError
        try:
            myloop.run_until_complete(asyncio.wait_for(t, 5, loop=client.loop))
            t.exception()
        except asyncio.InvalidStateError:
            pass
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            pass
    #Wait for a small delay to allow for all tasks to finish
    await asyncio.sleep(0.25)

async def savecontexts() :
    try :
        newcont = copy.deepcopy(contexts)
    except asyncio.CancelledError : #Task was cancelled, so quit.
        return
    except Exception as e :
        print("Error in deepcopy:",repr(e))
        #print(contexts)
        return
    try :
        #Dump contexts to a Bytes object - if it fails our file isn't touched
        buff = pickle.dumps(newcont,pickle.HIGHEST_PROTOCOL)
        with open('dbcontexts.bin',mode='wb') as f:
                #Actually write the data to the buffer
                f.write(buff)
    except asyncio.CancelledError : #Task was cancelled, so quit.
        return
    except Exception as e :
        print("error in savecontext",repr(e))
        #print(newcont)

async def savetask() :
    #Saves data every five minutes. Stops immediately if client is closed so it
    #won't interfere with the save on close.
    while not client.is_closed() :
        try :
            #These were broken up into minute chunks to avoid a hang when closing
            #The try:except CancelledError SHOULD have resolved that now.
            if not client.is_closed() :
                await asyncio.sleep(60)      
            if not client.is_closed() :
                await asyncio.sleep(60)      
            if not client.is_closed() :
                await asyncio.sleep(60)        
            if not client.is_closed() :
                await asyncio.sleep(60)        
            if not client.is_closed() :
                await asyncio.sleep(60)
            #We've waited five minutes, save data
            if not client.is_closed() :
                #If there's some kind of error, we mostly ignore it and try again later
                try :
                    await savecontexts()
                except asyncio.CancelledError : #Task was cancelled, so quit.
                    return
                except Exception as e :
                    print("Error in savetask:", repr(e))
        except asyncio.CancelledError :
            return

import signal
#This section should cause the bot to shutdown and exit properly on SIGTERM
#It should cause the threads to shut down, which ends client.run and then runs
#the finally block below to save the data.
#It's recommended to send SIGINT instead - systemd can do this if you're on
#Linux and using it to start/stop the bot. Ctrl+C also sends SIGINT.
#SIGINT is handled automatically by Python and works extremely well.
signal.signal(signal.SIGTERM,closebot)

async def makesession() :
    #Setup our aiohttp.ClientSession to pass to our modules that need it
    mytime = aiohttp.ClientTimeout(total=60)
    #Note that individual requests CAN still override this, but for most APIs it
    #shouldn't take that long.
    myconn = aiohttp.ClientSession(timeout=mytime)
    return myconn

async def startbot() :
    myconn = await makesession()
    #Saves our context data periodically
    tasks.append(client.loop.create_task(savetask()))
    #Start our context modules' updatewrapper task, if they had one when adding.
    for modname in taskmods :
        #print("Starting task for:",modname.__name__)
        tasks.append(client.loop.create_task(modname.updatewrapper(myconn)))
    try :
        await client.start(token)
    #On various kinds of errors, close our background tasks, the bot, and the loop
    except SystemExit :
        print("SystemExit or KBInt, closing")
        #task.cancel()
        for task in tasks :
            task.cancel()
        await aclosebot()
    except KeyboardInterrupt :
        print("SystemExit or KBInt, closing")
        #task.cancel()
        for task in tasks :
            task.cancel()
        await aclosebot()
        return
    await myconn.close()

def startupwrapper() :
    try :
        #client.run(token)
        myloop.run_until_complete(startbot())
    #On various kinds of errors, close our background tasks, the bot, and the loop
    except Exception as e :
        #These we want to note so we can catch them where it happened
        print("Uncaught exception, closing", repr(e))
        traceback.print_tb(e.__traceback__)
##        for task in tasks :
##            task.cancel()
##        closebot()
##        client.loop.close()
    except BaseException as e :
        #There shouldn't be many of these, as SystemExit and KBInt are the two big ones
        #so note them so we can see what we might need to do specifically for them.
        #OR it could completely ignore our try:catch in startbot and immediately go
        #here. OK then. 
        #print("Uncaught base exception, closing", repr(e))
        pass
##        for task in tasks :
##            task.cancel()
##        closebot()
##        client.loop.close()
    finally :
        try :
            for task in tasks :
                task.cancel()
            closebot()
        except Exception as e :
            #print(repr(e))
            pass
        #Save the handler data whenever we close for any reason.
        #Old and shouldn't be needed anymore - functions are stored separately now
        for cont in contexts :
            if 'function' in contexts[cont] :
                del contexts[cont]['function']
        #Dump contexts to a Bytes object - if it fails our file isn't touched
        buff = pickle.dumps(contexts,pickle.HIGHEST_PROTOCOL)
        with open('dbcontexts.bin',mode='wb') as f:
            #pickle.dump(contexts,f,pickle.HIGHEST_PROTOCOL)
            #Actually write the data to the buffer
            f.write(buff)
        #Close our ClientSession properly to avoid an annoying message.
        #client.loop.run_until_complete(myconn.close())
        client.loop.close() #Ensure loop is closed
    #Did someone use the debug quit option? If not, raise an error
    if not calledstop :
        raise Exception("Bot ended without being explicitly stopped!")
    #If so, print a message for logging purposes
    if calledstop :
        print("Called quit")

#This section is needed for Python 3.7 to 3.7.3 only.
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

    def ignore_ssl_error(loop, context):
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
                #print("Ignored bad exception")
                if loop.get_debug():
                    asyncio.log.logger.debug('Ignoring asyncio SSL KRB5_S_INIT error')
                return
        if orig_handler is not None:
            orig_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(ignore_ssl_error)
ignore_aiohttp_ssl_error(myloop)

if __name__ == "__main__" :
    startupwrapper()
