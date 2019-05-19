#discord bot with module based functionality.
#Currently based on older discord.py version 0.16.12

#PZwrap: ClientConnectorError(11001, 'getaddrinfo failed')
#Unclosed client session
#client_session: <aiohttp.client.ClientSession object at 0x00000282A572BB70>
#Twrap: URLError(gaierror(11001, 'getaddrinfo failed'))
#Pwrap: ClientConnectorError(11001, 'getaddrinfo failed')
#This happens when the internet connection fails. Can't do much about that.
#I do need to set up something to retry the connection so the bot doesn't
#completely fail though.


#Core TODO list:
#0.5
#Update to discord.py 1.0+ now that it is released.

#Respond to PMs, at least for the help context
#Some kind of command to file bugs? In the help context
##Use a GIT for these two things - wiki page can provide all the help

#All modules TODO
#Now that options exist, add option to ignore Adult streams in announcements.
##Not everything may support that
#Option to @here
#Change options to allow multiple setting. If in a group, last takes precedence.
#Maybe redo options to be a ['Servers'][server]['Options'] = set, includes all options in one group.
##That would make it more difficult to remove conflicting options though?

version = 0.5 #Current bot version
changelog = {}
changelog["0.5"] = '''0.5 from 0.4 Changelog:
GENERAL
Changed internal handling of module data - no longer passed to the handler.'''
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

#This holds the needed API keys. You may want to use other methods for storing these.
import apitoken
#token is the Discord API
token = apitoken.token

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
    with open('PWcontexts.bin',mode='rb') as f:
        contexts = pickle.load(f)
except FileNotFoundError :
    pass
print("Initial Contexts:",contexts)

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
    await thiscontext["function"](message.content.split()[2:],message)

async def handler(command, message, handlerdata) :
    '''A generic handler function for a context. It should accept a string list
       representing the command string AFTER the context identifier, the message
       and a dict that stores all it's relevant data. It should return the
       message to send to the originating channel, or None for no message.'''
    #This is also used as the default init function - essentially does nothing
    return

async def helphandle(command, message) :
##    if command :
##        msg = 'For help with a specific context, please use "<context> help"'
##        await client.send_message(message.channel,msg)
##    else :
    if len(command) > 0 :
        if command[0] == "version" :
            msg = "PicartoWatch bot version " + str(version)
            msg += ". Please use the 'help changelog' command for update details."
            await client.send_message(message.channel,msg)
        elif command[0] == "versions" :
            msg = "The following versions of PicartoWatch exist: "
            msg += ", ".join(changelog)
            await client.send_message(message.channel,msg)
        elif command[0] == "changelog" :
            #print(len(command))
            if len(command) == 1 :
                #print("Adding command")
                command.append(version)
            try :
                msg = changelog[str(command[1])]
                await client.send_message(message.channel,msg)
            except (KeyError, ValueError) as e :
                msg = "No changelog exists for version " + str(command[1])
                await client.send_message(message.channel,msg)
        elif command[0] == "help" :
            msg = "PicartoWatch bot version " + str(version)
            msg += "\nThe following commands are available for 'help':"
            msg += "\nhelp, changelog, invite, version, versions"
            await client.send_message(message.channel,msg)
        elif command[0] == 'invite' :
            msg = "I can be invited to join a server by an administrator of the server using the following link\n"
            msg += "Note that the link includes the permissions that I will be granted when joined.\n"
            msg += "<" + invite + ">"
            await client.send_message(message.channel,msg)
    else :
        msg = "PicartoWatch bot version " + str(version)
        msg += "\nPlease use '<module> help' for help with specific modules"
        msg += "\nThe following modules are available for use: " + ", ".join(contexts)
        msg += "\nI listen to commands on any channel from users with the Administrator role in channel."
        msg += "\nAdditionally, I will listen to commands from users with a role named " + str(client.user.name)
        await client.send_message(message.channel,msg)

newcontext("help",helphandle,{})

async def debughandler(command, message) :
    #'safe' commands like help can go up here
    if not (message.author.id == '273076937474441218') :
        print("Not GP, do not run")
        await client.send_message(message.channel,"Sorry, this command is limited to the bot developer.")
        #await client.send_message(message.channel,"Sorry, you are not the developer and do not have access to this command.\nThe debug feature should not be loaded into the public version of PicartoWatch.")
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
        await client.send_message(message.channel,msg,embed=myembed)
    elif command[0] == 'eval' :
        if command[1] == 'await' :
            await eval(" ".join(command[2:]))
        else :
            eval(" ".join(command[1:]))
    elif command[0] == 'reply' :
        msg = " ".join(command[1:])
        await client.send_message(message.channel,msg)
    elif command[0] == 'replyeval' :
        msg = eval(command[1:])
        await client.send_message(message.channel,msg)
    elif command[0] == 'sendall' :
        await sendall(" ".join(command[1:]))
    elif command[0] == 'updatenotice' :
        msg = "The bot has been restarted and updated to version " + str(version)
        msg += ". Please use 'help changelog' to see a list of the additions/changes/fixes to this version."
        await sendall(msg)
    elif command[0] == 'teststuff' :
        await picartocontext.removemsg(picartocontext.parsed[command[1]])
    elif command[0] == 'embedtest' :
        oldmess = await client.get_message(message.channel,command[1])
        oldmess.embeds[0]['fields'][0]['value'] = "Viewers: " + command[2]
        print("Old ver:",oldmess.embeds[0])
        newembed = discord.Embed.from_data(oldmess.embeds[0])
        print("New ver:",newembed.to_dict())
        newembed.set_image(url=oldmess.embeds[0]['image']['url'])
        await client.edit_message(oldmess,new_content=oldmess.content,embed=newembed)
        pass
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
                await client.send_message(channel,msg)

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
    if message.author.bot :
        return
    if not message.server : #Ignore PMs for now
        return
    hasrole = False
    for item in message.author.roles :
        #print(hasrole, item.name, client.user.name)
        if client.user.name == item.name :
            hasrole = True
    if message.author.server_permissions.administrator or hasrole :
        command = message.content.split()
##        if message.content.startswith('!PWhello') :
##            msg = 'Hello {0.author.mention}'.format(message)
##            await client.send_message(message.channel,msg)
##        if message.server.me in message.mentions :
##            print("I was mentioned")
##        if message.content.startswith('!' + client.user.name + " ") :
        if message.content.startswith('<@' + str(client.user.id) + "> ") :
            #print("Listening for message")
            #print(command[1])
            if command[1] in contexts :
                await getcontext(command[1],message)
            else :
                msg = "Unknown command '" + command[1] + "'."
                await client.send_message(message.channel,msg)

#Used when joining a server. Might want something for this.        
#@client.event
#async def on_server_join(server) :
#    pass

@client.event
async def on_ready() :
    print('------\nLogged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')
    await client.change_presence(game=discord.Game(name="@" + client.user.name + " help"))

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
    with open('PWcontexts.bin',mode='wb') as f:
        pickle.dump(newcont,f,pickle.HIGHEST_PROTOCOL)

async def savetask() :
    #Saves data every five minutes. Stops immediately if client is closed so it
    #won't interfere with the save on close.
    while not client.is_closed :
        if not client.is_closed :
            await asyncio.sleep(60) # task runs every 60 seconds        
        if not client.is_closed :
            await asyncio.sleep(60) # task runs every 60 seconds        
        if not client.is_closed :
            await asyncio.sleep(60) # task runs every 60 seconds        
        if not client.is_closed :
            await asyncio.sleep(60) # task runs every 60 seconds        
        if not client.is_closed :
            await asyncio.sleep(60) # task runs every 60 seconds
        #We've waited five minutes, save data
        if not client.is_closed :
            await savecontexts() # task runs every 60 seconds        

import signal
#This section should cause the bot to shutdown and exit properly on SIGTERM
#It should cause the threads to shut down, which ends client.run and then runs
#the finally block below to save the data.
#It may need 60 seconds for the updatepicarto task to finish sleeping.
signal.signal(signal.SIGTERM,closebot)

if __name__ == "__main__" :
    #Saves our context data periodically
    task = client.loop.create_task(savetask())
    #Start our context modules updatewrapper task, if they had one when adding.
    for modname in taskmods :
        print("Starting task for:",modname.__name__)
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
        with open('PWcontexts.bin',mode='wb') as f:
            pickle.dump(contexts,f,pickle.HIGHEST_PROTOCOL)
