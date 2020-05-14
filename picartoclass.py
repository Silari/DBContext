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

    values = ['adult', 'gaming', 'multistream', 'name',
              'title', 'viewers']
    # Keys that are present in a Picarto stream. We don't currently need most of these.
    # values2 = ['user_id', 'name', 'avatar', 'online', 'viewers', 'viewers_total', 'thumbnails', 'followers',
    #            'subscribers', 'adult', 'category', 'account_type', 'commissions', 'recordings', 'title',
    #            'description_panels', 'private', 'private_message', 'gaming', 'chat_settings', 'last_live', 'tags',
    #            'multistream', 'languages', 'following']
    # The first item in multistream is the host.

    def __init__(self, recdict, detailed=False):
        super().__init__(recdict, detailed)
        self.internal['preview'] = recdict['thumbnails']['web']
        if detailed:
            self.internal['online'] = recdict['online']
            self.internal['time'] = datetime.datetime.strptime(''.join(recdict['last_live'].rsplit(':', 1)),
                                                               '%Y-%m-%dT%H:%M:%S%z')
            self.internal['avatar'] = recdict['avatar']
            self.internal['viewers_total'] = recdict['viewers_total']
        else:
            self.internal['time'] = datetime.datetime.now(datetime.timezone.utc)
            self.internal['avatar'] = "https://picarto.tv/user_data/usrimg/" + recdict['name'].lower() + "/dsdefault" \
                                                                                                         ".jpg "
            self.internal['online'] = True

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
        value = "Multistream: No"
        if self.multistream:
            value = "Multistream: Yes"
        if not snowflake:
            embtitle = self.name + " has come online!"
        else:
            embtitle = await self.streammsg(snowflake, offline)
        noprev = discord.Embed(title=embtitle, url=PicartoContext.streamurl.format(self.name), description=description)
        noprev.add_field(name="Adult: " + ("Yes" if self.adult else "No"),
                         value="Gaming: " + ("Yes" if self.gaming else "No"),
                         inline=True)
        noprev.add_field(name=value, value="Viewers: " + str(self.viewers), inline=True)
        noprev.set_thumbnail(url=self.avatar)
        return noprev

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
        if self.multistream:
            # Pare down the list to those who are currently online
            online = list((x for x in self.otherstreams if x["online"]))
            # Remove the record we're detailing from the list
            online = list((x for x in online if x["name"] != self.name))
            if online:
                multstring += " and streaming with " + online[0]["name"]
                if len(online) == 2:
                    multstring += " and " + online[1]["name"]
                elif len(online) == 3:
                    multstring += ", " + online[1]["name"] + ", and " + online[2]["name"]
        # print(multstring," : ", str(record['multistream']))
        myembed = discord.Embed(
            title=self.name + "'s stream is " + ("" if self.online else "not ") + "online" + multstring,
            url="https://picarto.tv/" + self.name, description=description)
        myembed.add_field(name="Adult: " + ("Yes" if self.adult else "No"),
                          value="Gaming: " + ("Yes" if self.gaming else "No"), inline=True)
        if self.online:
            lastonline = "Streaming for " + await PicartoContext.streamtime(self.time)
            viewers = "Viewers: " + str(self.viewers)
        else:
            # Doesn't work pre 3.7, removed.
            # lastonline = datetime.datetime.fromisoformat(record['last_live']).strftime("%m/%d/%Y")
            # This works with 3.6/3.7
            lastonline = "Last online: " + self.internal['time'].strftime("%m/%d/%Y")
            viewers = "Total Views: " + str(self.total_views[1])
        myembed.add_field(name=lastonline, value=viewers, inline=True)
        if showprev:
            myembed.set_image(url=self.preview)
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
