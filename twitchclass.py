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

parsed = {} #Dict with key == 'user_name'

import apitoken
twitchheader = apitoken.twitchheader
if not twitchheader :
    raise Exception("You must provide a valid twitch header with access token for use!")

import basecontext
class TwitchContext(basecontext.APIContext) :
    defaultname = "twitch" #This is used to name this context and is the command
    streamurl = "https://twitch.tv/{0}"#Fill this with a string, gets called as self.streamurl.format(await self.getrecname(rec)) generally

    def __init__(self,instname=None) :
        #Init our base class
        basecontext.APIContext.__init__(self,instname)
        #Our parsed is going to be the global parsed in our module, instead of the
        #basecontext parsed. This gets shared with ALL instances of this class.
        #Primarily this will sharing API response data with all instances.
        self.parsed = parsed #Removing any of this isn't recommended.
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
    async def updateparsed2(self) :
        #Twitch is different since you can't get all online streams - there's far
        #too many. Instead we only grab watched channels in groups.
        apiurl = 'https://api.twitch.tv/helix/streams?user_login='
        found = {}
        try :
            for checkgroup in self.splitgroup(self.mydata['AnnounceDict']) :
                #print("Group:",checkgroup)
                newrequest = request.Request(apiurl + "&user_login=".join(checkgroup),headers=twitchheader)
                newconn = request.urlopen(newrequest)
                buff = newconn.read()
                #print("Buff:",buff)
                loaded = json.loads(buff)
                found.update({item['user_name']:item for item in loaded['data']})
        except Exception as e :
            print("Error in twitch uparsed:",repr(e))
        self.parsed = found
        return True

    #Called to update the API data by basecontext's updatetask. When it's finished
    #parsed should have the current list of online channels.
    async def updateparsed(self) :
        #Twitch is different since you can't get all online streams - there's far
        #too many. Instead we only grab watched channels in groups.
        apiurl = 'https://api.twitch.tv/helix/streams?user_login='
        found = {}
        updated = False
        try :
            for checkgroup in self.splitgroup(self.mydata['AnnounceDict']) :
                #print("Group:",checkgroup)
                async with aiohttp.request('GET',apiurl + "&user_login=".join(checkgroup),headers=twitchheader) as resp :
                    buff = await resp.text()
                    #print("Twitch Buff:",buff)
                    loaded = json.loads(buff)
                    found.update({item['user_name']:item for item in loaded['data']})
            updated = True #We finished our loop so updates are complete.
        except asyncio.CancelledError : #We're being closed, so exit out.
            raise
        except aiohttp.ClientConnectionError :
            pass #Low level connection problems per aiohttp docs. Ignore for now.
        except aiohttp.ClientConnectorError :
            pass #Also a connection problem. Ignore for now.
        except Exception as e :
            #Updated should be False anyway, but jic
            updated = False #Errors mean bad things happened, so skip this update
            print("Error in twitch uparsed2:",repr(e))
        if updated :
            self.parsed = found
        return updated

    #Gets the detailed information about a channel. Used for makedetailmsg.
    #It returns a channel record.
    async def agetchanneloffline(self,channelname) :
        try :
            async with aiohttp.request('GET','https://api.twitch.tv/helix/users?login=' + channelname,headers=twitchheader) as resp :
                buff = await resp.text()
                if not buff :
                    return False
                detchan = json.loads(buff)
                resp.close()
            return detchan['data'][0]
        except asyncio.CancelledError :
            raise
        except :
            return False

    #Gets the detailed information about a running stream
    async def agetchannel(self,channelname) :
        try :
            async with aiohttp.request('GET','https://api.twitch.tv/helix/streams?user_login=' + channelname,headers=twitchheader) as resp :
                buff = await resp.text()
                if not buff :
                    return False
                detchan = json.loads(buff)
                resp.close()
            #Stream isn't online so grab the offline data.
            if detchan['data'] :
                return detchan['data'][0]
            else :
                return await self.agetchanneloffline(channelname)
        except :
            return False

    #Gets the name of the game with gameid. Uses a caching system to prevent
    #unneeded lookups.
    async def getgame(self,gameid) :
        #For now, we just dont' know
        if gameid in self.mydata['Games'] :
            return self.mydata['Games'][gameid]
        try :
            async with aiohttp.request('GET','https://api.twitch.tv/helix/games?id=' + gameid,headers=twitchheader) as resp :
                buff = await resp.text()
                if not buff :
                    return False
                detchan = json.loads(buff)['data'][0]
                resp.close()
            self.mydata['Games'][gameid] = detchan['name']
            return detchan['name']
        except Exception as e:
            print(repr(e))
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

    #The embed used by the default message type. Same as the simple embed except
    #that was add on a preview of the stream.
    async def makeembed(self,rec) :
        #You can remove this function and baseclass will just use the simpembed
        #Simple embed is the same, we just need to add a preview image. Save code
        myembed = await self.simpembed(rec)
        myembed.set_image(url=rec['thumbnail_url'].replace("{width}","848").replace("{height}","480")) #Add your image here
        return myembed
    
    #The embed used by the noprev option message. This is general information
    #about the stream - just the most important bits. Users can get a more
    #detailed version using the detail command.
    async def simpembed(self,rec) :
        description = rec['title']
        noprev = discord.Embed(title=rec['user_name'] + " has come online!",url="https://twitch.tv/" + rec['user_name'],description=description)
        noprev.add_field(name="Game: " + await self.getgame(rec['game_id']),value="Viewers: " + str(rec['viewer_count']),inline=True)
        return noprev

    async def makedetailembed(self,rec) :
        #This generates the embed to send when detailed info about a channel is
        #requested. The actual message is handled by basecontext's detailannounce
        myembed = None
        if 'user_id' in rec : #user_id field is only on streams, not users
            description = rec['title']
            myembed = discord.Embed(title=rec['user_name'] + " is online!",url="https://twitch.tv/" + rec['user_name'],description=description)
            myembed.add_field(name="Game: " + await self.getgame(rec['game_id']),value="Viewers: " + str(rec['viewer_count']),inline=True)
            myembed.set_image(url=rec['thumbnail_url'].replace("{width}","848").replace("{height}","480"))
            msg = rec['user_name'] + " has come online! Watch them at <" + "https://twitch.tv/" + rec['user_name'] + ">"
        else : #We have a user record, due to an offline stream.
            description = rec['description'][:150]
            myembed = discord.Embed(title=rec['display_name'] + " is not currently streaming.",description=description)
            myembed.add_field(name="Viewers:",value=rec['view_count'])
            myembed.set_thumbnail(url=rec['profile_image_url'])
        return myembed
        
        
