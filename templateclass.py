#context to monitor an API for streams/uploads/etc.

#Note this module is INTENTIONALLY broken. Save it as your version then fix the
#syntax errors by inputting the proper values/commands/etc. Every single item in
#the class except __init__ NEEDS changes to work properly.

import aiohttp #Use this for any API requests - nonblocking. DO NOT use request!
import json #Interpreting json results - updateparsed most likely needs this.
import discord #The discord API module. Most useful for making Embeds
import asyncio #Use this for sleep, not time.sleep.
import time #Attaches to thumbnail URL to avoid discord's overly long caching
import datetime #Stream durations, time online, etc.

parsed = {} #Dict with key == 'user_name', filled by basecontext.updateparsed
lastupdate = [] #Did the last update succeed?

import basecontext
class TemplateContext(basecontext.APIContext) :
    defaultname = "template" #This is used to name this context and is the command
    streamurl = #URL for going to watch the stream, gets called as self.streamurl.format(await self.getrecname(rec))
    apiurl = #URL to call to update the list of online streams, used by updateparsed
    channelurl = #URL to call to get detailed information about a specific channel, used by agetchannel

    def __init__(self,instname=None) :
        #Init our base class
        basecontext.APIContext.__init__(self,instname)
        #Our parsed is going to be the global parsed in our module, instead of the
        #basecontext parsed. This gets shared with ALL instances of this class.
        #Primarily this will sharing API response data with all instances.
        self.parsed = parsed #Removing any of this isn't recommended.
        self.lastupdate = lastupdate #Tracks if last API update was successful.
        #Adding stuff below here is fine, obviously.

    #Called to update the API data by basecontext's updatetask. When it's finished
    #parsed should have the current list of online channels.
    async def updateparsed(self) :
        #basecontexts version can handle most cases, now that it's been generalized
        #If you don't need any special handling of the call or output, can be deleted

    #Gets the detailed information about a stream. Used for makedetailmsg.
    #It returns a stream record.
    async def agetstream(self,channelname) :
        #basecontexts version can handle most cases now that it's been generalized
        #If you don't need any special handling of the call or output, can be deleted
        #To see an example of overriding, look at piczel class, which needs to
        #modify the return a bit before passing it along.

    async def getrecname(self,rec) :
        #Should return the name of the record used to uniquely id the stream.
        #Generally, rec['name'] or possibly rec['id']. Used to store info about
        #the stream, such as who is watching and track announcement messages.
        return rec[=]

    async def getrectime(self,rec) :
        '''Time that a stream has ran, determined from the API data.'''
        #If the API returns any kind of data about stream length, it should go
        #here. The following works as a default return, as it's only ever used
        #in a max function with the time since the message was made. Some streams
        #use it in the detail embed as well, so you may want it there too.
        #Default return, duration of 0 seconds.
        return datetime.datetime.now(datetime.timezone.utc) - began

    #The embed used by the default message type. Same as the simple embed except
    #that we add on a preview of the stream.
    async def makeembed(self,rec) :
        #You can remove this function and baseclass will just use the simpembed
        #Simple embed is the same, we just need to add a preview image. Save code
        myembed = await self.simpembed(rec)
        myembed.set_image(url=) #Add your image here
        return myembed
    
    #The embed used by the noprev option message. This is general information
    #about the stream - just the most important bits. Users can get a more
    #detailed version using the detail command.
    async def simpembed(self,rec) :
        noprev = discord.Embed(title=)
        return noprev

    async def makedetailmsg(self,rec) :
        #This generates the embed to send when detailed info about a channel is
        #requested. The actual message is handled by basecontext's detailannounce
        myembed = discord.Embed(title=)
        return myembed
        
        
