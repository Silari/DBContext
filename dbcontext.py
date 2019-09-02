#discord bot with module based functionality.
#Now based on discord.py version 1.2.2

#Core TODO list:
#IF I END UP ALLOWING MULTIPLE INSTANCES TO SHARE ONE UPDATETASK THEN I NEED TO
#CORRECT USAGE OF PARSED TO BE .CLEAR AND .UPDATE INSTEAD OF REPLACING OUTRIGHT.
#This would mean redoing updatetask to deepcopy the old parsed to a new one to
#save it instead.

#ADD NotImplementedError TO FUNCTIONS NEEDING TO BE OVERRIDDEN!
#Not sure there are any of these left tbh

#I've seen a few cases of offline streams not getting edited to offline.
##Maybe some error in removemsg is causing it but getting hidden?

#If we add a channel we're already watching, does it resend an announcement?
#If so, stop that. Check for saved ID.

#maybe have it announce online channels if it hasn't announced them before -
#ie was offline when they came online, rather than only when they first come online
##This would require either constantly going through the entire online list and finding
##which don't have a saved channel, or modifying updatewrapper to hold off on
##the first update until it can use that to add any messages it needs to.
###On the other hand, doing it that way would mean that I could save the savedmsgs
###onto disk in case of shutdown, then on load match those back up automatically
###to still running streams/edit them to offline if needed. That'd be nice.

#Holdover from 0.5:
#Add role management permission - DONE
##Can also allow "PWNotify" role that can get @'d if proper option is set.
###Do this via reacting to a message sent by the bot. Can unreact to unset?

#0.6 Idea:
#Rewrite context modules to be class based
#This would allow for loading multiple copies of a class, just use a different
#name. The API calls and such would still need to be shared though! Maybe check
#if parsed is already filled or if non-default don't run, just use the already
#saved parsed. Would need that to be static then? Or not, since it's saved to the
#module itself, so each class would be able to access it just fine. Would need to
#keep a separate copy inside each class instance though so it'd know what changed
#unless I rewrite the module to keep the changes.

#Ok what if class based, with a default to an overall set of options if not set?
#If I make fallbacks that might allow setting different channels for different
#listens even within the same module. <Listen instance>-><context instance>-><discord bot options>
#Honestly it'd be easier to just set the listen instance to the context/discordbot channel
#Only downside would be changing the discordbot channel afterwards wouldn't change all the listens
#unless it always overwrites the old channel with new channel, which could be a minor issue.

#@Bot announce - announces here for all?
#@Bot accounce <channel> - announce in <channel> for all?

#All modules TODO
#Now that options exist, add option to ignore Adult streams in announcements.
##Not everything may support that - not a priority anyway - don't watch em if you don't want to see em.
#Option to @here
#Maybe redo options to be a ['Servers'][server]['Options'] = set, includes all options in one group.
##That would make it more difficult to remove conflicting options though?
#Redo detail announce so that it responds in the channel it was requested in?

version = 0.7 #Current bot version
changelog = {}
changelog["0.7"] = '''0.7 from 0.6 Changelog:
GENERAL
Quitting using the debug quit command now exits with status code 42, to allow for checking of intentional stoppage.
Updates before declaring a stream offline moved to variable, as it's used in multiple places now.
API based modules now track if the last API update succeeded. Failure will be noted in the list command.
API modules all share a ClientSession instance.
API calls have more stringent timeouts for server responses.
Added acallapi, async function to get the given URL, with optional headers. This is used to centralize API handling.
  All API calls in APIContext, Picartoclass, Piczelclass, and Twitchclass use acallapi now.
updateparsed added to APIContext, used by Picarto+Piczel. Twitch still overrides.
agetchannel added to APIContext, and result modified by subclasses as necessary.
Added stream length to edited announcement messages.
'''
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
import sys #Used for sys.exit(42) when debug quit is used.

myloop = asyncio.get_event_loop()
client = discord.Client(loop=myloop)
#Invite link for the PicartoBot. Allows adding to a server by a server admin.
#This is the official version of the bot, running the latest stable release.
invite = "https://discordapp.com/api/oauth2/authorize?client_id=553335277704445953&scope=bot&permissions=478272"
invite = "https://discordapp.com/api/oauth2/authorize?client_id=553335277704445953&scope=bot&permissions=268913728"
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
    else :
        msg = "PicartoWatch bot version " + str(version)
        msg += "\nOnline help and bug reporting are available at: <https://github.com/Silari/DBContext/wiki>"
        msg += "\nPlease use '<module> help' for help with specific modules"
        msg += "\nThe following modules are available for use: " + ", ".join(contexts)
        msg += "\nI listen to commands on any channel from users with the Administrator role in channel."
        msg += "\nAdditionally, I will listen to commands from users with a role named " + str(client.user.name)
        await message.channel.send(msg)

newcontext("help",helphandler,{})

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
    if len(command) == 0 :
        await message.channel.send("Please provide a command!")
        return
    if command[0] == 'help' :
        msg = "The following commands are available for manage. Separate multiple usernames with a single space.:"
        msg += "\ncheck <username#0000>: Check if given user(s) have access to bot commands."
        msg += "\nadd <username#0000>: Gives permission to one or more users to access bot commands. Note that bot accounts are ALWAYS ignored."
        msg += "\nremove <username#0000>: Revokes permission to one or more users to access bot commands. Note that channel admins ALWAYS have bot access!"
        if not message.channel.permissions_for(message.guild.me).manage_roles :
            msg += "\n**Bot does not** have permission to manage user roles. Only check and help commands are active."
            msg += "\Please manually add the 'manage roles' permission to make use of additional features."
        await message.channel.send(msg)
        return
    if command[0] == 'check' :
        userrole = await getuserrole(message.guild)
        hasperm = set()
        noperm = set()
        msg = ""
        notfound = set()
        for username in command[1:] :
            founduser = discord.utils.find(lambda m: str(m) == username, message.channel.guild.members)
            if founduser :
                if founduser.guild_permissions.administrator :
                    hasperm.add(username + ":admin")
                elif userrole and await hasrole(founduser,userrole.name) :
                    hasperm.add(username + ":role")
                else :
                    noperm.add(username)
            else :
                notfound.add(username)
        if hasperm :
            msg += "Permitted users: " + ", ".join(hasperm)
        if noperm :
            msg += "\nNot permitted users: " + ", ".join(noperm)
        if notfound :
            msg += "\nThe following users were not found in the server: " + ", ".join(notfound)
        if not msg :
            msg += "Unable to check any users due to unknown error."
        await message.channel.send(msg)
        return
    if not (command[0] in ['add','remove']) :
        await message.channel.send("Unknown command Please use 'manage help' to see available commands.")
        return
    if not message.channel.permissions_for(message.guild.me).manage_roles :
        await message.channel.send("Bot does not have permission to manage user roles.")
        return
    if command[0] == 'add' :
        userrole = await getuserrole(message.guild)
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
        print("Not GP, do not run",command[1:])
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
        msg = eval(command[1:])
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
        await client.logout() #closebot()
        client.loop.close()
    elif command[0] == 'checkupdate' :
        print(picartoclass.lastupdate,piczelclass.lastupdate,twitchclass.lastupdate)
    elif command[0] == 'typing' :
        await asyncio.sleep(6)
        await message.channel.send("Wait done.")
        
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
    #print(repr(before))
    #print(repr(after))
    if before.guild.id != 253682347420024832 :
        return
    print(repr(before.roles))
    print(repr(after.roles))
    #If roles are the same, do nothing
    if before.roles == after.roles :
        return
    #256408573397958656 - Sponsor
    #336063609815826444 - Patron
    addspon = False
    addpat = False
    if discord.utils.find(lambda m: m.id == 256408573397958656, before.roles) :
        #print("user had Trixsponsor")
        if not discord.utils.find(lambda m: m.id == 256408573397958656, after.roles) :
            #print("user no longer has trixsponsor")
            addspon = True
    if discord.utils.find(lambda m: m.id == 336063609815826444, before.roles) :
        #print("user had PWDpatron")
        if not discord.utils.find(lambda m: m.id == 336063609815826444, after.roles) :
            #print("user no longer has PWDpatron")
            addpat = True
    if addspon :
        #print("Adding Trixsponsor")
        userrole = discord.utils.find(lambda m: m.id == 256408573397958656, after.guild.roles)
        await after.add_roles(userrole,reason="Re-adding removed patreon role")
    if addpat :
        #print("user had PWDpatron")
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
        command = message.content.split()
        if message.content.startswith('<@' + str(client.user.id) + ">") :
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
    await client.change_presence(activity=discord.Game(name="@" + client.user.name + " help"))
    
@client.event
async def on_ready() :
    print('------\nLogged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')
    #We set out activity here - we can't do it in the client creation because we don't have the user name yet
    await client.change_presence(activity=discord.Game(name="@" + client.user.name + " help"))

def closebot() :
    client.loop.run_until_complete(client.logout())
    for t in asyncio.Task.all_tasks(loop=client.loop):
        if t.done():
            t.exception()
            continue
        t.cancel()
        try:
            client.loop.run_until_complete(asyncio.wait_for(t, 5, loop=client.loop))
            t.exception()
        except asyncio.InvalidStateError:
            pass
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            pass

async def savecontexts() :
    try :
        newcont = copy.deepcopy(contexts)
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
                except Exception as e :
                    print("Error in savetask:", repr(e))
        except asyncio.CancelledError :
            return

import signal
#This section should cause the bot to shutdown and exit properly on SIGTERM
#It should cause the threads to shut down, which ends client.run and then runs
#the finally block below to save the data.
signal.signal(signal.SIGTERM,closebot)

async def makeclient() :
    #Setup our aiohttp.ClientSession to pass to our modules that need it
    mytime = aiohttp.ClientTimeout(total=60)
    #Note that individual requests CAN still override this, but for most APIs it
    #shouldn't take that long.
    myconn = aiohttp.ClientSession(timeout=mytime)
    return myconn

async def startbot() :
    myconn = await makeclient()
    #Saves our context data periodically
    tasks.append(client.loop.create_task(savetask()))
    #Start our context modules' updatewrapper task, if they had one when adding.
    for modname in taskmods :
        #print("Starting task for:",modname.__name__)
        tasks.append(client.loop.create_task(modname.updatewrapper(myconn)))
    await client.start(token)
    
def startupwrapper() :
    try :
        #client.run(token)
        myloop.run_until_complete(startbot())
    #On various kinds of errors, close our background tasks, the bot, and the loop
    except SystemExit:
        print("SystemExit, closing")
        #task.cancel()
        for task in tasks :
            task.cancel()
        closebot()
        client.loop.close()
    except KeyboardInterrupt:
        print("KBInt, closing")
        #task.cancel()
        for task in tasks :
            task.cancel()
        closebot()
        client.loop.close()
    except Exception as e :
        print("Uncaught exception, closing", repr(e))
        raise
        #task.cancel()
        for task in tasks :
            task.cancel()
        closebot()
        client.loop.close()
    except BaseException as e :
        print("Uncaught base exception, closing", repr(e))
        #task.cancel()
        for task in tasks :
            task.cancel()
        closebot()
        client.loop.close()
    finally :
        #task.cancel()
        for task in tasks :
            task.cancel()
        #Save the handler data whenever we close for any reason.
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
    if calledstop :
        sys.exit(42) #Asked to quit - used to tell systemd to not restart

if __name__ == "__main__" :
    startupwrapper()
    myloop.close() #Ensure loop is closed
