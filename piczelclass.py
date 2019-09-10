#context to monitor piczel streams.

import aiohttp #Use this for any API requests - nonblocking. DO NOT use request!
import json #Interpreting json results - updateparsed most likely needs this.
import discord #The discord API module. Most useful for making Embeds
import asyncio #Use this for sleep, not time.sleep.
import urllib.request as request #Send HTTP requests - debug use only NOT IN BOT

parsed = {} #Dict with key == 'username'
lastupdate = [] #Did the last update succeed?

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
    defaultname = "piczel" #This is used to name this context and is the command to call it. Must be unique.
    streamurl = "http://piczel.tv/watch/{0}" #URL for going to watch the stream, gets called as self.streamurl.format(await self.getrecname(rec)) generally
    channelurl = apiurl + "{0}" #URL to call to get information on a single channel
    apiurl = apiurl + "?&sfw=false&live_only=false&followedStreams=false" #URL to call to find online streams

    def __init__(self,instname=None) :
        #Init our base class
        basecontext.APIContext.__init__(self,instname)
        #Our parsed is going to be the global parsed in our module, instead of the
        #basecontext parsed. This gets shared with ALL instances of this class.
        #Primarily this will sharing API response data with all instances.
        self.parsed = parsed #Removing any of this isn't recommended.
        self.lastupdate = lastupdate #Tracks if last API update was successful.
        #Adding stuff below here is fine.

    #Gets the detailed information about a channel. Used for makedetailmsg.
    #It returns a channel record. Needs a bit of modification from the default.
    async def agetchannel(self,channelname,headers=None) :
        rec = False
        #We can still use the baseclass version to handle the API call
        detchan = await basecontext.APIContext.agetchannel(self,channelname,headers)
        try : #Now we need to get the actual channel record from the return
            if detchan : #detchan may be False if API call errors
                rec = detchan['data'][0] #data is an array of channels - first one is our target channel
                #If user is in a multistream detchan may have multiple records - save them
                if rec["in_multi"] :
                    #The other records in data are members of a multistream with our target channel
                    #This is useful info for the detailed embed.
                    rec["DBMulti"] = detchan['data']
        except Exception: #Any errors, we can't return the record.
            rec = False
        return rec

    async def getrecname(self,rec) :
        #Should return the name of the record used to uniquely id the stream.
        #Generally, rec['name'] or possibly rec['id']. Used to store info about
        #the stream, such as who is watching and track announcement messages.
        return rec['username']

    #The embed used by the default message type. Same as the simple embed except
    #that was add on a preview of the stream.
    async def makeembed(self,rec,snowflake=None,offline=False) :
        #Simple embed is the same, we just need to add a preview image. Save code
        myembed = await self.simpembed(rec,snowflake,offline)
        thumburl = 'https://piczel.tv/static/thumbnail/stream_' + str(rec['id']) + '.jpg'
        myembed.set_image(url=thumburl) #Add your image here
        return myembed
    
    #The embed used by the noprev option message. This is general information
    #about the stream - just the most important bits. Users can get a more
    #detailed version using the detail command.
    async def simpembed(self,rec,snowflake=None,offline=False) :
        description = rec['title']
        value = "Multistream: No"
        if rec['in_multi'] :
            value = "\nMultistream: Yes"
        if not snowflake :
            embtitle = rec['username'] + " has come online!"
        else :
            embtitle = await self.streammsg(snowflake,offline)
        noprev = discord.Embed(title=embtitle,url=piczelurl + rec['username'],description=description)
        noprev.add_field(name="Adult: " + ("Yes" if rec['adult'] else "No"),value="Viewers: " + str(rec['viewers']),inline=True)
        noprev.add_field(name=value,value="Private: " + ("Yes" if rec['isPrivate?'] else "No"),inline=True)
        noprev.set_thumbnail(url=rec['user']['avatar']['avatar']['url'])
        return noprev

    async def makedetailembed(self,rec,snowflake=None,offline=False) :
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
