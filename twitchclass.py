#context to monitor twitch streams.
#This is significantly different from the other contexts, due to Twitch's API
#being quite different. It still fits in base context, but there are additional
#functions needed to identify games, work around limits, and lookup offline
#streams.

import aiohttp #Use this for any API requests - nonblocking. DO NOT use request!
import json #Interpreting json results - updateparsed most likely needs this.
import discord #The discord API module. Most useful for making Embeds
import asyncio #Use this for sleep, not time.sleep.
import urllib.request as request #Send HTTP requests - debug use only NOT IN BOT
import time #Attaches to thumbnail URL to avoid discord's overly long caching

parsed = {} #Dict with key == 'user_name'
lastupdate = [] #Did the last update succeed?

import apitoken
twitchheader = apitoken.twitchheader
if not twitchheader :
    raise Exception("You must provide a valid twitch header with access token for use!")

def connect() :
    global parsed
    newrequest = request.Request('https://api.twitch.tv/helix/streams',headers=twitchheader)
    newconn = request.urlopen(newrequest)
    buff = newconn.read()
    parsed = {item['user_name']:item for item in json.loads(buff)['data']}
    return True

#Gets the detailed information about a channel, non-async. only for testing.
def getchannel(channelname) :
    try :
        newrequest = request.Request('https://api.twitch.tv/helix/streams?user_login=' + channelname,headers=twitchheader)
        newconn = request.urlopen(newrequest)
        buff = newconn.read()
        if not buff :
            return False
        detchan = json.loads(buff)
        return detchan['data'][0]
    except :
        return False

import basecontext
class TwitchContext(basecontext.APIContext) :
    defaultname = "twitch" #This is used to name this context and is the command
    streamurl = "https://twitch.tv/{0}"#Fill this with a string, gets called as self.streamurl.format(await self.getrecname(rec)) generally
    channelurl = "https://api.twitch.tv/helix/streams?user_login={0}"
    apiurl = 'https://api.twitch.tv/helix/streams?user_login='
    
    def __init__(self,instname=None) :
        #Init our base class
        basecontext.APIContext.__init__(self,instname)
        #Our parsed is going to be the global parsed in our module, instead of the
        #basecontext parsed. This gets shared with ALL instances of this class.
        #Primarily this will sharing API response data with all instances.
        self.parsed = parsed #Removing any of this isn't recommended.
        self.lastupdate = lastupdate
        #Adding stuff below here is fine, obviously.

    #Simple generator to split list into groups no larger than 100. This is the
    #highest you can request at once from the twitch API.
    def splitgroup(self,grouplist) :
        count = 0
        while count < len(grouplist) :
            yield [x for x in grouplist][count:count+100]
            count += 100

    #Called to update the API data by basecontext's updatetask. When it's finished
    #parsed should have the current list of online channels.
    async def updateparsed(self) :
        #Twitch is different since you can't get all online streams - there's far
        #too many. Instead we only grab watched channels in groups.
        found = {}
        updated = False
        self.lastupdate.clear() #Update has not succeded.
        try :
            #We split the streams we need to check into chunks, due to the API
            #limit of 100 streams per call.
            for checkgroup in self.splitgroup(self.mydata['AnnounceDict']) :
                loaded = await self.acallapi(self.apiurl + "&user_login=".join(checkgroup),headers=twitchheader)
                #print(loaded)
                if loaded : #We got a response back
                    found.update({item['user_name']:item for item in loaded['data']})
                else :
                    raise ValueError()
            updated = True #We finished our loop so updates are complete.
        except ValueError as e : #Not success, or empty buffer.
            #Updated should be False anyway, but jic
            updated = False #Errors mean bad things happened, so skip this update
        if updated :
            self.parsed = found
            self.lastupdate.append(updated) #Not empty means list is True, update succeeded
        return updated

    #Gets the detailed information about a channel. Used for makedetailmsg.
    #It returns a channel record.
    async def agetchanneloffline(self,channelname) :
        detchan = await self.acallapi('https://api.twitch.tv/helix/users?login=' + channelname,headers=twitchheader)
        if not detchan :
            return False
        if detchan['data'] :
            return detchan['data'][0]
        return False

    #Gets the detailed information about a running stream
    async def agetchannel(self,channelname,headers=None) :
        #Call the API with our channel url, using the twitch header
        detchan = await self.acallapi(self.channelurl.format(channelname),headers=twitchheader)
        if not detchan :
            return False
        #If we have a record in 'data' then the stream is online
        if detchan['data'] :
            return detchan['data'][0]
        else : #Stream isn't online so grab the offline data.
            return await self.agetchanneloffline(channelname)

    #Gets the name of the game with gameid. Uses a caching system to prevent
    #unneeded lookups.
    async def getgame(self,gameid) :
        #Do we have that gameid cached?
        if gameid in self.mydata['Games'] :
            return self.mydata['Games'][gameid]
        if gameid == 0 : #Streamer might not have set one at all. Hardcoded.
            return "No game set"
        try :
            buff = await self.acallapi('https://api.twitch.tv/helix/games?id=' + gameid,headers=twitchheader)
            detchan = buff['data'][0]
            self.mydata['Games'][gameid] = detchan['name']
            return detchan['name']
        except Exception as e:
            print("Error in game name:",repr(e))
            return "Error getting game name: " + str(gameid)
        #Find the name of the game using the twitch API here
        return "No name found: " + str(gameid)

    async def getrecname(self,rec) :
        #Should return the name of the record used to uniquely id the stream.
        #Generally, rec['name'] or possibly rec['id']. Used to store info about
        #the stream, such as who is watching and track announcement messages.
        if 'user_name' in rec : #Stream type record
            return rec['user_name']
        else : #User type record
            return rec['display_name']

    async def getrectime(self,rec) :
        '''Time that a stream has ran, determined from the API data.'''
        try :
            #Time the stream began - given in UTC
            began = datetime.datetime.strptime(rec['started_at'],"%Y-%m-%dT%H:%M:%SZ")
        except KeyError : #May not have 'started_at' key, if offline?
            return datetime.timedelta()
        return datetime.datetime.utcnow() - began

    #The embed used by the default message type. Same as the simple embed except
    #that was add on a preview of the stream.
    async def makeembed(self,rec,snowflake=None,offline=False) :
        #You can remove this function and baseclass will just use the simpembed
        #Simple embed is the same, we just need to add a preview image. Save code
        myembed = await self.simpembed(rec,snowflake,offline)
        myembed.set_image(url=rec['thumbnail_url'].replace("{width}","848").replace("{height}","480") + "?msgtime=" + str(int(time.time()))) #Add your image here
        return myembed
    
    #The embed used by the noprev option message. This is general information
    #about the stream - just the most important bits. Users can get a more
    #detailed version using the detail command.
    async def simpembed(self,rec,snowflake=None,offline=False) :
        description = rec['title']
        if not snowflake :
            embtitle = rec['user_name'] + " has come online!"
        else :
            embtitle = await self.streammsg(snowflake,rec,offline)
        noprev = discord.Embed(title=embtitle,url="https://twitch.tv/" + rec['user_name'],description=description)
        noprev.add_field(name="Game: " + await self.getgame(rec['game_id']),value="Viewers: " + str(rec['viewer_count']),inline=True)
        return noprev

    async def makedetailembed(self,rec,snowflake=None,offline=False) :
        #This generates the embed to send when detailed info about a channel is
        #requested. The actual message is handled by basecontext's detailannounce
        myembed = None
        #This is more complicated since there is a different record type needed
        #if the stream is offline, than if it is online.
        if 'user_id' in rec : #user_id field is only on streams, not users
            description = rec['title']
            myembed = discord.Embed(title=rec['user_name'] + " is online!",url="https://twitch.tv/" + rec['user_name'],description=description)
            myembed.add_field(name="Game: " + await self.getgame(rec['game_id']),value="Viewers: " + str(rec['viewer_count']),inline=True)
            myembed.set_image(url=rec['thumbnail_url'].replace("{width}","848").replace("{height}","480") + "?msgtime=" + str(int(time.time())))
            msg = rec['user_name'] + " has come online! Watch them at <" + "https://twitch.tv/" + rec['user_name'] + ">"
        else : #We have a user record, due to an offline stream.
            description = rec['description'][:150]
            myembed = discord.Embed(title=rec['display_name'] + " is not currently streaming.",description=description)
            myembed.add_field(name="Viewers:",value=rec['view_count'])
            myembed.set_thumbnail(url=rec['profile_image_url'])
        return myembed
