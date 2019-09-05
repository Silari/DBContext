#context class to base new contexts on
#This file has all the items required by the dbcontext bot to be valid.
#Some values/functions WILL need to be updated. Please see the related module
#templateclass.py for details, as well as the minimum list of functions/values
#that need to be set for any new class inheriting from this.

#If I use this as a base, I could redo the commands + help to make use of a dict
#with {<command>:<help text>} which would simplify writing new commands
#into the help file. AND much more easily add context specific commands.

#TODO:

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
lastupdate = [] #List that tracks if update succeeded - empty if not successful

offlinewait = 10 #How many minutes to wait before declaring a stream offline

defaultopts = {
    'Type':'default',
    'MSG':'edit'
    }

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
        #There are two values set by dbcontext after initializing the class:
        #self.mydata - contains the persistent data for this instance.
        #self.client - is the Discord.Client instance in use. Please don't use it for being an asshat.
        if instname :
            self.name = instname
        else :
            self.name = self.defaultname
        self.savedmsg = {}
        self.parsed = parsed #This should be replaced in the subclass
        self.lastupdate = lastupdate #This should be replaced in the subclass

    #Display name of the record, used to ID the stream and in messages.
    #Should be overridden.
    async def getrecname(self,rec) :
        return 'Stream'

    #Get the channel to announce.
    async def resolvechannel(self,guildid,rec=None,channelid=None) :
        #guildid = int: snowflake of guild
        #rec = str: channel name
        #channelid = int: snowflake of channel - overrides any other option.
        #If we no longer have access to the channel, get_channel returns None.
        #Calling functions should all account for this possibility.
        #If we're supplied with the channelid, use it, no need to look it up.
        if channelid :
            return self.client.get_channel(channelid)
        mydata = self.mydata #Ease of use/potntially speed
        #Otherwise, try to look it up using a channel record and guild id
        if rec : #We have a channel record, see if it has an override
            try :
                newchan = mydata['COver'][guildid][rec]['Channel']
                return self.client.get_channel(newchan)
            except KeyError :
                pass
        #No record given, or we failed to find a channel override for that record
        try :
            return self.client.get_channel(mydata["Servers"][guildid]["AnnounceChannel"])
        except KeyError :
            pass #No announcement channel set
        #Reading from Global goes here.
        #print("No channel found for", guildid, rec)
        return None #We didn't get a good value from any of the three, so None

    #Gets the given option by searching (in the future) channel overrides, 
    async def getoption(self,guildid,option,rec=None) :
        #option = str: name of option to get ("Type" or "MSG" right now)
        #rec = str: channel name
        mydata = self.mydata
        if rec :
            try : #Try and read the streams override option
                return mydata['COver'][guildid][rec]['Option'][option]
            except KeyError :
                pass #No override set for that stream, try the next place.
        try : #Try to read this guild's option in it's data
            return mydata["Servers"][guildid][option]
        except KeyError :
            pass #Given option not set for this server, try the next place.
        try : #Lets see if the option is in the default options dict.
            return defaultopts[option]
        except KeyError :
            pass
        #Global here, or before defaults? Or maybe have global handle grabbing
        #the defaults if there isn't a global opt set. Seems better.
        return None #No option of that type found in any location.

    #Function to get length of time a stream was running for.
    async def streamtime(self,snowflake,offset=None,longtime=False) :
        dur = datetime.datetime.utcnow() - discord.utils.snowflake_time(snowflake)
        if offset :
            dur -= datetime.timedelta(minutes=offset)
        hours, remainder = divmod(dur.total_seconds(),3600)
        minutes, seconds = divmod(remainder,60)
        if longtime :
            retstr = ""
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
            return "{0}h:{1:02d}m.".format(int(hours),int(minutes))

    #Function to generate a string to say how long stream has lasted
    async def streammsg(self,snowflake,offline=False) :
        if offline :
            timestr = await self.streamtime(snowflake,offlinewait)
            retstr = "Stream lasted for "
        else :
            timestr = await self.streamtime(snowflake)
            retstr = "Stream running for "
        retstr += timestr
        return retstr

    #Embed creation stub. Should be overridden, but is functional.
    async def simpembed(self,rec,offline=False) :
        myembed = discord.Embed(title="Stream has come online!",url=self.streamurl.format(await self.getrecname(rec)))
        return myembed

    #Embed creation stub. Should be overridden, but is functional.
    #Returns the simple embed.
    async def makeembed(self,rec,offline=False) :
        return await self.simpembed(rec,offline)

    #Embed creation stub. Should be overridden, but is functional.
    #Returns the normal embed, which may be fine if detailed channel record has no additional information.
    async def makedetailembed(self,rec,offline=False) :
        return await self.makeembed(rec,offline)

    #Short string to announce the stream is online, with stream URL. 
    async def makemsg(self,rec) :
        return await self.getrecname(rec) + " has come online! Watch them at <" + self.streamurl.format(await self.getrecname(rec)) + ">"

    #Gets the detailed information about a channel. Used for makedetailmsg.
    #It returns the interpreted buffer. For Picarto, this is the channel record.
    #This is pretty basic, so most classes should be able to use this. At most,
    #override the function, call APIContext(self,channelname), then manipulate
    #the returned buffer as you need. See piczelclass as an example of this.
    async def agetchannel(self,channelname,headers=None) :
        #Call our API with the getchannel URL formatted with the channel name
        return await self.acallapi(self.channelurl.format(channelname),headers)

    #Handles calling the API at the given URL and interpreting the result as JSON
    #No changes are made to the data so it can be used by anything that needs a
    #simple GET ran.
    async def acallapi(self,url,headers=None) :
        rec = False #Used for the return - default of False means it failed.
        #header is currently only needed by twitch, where it contains the API key
        async with self.conn.get(url,headers=headers) as resp :
            try :
                if resp.status == 200 : #Success
                    buff = await resp.text()
                    #print(buff)
                    if buff :
                        rec = json.loads(buff) #Interpret the received JSON
            #Ignore connection errors, and we can try again next update
            except aiohttp.ClientConnectionError :
                rec = False #Low level connection problems per aiohttp docs.
            except aiohttp.ClientConnectorError :
                rec = False #Also a connection problem.
            except aiohttp.ServerDisconnectedError :
                rec = False #Also a connection problem.
            except aiohttp.ServerTimeoutError :
                rec = False #Also a connection problem.
            except asyncio.TimeoutError :
                rec = False #Exceeded the timeout we set - 60 seconds.
            except json.JSONDecodeError : #Error in reading JSON - bad response from server?
                print("JSON Error in",self.name) #Log this, since it shouldn't happen.
                rec = False #This shouldn't happen since status == 200
        return rec

    #Updates parsed dict by calling the API. Generalized enough that it works for Picarto+Piczel
    async def updateparsed(self) :
        updated = False
        self.lastupdate.clear() #Update has not succeded.
        #We no longer need any of this since acallapi can handle getting the buffer
##        #Only change is using self.conn.get( instead of aiohttp.request('GET',
##        try :
##            async with self.conn.get(self.apiurl) as resp :
##                if resp.status == 200 : #Success
##                    buff = await resp.text()
##                    if buff :
##                        self.parsed = {await self.getrecname(item):item for item in json.loads(buff)}
##                        updated = True #Parse finished, we updated fine.
##        #The following are low level connection problems per aiohttp docs.
##        #We can't do anything about it, so keep the update marked as failed and ignore
##        except aiohttp.ClientConnectionError :
##            pass
##        except aiohttp.ClientConnectorError :
##            pass
##        except aiohttp.ServerDisconnectedError :
##            pass
##        except aiohttp.ServerTimeoutError :
##            pass
##        except asyncio.TimeoutError :
##            pass
##        #This one is an actual problem that shouldn't happen.
##        except json.JSONDecodeError : #Error in reading JSON - bad response from server?
##            print("JSON Error in",self.name) #Log this, since it shouldn't happen.
##            pass #This shouldn't happen since status == 200, but ignore for now.
        buff = await self.acallapi(self.apiurl)
        if buff : #Any errors would return False instead of a buffer
            self.parsed = {await self.getrecname(item):item for item in json.loads(buff)}
            updated = True #Parse finished, we updated fine.
        if updated : #We updated fine so we need to record that
            self.lastupdate.append(updated) #Not empty means list is True, update succeeded
        return updated

    #This is started as a background task by dbcontext. It can be empty but
    #should exist.
    async def updatewrapper(self,conn) :
        '''Sets a function to be run continiously ever 60 seconds until the bot is closed.'''
        #Data validation should go here if needed for your mydata dict. This is
        #CURRENTLY only called once, when the bot is first started, but this may
        #change in future versions if the client needs to be redone.
        self.conn = conn #Set our ClientSession reference for connections.
        try :
            await self.updateparsed() #Start our first API scrape, shouldn't need client
        except Exception as error :
            print(self.name,"initial update error",repr(error))
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
            oldlist = self.parsed #Keep a reference to the old list
            if not await self.updateparsed() :
                #Updating failed for some reason
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
                #If the channel has not been gone the last offlinewait updates, readd it
                if rec['DBCOffline'] < offlinewait :
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
                    if 'DBCOnline' in oldrec : #Was online last check
                        if oldrec['DBCOnline'] >= 4 :
                            #Update the channel every 5 minutes.
                            #New record will have no count, resets timer.
                            await self.updatemsg(rec)
                        else :
                            #Add the count to the new record
                            rec['DBCOnline'] = oldrec['DBCOnline'] + 1
                    else :
                        #Start the count in the new record
                        rec['DBCOnline'] = 1 #Has just gone offline
            for old in removed :
                if old in mydata['AnnounceDict'] : #Someone is watching this channel
                    #print("Removing",old)
                    rec = oldlist[old]
                    await self.removemsg(rec) #Need to potentially remove messages
            return

    async def removemsg(self,rec,serverlist=None) :
        mydata = self.mydata #Ease of use and speed reasons
        recid = await self.getrecname(rec)
        if not serverlist :
            serverlist = mydata['AnnounceDict'][recid]
        for server in serverlist :
            try :
                #We don't have a saved message for this, so do nothing.
                if not (server in self.savedmsg) or not (recid in self.savedmsg[server]) :
                    pass
                #Either the MSG option is not set, or is set to edit, which is the default
                #We should edit the message to say they're not online
                elif not ("MSG" in mydata["Servers"][server]) or mydata["Servers"][server]["MSG"] == "edit" :
                    #channel = self.client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                    channel = await self.resolvechannel(server,recid)
                    if channel : #We may not have a channel if we're no longer in the guild/channel
                        oldmess = await channel.fetch_message(self.savedmsg[server][recid])
                        newembed = oldmess.embeds[0].to_dict()
                        del newembed['image'] #Delete preview as they're not online
                        newembed['title'] = await self.streammsg(self.savedmsg[server][recid],offline=True)
                        newembed = discord.Embed.from_dict(newembed)
                        newmsg = recid + " is no longer online. Better luck next time!"
                        await oldmess.edit(content=newmsg,embed=newembed)
                #We should delete the message
                elif mydata["Servers"][server]["MSG"] == "delete" :
                    #channel = self.client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                    channel = await self.resolvechannel(server,recid)
                    if channel :
                        oldmess = await channel.fetch_message(self.savedmsg[server][recid])
                        await oldmess.delete()
            except KeyError as e :
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
        #We'll need these later, but can't make them quite yet
        myembed = None
        noprev = None
        mydata = self.mydata #Ease of use and speed reasons
        recid = await self.getrecname(rec) #Keep record name cached, we need it a lot.
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
                #If we haven't made the embeds yet, do it now using the msg ID
                if not myembed : #This lets us only make the embed needed ONCE for each stream
                    myembed = await self.makeembed(rec,self.savedmsg[server][recid])
                    noprev = await self.simpembed(rec,self.savedmsg[server][recid])
                #Try and grab the old message we saved when posting originally
                oldmess = None
                try :
                    #channel = self.client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                    channel = await self.resolvechannel(server,recid)
                    if channel : #If we found the channel the saved message is in
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
                #channel = self.client.get_channel(mydata["Servers"][oneserv]["AnnounceChannel"])
                channel = await self.resolvechannel(oneserv,recid)
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
                #channel = self.client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                channel = await self.resolvechannel(server,recid)
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
    async def detailannounce(self,recid,oneserv=None) :
        #For now we should only call this with a specific server to respond to
        if not oneserv :
            return
        mydata = self.mydata #Ease of use and speed reasons
        rec = await self.agetchannel(recid)
        channel = await self.resolvechannel(oneserv,recid)
        if not rec :
            try :
                msg = "Sorry, I failed to load information about that channel. Check your spelling and try again."
                #channel = self.client.get_channel(mydata["Servers"][oneserv]["AnnounceChannel"])
                await channel.send(msg)
            except KeyError :
                pass
            return #Only announce on that server, then stop.
        myembed = await self.makedetailembed(rec)
        if myembed : #Make sure we got something, rather than None/False
            try :
                #channel = self.client.get_channel(mydata["Servers"][oneserv]["AnnounceChannel"])
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
                #This sets the channel to perform announcements/bot responses to.
                channelid = None
                if message.channel_mentions :
                    #Set the mentioned channel as the announcement channel
                    channelid = message.channel_mentions[0].id
                else :
                    #Set the channel the message was sent in as the announcement channel
                    channelid = message.channel.id
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
                msg += " Due to technical limitations with this version, announcements for channels with a channel override will not be stopped. Should be fixed for next version. Sorry."
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
                if not self.lastupdate :
                    msg += "\n**Last attempt to update API failed.**"
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
                if message.channel_mentions : #Channel mention, so make an override
                    if not 'COver' in mydata : #We need to make the section
                        mydata['COver'] = {} #New dict
                    if not message.guild.id in mydata['COver'] : #Make server in section
                        mydata['COver'][message.guild.id] = {}
                    if not command[1] in mydata['COver'][message.guild.id] : #Make record in section
                        mydata['COver'][message.guild.id][command[1]] = {}
                    #FINALLY we can make the actual channel override.
                    #Set this servers channel override for this stream to the mentioned channel.
                    mydata['COver'][message.guild.id][command[1]]['Channel'] = message.channel_mentions[0].id
                else : #If we're not SETTING an override, delete it.
                    try :
                        del mydata['COver'][message.guild.id][command[1]]['Channel']
                    except KeyError : #If any of those keys don't exist, it's fine
                        pass #Ignore it, because the override isn't set.
                msg = "Ok, I will now announce when " + command[1] + " comes online."
                if message.channel_mentions : #Inform the user the override was set
                    msg += " Announcement channel set to " + message.channel_mentions[0].mention
                await message.channel.send(msg)
                try :
                    #Announce the given user is online if the record exists.
                    if (message.guild.id in self.savedmsg) and (command[1] in self.savedmsg[message.guild.id]) :
                        pass #We already have a saved message for that stream.
                    elif message.channel_mentions :
                        await self.announce(self.parsed[command[1]],message.guild.id)
                    else :
                        await self.announce(self.parsed[command[1]],message.guild.id)
                except KeyError : #If they aren't online, silently fail.
                    pass #Channel name wasn't in dict, so they aren't online.
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
                #We're going to be setting a channel override, so make sure the
                #needed dicts are in place.
                if message.channel_mentions : #Channel mention, so make an override
                    if not 'COver' in mydata : #We need to make the section
                        mydata['COver'] = {} #New dict
                    if not message.guild.id in mydata['COver'] :
                        mydata['COver'][message.guild.id] = {}
                for newchan in command[1:] :
                    #print(newchan)
                    if len(mydata["Servers"][message.guild.id]["Listens"]) >= 100 :
                        msg += "Too many listens - limit is 100 per server. Did not add " + newchan + "or later channels."
                        break
                    #If the name ends with a comma, strip it off. This allows
                    #to copy/paste the result of the list command into add/mult
                    #to re-add all those channels. 
                    if newchan.endswith(',') :
                        newchan = newchan[:-1]
                    newrec = "" #String that holds the corrected channel name.
                    #This is a channel mention, so don't try to add it as a stream
                    if (newchan.startswith('<#') and newchan.endswith('>')) :
                        pass #We don't set newrec so it'll get skipped
                    #Need to match case with the API name, so test it first
                    #If we already are watching it, it must be the correct name.
                    elif not newchan in mydata["AnnounceDict"] :
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
                        if message.channel_mentions : #Channel mention, so make an override
                            if not newchan in mydata['COver'][message.guild.id] :
                                mydata['COver'][message.guild.id][newchan] = {}
                            #Set this servers channel override for this stream to the mentioned channel.
                            mydata['COver'][message.guild.id][newchan]['Channel'] = message.channel_mentions[0].id
                        else : #If we're not SETTING an override, delete it.
                            try :
                                del mydata['COver'][message.guild.id][newchan]['Channel']
                            except KeyError : #If any of those keys don't exist, it's fine
                                pass #Ignore it, because the override isn't set.
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
                    try : #We need to remove the server from that streams list of listeners
                        mydata["AnnounceDict"][command[1]].remove(message.guild.id)
                        #If no one is watching that channel anymore, remove it
                        if not mydata["AnnounceDict"][command[1]] :
                            mydata["AnnounceDict"].pop(command[1],None)
                    except ValueError :
                        pass #Value not in list, don't worry about it
                    except KeyError :
                        pass #Value not in list, don't worry about it
                    try : #Then we need to remove this stream from this servers listens
                        mydata["Servers"][message.guild.id]["Listens"].remove(command[1])
                    except ValueError :
                        pass #Value not in list, don't worry about it
                    except KeyError :
                        pass #Value not in list, don't worry about it
                    #If 'delete' option set, delete any announcement for that channel.
                    if ("MSG" in mydata["Servers"][message.guild.id]) and (mydata["Servers"][message.guild.id]["MSG"] == "delete" ) :
                        #This will delete announcement and clear savedmsg for us
                        try :
                            self.removemsg(parsed[command[1]],[message.guild.id])
                        except KeyError : #If stream not online, parsed won't have record.
                            pass
                    else :
                        #We still need to remove any savedmsg we have for this channel.
                        try : #They might not have a message saved, ignore that
                            del self.savedmsg[message.guild.id][command[1]]
                        except KeyError :
                            pass
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
                    #If 'delete' option set, delete any announcement for that channel.
                    if ("MSG" in mydata["Servers"][message.guild.id]) and (mydata["Servers"][message.guild.id]["MSG"] == "delete" ) :
                        #This will delete announcement and clear savedmsg for us
                        try :
                            self.removemsg(parsed[newchan],[message.guild.id])
                        except KeyError : #If stream not online, parsed won't have record.
                            pass
                    else :
                        #We still need to remove any savedmsg we have for this channel.
                        try : #They might not have a message saved, ignore that
                            del self.savedmsg[message.guild.id][newchan]
                        except KeyError :
                            pass
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
