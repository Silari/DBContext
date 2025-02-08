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
        if False or record["in_multi"]:  # This is no longer present
            record["DBMulti"] = detchan['data']
        return record
    except (KeyError, Exception):
        return False


class PiczelRecord(basecontext.StreamRecord):

    __slots__ = []

    values = ['adult', 'title']
    # Piczel keys for online/offline streams. DBMulti is only present if in_multi is True. Contains addl PiczelRecords
    # values2 = ['DBMulti', 'adult', 'banner', 'banner_link', 'description', 'follower_count', 'id', 'in_multi',
    #            'isPrivate?', 'live', 'live_since', 'offline_image', 'parent_streamer', 'preview', 'recordings',
    #            'rendered_description', 'settings', 'slug', 'tags', 'title', 'user', 'username', 'viewers']
    # NEWVALUES = {'id', 'title', 'live', 'live_since', 'slug', 'offline_image', 'preview', 'adult', 'user',
    # 'username', 'viewers', 'is_private'}
    # DETAILED = {'id', 'title', 'description', 'rendered_description', 'follower_count', 'live', 'live_since',
    # 'isPrivate?', 'is_private', 'slug', 'offline_image', 'banner', 'banner_link', 'preview', 'adult', 'in_multi',
    # 'parent_streamer', 'settings', 'viewers', 'username', 'tags', 'bitrate', 'has_b_frames', 'resolution',
    # 'keyframe_interval', 'framerate', 'video_codec', 'audio_codec', 'user', 'recordings'}
    # NEWNEWVALUES = {'id', 'title', 'live', 'live_since', 'slug', 'offline_image', 'preview', 'adult', 'username',
    # 'user'}
    # NEWDETAILED = {'id', 'title', 'description', 'rendered_description', 'follower_count', 'live', 'live_since',
    # 'isPrivate?', 'is_private', 'slug', 'offline_image', 'banner', 'banner_link', 'preview', 'adult', 'in_multi',
    # 'parent_streamer', 'settings', 'viewers', 'username', 'tags', 'offline_peers', 'bitrate', 'has_b_frames',
    # 'resolution', 'keyframe_interval', 'framerate', 'video_codec', 'audio_codec', 'user', 'recordings', 'DBMulti'}

    upvalues = ['adult',]
    streamurl = "http://piczel.tv/watch/{0}"  # Gets called as self.streamurl.format(await self.getrecordid(record))

    def __init__(self, recdict, detailed=False):
        if 'in_multi' in recdict:  # Detailed streams have the in_multi key present.
            detailed = True  # Detailed is used for multi-stream data and viewers_total.
        super().__init__(recdict, detailed)
        self.gaming = False
        self.avatar = recdict['user']['avatar']['url']
        self.name = recdict['username']
        self.online = recdict['live']
        self.preview = str(recdict['id'])
        # Time is in UTC, convert to a datetime and specify that it's UTC.
        if self.online:
            # live_since exists but is none in offline streams, so this would fail.
            self.time = datetime.datetime.strptime(recdict['live_since'], "%Y-%m-%dT%H:%M:%S.000Z")\
                .replace(tzinfo=datetime.timezone.utc)
        else:
            self.time = None
        if 'follower_count' in recdict:
            self.viewers_total = recdict['follower_count']
        if 'in_multi' in recdict and recdict['in_multi']:  # Is this a multistream?
            if detailed:  # We need to setup our multistream data. Only available in a detailed record.
                multi = []
                for stream in recdict['DBMulti'][1:]:  # First record is a copy of our record, ignore that.
                    if stream['live']:
                        # Trimming record down to just user_id, name, online, adult, same as what's in picarto.
                        # Normally these contain cyclic references to the other streams in their 'DBMulti' attributes,
                        # which makes these very weird. Removing all the unneeded stuff saves a lot of space.
                        multi.append(basecontext.MultiClass(adult=stream['adult'],
                                                            name=stream['username'],
                                                            user_id=stream['id']))
                self.multistream = multi  # If no one else is online this is empty and multistream is False
            else:
                self.multistream = [True]
        else:
            self.multistream = []

    def update(self, newdict):
        super().update(newdict)
        if 'in_multi' in newdict and newdict['in_multi']:
            self.multistream = [True]
        else:
            self.multistream = []
        # We'll never call this unless the stream is live. Offline only happens when a detailed record is created.
        # self.internal['online'] = newdict['live']

    @property
    def preview_url(self):
        """URL for the stream preview. We add a time property to the end to get around caching.

        :rtype: str
        """
        # Previously https://piczel.tv/static/thumbnail/stream_<ID>.jpg
        # Now https://piczel.tv/thumbnails/stream_<ID>.jpg
        return 'https://piczel.tv/thumbnails/stream_' + self.preview + '.jpg' + "?msgtime=" + \
               str(int(time.time()))

    @property
    def total_views(self):
        """Total number of people who haved viewed the stream, or a similar overview of how popular the stream is. For
        piczel, this is the follower count instead, as they don't track total views.

        :rtype: tuple[str, int]
        :return: A tuple with a string describing what we're counting, and an integer with the count.
        """
        return "Followers:", self.viewers_total

    async def detailembed(self, showprev=True):
        """This generates the embed to send when detailed info about a stream is requested. More information is provided
        than with the other embeds.

        :type showprev: bool
        :rtype: discord.Embed
        :param showprev: Should the embed include the preview image? Generally yes unless it's hidden by adult options.
        :return: a discord.Embed representing the current stream.
        """
        # This generates the embed to send when detailed info about a stream is
        # requested. The actual message is handled by basecontext's detailannounce
        description = self.title
        multstring = ""
        # If the stream is in a multi, we need to assemble the string that says who they are multistreaming with. This
        # is only available in a detailed record. With a non-detailed record, it will not include multistream info.
        if self.ismulti and len(self.otherstreams):
            multstring += " and streaming with "
            if len(self.otherstreams) == 1:
                multstring += self.otherstreams[0].name
            else:
                for stream in self.otherstreams[0:-1]:
                    multstring += stream.name + ", "
                multstring += "and " + self.otherstreams[-1:][0].name
        # print(multstring," : ", self.otherstreams)
        myembed = discord.Embed(
            title=self.name + "'s stream is " + ("" if self.online else "not ") + "online" + multstring,
            url="https://piczel.tv/" + self.name, description=description)
        myembed.add_field(name="Adult: " + ("Yes" if self.adult else "No"),
                          value="Followers: " + str(self.total_views[1]), inline=True)
        if self.online:
            myembed.add_field(name=await self.streammsg(None),
                              value="")  # Viewers: " + str(self.viewers))
        if showprev:
            myembed.set_image(url=self.preview_url)
        # We've had issues with the avatar location changing. If it does again,
        # announces will still work until we can fix it, just without the avatar.
        if self.avatar:
            myembed.set_thumbnail(url=self.avatar)
        return myembed

    async def simpembed(self, showtime=None, offline=False):
        """The embed used by the noprev message type. This is general information about the stream, but not everything.
        Users can get a more detailed version using the detail command, but we want something simple for announcements.

        :type showtime: bool
        :type offline: bool
        :rtype: discord.Embed
        :param showtime: Should the title field include how long the stream has ran?
        :param offline: Do we need to adjust the time to account for basecontext.offlinewait?
        :return: a discord.Embed representing the current stream.
        """
        description = self.title
        ismulti = "Multistream: No"
        if self.ismulti:
            ismulti = "Multistream: Yes"
        if not showtime:
            embtitle = self.name + " has come online!"
        else:
            embtitle = await self.streammsg(None, offset=offline)
        noprev = discord.Embed(title=embtitle, url=self.streamurl.format(self.name), description=description)
        noprev.add_field(name="Adult: " + ("Yes" if self.adult else "No"),
                         value="Gaming: " + ("Yes" if self.gaming else "No"),
                         inline=True)
        # We don't have either multistream OR viewers info anymore. So don't use either.
        # noprev.add_field(name=ismulti, value="Viewers: " + str(self.viewers), inline=True)
        noprev.set_thumbnail(url=self.avatar)
        return noprev

class PiczelContext(basecontext.APIContext):
    defaultname = "piczel"  # This is used to name this context and is the command to call it. Must be unique.
    streamurl = "http://piczel.tv/watch/{0}"  # Gets called as self.streamurl.format(await self.getrecordid(record))
    channelurl = apiurl + "{0}"  # URL to call to get information on a single stream
    apiurl = apiurl + "?&sfw=false&live_only=false&followedStreams=false"  # URL to call to find online streams
    recordclass = PiczelRecord

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
        :rtype: PiczelRecord
        :param recordid: String with the name of the stream, used to format the URL.
        :param headers: Headers to be passed on to the API call.
        :return: A PiczelRecord instance.
        """
        record = False
        # We can still use the baseclass version to handle the API call
        detchan = await self.acallapi(self.channelurl.format(recordid), headers)
        try:  # Now we need to get the actual stream record from the return
            if detchan:  # detchan may be False if API call errors
                record = detchan['data'][0]  # data is an array of streams - first one is our target stream
                # If user is in a multistream detchan may have multiple records - save them
                if record["in_multi"]:
                    # The other records in data are members of a multistream with our target stream
                    # This is useful info for the detailed embed.
                    record["DBMulti"] = detchan['data']
            else:
                return detchan  # Whatever we got, pass it back up the chain
        except Exception as e:  # Any errors, we can't return the record.
            # Log the error - there really shouldn't be any, as the basecontext
            # function should catch errors with the call and return False, which
            # we check for. This would probably signal a change in the API, which
            # we need to know about so we can fix.
            print("piczel agetstream", repr(e))
            record = False
        return PiczelRecord(record, True)

    agetstreamoffline = agetstream

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
