#context class to base new contexts on
#This file has all the items required by the dbcontext bot to be valid.
#Some values/functions WILL need to be updated. Please see the related module
#templateclass.py for details, as well as the minimum list of functions/values
#that need to be set for any new class inheriting from this.

#If I use this as a base, I could redo the commands + help to make use of a dict
#with {<command>:<help text>} which would simplify writing new commands
#into the help file. AND much more easily add context specific commands.
#REFACTOR the self.getrecname usage to only call once per function - store it as recname
##DONE.

#IMPORTANT - discord.py is based on coroutines, which are asynchronous and allow
#for easier management of multiple threads. Most functions used in this should
#also be coroutines, especially any potentially blocking functions, so that the
#bot can still be responsive to other requests.

import discord #Access to potentially needed classes/methods, Embed
import aiohttp #Should be used for any HTTP requests, NOT urllib!
import json #Useful for interpreting json from API requests.
import asyncio #Useful for asyncio.sleep - do NOT use the time.sleep method!
import traceback #For exception finding.
import datetime #For stream duration calculation

parsed = {}

class APIContext :
    defaultname = "template" #This must be a unique name, used to identify this context
    streamurl = "http://www.example.com/{0}" #This is used with .format(getrecname(record)) to get the link to the stream associated with the record.

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

    def __init__(self,instname=None) :
        if instname :
            self.name = instname
        else :
            self.name = self.defaultname
        self.savedmsg = {}
        self.parsed = parsed

    #Stub that always fails. Should be overridden.
    async def updateparsed() :
        return False

    #Stub that always fails. Should be overridden.
    async def agetchannel() :
        return False

    #Display name of the record, used to ID the stream and in messages.
    #Should be overridden.
    async def getrecname(self,rec) :
        return 'Stream'

    #Function to get length of time a stream was running for.
    async def streamtime(self,snowflake,offset=None,longtime=True) :
        dur = datetime.datetime.utcnow() - discord.utils.snowflake_time(snowflake)
        if offset :
            dur -= datetime.timedelta(minutes=10)
        hours, remainder = divmod(dur.total_seconds(),3600)
        minutes, seconds = divmod(remainder,60)
        if longtime :
            retstr = "Stream lasted for "
            if hours :
                retstr += str(int(hours)) + " hour"
                if hours == 1 :
                    retstr += ", "
                else :
                    retstr += "s, "
            retstr += str(int(minutes)) + " minute"
            if minutes == 1 :
                retstr += "."
            else :
                retstr += "s."
            return retstr
        else :
            return "Stream lasted for {0}:{1}.".format(int(hours),int(minutes))

    #Embed creation stub. Should be overridden, but is functional.
    async def makeembed(self,rec) :
        return await self.simpembed(rec)

    #Embed creation stub. Should be overridden, but is functional.
    async def simpembed(self,rec) :
        myembed = discord.Embed(title="Stream has come online!",url=self.streamurl.format(await self.getrecname(rec)))
        return myembed

    #Short string to announce the stream is online, with stream URL. 
    async def makemsg(self,rec) :
        return await self.getrecname(rec) + " has come online! Watch them at <" + self.streamurl.format(await self.getrecname(rec)) + ">"

    #This is started as a background task by dbcontext. It can be empty but
    #should exist.
    async def updatewrapper(self) :
        '''Sets a function to be run continiously ever 60 seconds until the bot is closed.'''
        #Data validation should go here if needed for your mydata dict. This is
        #CURRENTLY only called once, when the bot is first started, but this may
        #change in future versions if the client needs to be redone.
        await self.updateparsed() #Start our first API scrape, shouldn't need client
        #Logs our starting info for debugging/check purposes
        print("Start",self.name,len(self.parsed))
        #By the time that's done our client should be setup and ready to go.
        #but we wait to make absolutely sure.
        await self.client.wait_until_ready() #Don't start until client is ready
        #The above makes sure the client is ready to read/send messages and is fully
        #connected to discord. Usually, it is best to leave it in.
        #while not loop keeps a background task running until the client is closed
        while not self.client.is_closed() :
            try :
                await asyncio.sleep(60) # task runs every 60 seconds
                await self.updatetask() #The function that actually performs anything
            except asyncio.CancelledError : #This could be Exception or BaseException if Python 3.8+
                #Task was cancelled, so just stop.
                return
            #Error handling goes here. For now, we just print the error to console
            #then continue. We do NOT ignore BaseException errors - those stop us
            #since we're likely being shut down.
            except Exception as error :
                print(self.name,"wrapper:",repr(error))
                traceback.print_tb(error.__traceback__)
        
    #This sets our checker to be run every minute
    async def updatetask(self):
        if not self.client.is_closed(): #Don't run if client is closed.
            oldlist = self.parsed
            if not await self.updateparsed() :
                #Updating failed for some reason - empty buffer was given.
                #For now, just return and we'll try again in a minute.
                return
            #print("Old Count:", len(oldlist),"Updated Count:", len(self.parsed))
            oldset = set(oldlist) #Set of names from old dict
            newset = set(self.parsed) #Set of names from new dict
            #Compare the old list and the new list to find new/removed items
            newchans = newset - oldset #Channels that just came online
            oldchans = oldset - newset #Channels that have gone offline
            curchans = newset - newchans #Channels online that are not new - update
            removed = [] #List of channels too old and thus removed
            #Search through channels that have gone offline
            #DBCOffline is used to track channels that have gone offline or
            #have stayed online. Once the counter has hit a certain threshold
            #the channel is marked as needing announcements deleted/updated.
            for gone in oldchans :
                rec = oldlist[gone] #Record from last update
                if 'DBCOffline' in rec : #Has been offline in a previous check
                    rec['DBCOffline'] += 1
                else :
                    rec['DBCOffline'] = 1 #Has just gone offline
                #If the channel has not been gone the last ten updates, readd it
                if rec['DBCOffline'] < 10 :
                    self.parsed[gone] = rec
                else :
                    #Otherwise we assume it's not a temporary disruption and add it
                    #to our list of channels that have been removed
                    removed.append(gone)
            mydata = self.mydata #Ease of use and speed reasons
            for new in newchans :
                if new in mydata['AnnounceDict'] :
                    rec = self.parsed[new]
                    #print("I should announce",rec)
                    await self.announce(rec)
            for cur in curchans :
                if cur in mydata['AnnounceDict'] : #Someone is watching this channel
                    oldrec = oldlist[cur]
                    rec = self.parsed[cur]
                    #print("I should announce",rec)
                    if 'DBCOffline' in oldrec : #Was online last check
                        if oldrec['DBCOffline'] >= 4 :
                            #Update the channel every 5 minutes.
                            await self.updatemsg(rec)
                        else :
                            rec['DBCOffline'] = oldrec['DBCOffline'] + 1
                    else :
                        rec['DBCOffline'] = 1 #Has just gone offline
            for old in removed :
                if old in mydata['AnnounceDict'] : #Someone is watching this channel
                    #print("Removing",old)
                    rec = oldlist[old]
                    await self.removemsg(rec) #Need to potentially remove messages
            return

    async def removemsg(self,rec) :
        mydata = self.mydata #Ease of use and speed reasons
        recid = await self.getrecname(rec)
        for server in mydata['AnnounceDict'][recid] :
            try :
                #We don't have a saved message for this, so do nothing.
                if not (server in self.savedmsg) or not (recid in self.savedmsg[server]) :
                    pass
                #Either the MSG option is not set, or is set to edit, which is the default
                #We should edit the message to say they're not online
                elif not ("MSG" in mydata["Servers"][server]) or mydata["Servers"][server]["MSG"] == "edit" :
                    channel = self.client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                    if channel : #We may not have a channel if we're no longer in the guild/channel
                        oldmess = await channel.fetch_message(self.savedmsg[server][recid])
                        #newembed = discord.Embed.from_data(oldmess.embeds[0])
                        #New method for discord.py 1.0+
                        newembed = oldmess.embeds[0].to_dict()
                        del newembed['image'] #Delete preview as they're not online
                        newembed = discord.Embed.from_dict(newembed)
                        newmsg = recid + " is no longer online. Better luck next time!"
                        await oldmess.edit(content=newmsg,embed=newembed)
                #We should delete the message
                elif mydata["Servers"][server]["MSG"] == "delete" :
                    channel = self.client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                    oldmess = await channel.fetch_message(self.savedmsg[server][recid])
                    await oldmess.delete()
            except KeyError as e : #Exception as e :
                print(self.name,"remove message keyerror:", repr(e))
                pass
            except discord.HTTPException as e:
                #HTTP error running the edit/delete command. Possibly no msg anymore
                pass
            except discord.Forbidden as e:
                #We are not permitted to edit/delete message. This SHOULDN'T ever happen
                #since you can always delete/edit your own stuff, but JIC.
                pass
            #Remove the msg from the list, we won't update it anymore.
            try : #They might not have a message saved, ignore that
                del self.savedmsg[server][recid]
            except KeyError :
                pass

    async def updatemsg(self,rec) :
        mydata = self.mydata #Ease of use and speed reasons
        myembed = await self.makeembed(rec)
        noprev = await self.simpembed(rec)
        recid = await self.getrecname(rec)
        for server in mydata['AnnounceDict'][recid] :
            #If Type is simple, don't do this
            if "Type" in mydata["Servers"][server] and mydata["Servers"][server]["Type"] == "simple" :
                pass
            #If MSG option is static, we don't update.
            elif "MSG" in mydata["Servers"][server] and mydata["Servers"][server]["MSG"] == "static" :
                pass
            #If we don't have a saved message, we can't update.
            elif not (server in self.savedmsg) or not (recid in self.savedmsg[server]) :
                pass
            else :
                #Try and grab the old message we saved when posting originally
                oldmess = None
                try :
                    channel = self.client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                    if channel : #If we're no longer able to access the channel to announce in
                        oldmess = await channel.fetch_message(self.savedmsg[server][recid])
                except KeyError as e:
                    #print("1",repr(e))
                    pass #Server no longer has an announce channel set, or message
                    #wasn't sent for this channel. Possibly bot was offline.
                except discord.HTTPException as e:
                    #General HTTP errors from command. 
                    #Can happen if message was deleted - NOT FOUND status code 404
                    #print("2",repr(e))
                    pass
                if oldmess :
                    try :
                        channel = self.client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                        if "Type" in mydata["Servers"][server] and mydata["Servers"][server]["Type"] == "noprev" :
                                await oldmess.edit(content=oldmess.content,embed=noprev)
                        else :
                            await oldmess.edit(content=oldmess.content,embed=myembed)
                    except KeyError as e:
                        #print("3",repr(e))
                        pass

    #Announce a stream is online. oneserv only sends the message on the given
    #server, otherwise find all servers that should announce that name.                
    async def announce(self,rec,oneserv=None) :
        '''Announce a stream. Limit announcement to 'oneserv' if given.'''
        mydata = self.mydata #Ease of use and speed reasons
        myembed = await self.makeembed(rec)
        noprev = await self.simpembed(rec)
        msg = await self.makemsg(rec)
        recid = await self.getrecname(rec)
        if oneserv :
            sentmsg = None
            try :
                channel = self.client.get_channel(mydata["Servers"][oneserv]["AnnounceChannel"])
                if "Type" in mydata["Servers"][oneserv] :
                    if mydata["Servers"][oneserv]["Type"] == "simple" :
                        sentmsg = await channel.send(msg)
                    elif mydata["Servers"][oneserv]["Type"] == "noprev" :
                        sentmsg = await channel.send(msg,embed=noprev)
                    else :
                        sentmsg = await channel.send(msg,embed=myembed)
                else :
                    sentmsg = await channel.send(msg,embed=myembed)
            except KeyError :
                pass
            if sentmsg :
                if not (oneserv in self.savedmsg) :
                    self.savedmsg[oneserv] = {}
                #Save the msg id into a dict with the key the unique name of the record
                self.savedmsg[oneserv][recid] = sentmsg.id
            return #Only announce on that server, then stop.
        for server in mydata['AnnounceDict'][recid] :
            sentmsg = None
            try :
                channel = self.client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                if channel : #Might not be in server anymore, so no channel
                    if "Type" in mydata["Servers"][server] :
                        if mydata["Servers"][server]["Type"] == "simple" :
                            sentmsg = await channel.send(msg)
                        elif mydata["Servers"][server]["Type"] == "noprev" :
                            sentmsg = await channel.send(msg,embed=noprev)
                        else :
                            sentmsg = await channel.send(msg,embed=myembed)
                    else :
                        sentmsg = await channel.send(msg,embed=myembed)
            except KeyError :
                pass #Server has no announcement channel set
            if sentmsg :
                if not (server in self.savedmsg) :
                    self.savedmsg[server] = {}
                self.savedmsg[server][recid] = sentmsg.id

    #Embed for a detailed announcment - usually more info than in the default announce
    #Empty stub that should be overridden. This ignores the embed type option!
    async def makedetailembed(self,rec) :
        return None
        
    #Provides a more detailed announcement of a channel for the detail command
    #Note that it's just different enough that sharing code with announce isn't easy
    async def detailannounce(self,rec,oneserv=None) :
        #For now we should only call this with a specific server to respond to
        if not oneserv :
            return
        mydata = self.mydata #Ease of use and speed reasons
        rec = await self.agetchannel(rec)
        if not rec :
            try :
                msg = "Sorry, I failed to load information about that channel. Check your spelling and try again."
                channel = self.client.get_channel(mydata["Servers"][oneserv]["AnnounceChannel"])
                await channel.send(msg)
            except KeyError :
                pass
            return #Only announce on that server, then stop.
        myembed = await self.makedetailembed(rec)
        if myembed : #Make sure we got something, rather than None/False
            try :
                channel = self.client.get_channel(mydata["Servers"][oneserv]["AnnounceChannel"])
                await channel.send(embed=myembed)
            except KeyError :
                pass
            return #Only announce on that server, then stop.

    #Main context handler - messages are passed to this function from dbcontext
    #command is the trimmed command - without the bot name or context name in front
    #message is the full discord.Message instance that triggered the handler. 
    async def handler(self, command, message) :
        #print("TemplateHandler:", command, message)
        #This has help show if no specific command was given, or the help command
        #was specifically given. Useful to tell users how to work your context.
        mydata = self.mydata #Ease of use and speed reasons
        if len(command) > 0 and command[0] != 'help' :
            if command[0] == 'listen' :
                #Set the channel the message was sent in as the Announce channel
                if not (message.guild.id in mydata["Servers"]) :
                    mydata["Servers"][message.guild.id] = {} #Add data storage for server
                mydata["Servers"][message.guild.id]["AnnounceChannel"] = message.channel.id
                msg = "Ok, I will now start announcing in this server, using this channel."
                await message.channel.send(msg)
            elif command[0] == 'stop' :
                #Stop announcing - just removed the AnnounceChannel option
                try :
                    del mydata["Servers"][message.guild.id]["AnnounceChannel"]
                except KeyError :
                    pass #Not listening, so skip
                msg = "Ok, I will stop announcing on this server."
                await message.channel.send(msg)
            elif command[0] == 'option' :
                if len(command) == 1 :
                    msg = "No option provided. Please use the help menu for info on how to use the option command."
                    await message.channel.send(msg)
                    return
                msg = ""
                setopt = set()
                unknown = False
                for newopt in command[1:] :
                    if newopt in ("default","noprev","simple") :
                        if not (message.guild.id in mydata["Servers"]) :
                            #Haven't created servers info dict yet, make a dict.
                            mydata["Servers"][message.guild.id] = {}
                        mydata["Servers"][message.guild.id]["Type"] = newopt
                        setopt.add(newopt)
                        #await message.channel.send(msg)
                    elif newopt in ("delete","edit","static") :
                        if not (message.guild.id in mydata["Servers"]) :
                            #Haven't created servers info dict yet, make a dict.
                            mydata["Servers"][message.guild.id] = {}
                        mydata["Servers"][message.guild.id]["MSG"] = newopt
                        setopt.add(newopt)
                        #await message.channel.send(msg)
                    else :
                        unknown = True #msg = "Unknown option provided. Please use the help menu for info on how to use the option command."
                        #await message.channel.send(msg)
                if setopt :
                    msg += "Options set: " + ", ".join(setopt) + ". "
                if unknown :
                    msg += "One or more unknown options found. Please check the help menu for available options."
                await message.channel.send(msg)
            elif command[0] == 'list' :
                #List options and current listening channels
                msg = ""
                try :
                    msg = "I am currently announcing in " + self.client.get_channel(mydata["Servers"][message.guild.id]["AnnounceChannel"]).mention + "."
                except KeyError :
                    msg = "I am not currently set to announce streams in a channel."
                try :
                    #Create list of watched channels, bolding online ones.
                    newlist = [*["**" + item + "**" for item in mydata["Servers"][message.guild.id]["Listens"] if item in self.parsed], *[item for item in mydata["Servers"][message.guild.id]["Listens"] if not item in self.parsed]]
                    newlist.sort()
                    msg += " Announcing for (**online**) streamers: " + ", ".join(newlist)
                except :
                    msg += " No streamers are currently set to be watched."
                msg += ".\nAnnouncement type set to "
                try :
                    if not ('Type' in mydata["Servers"][message.guild.id]) :
                        msg += "default with "
                    else :
                        msg += mydata["Servers"][message.guild.id]['Type'] + " with "
                except KeyError :
                    msg += "default with "
                try :
                    if not ('MSG' in mydata["Servers"][message.guild.id]) :
                        msg += "edit messages."
                    else :
                        msg += mydata["Servers"][message.guild.id]['MSG'] + " messages."
                except KeyError :
                    msg += "edit messages."
                await message.channel.send(msg)
            elif command[0] == 'add' :
                if not command[1] in mydata["AnnounceDict"] :
                    newrec = await self.agetchannel(command[1])
                    if not newrec :
                        msg = "No stream found with that user name. Please check spelling and try again."
                        await message.channel.send(msg)
                        return
                    else :
                        command[1] = await self.getrecname(newrec)
                    #Haven't used this channel anywhere before, make a set for it
                    mydata["AnnounceDict"][command[1]] = set()
                if not (message.guild.id in mydata["Servers"]) :
                    #Haven't created servers info dict yet, make a dict.
                    mydata["Servers"][message.guild.id] = {}
                if not ("Listens" in mydata["Servers"][message.guild.id]) :
                    #No listens added yet, make a set
                    mydata["Servers"][message.guild.id]["Listens"] = set()
                if len(mydata["Servers"][message.guild.id]["Listens"]) >= 100 :
                        msg = "Too many listens already - limit is 100 per server."
                        await message.channel.send(msg)
                        return
                #This marks the channel as being listened to by the server
                mydata["AnnounceDict"][command[1]].add(message.guild.id)
                #This marks the server as listening to the channel
                mydata["Servers"][message.guild.id]["Listens"].add(command[1])
                msg = "Ok, I will now announce when " + command[1] + " comes online."
                await message.channel.send(msg)
                try :
                    #Announce the given user is online if the record exists.
                    await self.announce(self.parsed[command[1]],message.guild.id)
                except KeyError : #If they aren't online, silently fail.
                    pass
            elif command[0] == 'addmult' :
                if not (message.guild.id in mydata["Servers"]) :
                    #Haven't created servers info dict yet, make a dict.
                    mydata["Servers"][message.guild.id] = {}
                if not ("Listens" in mydata["Servers"][message.guild.id]) :
                    #No listens added yet, make a set
                    mydata["Servers"][message.guild.id]["Listens"] = set()
                added = set()
                msg = ""
                notfound = set()
                for newchan in command[1:] :
                    #print(newchan)
                    if len(mydata["Servers"][message.guild.id]["Listens"]) >= 100 :
                        msg += "Too many listens - limit is 100 per server. Did not add " + newchan
                        break
                    newrec = ""
                    #Need to match case with the API name, so test it first
                    if not newchan in mydata["AnnounceDict"] :
                        newrec = await self.agetchannel(newchan)
                        #print(newrec)
                        if not newrec :
                            notfound.add(newchan)
                        else :
                            newchan = await self.getrecname(newrec)
                            #Haven't used this channel anywhere before, make a set for it
                            mydata["AnnounceDict"][newchan] = set()
                    else :
                        newrec = newchan
                    #Channel does not exist on service, so do not add.
                    if newrec :
                        #This marks the channel as being listened to by the server
                        mydata["AnnounceDict"][newchan].add(message.guild.id)
                        #This marks the server as listening to the channel
                        mydata["Servers"][message.guild.id]["Listens"].add(newchan)
                        added.add(newchan)
                if added :
                    added = [*["**" + item + "**" for item in added if item in self.parsed], *[item for item in added if not item in self.parsed]]
                    added.sort()
                    msg += "Ok, I am now listening to the following (**online**) streamers: " + ", ".join(added)
                if notfound :
                    msg += "\nThe following channels were not found and could not be added: " + ", ".join(notfound)
                if not msg :
                    msg += "Unable to add any channels due to unknown error."
                await message.channel.send(msg)
            elif command[0] == 'remove' :
                if command[1] in mydata["AnnounceDict"] :
                    try :
                        mydata["AnnounceDict"][command[1]].remove(message.guild.id)
                        #If no one is watching that channel anymore, remove it
                        if not mydata["AnnounceDict"][command[1]] :
                            mydata["AnnounceDict"].pop(command[1],None)
                    except ValueError :
                        pass #Value not in list, don't worry about it
                    except KeyError :
                        pass #Value not in list, don't worry about it
                    try :
                        mydata["Servers"][message.guild.id]["Listens"].remove(command[1])
                    except ValueError :
                        pass #Value not in list, don't worry about it
                    except KeyError :
                        pass #Value not in list, don't worry about it
                msg = "Ok, I will no longer announce when " + command[1] + " comes online."
                await message.channel.send(msg)
            elif command[0] == 'removemult' :
                if not (message.guild.id in mydata["Servers"]) :
                    #Haven't created servers info dict yet
                    await message.channel.send("No channels are being listened to yet!")
                    return
                if not ("Listens" in mydata["Servers"][message.guild.id]) :
                    #No listens added yet
                    await message.channel.send("No channels are being listened to yet!")
                    return
                added = set()
                msg = ""
                notfound = set()
                for newchan in command[1:] :
                    #print(newchan)
                    try :
                        mydata["AnnounceDict"][newchan].remove(message.guild.id)
                        added.add(newchan)
                        #If no one is watching that channel anymore, remove it
                        if not mydata["AnnounceDict"][newchan] :
                            mydata["AnnounceDict"].pop(newchan,None)
                    except ValueError :
                        notfound.add(newchan)
                        pass #Value not in list, don't worry about it
                    except KeyError :
                        notfound.add(newchan)
                        pass #Value not in list, don't worry about it
                    try :
                        mydata["Servers"][message.guild.id]["Listens"].remove(newchan)
                    except ValueError :
                        pass #Value not in list, don't worry about it
                    except KeyError :
                        pass #Value not in list, don't worry about it
                if added :
                    msg += "Ok, I will no longer announce the following streamers: " + ", ".join(added)
                if notfound :
                    msg += "\nThe following channels were not found and could not be removed: " + ", ".join(notfound)
                if not msg :
                    msg += "Unable to remove any channels due to unknown error."
                await message.channel.send(msg)
            elif command[0] == 'detail' :
                if len(command) == 1 : #No channel given
                    await message.channel.send("You need to specify a user!")
                else :
                    await self.detailannounce(command[1],message.guild.id)
        else : #No extra command given, or unknown command
            #This is your help area, which should give your users an idea how to use
            #your context. 
            if len(command) > 1 :
                #This is for help with a specific command in this context
                if command[1] == 'option' :
                    msg = "The following options are available:"
                    msg += "\nAnnouncement Type options:"
                    msg += "\ndefault: sets announcements messages to the default embedded style with preview."
                    msg += "\nnoprev: Use default embed style announcement but remove the stream preview image."
                    msg += "\nsimple: Use a non-embedded announcement message with just a link to the stream."
                    msg += "\nAnnouncement Editing options:"
                    msg += "\ndelete: Same as edit, except announcement is deleted when the channel goes offline."
                    msg += "\nedit: default option. Viewers and other fields are updated periodically. Message is changed when channel is offline."
                    msg += "\nstatic: messages are not edited or deleted ever."
                    await message.channel.send(msg)
                    #msg += "\n"
            #The general help goes here - it should list commands or some site that
            #has a list of them
            else :
                msg = "The following commands are available for " + name + ":"
                msg += "\nlisten: starts announcing new streams in the channel it is said."
                msg += "\nstop: stops announcing streams and removes the announcement channel."
                msg += "\noption: sets ONE of the following options: default, noprev, simple. See help option for details."
                msg += "\nadd <name>: adds a new streamer to announce. Limit of 100 channels per server."
                msg += "\naddmult <names>: adds multiple new streams at once, seperated by a space. Channels past the server limit will be ignored."
                msg += "\nremove <name>: removes a streamer from announcements."
                msg += "\nremovemult <names>: removes multiple new streams at once, seperated by a space."
                msg += "\ndetail <name>: Provides details on the given channel, including multi-stream participants."
                msg += "\nlist: Lists the current announcement channel and all listened streamer."
                msg += "\nSome commands/responses will not work unless an announcement channel is set."
                msg += "\nPlease note that all commands, options and channel names are case sensitive!"
                await message.channel.send(msg)
