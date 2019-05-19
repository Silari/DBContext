#context template to base new contexts on
#This file has all the items required by the dbcontext bot to be valid.
#Some values/functions WILL need to be updated.

#IMPORTANT - discord.py is based on coroutines, which are asynchronous and allow
#for easier management of multiple threads. Most functions you use in this should
#also be coroutines, especially any potentially blocking functions, so that the
#bot can still be responsive to other requests.

#These imports aren't necessary, but generally are useful to have
##import discord #Access to potentially needed classes/methods, Embed
##import aiohttp #Should be used for any HTTP requests, NOT urllib!
##import json #Useful for interpreting json from API requests.
##import asyncio #Useful for asyncio.sleep - do NOT use the time.sleep method!

name = "template" #This must be a unique name, used to identify this context

client = None #Is filled by discordbot with a handle to the client instance
#Do not use this to perform potentially disruptive actions. It is mostly used
#for client.send_message and such in the currently available contexts.

mydata = None #Is filled by discordbot with a handle to the contexts stored data
#This is a dict that is saved and reloaded by dbcontext. Any item saved in this
#should be safe for pickling/unpickling via the pickle module.
#Any data that does not need to be persistent across restarts does NOT need to
#be contained here - this is just an easy place to store persistent data.

defaultdata = {"AnnounceDict":{},"Servers":{}}
#This is merged into the dict that dbcontext creates for this context on load,
#which is then stored in the mydata variable above.
#Basically, it just sets up some default structures for use later. It can be
#an empty dict, but these two options are currently used by every context to
#store their info, and it's recommended to keep that usage the same if you're
#doing a similar API based watch context, or at least the servers the same for
#what servers to respond in and what channel to respond to in that server if
#possible for your usage.

#The first keeps channels to search for, with a !set! of servers that want that
#info. For example, the twitch context would have info like this
#AnnounceDict
#   |-"AngriestPat"
#       |-<ServerID>
#   |-"WoolieVersus"
#       |-<ServerID>
#       |-<ServerID2>

#The second keeps a dict of servers, that holds the dict with the options they
#set, such as the channel to talk in, who they listen to, etc.
#Servers
#   |-<ServerID>
#       |"AnnounceChannel": <ChannelID>
#       |"Listens": set("AngriestPat","WoolieVersus")
#       |"Users": set()
#   |-<ServerID2>
#       |"AnnounceChannel": <ChannelID2>
#       |"Listens": set("WoolieVersus")
#       |"Users": set()
#       |"MSG": delete

#Again, these are not requirements, but recommended to simplify things. It means
#being able to copy/paste a lot of code from the existing templates, and time
#savers are always nice.

#This is started as a background task by dbcontext. It can be empty but should
#exist.
async def updatewrapper() :
    '''Sets a function to be run continiously ever 60 seconds until the bot is closed.'''
    #Data validation should go here if needed for your mydata dict. This is
    #CURRENTLY only called once, when the bot is first started, but this may
    #change in future versions if the client needs to be redone.
    await client.wait_until_ready() #Don't start until client is ready
    #The above makes sure the client is ready to read/send messages and is fully
    #connected to discord. Usually, it is best to leave it in.
    #while not loop keeps a background task running until the client is closed
    while not client.is_closed :
        try :
            await asyncio.sleep(60) # task runs every 60 seconds
            await updatetask() #The function that actually performs anything
        #Error handling goes here. For now, we just print the error to console
        except Exception as error :
            print("Tempwrap:",repr(error))
    
async def updatetask():
    #We want this check here in case we stopped in the last 60 seconds.
    if not client.is_closed:
        #The content of anything you need to do periodically would be here.
        pass

#Main context handler - messages are passed to this function from dbcontext
#command is the trimmed command - without the bot name or context name in front
#message is the full discord.Message instance that triggered the handler. 
async def handler(command, message) :
    #print("TemplateHandler:", command, message)
    #This has help show if no specific command was given, or the help command
    #was specifically given. Useful to tell users how to work your context.
    if len(command) > 0 and command[0] != 'help' :
        #Here's an example command - listen. This sets the channel it's said in
        #as the channel to use for automatic messages. Note that the response
        #always goes in the channel the message was sent from - message.channel
        if command[0] == 'listen' :
            #Set the channel the message was sent in as the Announce channel
            if not (message.server.id in mydata["Servers"]) :
                mydata["Servers"][message.server.id] = {} #Add data storage for server
            mydata["Servers"][message.server.id]["AnnounceChannel"] = message.channel.id
            msg = "Ok, I will now start announcing in this server, using this channel."
            await client.send_message(message.channel,msg)
        #And the reverse of listen is stop, which removes the channel
        elif command[0] == 'stop' :
            #Stop announcing - just removed the AnnounceChannel option
            try :
                del mydata["Servers"][message.server.id]["AnnounceChannel"]
            except KeyError :
                pass #Not listening, so skip
            msg = "Ok, I will stop announcing on this server."
            await client.send_message(message.channel,msg)
        #For additional examples of commands, see the other contexts
    else : #No extra command given, or unknown command
        #This is your help area, which should give your users an idea how to use
        #your context. 
        if len(command) > 1 :
            #This is for help with a specific command in this context
            if command[1] == 'option' :
                msg = "These are details for this command:"
                msg += "\nThis command does things."
                msg += "\nSentences are separated like this for readability and usage."
                msg += "\nIt's good practice to limit the number of messages sent at once."
                msg += "\nDiscord has a rate limit built in, and every context needs to be responsible for it's usage."
                await client.send_message(message.channel,msg)
                #msg += "\n"
        #The general help goes here - it should list commands or some site that
        #has a list of them
        else :
            msg = "The following commands are available for " + name + ":"
            msg += "\nlisten: starts announcing new streams in the channel it is said."
            msg += "\nstop: stops announcing streams and removes the announcement channel."
            msg += "\nSome commands/responses will not work unless an announcement channel is set."
            msg += "\nPlease note that all commands, options and channel names are case sensitive!"
            await client.send_message(message.channel,msg)
