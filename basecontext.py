#context class to base new contexts on
#This file has all the items required by the dbcontext bot to be valid.
#Some values/functions WILL need to be updated. Please see the related module
#templateclass.py for details, as well as the minimum list of functions/values
#that need to be set for any new class inheriting from this.

#If I use this as a base, I could redo the commands + help to make use of a dict
#with {<command>:<help text>} which would simplify writing new commands
#into the help file. AND much more easily add context specific commands.

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

    def __init__(self,instname=None) :
        #There are two values set by dbcontext after initializing the class:
        #self.mydata - contains the persistent data for this instance.
        #self.client - is the Discord.Client instance in use. Please don't use it for being an asshat.
        if instname :
            self.name = instname
        else :
            self.name = self.defaultname
        self.parsed = parsed #This should be replaced in the subclass
        self.lastupdate = lastupdate #This should be replaced in the subclass
        self.defaultdata = {"AnnounceDict":{},"Servers":{},"COver":{},"SavedMSG":{}}
        #This is merged into the dict that dbcontext creates for this context on load,
        #which is then stored in the mydata variable above.
        #Basically, it just sets up some default structures for use later. It can be
        #an empty dict, but these two options are currently used by every context to
        #store their info, and it's recommended to keep that usage the same if you're
        #doing a similar API based watch context, or at least the servers the same for
        #what servers to respond in and what channel to respond to in that server if
        #possible for your usage.

        #The first keeps streams to search for, with a !set! of servers that want that
        #info. For example, the twitch context would have info like this
        #AnnounceDict
        #   |-"AngriestPat"
        #       |-<ServerID>
        #   |-"WoolieVersus"
        #       |-<ServerID>
        #       |-<ServerID2>

        #The second keeps a dict of servers, that holds the dict with the options
        #they set, such as the channel to talk in, who they listen to, etc.
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
        #          |-"Option": #Holds a dict to hold option overrides in
        #              |-<optionname>: <optionvalue> #Holds the new value for the given option
        #              |-"Channel": <ChannelID> #Channel to announce in instead of listen channel

        #And now a fourth, SavedMSG. This is a dict that holds the discord I of any
        #announcement messages saved. It's a dict of server ID, that each hold a
        #dict of <streamname>:<messageid>
        #SavedMSG
        #  |-<ServerID> #Server ID these messages are for
        #      |<Stream1>:<messageid>
        #      |<Stream2>:<messageid2>
        #  |-<ServerID2>
        #      |<Stream2>:<messageid3>

        #Again, these are not requirements, but recommended to simplify things. It means
        #being able to copy/paste a lot of code from the existing templates, and time
        #savers are always nice.


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
            return self.mydata['SavedMSG'][guildid][recid]
        except KeyError : #Guild has no saved messages, or none for that record
            return False

    #Set saved message id
    async def setmsgid(self,guildid,recid,messageid) :
        if not guildid in self.mydata['SavedMSG'] :
            self.mydata['SavedMSG'][guildid] = {}
        self.mydata['SavedMSG'][guildid][recid] = messageid

    #Get the channel to announce.
    async def resolvechannel(self,guildid,recname=None,channelid=None) :
        '''guildid = int: snowflake of guild
        recname = str: stream name
        channelid = int: snowflake of channel - overrides any other option.
        Return: TextChannel instance if found.
        If we no longer have access to the channel, get_channel returns None.
        Calling functions should all account for this possibility.'''
        #If we're supplied with the channelid, use it to grab our TextChannel.
        if channelid : #Used for channel override things currently.
            return self.client.get_channel(channelid)
        mydata = self.mydata #Ease of use/potentially speed
        #Otherwise, try to look it up using a stream record and guild id
        if recname : #We have a stream name, see if it has an override
            try :
                newchan = mydata['COver'][guildid][recname]['Option']['Channel']
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
    async def getoption(self,guildid,option,recname=None) :
        #option = str: name of option to get ("Type", "Adult", or "MSG" right now)
        #recname = str: stream name, for setting a stream override
        mydata = self.mydata
        if recname :
            try : #Try and read the streams override option
                return mydata['COver'][guildid][recname]['Option'][option]
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

    async def setoption(self,guildid,optname,setting=None) :
        #guildid = int: the discord ID for the server
        #optname = str: the name of the option group
        #setting = str: option to set, or None to clear
        mydata = self.mydata
        #If we have no setting, try and delete it.
        if setting is None :
            try :
                del mydata["Servers"][guildid][optname]
            except KeyError : #Doesn't exist, so no need to do anything
                pass
            return True #We're done here, leave
        #If we're actually setting one, we need to ensure the upper dicts exist
        if not "Servers" in mydata :
            mydata["Servers"] = {}
        if not guildid in mydata["Servers"] :
            mydata["Servers"][guildid] = {}
        else :
            #Finally, set the option group to the provided settings.
            mydata["Servers"][guildid][optname] = setting
        return True
    
    #Sets the override option for the given stream
    async def setstreamoption(self, guildid, optname, recname, setting=None) :
        #guildid = int: the discord id for the server
        #optname = str: the name of the option group
        #recname = str: the name of the stream to set the option on
        #setting = str/int/bool: the value of the option to set
        mydata = self.mydata
        #We have no setting, try and delete it.
        if setting is None :
            try :
                del mydata['COver'][guildid][recname]['Option'][optname]
            except KeyError : #Doesn't exist, so no need to do anything
                pass
            return True #We're done here, leave
        #We need to make sure all our needed dicts are created
        if not 'COver' in mydata :
            mydata['COver'] = {}
        if not guildid in mydata['COver'] :
            mydata['COver'][guildid] = {}
        if not recname in mydata['COver'][guildid] :
            mydata['COver'][guildid][recname] = {}
        if not 'Option' in mydata['COver'][guildid][recname] :
            mydata['COver'][guildid][recname]['Option'] = {}
        #Now we know they exist, set the Option section to override our setting for the given option
        mydata['COver'][guildid][recname]['Option'][optname] = setting
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
            return "{0}h:{1:02d}m".format(int(hours),int(minutes))

    async def longertime(self,snowflake,rec) :
        '''Finds the longer of two durations - the time since the snowflake,
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
        #Find the duration of the stream.
        dur = await self.longertime(snowflake,rec)
        #If stream is offline, we adjust the time to account for the waiting
        #period before we marked it offline.
        if offline :
            timestr = await self.streamtime(dur,offlinewait)
            retstr = "Stream lasted for "
        else :
            #Online streams need no adjustement.
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
    #Returns the normal embed, which may be fine if detailed stream record has
    #no additional information.
    async def makedetailembed(self,rec,snowflake=None,offline=False) :
        return await self.makeembed(rec,offline)

    #Short string to announce the stream is online, with stream URL. 
    async def makemsg(self,rec) :
        #Note we purposely stop the embed for the link - if we want an embed
        #we'll generate one ourself which is more useful than the default ones.
        return await self.getrecname(rec) + " has come online! Watch them at <" + self.streamurl.format(await self.getrecname(rec)) + ">"

    #Gets the detailed information about a stream. Used for makedetailmsg.
    #It returns the interpreted buffer. For Picarto, this is the stream record.
    #This is pretty basic, so most classes should be able to use this. If needed,
    #you can override the function, then in your overriding function call
    #basecontext.APIContext.agetstream(self,streamname,headers), then
    #manipulate the returned buffer as you need. See piczelclass as an example
    #of this.
    async def agetstream(self,streamname,headers=None) :
        #Call our API with the getchannel URL formatted with the channel name
        return await self.acallapi(self.channelurl.format(streamname),headers)

    #Handles calling the API at the given URL and interpreting the result as
    #JSON. No changes are made to the data, so it can be used by anything that
    #needs a simple GET ran. 
    async def acallapi(self,url,headers=None) :
        '''Calls the API at the given URL, with optional headers, and interprets
        the result via the JSON library.
        Returns the interpreted JSON on success, None if the attempt timed out,
        and False if any other error occurs.'''
        #header is currently only needed by twitch, where it contains the API
        #key. For other callers, it is None.
        rec = False #Used for the return - default of False means it failed.
        try :
            async with self.conn.get(url,headers=headers) as resp :
                #print("acallapi",resp.status)
                if resp.status == 200 : #Success
                    buff = await resp.text()
                    #print(buff)
                    if buff :
                        rec = json.loads(buff) #Interpret the received JSON
                if resp.status == 404 : #Not found
                    rec = 0 #0 means no matching record - still false
        #Ignore connection errors, and we can try again next update
        except aiohttp.ClientConnectionError :
            rec = False #Low level connection problems per aiohttp docs.
        except aiohttp.ClientConnectorError :
            rec = False #Also a connection problem.
        except aiohttp.ServerDisconnectedError :
            rec = False #Also a connection problem.
        except aiohttp.ServerTimeoutError :
            rec = False #Also a connection problem.
        except asyncio.TimeoutError : #Exceeded the timeout we set - 60 seconds.
            #Note the different return - timeouts explicitly return None so the
            #calling code can check if it wants to differentiate it. Currently,
            #getting a detailed stream record does so to inform the user that
            #the attempt failed due to the API likely being down.
            rec = None
        except json.JSONDecodeError : #Error in reading JSON - bad response from server?
            if buff.startswith("<!DOCTYPE html>") :
                #We got an HTML document instead of a JSON response. piczel does this
                #during maintenence, and it's not valid for anyone else either so might
                #as well catch it here, so we can supress this error.
                #Putting it here in the except instead of above means it only matters if
                #JSON decoding failed. Maybe it wouldn't always.
                return False #We failed, return a false
            print("JSON Error in",self.name,"buff:",buff) #Log this, since it shouldn't happen.
            rec = False #This shouldn't happen since status == 200
        return rec

    #Updates parsed dict by calling the API. Generalized enough that it works for Picarto+Piczel
    async def updateparsed(self) :
        updated = False
        self.lastupdate.clear() #Update has not succeded.
        buff = await self.acallapi(self.apiurl)
        if buff : #Any errors would return False (or None) instead of a buffer
            #Note we REPLACE, not update, self.parsed. This is so references to
            #the old one are still valid elsewhere - updatetask keeps one so it
            #can compare the old vs new to find new/stopped streams.
            self.parsed = {await self.getrecname(item):item for item in buff}
            updated = True #Parse finished, we updated fine.
        if updated : #We updated fine so we need to record that
            self.lastupdate.append(updated) #Not empty means list is True, update succeeded
        return updated

    #This is started as a background task by dbcontext. It can be empty but
    #should exist.
    async def updatewrapper(self,conn) :
        '''Sets a function to be run continuously every 60 seconds until the bot
        is closed.'''
        #Data validation should go here if needed for your mydata dict. This is
        #CURRENTLY only called once, when the bot is first started, but this may
        #change in future versions if the client needs to be redone.
        self.conn = conn #Set our ClientSession reference for connections.
        #While we wait for the client to login, we can check our APIs
        try :
             await self.updateparsed() #Start our first API scrape
        except Exception as error :
            #We catch any errors that happen on the first update and log them
            #It shouldn't happen, but we need to catch it or our wrapper would
            #break.
            print(self.name,"initial update error",repr(error))
        #Logs our starting info for debugging/check purposes
        print("Start",self.name,len(self.parsed))
        #By the time that's done our client should be setup and ready to go.
        #but we wait to make absolutely sure.
        await self.client.wait_until_ready() #Don't start until client is ready
        #The above makes sure the client is ready to read/send messages and is
        #fully connected to discord. Usually, it is best to leave it in.
        #Now our client is ready and connected, let's check if our saved messages
        #are still online. If not, we need to pass it to removemsg.
        #Step 1: Get a list of all stream names with a saved message
        savedstreams = set([item for sublist in [self.mydata["SavedMSG"][k] for k in self.mydata["SavedMSG"]] for item in sublist])
        #print("savedstreams",savedstreams)
        #Note that if the initial update fails, due to the API being down most
        #likely, this WILL remove all stream messages. Waiting until the API
        #updates successfully might be the best option, but that'd require to
        #much reworking of the update task. This way they'll get announced when
        #the API comes back.
        for stream in savedstreams :
            #Step 2: Check if the stream is offline: not in self.parsed.
            if not stream in self.parsed : #No longer online
                #print("savedstreams removing",stream)
                #Send it to removemsg to edit/delete the message for everyone.
                await self.removemsg(rec=None,recid=stream)
        #while not loop keeps a background task running until client closing
        while not self.client.is_closed() :
            try :
                await asyncio.sleep(60) # task runs every 60 seconds
                await self.updatetask() #The function that actually performs anything
            #This NEEDS to be first, as it must take priority
            #This could be Exception, or BaseException if Python 3.8+
            except asyncio.CancelledError : 
                #Task was cancelled, stop execution.
                return
            #Error handling goes here. For now, we just print the error to console
            #then continue. We do NOT ignore BaseException errors - those stop us
            #since we're likely being shut down.
            except Exception as error :
                print(self.name,"wrapper:",repr(error))
                traceback.print_tb(error.__traceback__)

    async def updatetask(self):
        if not self.client.is_closed(): #Don't run if client is closed.
            oldlist = self.parsed #Keep a reference to the old list
            if not await self.updateparsed() :
                #Updating from the API failed for some reason, likely it's down
                #For now, just return and we'll try again in a minute.
                return
            #print("Old Count:", len(oldlist),"Updated Count:", len(self.parsed))
            oldset = set(oldlist) #Set of names from old dict
            newset = set(self.parsed) #Set of names from new dict
            #Compare the old list and the new list to find new/removed items
            newstreams = newset - oldset #Streams that just came online
            oldstreams = oldset - newset #Streams that have gone offline
            curstreams = newset - newstreams #Streams online that are not new
            removed = [] #List of streams too old and thus removed
            #Search through streams that have gone offline
            #DBCOffline is used to track streams that have gone offline or
            #have stayed online. Once the counter has hit a certain threshold
            #the streams is marked as needing announcements deleted/updated.
            for gone in oldstreams :
                rec = oldlist[gone] #Record from last update
                if 'DBCOffline' in rec : #Has been offline in a previous check
                    rec['DBCOffline'] += 1
                else :
                    rec['DBCOffline'] = 1 #Has just gone offline
                #If the stream has not been gone the last offlinewait updates, readd it
                if rec['DBCOffline'] < offlinewait :
                    self.parsed[gone] = rec
                else :
                    #Otherwise we assume it's not a temporary disruption and add it
                    #to our list of streams that have been removed
                    removed.append(gone)
            mydata = self.mydata #Ease of use and speed reasons
            for new in newstreams :
                if new in mydata['AnnounceDict'] :
                    rec = self.parsed[new]
                    #print("I should announce",rec)
                    await self.announce(rec)
            for cur in curstreams :
                if cur in mydata['AnnounceDict'] : #Someone is watching this stream
                    oldrec = oldlist[cur]
                    rec = self.parsed[cur]
                    #print("I should announce",rec)
                    if 'DBCOnline' in oldrec : #Was online last check
                        if oldrec['DBCOnline'] >= 4 :
                            #Update the stream every 5 minutes.
                            #New record will have no count, resets timer.
                            await self.updatemsg(rec)
                        else :
                            #Add the count to the new record
                            rec['DBCOnline'] = oldrec['DBCOnline'] + 1
                    else :
                        #Start the count in the new record
                        rec['DBCOnline'] = 1 #Has just gone offline
            for old in removed :
                if old in mydata['AnnounceDict'] : #Someone is watching this stream
                    #print("Removing",old)
                    rec = oldlist[old]
                    await self.removemsg(rec) #Need to potentially remove messages
            return

    async def removemsg(self,rec,serverlist=None,recid=None) :
        '''Removes or edits the announcement message(s) for streams that have
        gone offline.'''
        #Sending None for rec is supported, in order to allow edit/removal of
        #offline streams - ie after the bot was offline.
        mydata = self.mydata #Ease of use and speed reasons
        #If we were provided with a record id, we don't need to find it.
        if not recid :
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
                    channel = await self.resolvechannel(server,recid)
                    if channel : #We may not have a channel if we're no longer in the guild/channel
                        oldmess = await channel.fetch_message(msgid)
                        newembed = None
                        #Simple would not have an old embed to use.
                        if len(oldmess.embeds) > 0 :
                            newembed = oldmess.embeds[0].to_dict()
                            if 'image' in newembed : #Is there a stream preview?
                                #Delete preview as they're not online
                                del newembed['image']
                            #If we have the rec, this is an online edit so we
                            #can update the time.
                            if rec :
                                newembed['title'] = await self.streammsg(msgid,rec,offline=True)
                            #If we don't, this is an offline edit. We can't get
                            #the time stream ran for, so just edit the current
                            #stored time and use that.
                            else : 
                                newembed['title'] = newembed['title'].replace("running","lasted")
                            newembed = discord.Embed.from_dict(newembed)
                        newmsg = recid + " is no longer online. Better luck next time!"
                        await oldmess.edit(content=newmsg,embed=newembed)
                #We should delete the message
                elif msgopt == "delete" :
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
                #This MIGHT happen if we lost permissions to talk in that channel
                #Def gonna wanna log this, it bad.
                print(self.name,"remove message forbidden:", repr(e))
                pass
            except discord.NotFound :
                #Only the message finding should trigger this, in which case
                #nothing to do except ignore it. It was probably deleted.
                pass
            except discord.HTTPException as e :
                #HTTP error running the edit/delete command. The above two should've
                #caught the obvious ones, so lets log this to see what happened.
                print(self.name,"remove message HTTPException:", repr(e))
                pass
            #Remove the msg from the list, we won't update it anymore.
            #This still happens for static messages, which aren't edited or removed
            try : 
                del mydata['SavedMSG'][server][recid]
            except KeyError : #They might not have a message saved, ignore that
                pass

    async def updatemsg(self,rec) :
        '''Updates an announcement with the current stream info, including run time.'''
        recid = await self.getrecname(rec) #Keep record name cached
        mydata = self.mydata #Ease of use and speed reasons
        #Compile dict of all stored announcement messages for this stream.
        allsaved = {k:v[recid] for (k,v) in mydata['SavedMSG'].items() if recid in v}
        if allsaved : #List MAY be empty if no announcements were made
            oldest = min(allsaved.values()) #Find the id with the lowest value
            #print("updatemsg",allsaved,"@@@",oldest)
            #We use that lowest value to help calculate how long the stream has
            #been running for. Ideally we'd always get that info from the API,
            #but it's not always available (like in picarto's), so we may need
            #to use the time the message was created instead.
            myembed = await self.makeembed(rec,oldest)
            noprev = await self.simpembed(rec,oldest)
        else :
            #If allsaved was empty, we don't have any saved messages to update.
            #So we can just stop now and save time.
            #print("updatemsg found no saved!")
            return
        for server in mydata['AnnounceDict'][recid] :
            #Get the options set for type of message, and if messages are edited
            typeopt = await self.getoption(server,"Type",recid)
            msgopt = await self.getoption(server,"MSG",recid)
            #If Type is simple, there's nothing to edit so skip it.
            if typeopt == "simple" :
                continue
            #If MSG option is static, we don't update.
            elif msgopt == "static" :
                continue
            #Get the saved msg for this server
            msgid = await self.getmsgid(server,recid)
            #If we don't have a saved message, we can't update. May be deleted.
            #May not have been announced.
            if msgid :
                #Try and grab the old message we saved when posting originally
                oldmess = None
                try :
                    channel = await self.resolvechannel(server,recid)
                    #Guild may no longer have an announce channel set, or we're
                    #not in the guild any more.
                    if channel : #If we found the channel the saved message is in
                        oldmess = await channel.fetch_message(msgid)
                except KeyError as e:
                    #This used to happen if there wasn't a saved message, or if
                    #the server removed it's announce channel. Both of those are
                    #now handled by helper functions, so this shouldn't happen.
                    print("updatemsg keyerror!",repr(e)) #Log it
                    pass
                except discord.NotFound :
                    #The message wasn't found, probably deleted. Remove saved id
                    #Note this won't happen if we're not in the guild/channel or
                    #if the announce channel was removed, as we'd fail the if
                    #channel test instead for that case.
                    try :
                        #print("Removing message",server,recid,msgid)
                        #Message is gone, remove it
                        del mydata['SavedMSG'][server][recid]
                    except :
                        pass
                    pass
                except discord.HTTPException as e:
                    #General HTTP errors from command. Not much we can do here.
                    #print("2",repr(e))
                    pass
                if oldmess :
                    if typeopt == "noprev" :
                            await oldmess.edit(content=oldmess.content,embed=noprev)
                    else :
                        #Need to check if stream is adult, and what to do if it is.
                        isadult = await self.isadult(rec)
                        adult = await self.getoption(server,'Adult',recid)
                        if isadult and (adult != 'showadult') :
                            #hideadult or noadult, same as noprev option
                            await oldmess.edit(content=oldmess.content,embed=noprev)
                        else :
                            #Otherwise show the preview
                            await oldmess.edit(content=oldmess.content,embed=myembed)

    #Announce a stream is online. oneserv only sends the message on the given
    #server, otherwise find all servers that should announce that name.                
    async def announce(self,rec,oneserv=None) :
        '''Announce a stream. Limit announcement to 'oneserv' if given.'''
        mydata = self.mydata #Ease of use and speed reasons
        #Make the embeds and the message for our announcement - done once no
        #matter how many servers we need to send it too. Note we should always
        #have at least one server, or else announce wouldn't have been called.
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
            isadult = await self.isadult(rec)
            adult = await self.getoption(server,'Adult',recid)
            if (isadult) and (adult == 'noadult') :
                #This is an adult stream and channel does not allow those. Skip it.
                continue
            #print("Not adult, or adult allowed")
            sentmsg = None
            try :
                channel = await self.resolvechannel(server,recid)
                if channel : #Might not be in server anymore, so no channel
                    msgtype = await self.getoption(server,"Type",recid)
                    #print("msgtype",msgtype)
                    if msgtype == "simple" : #simple type, no embed
                        sentmsg = await channel.send(msg)
                    elif msgtype == "noprev" : #Embed without preview type
                        sentmsg = await channel.send(msg,embed=noprev)
                    else :
                        #default type, but adult stream and hide adult is set
                        if isadult and (adult == 'hideadult') :
                            #Same as noprev option
                            sentmsg = await channel.send(msg,embed=noprev)
                        else :
                            #Default stream type, full embed with preview
                            sentmsg = await channel.send(msg,embed=myembed)
            except KeyError as e :
                #We should've prevented any of these, so note that it happened.
                #Note there aren't even any key indices left in the above code
                #It'd have to have raised out of one of the awaits.
                print(self.name,"announce message keyerror:", repr(e))
                pass
            except discord.Forbidden :
                #We don't have permission to talk in the channel.
                pass
            #print("Sent",sentmsg)
            if sentmsg :
                await self.setmsgid(server,recid,sentmsg.id)

    #Embed for a detailed announcment - usually more info than in the default announce
    #Empty stub that should be overridden. This ignores the embed type option!
    async def makedetailembed(self,rec,snowflake=None,showprev=True) :
        raise NotImplementedError("makedetailembed must be implemented in subclass!")
        return None

    #Provides a more detailed announcement of a stream for the detail command
    async def detailannounce(self,recid,oneserv=None) :
        #We should only call this with a specific server to respond to
        if not oneserv :
            return
        mydata = self.mydata #Ease of use and speed reasons
        rec = await self.agetstream(recid)
        channel = await self.resolvechannel(oneserv,recid)
        #rec is only none if the timeout was reached. Other errors return False
        if rec == None :
            msg = "Timeout reached attempting API call; it is not responding. Please try again later."
            if not self.lastupdate : #Note if the API update failed
                msg += "\n**Last attempt to update API also failed. API may be down.**"
            await channel.send(msg)
            return
        if rec == 0 : #API call returned a Not Found response
            msg = "The API found no users by the name. Check the name and spelling for errors and try again."
            #API being down wouldn't be the cause of this, so for now we're
            #commenting these out. May reinstate them later.
            #if not self.lastupdate : #Note if the API update failed
            #    msg += "\n**Last attempt to update API failed. API may be down.**"
            await channel.send(msg)
            return
        #Non-timeout error happened.
        if not rec :
            try :
                msg = "Sorry, I failed to load information about that channel due to an error. Please wait and try again later."
                if not self.lastupdate : #Note if the API update failed
                    msg += "\n**Last attempt to update API failed. API may be down.**"
                await channel.send(msg)
            except KeyError : #Nothing left to have this but keep it for now.
                pass
            return #Only announce on that server, then stop.
        showprev = True
        if not (await self.getoption(oneserv,'Adult',recid) == 'showadult') and (await self.isadult(rec)) :
            #We need to not include the preview from the embed.
            showprev = False
        myembed = await self.makedetailembed(rec,showprev=showprev)
        if myembed : #Make sure we got something, rather than None/False
            #If the server isn't showadult, AND this is an adult stream
            await channel.send(embed=myembed)

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
                mydata["Servers"][message.guild.id]["AnnounceChannel"] = channelid
                channel = await self.resolvechannel(message.guild.id,channelid=channelid)
                msg = "Ok, I will now use " + channel.mention + " for announcements."
                #Do we have permission to talk in that channel?
                if not channel.permissions_for(channel.guild.me).send_messages :
                    msg += "\nI **do not** have permission to send messages in that channel! Announcements will fail until permission is granted."
                await message.channel.send(msg)
                return
            elif command[0] == 'stop' :
                #Stop announcing - we set an override option named Stop to true
                if not 'COver' in mydata : #We need to make the section
                    mydata['COver'] = {} #New dict
                if not message.guild.id in mydata['COver'] : #Make server in section
                    mydata['COver'][message.guild.id] = {}
                #Set the override. Announce checks for this before announcing
                mydata['COver'][message.guild.id]['Stop'] = True
                msg = "Ok, I will stop announcing on this server."
                await message.channel.send(msg)
                return
            elif command[0] == 'resume' :
                #Unset the Stop override - nothing else needed.
                try : #Try to delete the Stop override if it exists
                    del mydata['COver'][message.guild.id]['Stop']
                except KeyError :
                    pass #If it doesn't, ignore it.
                channel = await self.resolvechannel(message.guild.id)
                msg = ""
                if channel :
                    msg = "I will resume announcements to " + channel.mention + "."
                else :
                    msg = "No announcement channel has been set, please set one with listen."
                await message.channel.send(msg)
                return
            elif command[0] == 'option' :
                if len(command) == 1 :
                    msg = "No option provided. Please use the help menu for info on how to use the option command."
                    await message.channel.send(msg)
                    return
                msg = ""
                setopt = set()
                unknown = False
                for newopt in command[1:] :
                    newopt = newopt.lower()
                    if newopt == 'clear' : #Clear all out options
                        for group in ('Type','MSG','Adult') :
                            await self.setoption(message.guild.id,group)
                        setopt.add(newopt)
                    elif newopt in ("default","noprev","simple") :
                        await self.setoption(message.guild.id,"Type",newopt)
                        setopt.add(newopt)
                    elif newopt in ("delete","edit","static") :
                        await self.setoption(message.guild.id,"MSG",newopt)
                        setopt.add(newopt)
                    elif newopt in ("showadult","hideadult","noadult") :
                        await self.setoption(message.guild.id,"Adult",newopt)
                        setopt.add(newopt)
                    else :
                        unknown = True #msg = "Unknown option provided. Please use the help menu for info on how to use the option command."
                if setopt :
                    msg += "Options set: " + ", ".join(setopt) + ". "
                if unknown :
                    msg += "One or more unknown options found. Please check the help menu for available options."
                await message.channel.send(msg)
                return
            #Similar to option, but sets it only for a single stream
            elif command[0] == 'streamoption' :
                if len(command) < 2 :
                    msg = "Command requires a stream name, or a streamname and option(s). Please use the help menu for info on how to use the streamoption command."
                    await message.channel.send(msg)
                    return
                #If we're not listening to it right now, don't set the override.
                #This avoids mismatched capitalization from the user setting the
                #override on the wrong name.
                rec = command[1] #Name of stream
                if not (message.guild.id in mydata["Servers"]
                        and rec in mydata["Servers"][message.guild.id]["Listens"]) :
                    msg = rec + " is not in your list of watched streams. Check spelling and capitalization and try again."
                    await message.channel.send(msg)
                    return
                if len(command) == 2 : #No options given, just show current options
                    msg = "No overrides exist for the given stream."
                    try :
                        options = {}
                        #Copy the Options from the override to here,
                        #we need to make a slight edit
                        options.update(mydata['COver'][message.guild.id][rec]['Option'])
                        #print("streamoption",options)
                        if 'Channel' in options :
                            foundchan = await self.resolvechannel(message.guild.id,channelid=options['Channel'])
                            if foundchan :
                                options['Channel'] = foundchan.mention
                        msg = "\n".join([str(i[0]) + ": " + str(i[1]) for i in options.items()])
                        msg = "The following overrides are set (Option: Setting) :\n" + msg
                    except KeyError :
                        pass
                    await message.channel.send(msg)
                    return
                msg = ""
                setopt = set()
                unknown = False
                for newopt in command[2:] :
                    #Valid options are all lower case, or channel mentions, which have no
                    #letters in them.
                    newopt = newopt.lower()
                    if newopt == 'clear' : #Clear all stream options
                        try :
                            del mydata['COver'][message.guild.id][rec]
                        except KeyError :
                            pass
                        setopt.add(newopt)
                    #This is a channel mention, set the channel override
                    elif (newopt.startswith('<#') and newopt.endswith('>')) :
                        await self.setstreamoption(message.guild.id,'Channel',rec,int(newopt[2:-1]))
                        setopt.add(newopt)
                    elif newopt in ("default","noprev","simple") :
                        await self.setstreamoption(message.guild.id,"Type",rec,newopt) 
                        setopt.add(newopt)
                    elif newopt in ("delete","edit","static") :
                        await self.setstreamoption(message.guild.id,"MSG",rec,newopt) 
                        setopt.add(newopt)
                    elif newopt in ("showadult","hideadult","noadult") :
                        await self.setstreamoption(message.guild.id,"Adult",rec,newopt) 
                        setopt.add(newopt)
                    else :
                        #We had at least one unknown option
                        unknown = True
                if setopt :
                    msg += "Options set: " + ", ".join(setopt) + ". "
                if unknown :
                    msg += "One or more unknown options found. Please check the help menu for available options."
                await message.channel.send(msg)
                return
            elif command[0] == 'list' :
                #List options and current list of watched streams
                msg = ""
                channel = await self.resolvechannel(message.guild.id)
                if channel :
                    msg = "I am currently announcing in " + channel.mention + "."
                else :
                    msg = "I am not currently set to announce streams in a channel."
                try :
                    #Create list of watched streams, bolding online ones.
                    newlist = []
                    for item in mydata["Servers"][message.guild.id]["Listens"] :
                        newitem = item
                        if item in self.parsed : #Stream is online
                            newitem = "**" + item + "**"
                        try : #See if we have an override set, and add it if so.
                            chan = await self.resolvechannel(message.guild.id,channelid=mydata['COver'][message.guild.id][item]['Option']['Channel'])
                            if chan :
                                newitem += ":" + chan.mention
                        except KeyError : 
                            pass #We may not have an override set, so ignore it.
                        newlist.append(newitem)
                    newlist.sort()
                    msg += " Announcing for (**online**) streamers: " + ", ".join(newlist)
                except KeyError : #If server doesn't even have a Listens, no watches
                    msg += " No streams are currently set to be watched"
                msg += ".\nAnnouncement type set to "
                #Check our announcement type - default/noprev/simple.
                atype = await self.getoption(message.guild.id,'Type')
                msg += atype + " and "
                #Check our message type - edit/delete/static.
                msgtype = await self.getoption(message.guild.id,'MSG')
                msg += msgtype + " messages."
                #Do we show streams marked as adult? Not all streams support this
                adult = await self.getoption(message.guild.id,'Adult')
                if adult == 'showadult' :
                    msg += " Adult streams are shown normally."
                elif adult == 'hideadult' :
                    msg += " Adult streams are shown without previews."
                elif adult == 'noadult' :
                    msg += " Adult streams will not be announced."
                else : #There's only 3 valid options, this shouldn't activate
                    #But ya know JIC.
                    msg += " **WARNING!** Unknown option set for Adult streams! Please set the adult option to correct this."
                if not self.lastupdate : #Note if the API update failed
                    msg += "\n**Last attempt to update API failed.**"
                if await self.getoption(message.guild.id,'Stop') :
                    msg += "\nMessages are currently stopped via the stop command."
                await message.channel.send(msg)
                return
            elif command[0] == 'announce' : #Reannounce any missing announcements
                clive = 0 #Channels that are live
                canno = 0 #Channels that were announced
                #Iterate over all this servers' listens
                for item in mydata["Servers"][message.guild.id]["Listens"] :
                        if item in self.parsed : #Stream is online
                            clive = clive + 1
                            #Make sure we have a savedmsg, we're going to need it
                            if not (message.guild.id in mydata['SavedMSG']) :
                                mydata['SavedMSG'][message.guild.id] = {}
                            #Stream isn't listed, announce it
                            if not item in mydata['SavedMSG'][message.guild.id] :
                                #print("Announcing",item)
                                await self.announce(self.parsed[item],message.guild.id)
                                canno = canno + 1
                msg = "Found " + str(clive) + " live stream(s), found " + str(canno) + " stream(s) that needed an announcement."
                if await self.getoption(message.guild.id,'Stop') :
                    msg += "\nStop is currently enabled for this server - no announcements have been made. The 'resume' command must be used to re-enable announcements."
                if not self.lastupdate : #Note if the API update failed
                    msg += "\n**The last attempt to update API failed.** The API may be down. This will cause delays in announcing streams. Streams will be announced/edited/removed as needed when the API call succeeds."
                await message.channel.send(msg)
                return
            elif command[0] == 'add' :
                #We need listens to exist - things later expect it
                if not ("Listens" in mydata["Servers"][message.guild.id]) :
                    #No listens added yet, make a set
                    mydata["Servers"][message.guild.id]["Listens"] = set()
                #Limit how many listens a server has. No one should be hitting this.
                if len(mydata["Servers"][message.guild.id]["Listens"]) >= 100 :
                        msg = "Too many listens already - limit is 100 per server."
                        await message.channel.send(msg)
                        return
                if not command[1] in mydata["AnnounceDict"] :
                    newrec = await self.agetstream(command[1])
                    if newrec == 0 :
                        msg = "API found no stream with that user name. Please check spelling and try again."
                        await message.channel.send(msg)
                        return
                    elif not newrec :
                        msg = "Error checking API for stream. Please try again later."
                        if not self.lastupdate : #Note if the API update failed
                            msg += "\n**The last attempt to update API failed.** The API is likely down."
                        await message.channel.send(msg)
                        return
                    else :
                        command[1] = await self.getrecname(newrec)
                    #Haven't used this stream anywhere before, make a set for it
                    mydata["AnnounceDict"][command[1]] = set()
                if not (message.guild.id in mydata["Servers"]) :
                    #Haven't created servers info dict yet, make a dict.
                    mydata["Servers"][message.guild.id] = {}
                #This marks the stream as being listened to by the server
                mydata["AnnounceDict"][command[1]].add(message.guild.id)
                #This marks the server as listening to the stream
                mydata["Servers"][message.guild.id]["Listens"].add(command[1])
                if message.channel_mentions : #Channel mention, so make an override
                    #Set this servers stream override for this stream to the mentioned channel.
                    await self.setstreamoption(message.guild.id,'Channel',command[1],message.channel_mentions[0].id)
                else : #If we're not SETTING an override, delete it.
                    await self.setstreamoption(message.guild.id,'Channel',command[1])
                msg = "Ok, I will now announce when " + command[1] + " comes online."
                if message.channel_mentions : #Inform the user the override was set
                    msg += " Announcement channel set to " + message.channel_mentions[0].mention
                if not self.lastupdate : #Note if the API update failed
                    msg += "\n**The last attempt to update the API failed**, the API may be down. Stream was added, but current online status may be incorrect."
                await message.channel.send(msg)
                try :
                    #Announce the given user is online if the record exists.
                    if (await self.getmsgid(message.guild.id,command[1])) :
                        pass #We already have a saved message for that stream.
                    else :
                        await self.announce(self.parsed[command[1]],message.guild.id)
                except KeyError : #If they aren't online, silently fail.
                    pass #Stream name wasn't in dict, so they aren't online.
                return
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
                #We're going to be setting a stream override, so make sure the
                #needed dicts are in place.
                if message.channel_mentions : #Channel mention, so make an override
                    if not 'COver' in mydata : #We need to make the section
                        mydata['COver'] = {} #New dict
                    if not message.guild.id in mydata['COver'] :
                        mydata['COver'][message.guild.id] = {}
                for newstream in command[1:] :
                    #print(newstream)
                    if len(mydata["Servers"][message.guild.id]["Listens"]) >= 100 :
                        msg += "Too many listens - limit is 100 per server. Did not add " + newstream + "or later streams."
                        break
                    #If the name ends with a comma, strip it off. This allows
                    #to copy/paste the result of the list command into addmult
                    #to re-add all those streams. 
                    if newstream.endswith(',') :
                        newstream = newstream[:-1]
                    newrec = "" #String that holds the corrected stream name.
                    #This is a channel mention, so don't try to add it as a stream
                    if (newstream.startswith('<#') and newstream.endswith('>')) :
                        pass #We don't set newrec so it'll get skipped
                    #Need to match case with the API name, so test it first
                    #If we already are watching it, it must be the correct name.
                    elif not newstream in mydata["AnnounceDict"] :
                        newrec = await self.agetstream(newstream)
                        #print(newrec)
                        if not newrec :
                            notfound.add(newstream)
                        else :
                            newrec = await self.getrecname(newrec)
                            #Haven't used this stream anywhere before, make a set for it
                            mydata["AnnounceDict"][newrec] = set()
                    else :
                        newrec = newstream
                    #Stream does not exist on service, so do not add.
                    if newrec :
                        #This marks the stream as being listened to by the server
                        mydata["AnnounceDict"][newrec].add(message.guild.id)
                        #This marks the server as listening to the stream
                        mydata["Servers"][message.guild.id]["Listens"].add(newrec)
                        if message.channel_mentions : #Channel mention, so make an override
                            if not newrec in mydata['COver'][message.guild.id] :
                                mydata['COver'][message.guild.id][newrec] = {}
                            #Set this servers stream override for this stream to the mentioned channel.
                            await self.setstreamoption(message.guild.id,'Channel',newrec,message.channel_mentions[0].id)
                        else : #If we're not SETTING an override, delete it.
                            await self.setstreamoption(message.guild.id,'Channel',newrec)
                        added.add(newrec)
                if added :
                    added = [*["**" + item + "**" for item in added if item in self.parsed], *[item for item in added if not item in self.parsed]]
                    added.sort()
                    msg += "Ok, I am now listening to the following (**online**) streamers: " + ", ".join(added)
                if notfound :
                    msg += "\nThe following streams were not found and could not be added: " + ", ".join(notfound)
                if not msg :
                    msg += "Unable to add any streams due to unknown error."
                if not self.lastupdate : #Note if the API update failed
                    msg += "\n**The last attempt to update the API failed**, the API may be down. Please try your command again later."
                await message.channel.send(msg)
                return
            elif command[0] == 'remove' :
                if command[1] in mydata["AnnounceDict"] :
                    try : #We need to remove the server from that streams list of listeners
                        mydata["AnnounceDict"][command[1]].remove(message.guild.id)
                        #If no one is watching that stream anymore, remove it
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
                    #If 'delete' option set, delete any announcement for that stream.
                    if ("MSG" in mydata["Servers"][message.guild.id]) and (mydata["Servers"][message.guild.id]["MSG"] == "delete" ) :
                        #This will delete announcement and clear savedmsg for us
                        try :
                            await self.removemsg(parsed[command[1]],[message.guild.id])
                        except KeyError : #If stream not online, parsed won't have record.
                            pass
                    else :
                        #We still need to remove any savedmsg we have for this stream.
                        try : #They might not have a message saved, ignore that
                            del mydata['SavedMSG'][message.guild.id][command[1]]
                        except KeyError :
                            pass
                    #And remove any overrides for the stream
                    try :
                        del mydata['COver'][message.guild.id][command[1]]
                    except KeyError : #If any of those keys don't exist, it's fine
                        pass #Ignore it, because the override isn't set.
                msg = "Ok, I will no longer announce when " + command[1] + " comes online."
                await message.channel.send(msg)
                return
            elif command[0] == 'removemult' :
                if not (message.guild.id in mydata["Servers"]) :
                    #Haven't created servers info dict yet
                    await message.channel.send("No streams are being listened to yet!")
                    return
                if not ("Listens" in mydata["Servers"][message.guild.id]) :
                    #No listens added yet
                    await message.channel.send("No streams are being listened to yet!")
                    return
                added = set()
                msg = ""
                notfound = set()
                for newstream in command[1:] :
                    #If the name ends with a comma, strip it off. This allows
                    #to copy/paste the result of the list command into removemult
                    #to remove all those streams. 
                    if newstream.endswith(',') :
                        newstream = newstream[:-1]
                    #print(newstream)
                    try :
                        mydata["AnnounceDict"][newstream].remove(message.guild.id)
                        added.add(newstream)
                        #If no one is watching that stream anymore, remove it
                        if not mydata["AnnounceDict"][newstream] :
                            mydata["AnnounceDict"].pop(newstream,None)
                    except ValueError :
                        notfound.add(newstream)
                        pass #Value not in list, don't worry about it
                    except KeyError :
                        notfound.add(newstream)
                        pass #Value not in list, don't worry about it
                    try :
                        mydata["Servers"][message.guild.id]["Listens"].remove(newstream)
                    except ValueError :
                        pass #Value not in list, don't worry about it
                    except KeyError :
                        pass #Value not in list, don't worry about it
                    #If 'delete' option set, delete any announcement for that stream.
                    if ("MSG" in mydata["Servers"][message.guild.id]) and (mydata["Servers"][message.guild.id]["MSG"] == "delete" ) :
                        #This will delete announcement and clear savedmsg for us
                        try :
                            await self.removemsg(parsed[newstream],[message.guild.id])
                        except KeyError : #If stream not online, parsed won't have record.
                            pass
                    else :
                        #We still need to remove any savedmsg we have for this stream.
                        try : #They might not have a message saved, ignore that
                            del mydata['SavedMSG'][message.guild.id][newstream]
                        except KeyError :
                            pass
                    #And remove any overrides for the stream
                    try :
                        del mydata['COver'][message.guild.id][command[1]]
                    except KeyError : #If any of those keys don't exist, it's fine
                        pass #Ignore it, because the override isn't set.
                if added :
                    msg += "Ok, I will no longer announce the following streamers: " + ", ".join(added)
                if notfound :
                    msg += "\nThe following streams were not found and could not be removed: " + ", ".join(notfound)
                if not msg :
                    msg += "Unable to remove any streams due to unknown error."
                await message.channel.send(msg)
                return
            elif command[0] == 'detail' :
                if len(command) == 1 : #No stream given
                    await message.channel.send("You need to specify a user!")
                else :
                    await self.detailannounce(command[1],message.guild.id)
                return
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
                    msg += "\ndelete: Same as edit, except announcement is deleted when the stream goes offline."
                    msg += "\nedit: default option. Viewers and other fields are updated periodically. Message is changed when stream is offline."
                    msg += "\nstatic: messages are not edited or deleted ever."
                    msg += "\nThe following options are not support for Twitch streams:"
                    msg += "\nshowadult: default option. Adult streams are shown normally."
                    msg += "\nhideadult: Adult streams are announced but not previewed."
                    msg += "\nnoadult: Adult streams are not announced. Streams that are marked adult after announcement will have their previews disabled."
                    msg += "\nThe adult options CAN NOT 100% shield your users from adult content. Forgetful streamers, API errors, bugs in the module, and old adult previews cached by the streaming site/discord/etc. may allow adult content through."
                    await message.channel.send(msg)
                    #msg += "\n"
            #The general help goes here - it should list commands or some site that
            #has a list of them
            else :
                msg = "The following commands are available for " + self.name + ":"
                msg += "\nlisten: starts announcing new streams in the channel it is said."
                msg += "\nstop: stops announcing streams, edits to existing announcements will still occur."
                msg += "\nresume: resumes announcing streams."
                msg += "\noption <option(s)>: sets one or more space separated options. See help option for details on available options."
                msg += "\streamoption <name> <option(s)>: overrides one or more space separated options for the given stream. If no options are provided, lists any overrides currently set."
                msg += "\nadd <name>: adds a new streamer to announce. Limit of 100 streams per server."
                msg += "\naddmult <names>: adds multiple new streams at once, seperated by a space. Streams past the server limit will be ignored."
                msg += "\announce: immediately announces any online streams that were not previously announced."
                msg += "\nremove <name>: removes a streamer from announcements."
                msg += "\nremovemult <names>: removes multiple new streams at once, seperated by a space."
                msg += "\ndetail <name>: Provides details on the given stream, including multi-stream participants, if applicable. Please note that certain options that affect announcements, like stop and noadult, are ignored. However, adult streams WILL NOT show a preview unless showadult is set."
                msg += "\nlist: Lists the current announcement channel and all watched streams. Certain options/issues are also included when relevant."
                msg += "\nSome commands/responses will not work unless an announcement channel is set."
                msg += "\nPlease note that all commands, options and stream names are case sensitive!"
                if not self.lastupdate : #Note if the API update failed
                    msg += "\n**The last attempt to update the API failed!** The API may be down. This will cause certain commands to not work properly. Announcements will resume normally once the API is connectable."
                await message.channel.send(msg)
            return
