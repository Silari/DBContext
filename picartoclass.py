#context to monitor picarto streams

import aiohttp #Use this for any API requests - nonblocking. DO NOT use request!
import json #Interpreting json results - updateparsed most likely needs this.
import discord #The discord API module. Most useful for making Embeds
import asyncio #Use this for sleep, not time.sleep.
import datetime #Interpret date+time results for lastonline
import urllib.request as request #Send HTTP requests - debug use only NOT IN BOT
import time #Attaches to thumbnail URL to avoid discord's overly long caching

parsed = {} #Dict with key == 'name'
lastupdate = [] #Did the last update succeed?

#Old non-async method. Kept for debugging.
def connect() :
    global parsed
    newrequest = request.Request("https://api.picarto.tv/v1/online?adult=true&gaming=true")
    newconn = request.urlopen(newrequest)
    buff = newconn.read()
    parsed = {item['name']:item for item in json.loads(buff)}
    return True

#Gets the detailed information about a channel. Non-async, debugging.
def getchannel(channelname) :
    try :
        newrequest = request.Request("https://api.picarto.tv/v1/channel/name/" + channelname)
        newconn = request.urlopen(newrequest)
        buff = newconn.read()
        parsed = json.loads(buff)
        return parsed
    except :
        return False

import basecontext
class PicartoContext(basecontext.APIContext) :
    defaultname = "picarto" #This is used to name this context and is the command to call it. Must be unique.
    streamurl = "https://picarto.tv/{0}" #URL for going to watch the stream
    apiurl = "https://api.picarto.tv/v1/online?adult=true&gaming=true" #URL to call to find online streams
    channelurl = "https://api.picarto.tv/v1/channel/name/{0}" #URL to call to get information on a single channel

    def __init__(self,instname=None) :
        #Init our base class
        basecontext.APIContext.__init__(self,instname)
        #Our parsed is going to be the global parsed in our module, instead of the
        #basecontext parsed. This gets shared with ALL instances of this class.
        #Primarily this will allow sharing API response data with all instances.
        self.parsed = parsed #Removing any of this isn't recommended.
        self.lastupdate = lastupdate #Tracks if last API update was successful.
        #Adding stuff below here is fine, obviously.

    async def getrecname(self,rec) :
        #Should return the name of the record used to uniquely id the stream.
        #Generally, rec['name'] or possibly rec['id']. Used to store info about
        #the stream, such as who is watching and track announcement messages.
        return rec['name']

    async def isadult(self,rec) :
        '''Whether the API sets the stream as Adult. '''
        return rec['adult']

    async def getrectime(self,rec) :
        '''Time that a stream has ran, determined from the API data.'''
        try :
            #Time the stream began
            print("getrectime",rec)
            began = datetime.datetime.strptime(''.join(rec['last_live'].rsplit(':', 1)), '%Y-%m-%dT%H:%M:%S%z')
        except KeyError : #May not have last_live, ONLY detailed records have that.
            return datetime.timedelta()
        return datetime.datetime.now(datetime.timezone.utc) - began

    async def makeembed(self,rec,snowflake=None,offline=False) :
        #Simple embed is the same, we just need to add a preview image.
        myembed = await self.simpembed(rec,snowflake,offline)
        myembed.set_image(url=rec['thumbnails']['web'] + "?msgtime=" + str(int(time.time())))
        return myembed

    async def simpembed(self,rec,snowflake=None,offline=False) :
        description = rec['title']
        value = "Multistream: No"
        if rec['multistream'] :
            value = "Multistream: Yes"
        if not snowflake :
            embtitle = rec['name'] + " has come online!"
        else :
            embtitle = await self.streammsg(snowflake,rec,offline)
        noprev = discord.Embed(title=embtitle,url=self.streamurl.format(rec['name']),description=description)
        noprev.add_field(name="Adult: " + ("Yes" if rec['adult'] else "No"),value="Viewers: " + str(rec['viewers']),inline=True)
        noprev.add_field(name=value,value="Gaming: " + ("Yes" if rec['gaming'] else "No"),inline=True)
        noprev.set_thumbnail(url="https://picarto.tv/user_data/usrimg/" + rec['name'].lower() + "/dsdefault.jpg")
        return noprev

    async def makedetailembed(self,rec,snowflake=None,offline=False) :
        description = rec['title']
        multstring = ""
        if rec["multistream"] :
            online = list((x for x in rec["multistream"] if x["online"] == True))
            online = list((x for x in online if x["name"] != rec["name"]))
            if online :
                multstring += " and streaming with " + online[0]["name"]
                if len(online) == 2 :
                    multstring += " and " + online[1]["name"]
                elif len(online) == 3 :
                    multstring += ", " + online[1]["name"] + ", and " + online[2]["name"]
        #print(multstring," : ", str(rec['multistream']))
        myembed = discord.Embed(title=rec['name'] + "'s stream is " + ("" if rec['online'] else "not ") + "online" + multstring,url="https://picarto.tv/" + rec['name'],description=description)
        myembed.add_field(name="Adult: " + ("Yes" if rec['adult'] else "No"),value="Viewers: " + str(rec['viewers']),inline=True)
        if rec['online'] :
            lastonline = "Streaming for " + await self.streamtime(await self.getrectime(rec))
        else :
            #Doesn't work pre 3.7, removed.
            #lastonline = datetime.datetime.fromisoformat(rec['last_live']).strftime("%m/%d/%Y")
            lastonline = "Last online: " + datetime.datetime.strptime(''.join(rec['last_live'].rsplit(':', 1)), '%Y-%m-%dT%H:%M:%S%z').strftime("%m/%d/%Y")
        myembed.add_field(name=lastonline,value="Gaming: " + ("Yes" if rec['gaming'] else "No"),inline=True)
        myembed.set_image(url=rec['thumbnails']['web'] + "?msgtime=" + str(int(time.time())))
        myembed.set_thumbnail(url="https://picarto.tv/user_data/usrimg/" + rec['name'].lower() + "/dsdefault.jpg")
        return myembed
