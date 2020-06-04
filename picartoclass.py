# context to monitor picarto streams

import json  # Interpreting json results - updateparsed most likely needs this.
import discord  # The discord API module. Most useful for making Embeds
# import asyncio  # Use this for sleep, not time.sleep.
import datetime  # Stream durations, time online, etc.
import basecontext  # Base class for our API based context
import urllib.request as request  # Send HTTP requests - debug use only NOT IN BOT

parsed = {}  # Dict with key == 'name'
lastupdate = basecontext.Updated()  # Class that tracks if update succeeded - empty if not successful


# Old non-async method. Kept for debugging.
def connect():
    global parsed
    newrequest = request.Request("https://api.picarto.tv/v1/online?adult=true&gaming=true")
    newconn = request.urlopen(newrequest)
    buff = newconn.read()
    parsed = {item['name']: item for item in json.loads(buff)}
    return True


# Gets the detailed information about a stream. Non-async, debugging.
def getstream(recordid):
    try:
        newrequest = request.Request("https://api.picarto.tv/v1/channel/name/" + recordid)
        newconn = request.urlopen(newrequest)
        buff = newconn.read()
        parse = json.loads(buff)
        return parse
    except (KeyError, Exception):
        return False


class PicartoRecord(basecontext.StreamRecord):

    __slots__ = []

    values = ['adult', 'gaming', 'name', 'title', 'viewers']
    # Keys that are present in a Picarto stream. We don't currently need most of these.
    # values2 = ['user_id', 'name', 'avatar', 'online', 'viewers', 'viewers_total', 'thumbnails', 'followers',
    #            'subscribers', 'adult', 'category', 'account_type', 'commissions', 'recordings', 'title',
    #            'description_panels', 'private', 'private_message', 'gaming', 'chat_settings', 'last_live', 'tags',
    #            'multistream', 'languages', 'following']
    # The first item in multistream is the host.

    streamurl = "https://picarto.tv/{0}"  # URL for going to watch the stream

    def __init__(self, recdict, detailed=False):
        super().__init__(recdict, detailed)
        self.preview = recdict['thumbnails']['web']
        if detailed:
            if recdict['multistream']:
                self.multistream = [basecontext.MultiClass(x['adult'], x['name'], x['user_id'])
                                    for x in recdict['multistream']
                                    if (x['online'] and x['user_id'] != self.name)]
            else:
                self.multistream = []
            self.online = recdict['online']
            self.time = datetime.datetime.strptime(''.join(recdict['last_live'].rsplit(':', 1)), '%Y-%m-%dT%H:%M:%S%z')
            self.avatar = recdict['avatar']  # We COULD make this ourself same as below, but easier to just grab it.
            self.viewers_total = recdict['viewers_total']
        else:
            # Non detailed records omit the time and avatar URLs, but we can make those easily enough.
            self.time = datetime.datetime.now(datetime.timezone.utc)
            self.avatar = "https://picarto.tv/user_data/usrimg/" + recdict['name'].lower() + "/dsdefault.jpg "
            self.multistream = recdict['multistream']
            self.online = True

    async def detailembed(self, showprev=True):
        """This generates the embed to send when detailed info about a stream is requested. More information is provided
        than with the other embeds.

        :type showprev: bool
        :rtype: discord.Embed
        :param showprev: Should the embed include the preview image?
        :return: a discord.Embed representing the current stream.
        """
        description = self.title
        multstring = ""
        # If the stream is in a multi, we need to assemble the string that says
        # who they are multistreaming with.
        if self.ismulti:
            online = self.otherstreams
            if online:
                multstring += " and streaming with " + online[0].name
                if len(online) == 2:
                    multstring += " and " + online[1].name
                elif len(online) == 3:
                    multstring += ", " + online[1].name + ", and " + online[2].name
        # print(multstring," : ", str(record['multistream']))
        myembed = discord.Embed(
            title=self.name + "'s stream is " + ("" if self.online else "not ") + "online" + multstring,
            url="https://picarto.tv/" + self.name, description=description)
        myembed.add_field(name="Adult: " + ("Yes" if self.adult else "No"),
                          value="Gaming: " + ("Yes" if self.gaming else "No"), inline=True)
        if self.online:
            lastonline = await self.streammsg(None)
            viewers = "Viewers: " + str(self.viewers)
        else:
            # If this were used on a non-detailed record, it would be the time the record was created.
            lastonline = "Last online: " + self.time.strftime("%m/%d/%Y")
            viewers = "Total Views: " + str(self.total_views[1])
        myembed.add_field(name=lastonline, value=viewers, inline=True)
        if showprev:
            myembed.set_image(url=self.preview_url)
        myembed.set_thumbnail(url=self.avatar)
        return myembed


class PicartoContext(basecontext.APIContext):
    defaultname = "picarto"  # This is used to name this context and is the command to call it. Must be unique.
    streamurl = "https://picarto.tv/{0}"  # URL for going to watch the stream
    apiurl = "https://api.picarto.tv/v1/online?adult=true&gaming=true"  # URL to call to find online streams
    channelurl = "https://api.picarto.tv/v1/channel/name/{0}"  # URL to call to get information on a single stream
    recordclass = PicartoRecord

    def __init__(self, instname=None):
        # Init our base class
        basecontext.APIContext.__init__(self, instname)
        # Our parsed is going to be the global parsed in our module, instead of the
        # basecontext parsed. This gets shared with ALL instances of this class.
        # Primarily this will allow sharing API response data with all instances.
        self.parsed = parsed  # Removing any of this isn't recommended.
        self.lastupdate = lastupdate  # Tracks if last API update was successful.
        # Adding stuff below here is fine, obviously.

    async def getrecordid(self, record):
        """Gets the name of the record used to uniquely id the stream. Generally, record['name'] or possibly
        record['id']. Used to store info about the stream, such as who is watching and track announcement messages.

        :rtype: str
        :param record: A full stream record as returned by the API.
        :return: A string with the record's unique name.
        """
        return record['name']
