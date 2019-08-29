#context to monitor picarto streams

import aiohttp #Use this for any API requests - nonblocking. DO NOT use request!
import json #Interpreting json results - updateparsed most likely needs this.
import discord #The discord API module. Most useful for making Embeds
import asyncio #Use this for sleep, not time.sleep.
import datetime #Interpret date+time results for lastonline
import urllib.request as request #Send HTTP requests - debug use only NOT IN BOT

parsed = {} #Dict with key == 'user_name'

#Keep a dict of channels to search for, list of servers that want that info
#AnnounceDict
#   |-"JazzyZ401"
#       |JazzySpeaksThingy
#   |-"Krypt"
#       |-Glittershell
#       |-PonyPervingParty

#Keep a dict of servers, that holds the dict of options
#Servers
#   |-"JazzySpeaksThingy"
#       |"AnnounceChannel": "#announcements"
#       |"Listens": set()
#       |"Users": set()
#   |-"Glittershell"
#       |"AnnounceChannel": "#livestream"
#       |"Listens": set()
#       |"Users": set()
#       |"Here": true

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
    defaultname = "picarto"
    streamurl = "https://picarto.tv/{0}"

    def __init__(self,instname=None) :
        #Init our base class
        basecontext.APIContext.__init__(self,instname)
        #Our parsed is going to be the global picartoclass parsed, instead of the
        #basecontext parsed. This gets shared with ALL instances of this class.
        self.parsed = parsed

    #Called to update the API data by basecontext's updatetask. When it's finished
    #parsed should have the current list of online channels.
    async def updateparsed(self) :
        updated = False
        async with aiohttp.request('GET',"https://api.picarto.tv/v1/online?adult=true&gaming=true") as resp :
            try :
                buff = await resp.text()
                #resp.close()
                if buff :
                    self.parsed = {item['name']:item for item in json.loads(buff)}
                    updated = True
            except aiohttp.ClientConnectionError :
                pass #Low level connection problems per aiohttp docs. Ignore for now.
            except aiohttp.ClientConnectorError :
                pass #Also a connection problem. Ignore for now.
            except json.JSONDecodeError :
                pass #Error in reading JSON - bad response from server. Ignore for now.
        return updated

    #Gets the detailed information about a channel. Used for makedetailmsg.
    #It returns a channel record.
    async def agetchannel(self,channelname) :
        rec = False
        async with aiohttp.request('GET',"https://api.picarto.tv/v1/channel/name/" + channelname) as resp :
            try :
                buff = await resp.text()
                #resp.close()
                if buff :
                    rec = json.loads(buff)
            except :
                rec = False
        return rec

    async def getrecname(self,rec) :
        return rec['name']

    async def makeembed(self,rec) :
        #Simple embed is the same, we just need to add a preview image. Save code
        myembed = await self.simpembed(rec)
        myembed.set_image(url=rec['thumbnails']['web'])
        return myembed

    async def simpembed(self,rec) :
        description = rec['title']
        value = "Multistream: No"
        if rec['multistream'] :
            value = "Multistream: Yes"
        noprev = discord.Embed(title=rec['name'] + " has come online!",url=self.streamurl.format(rec['name']),description=description)
        noprev.add_field(name="Adult: " + ("Yes" if rec['adult'] else "No"),value="Viewers: " + str(rec['viewers']),inline=True)
        noprev.add_field(name=value,value="Gaming: " + ("Yes" if rec['gaming'] else "No"),inline=True)
        noprev.set_thumbnail(url="https://picarto.tv/user_data/usrimg/" + rec['name'].lower() + "/dsdefault.jpg")
        return noprev

    async def makedetailembed(self,rec) :
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
        #Doesn't work pre 3.7, removed.
        #lastonline = datetime.datetime.fromisoformat(rec['last_live']).strftime("%m/%d/%Y")
        lastonline = datetime.datetime.strptime(''.join(rec['last_live'].rsplit(':', 1)), '%Y-%m-%dT%H:%M:%S%z').strftime("%m/%d/%Y")
        myembed.add_field(name="Last online: " + lastonline,value="Gaming: " + ("Yes" if rec['gaming'] else "No"),inline=True)
        myembed.set_image(url=rec['thumbnails']['web'])
        myembed.set_thumbnail(url="https://picarto.tv/user_data/usrimg/" + rec['name'].lower() + "/dsdefault.jpg")
        return myembed
