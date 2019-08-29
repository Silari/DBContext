#context to monitor piczel streams.

import aiohttp #Use this for any API requests - nonblocking. DO NOT use request!
import json #Interpreting json results - updateparsed most likely needs this.
import discord #The discord API module. Most useful for making Embeds
import asyncio #Use this for sleep, not time.sleep.
import urllib.request as request #Send HTTP requests - debug use only NOT IN BOT

parsed = {} #Dict with key == 'user_name'
apiurl = 'https://piczel.tv/api/streams/'
offurl = 'https://piczel.tv/static'
piczelurl = "http://piczel.tv/watch/"

#Old non-async method. Kept for debugging.
def connect() :
    global parsed
    newrequest = request.Request(apiurl + '?&sfw=false&live_only=false&followedStreams=false')
    newconn = request.urlopen(newrequest)
    buff = newconn.read()
    parsed = {item['username']:item for item in json.loads(buff)}
    return True

#Gets the detailed information about a channel, non-async. only for testing.
def getchannel(channelname) :
    try :
        newrequest = request.Request(apiurl + channelname)
        newconn = request.urlopen(newrequest)
        buff = newconn.read()
        if not buff :
            return False
        detchan = json.loads(buff)
        rec = detchan['data'][0]
        #If user is in a multistream detchan may have multiple records - save them
        if rec["in_multi"] : 
            rec["DBMulti"] = detchan['data']
        return rec
    except :
        return False

import basecontext
class PiczelContext(basecontext.APIContext) :
    defaultname = "piczel" #This is used to name this context and is the command
    streamurl = "http://piczel.tv/watch/{0}"#Fill this with a string, gets called as self.streamurl.format(await self.getrecname(rec)) generally

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
        updated = False
        async with aiohttp.request('GET',apiurl + "?&sfw=false&live_only=false&followedStreams=false") as resp :
            try :
                buff = await resp.text()
                #resp.close()
                if buff :
                    self.parsed = {item['username']:item for item in json.loads(buff)}
                    updated = True
            except aiohttp.ClientConnectionError :
                pass #Low level connection problems per aiohttp docs. Ignore for now.
            except aiohttp.ClientConnectorError :
                pass #Also a connection problem. Ignore for now.
        return updated

    #Gets the detailed information about a channel. Used for makedetailmsg.
    #It returns a channel record.
    async def agetchannel(self,channelname) :
        rec = False
        async with aiohttp.request('GET',apiurl + channelname) as resp :
            try :
                buff = await resp.text()
                #resp.close()
                if buff :
                    detchan = json.loads(buff)
                    rec = detchan['data'][0]
                    #If user is in a multistream detchan may have multiple records - save them
                    if rec["in_multi"] : 
                        rec["DBMulti"] = detchan['data']
            except :
                rec = False
        return rec

    async def getrecname(self,rec) :
        #Should return the name of the record used to uniquely id the stream.
        #Generally, rec['name'] or possibly rec['id']. Used to store info about
        #the stream, such as who is watching and track announcement messages.
        return rec['username']

    #The embed used by the default message type. Same as the simple embed except
    #that was add on a preview of the stream.
    async def makeembed(self,rec) :
        #Simple embed is the same, we just need to add a preview image. Save code
        myembed = await self.simpembed(rec)
        thumburl = 'https://piczel.tv/static/thumbnail/stream_' + str(rec['id']) + '.jpg'
        myembed.set_image(url=thumburl) #Add your image here
        return myembed
    
    #The embed used by the noprev option message. This is general information
    #about the stream - just the most important bits. Users can get a more
    #detailed version using the detail command.
    async def simpembed(self,rec) :
        description = rec['title']
        value = "Multistream: No"
        if rec['in_multi'] :
            value = "\nMultistream: Yes"
        noprev = discord.Embed(title=rec['username'] + " has come online!",url=piczelurl + rec['username'],description=description)
        noprev.add_field(name="Adult: " + ("Yes" if rec['adult'] else "No"),value="Viewers: " + str(rec['viewers']),inline=True)
        noprev.add_field(name=value,value="Private: " + ("Yes" if rec['isPrivate?'] else "No"),inline=True)
        noprev.set_thumbnail(url=rec['user']['avatar']['avatar']['url'])
        return noprev

    async def makedetailembed(self,rec) :
        #This generates the embed to send when detailed info about a channel is
        #requested. The actual message is handled by basecontext's detailannounce
        description = rec['title']
        multstring = ""
        if rec["in_multi"] :
            online = list((x for x in rec['DBMulti'] if x["live"] == True))
            online = list((x for x in online if x["username"] != rec["username"]))
            if online :
                multstring += " and streaming with "
                if len(online) == 1 :
                    multstring += online[0]["username"]
                else :
                    for stream in online[0:-1] :
                        multstring += stream['username'] + ", "
                    multstring += "and " + online[-1:][0]['username']
        #print(multstring," : ", str(rec['multistream']))
        myembed = discord.Embed(title=rec['username'] + "'s stream is " + ("" if rec['live'] else "not ") + "online" + multstring,url="https://piczel.tv/" + rec['username'],description=description)
        myembed.add_field(name="Adult: " + ("Yes" if rec['adult'] else "No"),value="Viewers: " + str(rec['viewers']),inline=True)
        #Doesn't work pre 3.7, removed.
        #lastonline = datetime.datetime.fromisoformat(rec['last_live']).strftime("%m/%d/%Y")
        #lastonline = datetime.datetime.strptime(''.join(rec['last_live'].rsplit(':', 1)), '%Y-%m-%dT%H:%M:%S%z').strftime("%m/%d/%Y")
        #myembed.add_field(name="Last online: " + lastonline,value="Gaming: " + ("Yes" if rec['gaming'] else "No"),inline=True)
        thumburl = 'https://piczel.tv/static/thumbnail/stream_' + str(rec['id']) + '.jpg'
        myembed.set_image(url=thumburl)
        myembed.set_thumbnail(url=rec['user']['avatar']['avatar']['url'])
        return myembed
        
        
