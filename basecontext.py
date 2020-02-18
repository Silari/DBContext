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

    getglobal = None #Can be used to read options set by the manage context,
    #which should apply globally to all contexts. basecontext handles reading
    #from global as part of getoption.

    addglobal = None #Can be used to add a new variable to the list of options
    #that global will allow setting.

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

    #Now there's a third, COver, which overriddes certain settings or acts as a
    #flag for the server in the context.
    #COver
    #  |-<ServerID> #Server ID for the settings
    #      |"Stop": True #Set of stop command used, unset by Listen.
    #      |-<Streamname> #Stream to override context setting for
    #          |-"Channel": <ChannelID> #Channel to announce in instead of listen channel

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
        raise NotImplementedError("getrecname must be overridden in subclass!")
        return 'Stream'

    #Is the stream set as adult? Returns True/False
    async def isadult(self,rec) :
        '''Whether the API sets the stream as Adult. Defaults to False.'''
        return False

    async def getrectime(self,rec) :
        '''Time that a stream has ran, determined from the API data. Defaults to 0s'''
        return datetime.timedelta()

    #Get saved message id
    async def getmsgid(self,guildid,recid) :
        try :
            return self.savedmsg[guildid][recid]
        except KeyError :
            return False

    #Get the channel to announce.
    async def resolvechannel(self,guildid,rec=None,channelid=None) :
        '''guildid = int: snowflake of guild
        rec = str: channel name
        channelid = int: snowflake of channel - overrides any other option.
        Return: TextChannel instance if found.
        If we no longer have access to the channel, get_channel returns None.
        Calling functions should all account for this possibility.'''
        #If we're supplied with the channelid, use it, no need to look it up.
        if channelid : #Used for channel override things currently.
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
        #See if we have set the channel globally. If not, it returns None which
        #calling functions should check for.
        glob = await self.getglobal(guildid,'Channel')
        return glob

    #Gets the given option by searching stream overrides, guild override,
    #guild setting, or global settings (which checks for default settings)
    async def getoption(self,guildid,option,rec=None) :
        #option = str: name of option to get ("Type", "Adult", or "MSG" right now)
        #rec = str: channel name
        mydata = self.mydata
        if rec :
            try : #Try and read the streams override option
                return mydata['COver'][guildid][rec]['Option'][option]
            except KeyError :
                pass #No override set for that stream, try the next place.
        try : #Try to read an override for the option
            return mydata["COver"][guildid][option]
        except KeyError :
            pass #No override set, try next.
        try : #Try to read this guild's option in it's data
            return mydata["Servers"][guildid][option]
        except KeyError :
            pass #Given option not set for this server, try the next place.
        #See if we have set the option globally. If not, it also handles the
        #default option value, or None if it doesn't have that either.
        glob = await self.getglobal(guildid,option)
        return glob

    #Sets the override option for the given stream
    async def setstreamoption(self, guildid, option, rec, setting) :
        #We need to make sure all our needed dicts are created
        if not 'COver' in mydata :
            mydata['COver'] = {}
        if not message.guild.id in mydata['COver'] :
            mydata['COver'][message.guild.id] = {}
        if not mydata['COver'][message.guild.id][rec] in mydata['COver'][message.guild.id] :
            mydata['COver'][message.guild.id][rec] = {}
        if not mydata['COver'][message.guild.id][rec]['Option'] in mydata['COver'][message.guild.id][rec] :
            mydata['COver'][message.guild.id][rec]['Option'] = {}
        #Now we know they exist, set the Option section to override our setting for the given option
        mydata['COver'][message.guild.id][rec]['Option'][option] = setting
        return True

    #Function to get length of time a stream was running for, based on a message
    #snowflake.
    async def streamtime(self,dur,offset=None,longtime=False) :
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

    async def longertime(self,snowflake,rec) :
        '''Returns the longer of two durations - the time since the snowflake,
        and the time since the stream came online, from getrectime.
        Returns a datetime.timedelta object.'''
        rectime = await self.getrectime(rec)
        if snowflake :
            dur = datetime.datetime.utcnow() - discord.utils.snowflake_time(snowflake)
        else :
            dur = datetime.timedelta()
        return max(rectime,dur)

    #Function to generate a string to say how long stream has lasted
    async def streammsg(self,snowflake,rec,offline=False) :
        dur = await self.longertime(snowflake,rec)
        if offline :
            timestr = await self.streamtime(dur,offlinewait)
            retstr = "Stream lasted for "
        else :
            timestr = await self.streamtime(dur)
            retstr = "Stream running for "
        retstr += timestr
        return retstr

    #Embed creation stub. Should be overridden, but is functional.
    async def simpembed(self,rec,snowflake=None,offline=False) :
        myembed = discord.Embed(title="Stream has come online!",url=self.streamurl.format(await self.getrecname(rec)))
        return myembed

    #Embed creation stub. Should be overridden, but is functional.
    #Returns the simple embed.
    async def makeembed(self,rec,snowflake=None,offline=False) :
        return await self.simpembed(rec,offline)

    #Embed creation stub. Should be overridden, but is functional.
    #Returns the normal embed, which may be fine if detailed channel record has no additional information.
    async def makedetailembed(self,rec,snowflake=None,offline=False) :
        return await self.makeembed(rec,offline)

    #Short string to announce the stream is online, with stream URL. 
    async def makemsg(self,rec) :
        #Note we purposely stop the embed for the link - if we want an embed we'll
        #generate one ourself which is more useful than the default ones.
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
        try :
            async with self.conn.get(url,headers=headers) as resp :
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
            rec = None #Exceeded the timeout we set - 60 seconds.
        except json.JSONDecodeError : #Error in reading JSON - bad response from server?
            print("JSON Error in",self.name,"buff:",buff) #Log this, since it shouldn't happen.
            rec = False #This shouldn't happen since status == 200
        return rec

    #Updates parsed dict by calling the API. Generalized enough that it works for Picarto+Piczel
    async def updateparsed(self) :
        updated = False
        self.lastupdate.clear() #Update has not succeded.
        buff = await self.acallapi(self.apiurl)
        if buff : #Any errors would return False instead of a buffer
            self.parsed = {await self.getrecname(item):item for item in buff}
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
        '''Removes or edits the announcement message(s) for streams that have
        gone offline.'''
        mydata = self.mydata #Ease of use and speed reasons
        recid = await self.getrecname(rec)
        if not serverlist :
            serverlist = mydata['AnnounceDict'][recid]
        for server in serverlist :
            try :
                #Try to retreive our saved id
                msgid = await self.getmsgid(server,recid)
                #We don't have a saved message for this, so do nothing.
                if not msgid :
                    continue
                #Either the MSG option is not set, or is set to edit, which is the default
                #We should edit the message to say they're not online
                msgopt = await self.getoption(server,"MSG",recid)
                if msgopt == "edit" :
                    #channel = self.client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                    channel = await self.resolvechannel(server,recid)
                    if channel : #We may not have a channel if we're no longer in the guild/channel
                        oldmess = await channel.fetch_message(msgid)
                        newembed = oldmess.embeds[0].to_dict()
                        del newembed['image'] #Delete preview as they're not online
                        newembed['title'] = await self.streammsg(self.savedmsg[server][recid],rec,offline=True)
                        newembed = discord.Embed.from_dict(newembed)
                        newmsg = recid + " is no longer online. Better luck next time!"
                        await oldmess.edit(content=newmsg,embed=newembed)
                #We should delete the message
                elif msgopt == "delete" :
                    #channel = self.client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                    channel = await self.resolvechannel(server,recid)
                    if channel :
                        oldmess = await channel.fetch_message(msgid)
                        await oldmess.delete()
                #Only other possible value is 'static' in which case we'd do nothing.
            except KeyError as e :
                #We should've prevented any of these, so note that it happened.
                print(self.name,"remove message keyerror:", repr(e))
                pass
            except discord.Forbidden :
                #We are not permitted to edit/delete message. This SHOULDN'T ever happen
                #since you can always delete/edit your own stuff, but JIC.
                pass
            except discord.NotFound :
                #Only the message finding should trigger this, in which case nothing
                #to do except ignore it. It was probably deleted.
                pass
            except discord.HTTPException as e :
                #HTTP error running the edit/delete command. The above two should've
                #caught the obvious ones, so lets log this to see what happened.
                print(self.name,"remove message keyerror:", repr(e))
                pass
            #Remove the msg from the list, we won't update it anymore.
            #This still happens for static messages, which aren't edited or removed
            try : 
                del self.savedmsg[server][recid]
            except KeyError : #They might not have a message saved, ignore that
                pass

    async def updatemsg(self,rec) :
        #We'll need these later, but can't make them quite yet
        myembed = None
        noprev = None
        mydata = self.mydata #Ease of use and speed reasons
        recid = await self.getrecname(rec) #Keep record name cached, we need it a lot.
        for server in mydata['AnnounceDict'][recid] :
            typeopt = await self.getoption(server,"Type",recid)
            msgopt = await self.getoption(server,"MSG",recid)
            #If Type is simple, there's nothing to edit so skip it.
            if typeopt == "simple" :
                continue
            #If MSG option is static, we don't update.
            elif msgopt == "static" :
                continue
            #If we don't have a saved message, we can't update.
            msgid = await self.getmsgid(server,recid)
            if msgid :
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
                except discord.NotFound :
                    #The message wasn't found, probably deleted. Remove the saved id
                    #Note this won't happen if we're not in the guild/channel, since
                    #we'll fail the if channel test instead for that case.
                    try :
                        #print("Removing message",server,recid,self.savedmsg[server][recid])
                        del self.savedmsg[server][recid]
                    except :
                        pass
                    pass
                except discord.HTTPException as e:
                    #General HTTP errors from command. 
                    #print("2",repr(e))
                    pass
                if oldmess :
                    try :
                        if typeopt == "noprev" :
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
        guildlist = None
        #We're going to iterate over a list of servers to announce on
        if oneserv : #If given a server, that list is the one we were given
            guildlist = [oneserv]
        else : #Otherwise it's all servers that the stream has listed as listening
            guildlist = mydata['AnnounceDict'][recid]
        #print("Made guildlist",guildlist,":",oneserv)
        for server in guildlist: #mydata['AnnounceDict'][recid] :
            #print("found a server")
            if await self.getoption(server,'Stop',recid) :
                #Channel was stopped, do not announce
                continue
            #print("Wasn't stopped")
            if (await self.isadult(rec)) and (not await self.getoption(server,'Adult')) :
                #This is an adult stream and channel does not allow those. Skip it.
                continue
            #print("Not adult, or adult allowed")
            sentmsg = None
            try :
                channel = await self.resolvechannel(server,recid)
                if channel : #Might not be in server anymore, so no channel
                    msgtype = await self.getoption(server,"Type",recid)
                    #print("msgtype",msgtype)
                    if msgtype == "simple" :
                        sentmsg = await channel.send(msg)
                    elif msgtype == "noprev" :
                        sentmsg = await channel.send(msg,embed=noprev)
                    else :
                        sentmsg = await channel.send(msg,embed=myembed)
            except KeyError :
                pass #Server has no announcement channel set
            #print("Sent",sentmsg)
            if sentmsg :
                if not (server in self.savedmsg) :
                    self.savedmsg[server] = {}
                self.savedmsg[server][recid] = sentmsg.id

    #Embed for a detailed announcment - usually more info than in the default announce
    #Empty stub that should be overridden. This ignores the embed type option!
    async def makedetailembed(self,rec) :
        raise NotImplementedError("makedetailembed must be implemented in subclass!")
        return None
        
    #Provides a more detailed announcement of a channel for the detail command
    async def detailannounce(self,recid,oneserv=None) :
        #For now we should only call this with a specific server to respond to
        if not oneserv :
            return
        mydata = self.mydata #Ease of use and speed reasons
        rec = await self.agetchannel(recid)
        channel = await self.resolvechannel(oneserv,recid)
        if rec == None :
            msg = "Timeout reached attempting API call. Please try again later."
            if not self.lastupdate : #Note if the API update failed
                msg += "\n**Last attempt to update API also failed. API may be down.**"
            await channel.send(msg)
            return
        if not rec :
            try :
                msg = "Sorry, I failed to load information about that channel. Check your spelling and try again."
                if not self.lastupdate : #Note if the API update failed
                    msg += "\n**Last attempt to update API failed. API may be down.**"
                await channel.send(msg)
            except KeyError : #Nothing left to have this but keep it for now.
                pass
            return #Only announce on that server, then stop.
        myembed = await self.makedetailembed(rec)
        if myembed : #Make sure we got something, rather than None/False
            try :
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
                try : #Try to delete the Stop override if it exists
                    del mydata['COver'][message.guild.id]['Stop']
                except KeyError :
                    pass #If it doesn't, ignore it.
                mydata["Servers"][message.guild.id]["AnnounceChannel"] = message.channel.id
                msg = "Ok, I will now start announcing in this server, using this channel."
                await message.channel.send(msg)
            elif command[0] == 'stop' :
                #Stop announcing - just removed the AnnounceChannel option
                try :
                    del mydata["Servers"][message.guild.id]["AnnounceChannel"]
                except KeyError :
                    pass #Not listening, so skip
                if not 'COver' in mydata : #We need to make the section
                    mydata['COver'] = {} #New dict
                if not message.guild.id in mydata['COver'] : #Make server in section
                    mydata['COver'][message.guild.id] = {}
                mydata['COver'][message.guild.id]['Stop'] = True
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
                    elif newopt.lower() in ("showadult","hideadult") :
                        if not (message.guild.id in mydata["Servers"]) :
                            #Haven't created servers info dict yet, make a dict.
                            mydata["Servers"][message.guild.id] = {}
                        if newopt.lower() == 'showadult' :
                            mydata["Servers"][message.guild.id]["Adult"] = True
                        else :
                            mydata["Servers"][message.guild.id]["Adult"] = False
                        setopt.add(newopt)
                    else :
                        unknown = True #msg = "Unknown option provided. Please use the help menu for info on how to use the option command."
                        #await message.channel.send(msg)
                if setopt :
                    msg += "Options set: " + ", ".join(setopt) + ". "
                if unknown :
                    msg += "One or more unknown options found. Please check the help menu for available options."
                await message.channel.send(msg)
            #Similar to option, but sets it only for a single stream
            elif command[0] == 'streamoption' :
                if len(command) < 2 :
                    msg = "Missing stream name or option. Please use the help menu for info on how to use the streamoption command."
                    await message.channel.send(msg)
                    return
                #If we're not listening to it right now, don't set the override.
                #This avoids mismatched capitalization from the user setting the
                #override on the wrong name.
                rec = command[1] #Name of stream
                if not (message.guild.id in mydata["Servers"]
                        and rec in mydata["Servers"][message.guild.id]["Listens"]) :
                    msg = rec + "is not in your list of watched streams. Check spelling and capitalization and try again."
                    await message.channel.send(msg)
                    return
                msg = ""
                setopt = set()
                unknown = False
                for newopt in command[2:] :
                    if newopt == 'clear' : #Clear all stream options
                        try :
                            del mydata['COver'][message.guild.id][rec]
                        except KeyError :
                            pass
                        setopt.add(newopt)
                    elif newopt in ("default","noprev","simple") :
                        await setstreamoption(message.guild.id, "Type", rec, newopt) 
                        setopt.add(newopt)
                    elif newopt in ("delete","edit","static") :
                        await setstreamoption(message.guild.id, "MSG", rec, newopt) 
                        setopt.add(newopt)
                    elif newopt.lower() in ("showadult","hideadult") :
                        if newopt.lower() == 'showadult' :
                            val = True
                        else :
                            val = False
                        await setstreamoption(message.guild.id, "Adult", rec, val) 
                        setopt.add(newopt)
                    else :
                        #We had at least one unknown option
                        unknown = True
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
                    #newlist = [*["**" + item + "**" for item in mydata["Servers"][message.guild.id]["Listens"] if item in self.parsed],*[item for item in mydata["Servers"][message.guild.id]["Listens"] if not item in self.parsed]]
                    newlist = []
                    for item in mydata["Servers"][message.guild.id]["Listens"] :
                        newitem = item
                        if item in self.parsed : #Stream is online
                            newitem = "**" + item + "**"
                        try : #See if we have a channel override set, and add it if so.
                            chan = await self.resolvechannel(message.guild.id,channelid=mydata['COver'][message.guild.id][item]['Channel'])
                            newitem += ":" + chan.mention
                        except KeyError : 
                            pass #We may not have an override set, so ignore it.
                        newlist.append(newitem)
                    newlist.sort()
                    msg += " Announcing for (**online**) streamers: " + ", ".join(newlist)
                except : 
                    msg += " No streamers are currently set to be watched"
                msg += ".\nAnnouncement type set to "
                try : #Check our announcement type. If doesn't exist it's default
                    if not ('Type' in mydata["Servers"][message.guild.id]) :
                        msg += "default with "
                    else :
                        msg += mydata["Servers"][message.guild.id]['Type'] + " with "
                except KeyError : #Server section doesn't exist, use default.
                    msg += "default with "
                try : #Check if we're set to edit messages. None set is default edit
                    if not ('MSG' in mydata["Servers"][message.guild.id]) :
                        msg += "edit messages."
                    else :
                        msg += mydata["Servers"][message.guild.id]['MSG'] + " messages."
                except KeyError : #Server section doesn't exist, use default.
                    msg += "edit messages."
                #Do we show streams marked as adult? Not all streams support this
                if await self.getoption(message.guild.id,'Adult') :
                    msg += " Adult streams are shown normally."
                else :
                    msg += " Adult streams will not be announced."
                if not self.lastupdate : #Note if the API update failed
                    msg += "\n**Last attempt to update API failed.**"
                if await self.getoption(message.guild.id,'Stop') :
                    msg += "\nMessages are currently stopped via the stop command."
                await message.channel.send(msg)
            elif command[0] == 'announce' : #Reannounce any missing announcements
                clive = 0
                canno = 0
                for item in mydata["Servers"][message.guild.id]["Listens"] :
                        if item in self.parsed : #Stream is online
                            clive = clive + 1
                            #Make sure we have a savedmsg, we're going to need it
                            if not (message.guild.id in self.savedmsg) :
                                self.savedmsg[message.guild.id] = {}
                            #Stream isn't listed, announce it
                            if not item in self.savedmsg[message.guild.id] :
                                #print("Announcing",item)
                                await self.announce(self.parsed[item],message.guild.id)
                                canno = canno + 1
                msg = "Found " + str(clive) + " live stream(s), found " + str(canno) + " stream(s) that needed an announcement."
                #old message msg = "Announced " + str(canno) + " stream(s) that are live but not announced of " + str(clive) + " live streams."
                if not self.lastupdate : #Note if the API update failed
                    msg += "\n**The last attempt to update API failed.** The API may be down. This will cause delays in announcing streams. Streams will be announced/edited/removed as needed when the API call succeeds."
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
                if not self.lastupdate : #Note if the API update failed
                    msg += "\n**The last attempt to update the API failed**, the API may be down. Please try your command again later."
                if message.channel_mentions : #Inform the user the override was set
                    msg += " Announcement channel set to " + message.channel_mentions[0].mention
                await message.channel.send(msg)
                try :
                    #Announce the given user is online if the record exists.
                    if (message.guild.id in self.savedmsg) and (command[1] in self.savedmsg[message.guild.id]) :
                        pass #We already have a saved message for that stream.
                    elif message.channel_mentions : #Does nothing now since we saved the override elsewhere
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
                    newrec = "" #String that holds the corrected stream name.
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
                    #Stream does not exist on service, so do not add.
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
                if not self.lastupdate : #Note if the API update failed
                    msg += "\n**The last attempt to update the API failed**, the API may be down. Please try your command again later."
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
                    #And remove any overrides for the channel
                    try :
                        del mydata['COver'][message.guild.id][command[1]]
                    except KeyError : #If any of those keys don't exist, it's fine
                        pass #Ignore it, because the override isn't set.
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
                    #And remove any overrides for the channel
                    try :
                        del mydata['COver'][message.guild.id][command[1]]
                    except KeyError : #If any of those keys don't exist, it's fine
                        pass #Ignore it, because the override isn't set.
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
                    msg += "\nshowadult: default option. Adult streams are shown normally."
                    msg += "\nhideadult: Adult streams are not announced/previewed (function in progress). Streams that are marked adult after announcement are not currently handled."
                    await message.channel.send(msg)
                    #msg += "\n"
            #The general help goes here - it should list commands or some site that
            #has a list of them
            else :
                msg = "The following commands are available for " + self.name + ":"
                msg += "\nlisten: starts announcing new streams in the channel it is said."
                msg += "\nstop: stops announcing streams and removes the announcement channel."
                msg += "\noption: sets ONE of the following options: default, noprev, simple. See help option for details."
                msg += "\nadd <name>: adds a new streamer to announce. Limit of 100 channels per server."
                msg += "\naddmult <names>: adds multiple new streams at once, seperated by a space. Channels past the server limit will be ignored."
                msg += "\announce: immediately announces any online streams that were not previously announced."
                msg += "\nremove <name>: removes a streamer from announcements."
                msg += "\nremovemult <names>: removes multiple new streams at once, seperated by a space."
                msg += "\ndetail <name>: Provides details on the given channel, including multi-stream participants."
                msg += "\nlist: Lists the current announcement channel and all listened streamer."
                msg += "\nSome commands/responses will not work unless an announcement channel is set."
                msg += "\nPlease note that all commands, options and channel names are case sensitive!"
                if not self.lastupdate : #Note if the API update failed
                    msg += "\n**The last attempt to update the API failed!** The API may be down. This may cause unexpected behavoir, and certain commands to not work."
                await message.channel.send(msg)
