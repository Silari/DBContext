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
import datetime #Stream durations, time online, etc.
import basecontext #Base class for our API based context

parsed = {} #Dict with key == 'user_name'
lastupdate = basecontext.Updated() #Class that tracks if update succeeded - empty if not successful

import apitoken
twitchheader = apitoken.twitchheader
if (not twitchheader) or (not apitoken.clientid) or (not apitoken.clientsecret) :
    raise Exception("You must provide a valid twitch header with access token, client ID, and client secret for use!")

def connect() :
    global parsed
    newrequest = request.Request('https://api.twitch.tv/helix/streams',headers=twitchheader)
    newconn = request.urlopen(newrequest)
    buff = newconn.read()
    parsed = {item['user_name']:item for item in json.loads(buff)['data']}
    return True

#Gets the detailed information about a stream, non-async. only for testing.
def getstream(streamname) :
    try :
        newrequest = request.Request('https://api.twitch.tv/helix/streams?user_login=' + streamname,headers=twitchheader)
        newconn = request.urlopen(newrequest)
        buff = newconn.read()
        if not buff :
            return False
        detchan = json.loads(buff)
        return detchan['data'][0]
    except :
        return False

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
    #parsed should have the current list of online streams.
    async def updateparsed(self) :
        #Twitch is different since you can't get all online streams - there's far
        #too many. Instead we only grab watched streams in groups.
        found = {} #Used to hold the records from API call
        updated = False #Tracks if this attempt succeeded.
        #If one or more calls succeded, we could have a partial update. To avoid
        #that, we gather the data into found first, then if we finish without
        #any errors, we copy that data over self.parsed. If an error occurs at
        #any point, we leave the loop and discard any data we gathered
        try :
            #We split the streams we need to check into chunks, due to the API
            #limit of 100 streams per call.
            for checkgroup in self.splitgroup(self.mydata['AnnounceDict']) :
                loaded = await self.acallapi(self.apiurl + "&user_login=".join(checkgroup))
                #print(loaded)
                if loaded : #We got a response back
                    found.update({item['user_name']:item for item in loaded['data']})
                else :
                    #We didn't get any data back, thus the update failed.
                    #IMPORTANT NOTE: even if no one was online, we'd still have
                    #gotten back data - loaded['data'] would exist, just with 0
                    #items in it.
                    raise ValueError()
            updated = True #We finished our loop so updates are complete.
        except ValueError as e : #Not success, or empty buffer.
            updated = False #Errors mean bad things happened, so skip this update
        if updated : #Only replace parsed data if we succeeded
            self.parsed = found
        #Update the tracking variable
        self.lastupdate.record(updated) 
        return updated

    async def makeheader(self) :
        '''Makes the needed headers for twitch API calls, which includes dealing
        with the OAuth jank they now require.'''
        if not 'OAuth' in self.mydata : #We haven't gotten our OAuth token yet
            #request version, need to rewrite to use 
            #request.Request(url='https://id.twitch.tv/oauth2/token?client_id=' + apitoken.clientid + '&client_secret=' + apitoken.clientsecret + "&grant_type=client_credentials",method='POST')
            #URL to call to request our OAuth token
            url = 'https://id.twitch.tv/oauth2/token?client_id=' + apitoken.clientid + '&client_secret=' + apitoken.clientsecret + "&grant_type=client_credentials"
            try :
                async with self.conn.post(url) as resp :
                    if resp.status == 200 : #Success
                        buff = await resp.text()
                        #print("makeheader",buff)
                        if buff :
                            result = json.loads(buff)
                            self.mydata['OAuth'] = result['access_token']
            except Exception as e :
                #Log this for now while debugging
                print("makeheader",repr(e))
        if not self.mydata['OAuth'] : #It still didn't work out
            print("Didn't get an access token!")
            return False #Return False so we don't attempt any calls.
        else :
            #Return the headers we need for Twitch to work
            return {"Client-ID": apitoken.clientid,
                    "Authorization": "Bearer " + self.mydata['OAuth']}
        return False #Shouldn't get here, but something screwed up for sure
    
    #Gets the detailed information about a stream. Used for makedetailmsg.
    #It returns a stream record.
    async def agetstreamoffline(self,streamname) :
        detchan = await self.acallapi('https://api.twitch.tv/helix/users?login=' + streamname)
        if not detchan :
            return False
        if detchan['data'] :
            return detchan['data'][0]
        return False

    #Gets the detailed information about a stream
    async def agetstream(self,streamname) :
        #Call the API with our channelurl, using the twitch header
        detchan = await self.acallapi(self.channelurl.format(streamname))
        if not detchan :
            return False
        #If we have a record in 'data' then the stream is online
        if detchan['data'] :
            return detchan['data'][0]
        else : #Stream isn't online so grab the offline data.
            return await self.agetstreamoffline(streamname)

    async def acallapi(self,url,headers=None) :
        '''Overrides acallapi to ensure we send in the needed twitch headers.'''
        #If the base call fails due to 401, it'll unset our OAuth token so we
        #would then remake it on the next call of this.
        if not headers : #We weren't provided with headers
            #We need to make them
            headers = await self.makeheader()
        return await basecontext.APIContext.acallapi(self,url,headers=headers)

    #Gets the name of the game with gameid. Uses a caching system to prevent
    #unneeded lookups.
    async def getgame(self,gameid) :
        #Do we have that gameid cached?
        if gameid in self.mydata['Games'] :
            return self.mydata['Games'][gameid]
        if gameid == 0 : #Streamer might not have set one at all. Hardcoded.
            return "No game set"
        if gameid == '' : #Streamer might not have set one at all. Hardcoded.
            #This started showing up recently, might have supplanted 0.
            return "No game set"
        try :
            buff = await self.acallapi('https://api.twitch.tv/helix/games?id=' + gameid)
            detchan = buff['data'][0]
            self.mydata['Games'][gameid] = detchan['name']
            return detchan['name']
        except Exception as e:
            #We had an issue, so print the issue, the error, what ID we tried to
            #get, and the entire returned buffer for inspection.
            print("Error in game name:",repr(e), ":", repr(gameid), ":", buff)
            return "Error getting game name: " + str(gameid)
        #Find the name of the game using the twitch API here
        return "No name found: " + str(gameid)

    async def getrecname(self,rec) :
        #Should return the name of the record used to uniquely id the stream.
        #Generally, rec['name'] or possibly rec['id']. Used to store info about
        #the stream, such as who is watching and track announcement messages.
        if 'user_name' in rec : #Stream type record, ie online streams
            return rec['user_name']
        else : #User type record - ie offline record used by detailannounce
            return rec['display_name']

    async def getrectime(self,rec) :
        '''Time that a stream has ran, determined from the API data.'''
        try :
            #Time the stream began - given in UTC
            began = datetime.datetime.strptime(rec['started_at'],"%Y-%m-%dT%H:%M:%SZ")
        except KeyError : #May not have 'started_at' key, if offline?
            #This creates an empty timedelta - 0 seconds long. It'll never be
            #the longest duration, so it's discarded later.
            return datetime.timedelta()
        return datetime.datetime.utcnow() - began

    #The embed used by the default message type. Same as the simple embed except
    #that was add on a preview of the stream.
    async def makeembed(self,rec,snowflake=None,offline=False) :
        #You can remove this function and baseclass will just use the simpembed
        #Simple embed is the same, we just need to add a preview image.
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

    async def makedetailembed(self,rec,showprev=True) :
        #This generates the embed to send when detailed info about a stream is
        #requested. The actual message is handled by basecontext's detailannounce
        myembed = None
        #This is more complicated since there is a different record type needed
        #if the stream is offline, than if it is online.
        if 'user_id' in rec : #user_id field is only on streams, not users
            description = rec['title']
            myembed = discord.Embed(title=rec['user_name'] + " is online for " + await self.streamtime(await self.getrectime(rec)) + "!",url="https://twitch.tv/" + rec['user_name'],description=description)
            myembed.add_field(name="Game: " + await self.getgame(rec['game_id']),value="Viewers: " + str(rec['viewer_count']),inline=True)
            if showprev :
                myembed.set_image(url=rec['thumbnail_url'].replace("{width}","848").replace("{height}","480") + "?msgtime=" + str(int(time.time())))
            msg = rec['user_name'] + " has come online! Watch them at <" + "https://twitch.tv/" + rec['user_name'] + ">"
        else : #We have a user record, due to an offline stream.
            description = rec['description'][:150]
            myembed = discord.Embed(title=rec['display_name'] + " is not currently streaming.",description=description)
            myembed.add_field(name="Viewers:",value=rec['view_count'])
            myembed.set_thumbnail(url=rec['profile_image_url'])
        return myembed
