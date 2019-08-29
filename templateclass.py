#context to monitor an API for streams/uploads/etc.

#Note this module is INTENTIONALLY broken. Save it as your version then fix the
#syntax errors by inputting the proper values/commands/etc. Every single item in
#the class except __init__ NEEDS changes to work properly.

import aiohttp #Use this for any API requests - nonblocking. DO NOT use request!
import json #Interpreting json results - updateparsed most likely needs this.
import discord #The discord API module. Most useful for making Embeds
import asyncio #Use this for sleep, not time.sleep.

parsed = {} #Dict with key == 'user_name'

import basecontext
class TemplateContext(basecontext.APIContext) :
    defaultname = "template" #This is used to name this context and is the command
    streamurl = #Fill this with a string, gets called as self.streamurl.format(await self.getrecname(rec)) generally

    def __init__(self,instname=None) :
        #Init our base class
        basecontext.APIContext.__init__(self,instname)
        #Our parsed is going to be the global parsed in our module, instead of the
        #basecontext parsed. This gets shared with ALL instances of this class.
        #Primarily this will sharing API response data with all instances.
        self.parsed = parsed #Removing any of this isn't recommended.
        #Adding stuff below here is fine, obviously.

    #Called to update the API data by basecontext's updatetask. When it's finished
    #parsed should have the current list of online channels.
    async def updateparsed(self) :

    #Gets the detailed information about a channel. Used for makedetailmsg.
    #It returns a channel record.
    async def agetchannel(self,channelname) :

    async def getrecname(self,rec) :
        #Should return the name of the record used to uniquely id the stream.
        #Generally, rec['name'] or possibly rec['id']. Used to store info about
        #the stream, such as who is watching and track announcement messages.
        return rec[=]

    #The embed used by the default message type. Same as the simple embed except
    #that was add on a preview of the stream.
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
        
        
