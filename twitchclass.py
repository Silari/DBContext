# context to monitor twitch streams.
# This is significantly different from the other contexts, due to Twitch's API
# being quite different. It still fits in base context, but there are additional
# functions needed to identify games, work around limits, and lookup offline
# streams.

import json  # Interpreting json results - updateparsed most likely needs this.
import discord  # The discord API module. Most useful for making Embeds
# import asyncio  # Use this for sleep, not time.sleep.
import urllib.request as request  # Send HTTP requests - debug use only NOT IN BOT
import time  # Attaches to thumbnail URL to avoid discord's overly long caching
import datetime  # Stream durations, time online, etc.
import basecontext  # Base class for our API based context
import apitoken

parsed = {}  # Dict with key == 'user_name'
lastupdate = basecontext.Updated()  # Class that tracks if update succeeded - empty if not successful

twitchheader = apitoken.twitchheader
if (not twitchheader) or (not apitoken.clientid) or (not apitoken.clientsecret):
    raise Exception("You must provide a valid twitch header with access token, client ID, and client secret for use!")


def connect():
    global parsed
    newrequest = request.Request('https://api.twitch.tv/helix/streams', headers=twitchheader)
    newconn = request.urlopen(newrequest)
    buff = newconn.read()
    parsed = {item['user_name']: item for item in json.loads(buff)['data']}
    return True


# Gets the detailed information about a stream, non-async. only for testing.
def getstream(recordid):
    try:
        newrequest = request.Request('https://api.twitch.tv/helix/streams?user_login=' + recordid,
                                     headers=twitchheader)
        newconn = request.urlopen(newrequest)
        buff = newconn.read()
        if not buff:
            return False
        detchan = json.loads(buff)
        return detchan['data'][0]
    except (KeyError, Exception):
        return False


class TwitchRecord(basecontext.StreamRecord):

    __slots__ = []

    values = []
    # Online keys (Stream record)
    # values2 = ['game_id', 'id', 'language', 'started_at', 'tag_ids', 'thumbnail_url',
    #            'title', 'type', 'user_id', 'user_name', 'viewer_count']
    # Offline keys (User record)
    # values3 = ['broadcaster_type', 'description', 'display_name', 'email', 'id', 'login',
    #            'offline_image_url', 'profile_image_url', 'type', 'view_count']

    # List of values to update when given a new dictionary. Several items are static so don't need to be updated.
    upvalues = []  # viewer_count manually updated

    streamurl = "https://twitch.tv/{0}"  # Gets called as self.streamurl.format(await self.getrecordid(rec)) generally

    def __init__(self, recdict, detailed=True):  # No detailed version of a record here.
        super().__init__(recdict, detailed)
        self.internal['multistream'] = []
        if 'view_count' in recdict:  # Is a user record rather than a stream record.
            self.internal['avatar'] = recdict['profile_image_url']
            self.internal['name'] = recdict['display_name']
            self.internal['online'] = False
            self.internal['viewers_total'] = recdict['view_count']
            self.internal['title'] = recdict['description']
        else:
            self.internal['name'] = recdict['user_name']
            self.internal['online'] = True
            self.internal['preview'] = recdict['thumbnail_url'].replace("{width}", "848").replace("{height}", "480")
            self.internal['time'] = datetime.datetime.strptime(recdict['started_at'], "%Y-%m-%dT%H:%M:%SZ")\
                .replace(tzinfo=datetime.timezone.utc)
            self.internal['title'] = recdict['title']
            self.internal['viewers'] = recdict['viewer_count']
            self.internal['game_id'] = recdict['game_id']  # Specific to Twitch.

    def update(self, newdict):
        # self.internal.update({k: newdict[k] for k in self.upvalues})
        self.internal['viewers'] = newdict['viewer_count']
        self.internal['game_id'] = newdict['game_id']

    @property
    def adult(self):
        """Is the stream marked Adult?

        :rtype: bool
        """
        return False

    @property
    def avatar(self):
        """URL for the avatar of the stream.

        :rtype: str
        """
        try:
            return self.internal['avatar']
        except KeyError:
            return ''

    @property
    def detailed(self):
        """Is the record a detailed record?

        :rtype: bool
        """
        # There are no detailed records, just stream records (only if online) and user records.
        return True

    @property
    def gaming(self):
        """Is the stream set as a gaming stream?

        :rtype: bool
        """
        return True

    @property
    def preview(self):
        """URL for the stream preview. We add a time property to the end to get around caching.

        :rtype: str
        """
        try:
            return self.internal['preview'] + "?msgtime=" + str(int(time.time()))
        except KeyError:
            return ''

    async def getgame(self, gameid):
        """Gets the name associated with the given gameid. Stores results to prevent unneeded lookups.

        :type gameid: str
        :rtype: str
        :param gameid:
          Game id to look up, must be a string representing an integer >= 0
        :return:
          str containing the name of the set game, or an error message.
        """
        # This should get overriden once we get a TwitchContext instance.
        pass

    async def simpembed(self, snowflake=None, offline=False):
        """The embed used by the noprev message type. This is general information about the stream, but not everything.
        Users can get a more detailed version using the detail command, but we want something simple for announcements.

        :type snowflake: int
        :type offline: bool
        :rtype: discord.Embed
        :param snowflake: Integer representing a discord Snowflake
        :param offline: Do we need to adjust the time to account for basecontext.offlinewait?
        :return: a discord.Embed representing the current stream.
        """
        description = self.title
        if not snowflake:
            embtitle = self.name + " has come online!"
        else:
            embtitle = await self.streammsg(snowflake, offset=offline)
        noprev = discord.Embed(title=embtitle, url="https://twitch.tv/" + self.name, description=description)
        noprev.add_field(name="Game: " + await self.getgame(self.internal['game_id']),
                         value="Viewers: " + str(self.viewers), inline=True)
        return noprev

    async def detailembed(self, showprev=True):
        """This generates the embed to send when detailed info about a stream is requested. More information is provided
        than with the other embeds.

        :type showprev: bool
        :rtype: discord.Embed
        :param showprev: Should the embed include the preview image?
        :return: a discord.Embed representing the current stream.
        """
        # This is more complicated since there is a different record type needed
        # if the stream is offline, than if it is online.
        description = self.title[:150]
        if self.online:  # user_id field is only on streams, not users
            myembed = discord.Embed(title=self.name + " is online for " +
                                    await TwitchContext.streamtime(self.time) + "!",
                                    url="https://twitch.tv/" + self.name,
                                    description=description)
            myembed.add_field(name="Game: " + await self.getgame(self.internal['game_id']),
                              value="Viewers: " + str(self.viewers), inline=True)
            if showprev:
                myembed.set_image(url=self.preview)
        else:  # We have a user record, due to an offline stream.
            myembed = discord.Embed(title=self.name + " is not currently streaming.",
                                    description=description)
            myembed.add_field(name="Total Views:", value=self.total_views[1])
            myembed.set_thumbnail(url=self.avatar)
        return myembed


class TwitchContext(basecontext.APIContext):
    defaultname = "twitch"  # This is used to name this context and is the command
    streamurl = "https://twitch.tv/{0}"  # Gets called as self.streamurl.format(await self.getrecordid(rec)) generally
    channelurl = "https://api.twitch.tv/helix/streams?user_login={0}"
    apiurl = 'https://api.twitch.tv/helix/streams?user_login='
    recordclass = TwitchRecord

    def __init__(self, instname=None):
        # Init our base class
        basecontext.APIContext.__init__(self, instname)
        # Our parsed is going to be the global parsed in our module, instead of the
        # basecontext parsed. This gets shared with ALL instances of this class.
        # Primarily this will sharing API response data with all instances.
        self.parsed = parsed  # Removing any of this isn't recommended.
        self.lastupdate = lastupdate
        # Adding stuff below here is fine, obviously.
        self.recordclass.getgame = self.getgame

    # Simple generator to split list into groups no larger than 100. This is the
    # highest you can request at once from the twitch API.
    @staticmethod
    def splitgroup(grouplist):
        """Simple generator to split the list of watched streams into groups of no more than 100. The twitch API allows
        no more than 100 streams per call to the streams endpoint.

        :type grouplist: list
        :rtype: list
        :param grouplist: iterable:
          Iterable of str containing a stream name
        :return:
          List of str
        """
        count = 0
        while count < len(grouplist):
            yield [x for x in grouplist][count:count + 100]
            count += 100

    # Called to update the API data by basecontext's updatetask. When it's finished
    # parsed should have the current list of online streams.
    async def updateparsed(self):
        """Calls the API and updates our parsed variable with the dict of currently online streams.

        :rtype: bool
        :return: True on success, False if any error occurs.
        """
        # TODO Should be done. May need to rewrite the updater to grab the user record for any new streams.
        #  Up to 100 can be in one call, same as streams, and with the update system I won't need to recall it again
        #  for anything. That'd give ALL the info for twitch streams. If I do that I can update simpembed with a bit
        #  more information.
        # Twitch is different since you can't get all online streams - there's far
        # too many. Instead we only grab watched streams in groups.
        found = {}  # Used to hold the records from the API calls.
        newparsed = {}  # dict that is returned after all calls complete.
        # If one or more calls succeded, we could have a partial update. To avoid
        # that, we gather the data into found first, then if we finish without
        # any errors, we copy that data over self.parsed. If an error occurs at
        # any point, we leave the loop and discard any data we gathered
        try:
            # We split the streams we need to check into chunks, due to the API
            # limit of 100 streams per call.
            for checkgroup in self.splitgroup(self.mydata['AnnounceDict']):
                loaded = await self.acallapi(self.apiurl + "&user_login=".join(checkgroup))
                # print(loaded)
                if loaded:  # We got a response back
                    found.update({item['user_name']: item for item in loaded['data']})
                else:
                    # We didn't get any data back, thus the update failed.
                    # IMPORTANT NOTE: even if no one was online, we'd still have
                    # gotten back data - loaded['data'] would exist, just with 0
                    # items in it.
                    raise ValueError()
            updated = True  # We finished our loop so updates are complete.
        except ValueError:  # Not success, or empty buffer.
            updated = False  # Errors mean bad things happened, so skip this update
        if updated:  # Only replace parsed data if we succeeded
            newparsed = found
        # Update the tracking variable
        self.lastupdate.record(updated)
        return updated, newparsed

    async def makeheader(self):
        """Makes the needed headers for twitch API calls, which includes dealing
        with the OAuth jank they now require.

        :rtype: dict
        :return: Returns dict of headers required for calls to Twitch API, suitable for aiohttp or Request.
        """
        if 'OAuth' not in self.mydata:  # We haven't gotten our OAuth token yet
            # URL to call to request our OAuth token
            url = 'https://id.twitch.tv/oauth2/token?client_id=' + apitoken.clientid + '&client_secret=' \
                  + apitoken.clientsecret + "&grant_type=client_credentials"
            try:
                async with self.conn.post(url) as resp:
                    if resp.status == 200:  # Success
                        buff = await resp.text()
                        # print("makeheader",buff)
                        if buff:
                            result = json.loads(buff)
                            self.mydata['OAuth'] = result['access_token']
            except Exception as e:
                # Log this for now while debugging
                print("makeheader", repr(e))
        if not self.mydata['OAuth']:  # It still didn't work out
            print("Didn't get an access token!")
            return False  # Return False so we don't attempt any calls.
        else:
            # Return the headers we need for Twitch to work
            return {"Client-ID": apitoken.clientid,
                    "Authorization": "Bearer " + self.mydata['OAuth']}

    # Gets the detailed information about a stream. Used for makedetailmsg.
    # It returns a stream record.
    async def agetstreamoffline(self, recordid, headers=None):
        """Call our API with the getchannel URL formatted with the channel name

        :type recordid: str
        :type headers: dict
        :rtype: TwitchRecord
        :param recordid: String with the name of the stream, used to format the URL.
        :param headers: Headers to be passed on to the API call.
        :return: A dict with the information for the stream, exact content depends on the API.
        """
        detchan = await self.acallapi('https://api.twitch.tv/helix/users?login=' + recordid, headers)
        if not detchan:
            return False
        if detchan['data']:
            return TwitchRecord(detchan['data'][0])
        return False

    # Gets the detailed information about a stream
    async def agetstream(self, recordid, headers=None):
        """Call our API with the getchannel URL formatted with the channel name

        :type recordid: str
        :type headers: dict
        :rtype: TwitchRecord
        :param recordid: String with the name of the stream, used to format the URL.
        :param headers: Headers to be passed on to the API call.
        :return: A dict with the information for the stream, exact content depends on the API.
        """
        # Call the API with our channelurl, using the twitch header
        detchan = await self.acallapi(self.channelurl.format(recordid))
        if not detchan:  # This is an API error, so we fail.
            return False
        # If we have a record in 'data' then the stream is online
        if detchan['data']:
            return TwitchRecord(detchan['data'][0])
        else:  # Stream isn't online so grab the offline data.
            return await self.agetstreamoffline(recordid)

    async def acallapi(self, url, headers=None):
        """Overrides acallapi to ensure we send in the needed twitch headers.

        :type url: str
        :type headers: dict
        :rtype: dict | bool | int
        :param url: URL to call
        :param headers: Headers to send with the request
        :return: The interpreted JSON result of the call, or 0 or False.
        """
        # If the base call fails due to 401, it'll unset our OAuth token so we
        # would then remake it on the next call of this.
        if not headers:  # We weren't provided with headers
            # We need to make them
            headers = await self.makeheader()
        return await basecontext.APIContext.acallapi(self, url, headers=headers)

    async def getgame(self, gameid):
        """Gets the name associated with the given gameid. Stores results to prevent unneeded lookups.

        :type gameid: str
        :rtype: str
        :param gameid:
          Game id to look up, must be a string representing an integer >= 0
        :return:
          str containing the name of the set game, or an error message.
        """
        # Do we have that gameid cached?
        if gameid in self.mydata['Games']:
            return self.mydata['Games'][gameid]
        if gameid == 0:  # Streamer might not have set one at all. Hardcoded.
            return "No game set"
        if gameid == '':  # Streamer might not have set one at all. Hardcoded.
            # This started showing up recently, might have supplanted 0.
            return "No game set"
        buff = ''
        try:
            buff = await self.acallapi('https://api.twitch.tv/helix/games?id=' + gameid)
            detchan = buff['data'][0]
            self.mydata['Games'][gameid] = detchan['name']
            return detchan['name']
        except Exception as e:
            # We had an issue, so print the issue, the error, what ID we tried to
            # get, and the entire returned buffer for inspection.
            print("Error in game name:", repr(e), ":", repr(gameid), ":", buff)
            return "Error getting game name: " + str(gameid)

    async def getrecordid(self, record):
        """Gets the name of the record used to uniquely id the stream. Generally, record['name'] or possibly
        record['id']. Used to store info about the stream, such as who is watching and track announcement messages.

        :rtype: str
        :param record: A full stream record as returned by the API.
        :return: A string with the record's unique name.
        """
        if 'user_name' in record:  # Stream type record, ie online streams
            return record['user_name']
        else:  # User type record - ie offline record used by detailannounce
            return record['display_name']
