#discord bot with module based functionality.
#Now based on discord.py version 1.3.2

#TESTING NOTES
#Completed and testing:

#Todo:
#Rewrite the messages so they're marked offline quicker, with the message being
#reused if it comes back within 10 minutes. Basically just change the edit message
#part to note that it is currently offline?

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

#Add a module named Global for handling global settings - pretty simple data layout
#ServerID->['Channel'],['MSG'],['Type'], etc.
#Need to add a way for modules to READ but not WRITE this - getglobal(globalname)?
#Reading done, but still need a way to set this.
##See below, module options instead

#Still need to think about a module to set things globally - the backend is there
#already with getoption+getglobal but there's no way to set them. It just uses
#the default option dict.

#SIMILAR TO ABOVE: maybe a dict with the allowed option TYPES? Then again that
#could be gotten from the defaultopts list maybe? Except that's global! so mods
#can't access it directly.
##Maybe a dict with {'OptName':set(val1,val2,val3),'OptName2':set(True,False)}
##Then I have an easy to access and change list of groups and their allowed
#values

#Might want to rewrite remove/removemult to call a common function to handle
#all the stuff that needs to be done to remove a stream. Save some code, easier
#to update/fix with one location instead.
#maybe can do similar for add/addmult.

#Something to move a savedmsg to a new channel if the channel
#gets changed. So 'add stream <channel>' would delete the old message and make a
#new one in the proper channel.

##Can also allow "PWNotify" role that can get @'d if proper option is set.
###Do this via reacting to a message sent by the bot. Can unreact to unset?

#Option to @here - probably better handled by channel notifications user side
##Adding in the notify role instead, so that'd handle it just fine.

#TODO for 1.0
#NEED to rename dbcontexts.bin and double check everything works still. Might be
#some spots I forgot to check that certain things exist. The default dicts should
#handle the major sections, but I don't think I tested that.

#Change permission to use the bot to manage server? I think that's what allows
#someone to invite a bot to begin with, and at that point they should be able to
#control this one.

#Account for options changing after initial announcement. I've caught a few of
#these but especially removemsg assumes that an embed is already present: if the
#type was changed from simple to the others and then goes offline it doesn't get
#an embed. There's already an if embeds>0 check, have else newembed = (make new embed)
#and to_dict() it, then move the if 'image' and past it out of the if, as there'd
#always be a newembed dict at that point.
#Remove client from contexts. They don't need it for send_message anymore
#Currently only used for get_channel and wait_until_ready

#Redo the updatetask to not bother with DBCOffline/DBCOnline unless the stream
#is in mydata['AnnounceDict']. If no one is watching a stream, we can just remove
#it immediately. Looks like curstreams does this already. Can probably fiddle
#with it and merge the for old in removed with for gone in oldstreams.

#Change announce to channel - all it really does now is set the default channel
#Hell, maybe remove it entirely and use option instead? Could set channel the
#same way streamoption does.

#Is there a reason to keep addmult/removemult separate? They share the same
#functionality is their single counterparts, including the channel override.
#Only reason to keep add separate would be to allow settings options with the
#add command - <stream> <option1> <option2>. Not sure that's needed though.

version = 0.9 #Current bot version
changelogurl = "https://github.com/Silari/DBContext/wiki/ChangeLog"
#We're not keeping the changelog in here anymore - it's too long to reliably send
#as a discord message, so it'll just be kept on the wiki. Latest version will be
#here solely as an organizational thing, until it's ready for upload to the wiki
#proper.
changelog["0.9"] = '''0.9 from 0.8 Changelog:
GENERAL
Added resume command - resumes announcements after stop command
  stop command no longer unsets the announcement channel
Added new adult options - showadult (default, show all adults streams), hideadult (adult streams never have a preview), and no adult (adult streams are not announced, hides preview if already announced).
Added timestamp to picarto/piczel/twitch thumbnail URLs to avoid Discord's overly long caching.
Added new option - clear. Removes all set options (except announce channel)
Added streamoption command. Allows setting any option on a per stream basis, rather than server wide. Can also set announcement channel for the stream.
Changed removemult command to allow a trailing ',' same as addmult does.
Stream length times are more accurate in cases of API/bot downtime; uses API info to get the length of a stream.
  Limited use on Picarto due to API constraints - stream length isn't given when checking online streams, only the detailed channel info (which is only used by detailannounce). If this data is added later, the bot will automatically use it.
Added stream length time to picarto/piczel/twitch detail announce, rearranged order of items.
Added follower count to piczel detailed announce.
Bot will check if it lacks permission to send messages to the listen channel, and add the issue to it's response to the command.
  Note that if the listen channel is where the command was sent, the reply will fail due to the issue.
  There is already a PM sent to the user if that is the case.
Fixed bug in announce command that caused it to count all live streams instead of just non-announced ones.
Fixed bug in offline message editing when previews weren't being used.
announce and help commands will now include a message if the last API update failed.
Fixed and updated help commands, rewrote some to add details/clarity. 
API reads will return None if the API call timed out, allowing for more detailed error messages.
  Currently, detailannounce will explicitly state if the API call timed out.
API reads will return 0 if the API returns a Not Found error.
  Currently, add and detailannounce will explicitly state if the requested stream was not found.
announce handles Forbidden errors when sending the announcement.
Added missing help description for manage create command.
Fixed add command always stating the message channel was being used for announcements even when mentioning a channel
Fixed listen always using the message channel as the listen target, even when mentioning a channel.
Fixed issue with Twitch API when gameid is set to ''
'''

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
    if len(command) > 0 : #We were given additional paramters
        #Let's see if it's a command we understand.
        if command[0] == "version" :
            msg = client.user.name + " bot version " + str(version)
            msg += ". Please use the 'help changelog' command for update details."
            await message.channel.send(msg)
            return
        elif command[0] == "changelog" :
            msg = "The complete changelog can be found at <" + changelogurl + ">, due to length."
            msg += "Current version is: " + str(version)
            await message.channel.send(msg)
            return
        elif command[0] == "help" :
            msg = "PicartoWatch bot version " + str(version)
            msg += "\nThe following commands are available for 'help':"
            msg += "\nhelp, changelog, invite, version, versions"
            await message.channel.send(msg)
            return
        elif command[0] == 'invite' :
            msg = "I can be invited to join a server by an administrator of the server using the following links\n"
            msg += "\nNote that the link includes the permissions that I will be granted when joined.\n"
            msg += "\nThe current link is: <" + roleinvite + ">"
            msg += "\nIf the bot is already in your server, re-inviting will NOT change the current permissions."
            await message.channel.send(msg)
            return
        elif command[0] in contfuncs : #User asking for help with a context.
            #Redirect the command to the given module.
            #print("cont help", ["help"] + command[1:])
            await contfuncs[command[0]](["help"] + command[1:],message)
            return
    msg = "PicartoWatch bot version " + str(version)
    msg += "\nOnline help, and bug reporting are available at: <https://github.com/Silari/DBContext/wiki>"
    msg += "\nThe complete changelog can be found at <" + changelogurl + ">
    msg += "\nPlease use '<module> help' for help with specific modules"
    msg += "\nThe following modules are available for use: " + ", ".join(contexts)
    msg += "\nI listen to commands on any channel from users with the Administrator role on the server."
    msg += "\nAdditionally, I will listen to commands from users with a role named " + str(client.user.name)
    await message.channel.send(msg)

newcontext("help",helphandler,{})

defaultopts = {
    'Type':'default', #Type of announcement to use, default= embed with preview.
    'MSG':'edit', #Should messages be edited and/or removed after announcement?
    'Stop':False, #Should no new announcements be made?
    'Channel':None, #Default channel to announce in is no channel.
    'Adult':'showadult' #Should streams marked adult be shown normally? 
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
        except discord.Forbidden : #May not have permission
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
        msg += "\ncreate <#channel>: Creates the user role to manage the bot, and adds an override to allow them to send messages in #channel. #channel MUST be a channel mention."
        msg += "\ncheck <username#0000>: Check if given user(s) have access to bot commands. Separate user names with spaces."
        msg += "\nadd <username#0000>: Gives permission to one or more users to access bot commands. Note that bot accounts are ALWAYS ignored."
        msg += "\nremove <username#0000>: Revokes permission to one or more users to access bot commands. Note that server admins ALWAYS have bot access!"
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
    #If there wasn't a command given, or the command was help
    if len(command) == 0 or command[0] == 'help' :
        msg = "Debug module. This module is used for debugging/testing and notifying servers of updates/downtimes/etc."
        msg += "\nIt can not be used by anyone other than the bot developer."
        await message.channel.send(msg)
        return
    #Unsafe commands go down here
    if not (message.author.id == 273076937474441218) :
        #print("Not GP, do not run",command[1:])
        await message.channel.send("Sorry, this command is limited to the bot developer.")
        #await message.channel.send("Sorry, you are not the developer and do not have access to this command.\nThe debug feature should not be loaded into the public version of PicartoWatch.")
        return
    if command[0] == 'embed' :
        #Debug to create detail embed from picarto stream
        rec = await picartocontext.agetstream(command[1])
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
        #print(msg)
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
            if channel : #We may no longer be in the server which would mean no channel
                await channel.send(msg)

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

#The main event handler: handles all incoming messages and assigns them to the
#proper context/replies to DMs.
@client.event
async def on_message(message):
    #Ignore messages we sent
    #print("on_message")
    if message.author == client.user :
        return
    #We ignore any messages from other bots. Could lead to bad things.
    elif message.author.bot :
        return
    #print("not us or a bot")
    if not message.guild : #PMs just get a help dialog and then we're done.
        msg = client.user.name + " bot version " + str(version)
        msg += "\nPlease use '@" + client.user.name + " help' in a server channel for help on using the bot."
        msg += "\nOnline help is also available at <" + helpurl + ">."
        await message.channel.send(msg)
        return
    #print("not a PM")
    hasrole = False
    #Check if one of the users roles matches the bot's name
    for item in message.author.roles :
        #print(hasrole, item.name, client.user.name)
        if client.user.name == item.name :
            hasrole = True
            #print(hasrole, item.name, client.user.name)
    #print("hasrole", hasrole,":",message.author.guild_permissions.administrator)
    #The bot listens to anyone who is an admin, or has a role named after the bot
    if message.author.guild_permissions.administrator or hasrole :
        #print("passed check",message.content)
        #print('<@!' + str(client.user.id) + ">",":",client.user.mention)
        if message.content.startswith('<@!' + str(client.user.id) + ">") :
            command = message.content.split()
            #print("Listening for message", len(command))
            if len(command) < 2 :
                msg = client.user.name + " bot version " + str(version)
                msg += "\nPlease use '@" + client.user.name + " help' for help on using the bot."
                msg += "\nOnline help is available at <" + helpurl + ">."
                await message.channel.send(msg)
            elif command[1] in contexts :
                #print("calling module",command[1], command[2:])
                #If we don't have permission to send messages in the channel, don't use
                #the typing function as that would throw Forbidden.
                if not message.channel.permissions_for(message.guild.me).send_messages :
                    msg = "I do not have permission to respond in the channel you messaged me in. While I will still attempt to perform the command, any error or success messages will fail."
                    try :
                        await message.author.send(msg)
                    except discord.Forbidden : #We aren't allowed to DM the user
                        pass #nothing to do here
                    #This is a separate block because we need to do both even if
                    #the first fails, and we still need to ignore Forbidden in
                    #the second part.
                    try :
                        await getcontext(command[1],message)
                    except discord.Forbidden : #Chances are we're going to fail
                        pass #still nothing to do here
                else :
                    #If we can send messages, use the context manager
                    async with message.channel.typing() :
                        await getcontext(command[1],message)
            else :
                msg = "Unknown module '" + command[1] + "'. Remember, you must specify the module name before the command - e.g. 'picarto " + " ".join(command[1:]) + "'"
                await message.channel.send(msg)

#Used when joining a server. Might want something for this.        
#@client.event
#async def on_guild_join(server) :
#    pass

@client.event
async def on_resumed() :
    #Ensure our activity is set when resuming and add a log that it resumed.
    print("Client resumed")
    await client.change_presence(activity=discord.Game(name="@" + client.user.name + " help"))

#Fires when the bot is up and running. Sets our presence and logs the connection
@client.event
async def on_ready() :
    print("------\nLogged in as")
    print(client.user.name)
    print(client.user.id)
    print("------")
    #We set our activity here - we can't do it in the client creation because
    #we didn't have the user name yet
    await client.change_presence(activity=discord.Game(name="@" + client.user.name + " help"))

#Old method to close tasks and log out
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

#Logs the bot out and ends all tasks
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
    '''Saves the data for all contexts to a file.'''
    try :
        #Copy the current contexts into a new dictionary
        newcont = copy.deepcopy(contexts)
    except asyncio.CancelledError : #Task was cancelled, so quit.
        return
    except Exception as e :
        #Any errors, log them as that's a serious problem.
        print("Error in deepcopy:",repr(e))
        #print(contexts)
        return
    try :
        #Dump contexts to a Bytes object - if it fails our file isn't touched
        buff = pickle.dumps(newcont,pickle.HIGHEST_PROTOCOL)
        with open('dbcontexts.bin',mode='wb') as f:
                #Now we actually write the data to the file
                f.write(buff)
    except asyncio.CancelledError : #Task was cancelled, so quit.
        #Note that closing will save the contexts elsewhere, so we don't care
        #that we're potentially skipping a save here.
        return
    except Exception as e :
        #Again, log errors as those are potentially serious.
        print("error in savecontext",repr(e))
        #print(newcont)

async def savetask() :
    #Calls savecontext every five minutes. Stops immediately if client is closed
    #so it won't interfere with the save on close.
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
            #Task was cancelled, so immediately exit. Bot is likely closing.
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
    '''Creates an aiohttp.ClientSession instance, shared among all modules.'''
    #We create a timeout instance to allow a max of 60 seconds per call
    mytime = aiohttp.ClientTimeout(total=60)
    #Note that individual requests CAN still override this, but for most APIs it
    #shouldn't take that long.
    myconn = aiohttp.ClientSession(timeout=mytime)
    return myconn

async def startbot() :
    '''Handles starting the bot, making the session, and starting tasks.'''
    myconn = await makesession() #The shared aiohttp clientsession
    #Saves our context data periodically
    tasks.append(client.loop.create_task(savetask()))
    #Start our context modules' updatewrapper task, if they had one when adding.
    for modname in taskmods :
        #print("Starting task for:",modname.__name__)
        #This starts the modules updatewrapper and passes the connection to it.
        tasks.append(client.loop.create_task(modname.updatewrapper(myconn)))
    try :
        #Starts the discord.py client with our discord token.
        await client.start(token)
    #On various kinds of errors, close our background tasks, the bot, and the loop
    except SystemExit :
        print("SystemExit, closing")
        for task in tasks : #Mark all tasks as cancelled
            task.cancel()
        #Logs out bot and ensures tasks were properly stopped before moving on.
        await aclosebot()
    except KeyboardInterrupt :
        print("KBInt, closing")
        for task in tasks : #Mark all tasks as cancelled
            task.cancel()
        #Logs out bot and ensures tasks were properly stopped before moving on.
        await aclosebot()
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
#END 3.7 to 3.7.3 only section

#If the module was run, call our startup wrapper
if __name__ == "__main__" :
    startupwrapper()
