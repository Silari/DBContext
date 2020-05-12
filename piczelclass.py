# context to monitor piczel streams.

import json  # Interpreting json results - updateparsed most likely needs this.
import discord  # The discord API module. Most useful for making Embeds
# import asyncio  # Use this for sleep, not time.sleep.
import time  # Attaches to thumbnail URL to avoid discord's overly long caching
import datetime  # Stream durations, time online, etc.
import basecontext  # Base class for our API based context
import urllib.request as request  # Send HTTP requests - debug use only NOT IN BOT

parsed = {}  # Dict with key == 'username'
lastupdate = basecontext.Updated()  # Class that tracks if update succeeded - empty if not successful

apiurl = 'https://piczel.tv/api/streams/'
offurl = 'https://piczel.tv/static'
piczelurl = "http://piczel.tv/watch/"


# Old non-async method. Kept for debugging.
def connect():
    global parsed
    newrequest = request.Request(apiurl + '?&sfw=false&live_only=false&followedStreams=false')
    newconn = request.urlopen(newrequest)
    buff = newconn.read()
    parsed = {item['username']: item for item in json.loads(buff)}
    return True


# Gets the detailed information about a stream, non-async. only for testing.
def getstream(recordid):
    try:
        newrequest = request.Request(apiurl + recordid)
        newconn = request.urlopen(newrequest)
        buff = newconn.read()
        if not buff:
            return False
        detchan = json.loads(buff)
        record = detchan['data'][0]
        # If user is in a multistream detchan may have multiple records - save them
        if record["in_multi"]:
            record["DBMulti"] = detchan['data']
        return record
    except (KeyError, Exception):
        return False


class PiczelRecord(basecontext.StreamRecord):

    values = ['adult', 'title', 'viewers']
    # Piczel keys for online/offline streams. DBMulti is only present if in_multi is True. Contains addl PiczelRecords
    # values2 = ['DBMulti', 'adult', 'banner', 'banner_link', 'description', 'follower_count', 'id', 'in_multi',
    #            'isPrivate?', 'live', 'live_since', 'offline_image', 'parent_streamer', 'preview', 'recordings',
    #            'rendered_description', 'settings', 'slug', 'tags', 'title', 'user', 'username', 'viewers']

    upvalues = ['adult', 'viewers']  # Manually update multistream. No other changes.

    def __init__(self, recdict, detailed=False):
        super().__init__(recdict, detailed)
        self.internal['avatar'] = recdict['user']['avatar']['url']
        self.internal['name'] = recdict['username']
        self.internal['online'] = recdict['live']
        self.internal['preview'] = recdict['id']
        self.internal['time'] = datetime.datetime.strptime(recdict['live_since'], "%Y-%m-%dT%H:%M:%S.000Z")
        self.internal['viewers_total'] = recdict['follower_count']
        if recdict['in_multi']:
            if detailed:  # We need to setup our multistream data. Only available in a detailed record.
                multi = []
                for stream in recdict['DBMulti'][1:]:  # First record is a copy of our record, ignore that.
                    if stream['live']:
                        # Trimming record down to just user_id, name, online, adult, same as what's in picarto.
                        # Normally these contain cyclic references to the other streams in their 'DBMulti' attributes,
                        # which makes these very weird. Removing all the unneeded stuff saves a lot of space.
                        multi.append({'name': stream['username'],
                                      'online': True,
                                      'user_id': stream['id'],
                                      'adult': stream['adult']})
                self.internal['multistream'] = multi  # If no one else is online this is empty and multistream is False
            else:
                self.internal['multistream'] = [True]
        else:
            self.internal['multistream'] = []

    def update(self, newdict):
        super().update(newdict)
        if newdict['in_multi']:
            self.internal['multistream'] = [True]
        else:
            self.internal['multistream'] = []
        # self.internal['online'] = newdict['live']

    @property
    def gaming(self):
        """Is the stream set as a gaming stream?

        :rtype: bool
        """
        return False

    @property
    def preview(self):
        """URL for the stream preview. We add a time property to the end to get around caching.

        :rtype: str
        """
        return 'https://piczel.tv/static/thumbnail/stream_' + str(self.internal['id']) + '.jpg' + "?msgtime=" + str(
            int(time.time()))

    @property
    def total_views(self):
        """Total number of people who haved viewed the stream, or a similar overview of how popular the stream is. For
        piczel, this is the follower count instead, as they don't track total views.

        :rtype: tuple[str, int]
        :return: A tuple with a string describing what we're counting, and an integer with the count.
        """
        return "Followers:", self.internal['viewers_total']


class PiczelContext(basecontext.APIContext):
    defaultname = "piczel"  # This is used to name this context and is the command to call it. Must be unique.
    streamurl = "http://piczel.tv/watch/{0}"  # Gets called as self.streamurl.format(await self.getrecordid(record))
    channelurl = apiurl + "{0}"  # URL to call to get information on a single stream
    apiurl = apiurl + "?&sfw=false&live_only=false&followedStreams=false"  # URL to call to find online streams

    def __init__(self, instname=None):
        # Init our base class
        basecontext.APIContext.__init__(self, instname)
        # Our parsed is going to be the global parsed in our module, instead of the
        # basecontext parsed. This gets shared with ALL instances of this class.
        # Primarily this would allow sharing API response data with all instances.
        self.parsed = parsed  # Removing any of this isn't recommended.
        self.lastupdate = lastupdate  # Tracks if last API update was successful.
        # Adding stuff below here is fine.

    async def agetstream(self, recordid, headers=None):
        """Call our API with the getchannel URL formatted with the channel name

        :type recordid: str
        :type headers: dict
        :rtype: dict
        :param recordid: String with the name of the stream, used to format the URL.
        :param headers: Headers to be passed on to the API call.
        :return: A dict with the information for the stream, exact content depends on the API.
        """
        record = False
        # We can still use the baseclass version to handle the API call
        detchan = await basecontext.APIContext.agetstream(self, recordid, headers)
        try:  # Now we need to get the actual stream record from the return
            if detchan:  # detchan may be False if API call errors
                record = detchan['data'][0]  # data is an array of streams - first one is our target stream
                # If user is in a multistream detchan may have multiple records - save them
                if record["in_multi"]:
                    # The other records in data are members of a multistream with our target stream
                    # This is useful info for the detailed embed.
                    record["DBMulti"] = detchan['data']
        except Exception as e:  # Any errors, we can't return the record.
            # Log the error - there really shouldn't be any, as the basecontext
            # function should catch errors with the call and return False, which
            # we check for. This would probably signal a change in the API, which
            # we need to know about so we can fix.
            print("piczel agetstream", repr(e))
            record = False
        return record

    async def getrecordid(self, record):
        """Gets the name of the record used to uniquely id the stream. Generally, record['name'] or possibly
        record['id']. Used to store info about the stream, such as who is watching and track announcement messages.

        :rtype: str
        :param record: A full stream record as returned by the API.
        :return: A string with the record's unique name.
        """
        # Should return the name of the record used to uniquely id the stream.
        # Generally, record['name'] or possibly record['id']. Used to store info about
        # the stream, such as who is watching and track announcement messages.
        return record['username']

    async def getavatar(self, record):
        """Parse the avatar URL from the record - this seems to have changed around Feb 1, 2020 so it's a function,
        whereas the other subclasses just grab it directly.

        :rtype: str
        :param record: A full stream record as returned by the API
        :return: String with the URL where the avatar image is kept.
        """
        try:  # New location, looks like everything uses this now
            return record['user']['avatar']['url']
        except KeyError:
            pass
        try:  # Old location, keep JIC some records still use it
            return record['user']['avatar']['avatar']['url']
        except KeyError:
            pass
        return None

    async def isadult(self, record):
        """Whether the API sets the stream as Adult.

        :rtype: bool
        :param record: A full stream record as returned by the API
        :return: Boolean representing if the API has marked the stream as Adult.
        """
        return record['adult']

    async def getrectime(self, record):
        """Time that a stream has ran, determined from the API data.

        :rtype: datetime.timedelta
        :param record: A full stream record as returned by the API
        :return: A timedelta representing how long the stream has run.
        """
        # Time the stream began - given in UTC
        began = datetime.datetime.strptime(record['live_since'], "%Y-%m-%dT%H:%M:%S.000Z")
        return datetime.datetime.utcnow() - began

    # The embed used by the default message type. Same as the simple embed except
    # that we add on a preview of the stream.
    async def makeembed(self, record, snowflake=None, offline=False):
        """The embed used by the default message type. Same as the simple embed except for added preview of the stream.

        :type snowflake: int
        :type offline: bool
        :rtype: discord.Embed
        :param record: A full stream record as returned by the API
        :param snowflake: Integer representing a discord Snowflake
        :param offline: Do we need to adjust the time to account for basecontext.offlinewait?
        :return: a discord.Embed representing the current stream.
        """
        # Simple embed is the same, we just need to add a preview image. Save code
        myembed = await self.simpembed(record, snowflake, offline)
        thumburl = 'https://piczel.tv/static/thumbnail/stream_' + str(record['id']) + '.jpg' + "?msgtime=" + str(
            int(time.time()))
        myembed.set_image(url=thumburl)  # Add your image here
        return myembed

    # The embed used by the noprev option message. This is general information
    # about the stream - just the most important bits. Users can get a more
    # detailed version using the detail command.
    async def simpembed(self, record, snowflake=None, offline=False):
        """The embed used by the noprev message type. This is general information about the stream, but not everything.
        Users can get a more detailed version using the detail command, but we want something simple for announcements.

        :type snowflake: int
        :type offline: bool
        :rtype: discord.Embed
        :param record: A full stream record as returned by the API
        :param snowflake: Integer representing a discord Snowflake
        :param offline: Do we need to adjust the time to account for basecontext.offlinewait?
        :return: a discord.Embed representing the current stream.
        """
        description = record['title']
        value = "Multistream: No"
        if record['in_multi']:
            value = "\nMultistream: Yes"
        if not snowflake:
            embtitle = record['username'] + " has come online!"
        else:
            embtitle = await self.streammsg(snowflake, record, offline)
        noprev = discord.Embed(title=embtitle, url=piczelurl + record['username'], description=description)
        noprev.add_field(name="Adult: " + ("Yes" if record['adult'] else "No"),
                         value="Viewers: " + str(record['viewers']),
                         inline=True)
        noprev.add_field(name=value, value="Private: " + ("Yes" if record['isPrivate?'] else "No"), inline=True)
        avatar = await self.getavatar(record)
        if avatar:
            noprev.set_thumbnail(url=avatar)
        return noprev

    async def makedetailembed(self, record, showprev=True):
        """This generates the embed to send when detailed info about a stream is requested. More information is provided
        than with the other embeds.

        :type showprev: bool
        :rtype: discord.Embed
        :param record: A full stream record as returned by the API
        :param showprev: Should the embed include the preview image?
        :return: a discord.Embed representing the current stream.
        """
        # This generates the embed to send when detailed info about a stream is
        # requested. The actual message is handled by basecontext's detailannounce
        description = record['title']
        multstring = ""
        # If the stream is in a multi, we need to assemble the string that says who they are multistreaming with. This
        # is only available in a detailed record.
        if record["in_multi"]:
            # Pare down the list to those who are currently online
            online = list((x for x in record['DBMulti'] if x["live"]))
            # Remove the record we're detailing from the list, ALWAYS(?) [0]
            online = list((x for x in online if x["username"] != record["username"]))
            if online:
                multstring += " and streaming with "
                if len(online) == 1:
                    multstring += online[0]["username"]
                else:
                    for stream in online[0:-1]:
                        multstring += stream['username'] + ", "
                    multstring += "and " + online[-1:][0]['username']
        # print(multstring," : ", str(record['multistream']))
        myembed = discord.Embed(
            title=record['username'] + "'s stream is " + ("" if record['live'] else "not ") + "online" + multstring,
            url="https://piczel.tv/" + record['username'], description=description)
        myembed.add_field(name="Adult: " + ("Yes" if record['adult'] else "No"),
                          value="Followers: " + str(record['user']['follower_count']), inline=True)
        if record['live']:
            myembed.add_field(name="Streaming for " + await self.streamtime(await self.getrectime(record)),
                              value="Viewers: " + str(record['viewers']))
        if showprev:
            thumburl = 'https://piczel.tv/static/thumbnail/stream_' + str(record['id']) + '.jpg' + "?msgtime=" + str(
                int(time.time()))
            myembed.set_image(url=thumburl)
        avatar = await self.getavatar(record)
        # We've had issues with the avatar location changing. If it does again,
        # announces will still work until we can fix it, just without the avatar.
        if avatar:
            myembed.set_thumbnail(url=avatar)
        return myembed
