#discord bot with module based functionality.
#Now based on discord.py version 1.1.1

#Core TODO list:
#0.5

#Add role management permission - DONE
##Can also allow "PWNotify" role that can get @'d if proper option is set.
###Do this via reacting to a message sent by the bot. Can unreact to unset?

#0.6 Idea:
#Rewrite context modules to be class based? picartocontext(name='picarto')
#Would allow GREATLY simplifying code, as they could all inherit from a base API
#handling context class, and only overwrite the few pieces I need to change.
#This would allow for loading multiple copies of a class, just use a different
#name. The API calls and such would still need to be shared though! Maybe check
#if parsed is already filled or if non-default don't run, just use the already
#saved parsed. Would need that to be static then? Or not, since it's saved to the
#module itself, so each class would be able to access it just fine. Would need to
#keep a separate copy inside each class instance though so it'd know what changed
#unless I rewrite the module to keep the changes.

#All modules TODO
#Now that options exist, add option to ignore Adult streams in announcements.
##Not everything may support that
#Option to @here
#Maybe redo options to be a ['Servers'][server]['Options'] = set, includes all options in one group.
##That would make it more difficult to remove conflicting options though?

version = 0.5 #Current bot version
changelog = {}
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
client = discord.Client()
#Invite link for the PicartoBot. Allows adding to a server by a server admin.
#This is the official version of the bot, running the latest stable release.
invite = "https://discordapp.com/api/oauth2/authorize?client_id=553335277704445953&scope=bot&permissions=478272"
roleinvite = "https://discordapp.com/api/oauth2/authorize?client_id=553335277704445953&scope=bot&permissions=268913728"
#URL to the github wiki for DBContext, which has a help page
helpurl = "https://github.com/Silari/DBContext/wiki"

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

#Function to setup new context handler
def newcontext(name,handlefunc,data) :
    '''Registers a new context for the bot to handle.'''
    if not (name in contexts) :
        #Context doesn't exist, create and init with default data and function
        contexts[name] = {"name":name,"Data":data,"function":handlefunc}
    else :
        #Context exists, update handler function
        contexts[name]["function"] = handlefunc
        #If data wasn't created, add it
        if not contexts[name]["Data"] :
            contexts[name]["Data"] = data
        else : #If it was, merge it with saved data overwriting defaults
            contexts[name]["Data"] = {**data, **contexts[name]["Data"]}
    return

#Function to setup a module as a context
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

import twitchcontext
newmodcontext(twitchcontext)
import piczelcontext
newmodcontext(piczelcontext)
import picartocontext
newmodcontext(picartocontext)

async def getcontext(name,message) :
    '''Grabs the context handler associated with name and calls the registered
       function, providing the command and the data dict.'''
    thiscontext = contexts[name]
    await thiscontext["function"](message.content.split()[2:],message)

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
    elif command[0] == 'testperm' :
        try :
            print(message.channel.permissions_for(message.author))
        except :
            pass
        try :
            print(message.channel.permissions_for(message.guild.get_member(client.user.id)))
        except :
            pass
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
                await message.channel.send(msg)

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
    newcont = copy.deepcopy(contexts)
    for cont in newcont :
        if 'function' in newcont[cont] :
            del newcont[cont]['function']
    with open('dbcontexts.bin',mode='wb') as f:
        pickle.dump(newcont,f,pickle.HIGHEST_PROTOCOL)

async def savetask() :
    #Saves data every five minutes. Stops immediately if client is closed so it
    #won't interfere with the save on close.
    while not client.is_closed() :
        try :
            if not client.is_closed() :
                await asyncio.sleep(60) # task runs every 60 seconds        
            if not client.is_closed() :
                await asyncio.sleep(60) # task runs every 60 seconds        
            if not client.is_closed() :
                await asyncio.sleep(60) # task runs every 60 seconds        
            if not client.is_closed() :
                await asyncio.sleep(60) # task runs every 60 seconds        
            if not client.is_closed() :
                await asyncio.sleep(60) # task runs every 60 seconds
            #We've waited five minutes, save data
            if not client.is_closed() :
                await savecontexts() # task runs every 60 seconds
        except asyncio.CancelledError :
            return

import signal
#This section should cause the bot to shutdown and exit properly on SIGTERM
#It should cause the threads to shut down, which ends client.run and then runs
#the finally block below to save the data.
signal.signal(signal.SIGTERM,closebot)

if __name__ == "__main__" :
    #Saves our context data periodically
    task = client.loop.create_task(savetask())
    #Start our context modules updatewrapper task, if they had one when adding.
    for modname in taskmods :
        #print("Starting task for:",modname.__name__)
        tasks.append(client.loop.create_task(modname.updatewrapper()))
    try :
        client.run(token)
    #On various kinds of errors, close our background tasks, the bot, and the loop
    except SystemExit:
        print("SystemExit, closing")
        task.cancel()
        for task in tasks :
            task.cancel()
        closebot()
        client.loop.close()
    except KeyboardInterrupt:
        print("KBInt, closing")
        task.cancel()
        for task in tasks :
            task.cancel()
        closebot()
        client.loop.close()
    except Exception as e :
        print("Uncaught exception, closing", repr(e))
        task.cancel()
        for task in tasks :
            task.cancel()
        closebot()
        client.loop.close()
    except BaseException as e :
        print("Uncaught base exception, closing", repr(e))
        task.cancel()
        for task in tasks :
            task.cancel()
        closebot()
        client.loop.close()
    finally :
        #Save the handler data whenever we close for any reason.
        for cont in contexts :
            if 'function' in contexts[cont] :
                del contexts[cont]['function']
        with open('dbcontexts.bin',mode='wb') as f:
            pickle.dump(contexts,f,pickle.HIGHEST_PROTOCOL)
