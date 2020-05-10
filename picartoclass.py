# context to monitor picarto streams

import json  # Interpreting json results - updateparsed most likely needs this.
import discord  # The discord API module. Most useful for making Embeds
# import asyncio  # Use this for sleep, not time.sleep.
import datetime  # Stream durations, time online, etc.
import time  # Attaches to thumbnail URL to avoid discord's overly long caching
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


class PicartoContext(basecontext.APIContext):
    defaultname = "picarto"  # This is used to name this context and is the command to call it. Must be unique.
    streamurl = "https://picarto.tv/{0}"  # URL for going to watch the stream
    apiurl = "https://api.picarto.tv/v1/online?adult=true&gaming=true"  # URL to call to find online streams
    channelurl = "https://api.picarto.tv/v1/channel/name/{0}"  # URL to call to get information on a single stream

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
        try:
            # Time the stream began
            # print("getrectime",record)
            began = datetime.datetime.strptime(''.join(record['last_live'].rsplit(':', 1)), '%Y-%m-%dT%H:%M:%S%z')
        except KeyError:  # ONLY detailed records have last_live.
            # If the API changes to include it, this'll work as is to use it.
            return datetime.timedelta()
        return datetime.datetime.now(datetime.timezone.utc) - began

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
        # Simple embed is the same, we just need to add a preview image.
        myembed = await self.simpembed(record, snowflake, offline)
        myembed.set_image(url=record['thumbnails']['web'] + "?msgtime=" + str(int(time.time())))
        return myembed

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
        if record['multistream']:
            value = "Multistream: Yes"
        if not snowflake:
            embtitle = record['name'] + " has come online!"
        else:
            embtitle = await self.streammsg(snowflake, record, offline)
        noprev = discord.Embed(title=embtitle, url=self.streamurl.format(record['name']), description=description)
        noprev.add_field(name="Adult: " + ("Yes" if record['adult'] else "No"),
                         value="Viewers: " + str(record['viewers']),
                         inline=True)
        noprev.add_field(name=value, value="Gaming: " + ("Yes" if record['gaming'] else "No"), inline=True)
        noprev.set_thumbnail(url="https://picarto.tv/user_data/usrimg/" + record['name'].lower() + "/dsdefault.jpg")
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
        description = record['title']
        multstring = ""
        # If the stream is in a multi, we need to assemble the string that says
        # who they are multistreaming with.
        if record["multistream"]:
            # Pare down the list to those who are currently online
            online = list((x for x in record["multistream"] if x["online"]))
            # Remove the record we're detailing from the list
            online = list((x for x in online if x["name"] != record["name"]))
            if online:
                multstring += " and streaming with " + online[0]["name"]
                if len(online) == 2:
                    multstring += " and " + online[1]["name"]
                elif len(online) == 3:
                    multstring += ", " + online[1]["name"] + ", and " + online[2]["name"]
        # print(multstring," : ", str(record['multistream']))
        myembed = discord.Embed(
            title=record['name'] + "'s stream is " + ("" if record['online'] else "not ") + "online" + multstring,
            url="https://picarto.tv/" + record['name'], description=description)
        myembed.add_field(name="Adult: " + ("Yes" if record['adult'] else "No"),
                          value="Gaming: " + ("Yes" if record['gaming'] else "No"), inline=True)
        if record['online']:
            lastonline = "Streaming for " + await self.streamtime(await self.getrectime(record))
            viewers = "Viewers: " + str(record['viewers'])
        else:
            # Doesn't work pre 3.7, removed.
            # lastonline = datetime.datetime.fromisoformat(record['last_live']).strftime("%m/%d/%Y")
            # This works with 3.6/3.7
            lastonline = "Last online: " + datetime.datetime.strptime(''.join(record['last_live'].rsplit(':', 1)),
                                                                      '%Y-%m-%dT%H:%M:%S%z').strftime("%m/%d/%Y")
            viewers = "Total Views: " + str(record['viewers_total'])
        myembed.add_field(name=lastonline, value=viewers, inline=True)
        if showprev:
            myembed.set_image(url=record['thumbnails']['web'] + "?msgtime=" + str(int(time.time())))
        myembed.set_thumbnail(url="https://picarto.tv/user_data/usrimg/" + record['name'].lower() + "/dsdefault.jpg")
        return myembed
