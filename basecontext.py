# context class to base new contexts on
# This file has all the items required by the dbcontext bot to be valid.
# Some values/functions WILL need to be updated. Please see the related module
# templateclass.py for details, as well as the minimum list of functions/values
# that need to be set for any new class inheriting from this.

# If I use this as a base, I could redo the commands + help to make use of a dict
# with {<command>:<help text>} which would simplify writing new commands
# into the help file. AND much more easily add context specific commands.

# IMPORTANT - discord.py is based on coroutines, which are asynchronous and allow
# for easier management of multiple threads. Most functions used in this should
# also be coroutines, especially any potentially blocking functions, so that the
# bot can still be responsive to other requests.
from typing import Dict, AsyncGenerator

import discord  # Access to potentially needed classes/methods, Embed
import aiohttp  # Should be used for any HTTP requests, NOT urllib!
import json  # Useful for interpreting json from API requests.
import asyncio  # Useful for asyncio.sleep - do NOT use the time.sleep method!
import traceback  # For exception finding.
import datetime  # For stream duration calculation.
import time  # Used to add a time stamp to images to avoid caches.

if False:
    from dbcontext import LimitedClient


class Updated:
    """Represents if the last API update succeeded, and counts contiguous failures."""

    __slots__ = ['failed']

    def __init__(self):
        self.failed = 0

    def __bool__(self):
        return self.failed == 0

    def record(self, updated):
        if updated:
            self.failed = 0
        else:
            self.failed += 1


lastupdate = Updated()  # Class that tracks if update succeeded - empty if not successful

offlinewait = 10  # How many minutes to wait before declaring a stream offline - OLD
updatetime = 300  # How many seconds to wait before updating stream announcements
offlinetime = 600  # How many seconds to wait before declaring a stream offline


class ChannelNotSet(discord.DiscordException):
    """Exception to use when a server does not have an announcement channel set, but it is explicitly required."""
    pass


class MultiClass:
    """Holds information about the other participants in a multistream."""

    __slots__ = ["adult", "name", "user_id"]

    def __init__(self, adult, name, user_id):
        self.adult = adult
        self.name = name
        self.user_id = user_id


class StreamRecord:
    """Class that encapsulates a record from a stream.

    adult: bool
      Is the stream marked Adult?
    avatar: str
      URL for the avatar of the stream.
    detailed: bool
      Is the record a detailed record?
    gaming: bool
      Is the stream set as a gaming stream?
    multistream: list[MultiClass] | bool
      Stores information about multistream status. This should be interacted with via ismulti or otherstreams, as the
      actual type varies between APIs and what call is used. Should always be a list if detailed.
    name: str
      Name of the stream.
    offlinetime: datetime.datetime
      Time the stream went offline. Used to determine when to call removemsg on the announcement.
    online: bool
      Is the stream online?
    onlinetime: datetime.datetime
      Time the stream came online/was last updated. Used to determine if announcement needs to be updated.
    preview: str
      Used by preview_url to generate the URL to watch the stream at. Typically a URL, but possibly an ID used to
      generate the final URL.
    time: datetime.datetime
      Time the stream went online.
    title: str
      Channel title/description.
    viewers: int
      Number of people viewing the stream.
    """

    # __slots__ = ['internal', 'offlinetime', 'onlinetime']
    __slots__ = ['adult', 'avatar', 'detailed', 'gaming', 'multistream', 'name',
                 'offlinetime', 'online', 'onlinetime', 'preview', 'time',
                 'title', 'viewers', 'viewers_total']
    # List of values to retain from the starting dictionary.
    # Generally subclasses are going to overwrite this, but this is a basic list of what we generally expect to exist.
    values = ['adult', 'avatar', 'gaming', 'multistream', 'name', 'online',
              'preview', 'time', 'title', 'viewers_total', 'viewers']
    # List of values to update when given a new dictionary. Several items are static so don't need to be updated.
    upvalues = ['adult', 'gaming', 'multistream', 'viewers']
    streamurl = ''

    # noinspection PyTypeChecker
    def __init__(self, recdict, detailed=False):
        # self.internal = {k: recdict[k] for k in self.values}
        for name in self.values:
            setattr(self, name, recdict[name])
        self.detailed = detailed
        self.offlinetime = None  # type: datetime.datetime # Time since stream went offline.
        self.onlinetime = None  # type: datetime.datetime # Time since last stream update.

    def update(self, newdict):
        # self.internal.update({k: newdict[k] for k in self.upvalues})
        for name in self.upvalues:
            setattr(self, name, newdict[name])

    @property
    def ismulti(self):
        """Is the stream a multistream?

        :return: Returns True if stream is an a multistream, otherwise False.
        :rtype: bool
        """
        # Depending on the API and the call used, this could be True, False, or a(n empty) list of streams. This pares
        # all that down into a simple True or False.
        return bool(self.multistream)

    @property
    def otherstreams(self):
        """Is the stream a multistream? Empty list if not, otherwise a list of multistream participants. Currently the
        list contains dicts with user_id, name, and adult, as that's what Picarto provides.

        :return: Returns an empty list if no multi, otherwise list contains MultiClass instances for each stream.
        :rtype: list
        """
        if self.detailed:
            return self.multistream
        return []

    @property
    def preview_url(self):
        """URL for the stream preview. We add a time property to the end to get around caching.

        :rtype: str
        """
        return self.preview + "?msgtime=" + str(int(time.time()))

    @property
    def duration(self):
        """Length of time the stream has been running. internal['time'] must be a datetime.datetime which is used to
        calculate the stream length.

        :rtype: datetime.timedelta
        """
        try:
            return datetime.datetime.now(datetime.timezone.utc) - self.time
        except AttributeError:
            pass
        return datetime.timedelta()

    @property
    def total_views(self):
        """Total number of people who haved viewed the stream, or a similar overview of how popular the stream is. For
        piczel, this is the follower count instead, as they don't track total views.

        :rtype: tuple[str, int]
        :return: A tuple with a string describing what we're counting, and an integer with the count.
        """
        return "Total views:", self.viewers_total

    async def streammsg(self, snowflake, offset=False):
        """Function to generate a string to say how long stream has lasted.

        :type snowflake: int | None
        :type offset: bool
        :rtype: str
        :param snowflake: Integer representing a discord Snowflake, or None to only use the stored time.
        :param offset: Do we need to adjust the time to account for basecontext.offlinewait?
        :return: a string stating the time the stream has ran for.
        """
        # Find the duration of the stream.
        if snowflake:  # If a snowflake was given instead of None
            dur = await APIContext.longertime(snowflake, self.duration)
        else:
            dur = self.duration
        # If stream is offline, we adjust the time to account for the waiting
        # period before we marked it offline.
        if offset:
            timestr = await APIContext.streamtime(dur, offlinewait)
        else:
            # Online streams need no adjustement.
            timestr = await APIContext.streamtime(dur)
        # We can revert this to using self.online and having updatetask change it as needed if we have to later, but for
        # now this is much simpler, and NOTHING uses offset except for removemsg.
        if not offset:
            retstr = "Stream running for "
        else:
            retstr = "Stream lasted for "
        retstr += timestr
        return retstr

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
        ismulti = "Multistream: No"
        if self.ismulti:
            ismulti = "Multistream: Yes"
        if not snowflake:
            embtitle = self.name + " has come online!"
        else:
            embtitle = await self.streammsg(snowflake, offset=offline)
        noprev = discord.Embed(title=embtitle, url=self.streamurl.format(self.name), description=description)
        noprev.add_field(name="Adult: " + ("Yes" if self.adult else "No"),
                         value="Gaming: " + ("Yes" if self.gaming else "No"),
                         inline=True)
        noprev.add_field(name=ismulti, value="Viewers: " + str(self.viewers), inline=True)
        noprev.set_thumbnail(url=self.avatar)
        return noprev

    async def makeembed(self, snowflake=None, offline=False):
        """The embed used by the default message type. Same as the simple embed except for added preview of the stream.
        Generally this doesn't need to be overridden as it just adds the preview, which the preview property handles.

        :type snowflake: int
        :type offline: bool
        :rtype: discord.Embed
        :param snowflake: Integer representing a discord Snowflake
        :param offline: Do we need to adjust the time to account for basecontext.offlinewait?
        :return: a discord.Embed representing the current stream.
        """
        # Simple embed is the same, we just need to add a preview image. Save code
        myembed = await self.simpembed(snowflake, offline)
        myembed.set_image(url=self.preview_url)  # Add your image here
        return myembed

    async def detailembed(self, showprev=True):
        """Makes a detailed embed from the given record.

        :rtype: discord.Embed
        """
        raise NotImplementedError


parsed: Dict[str, StreamRecord] = {}


class APIContext:
    """Class that acts as a context for a dbcontext bot, that interacts with an API to track streams that come online
    and provide announcements to servers that have requested it. Attempts to keep functions general such that they can
    work for multiple APIs, and easy overrides for those changes which need to be made.

    :type instname: str
    :param instname: A string representing the name the context will be used as. Must be unique among all contexts.
    """
    defaultname = "template"  # This must be a unique name, used to identify this context

    # Is filled by discordbot with a handle to the client instance
    client = None  # type: LimitedClient
    # Do not use this to perform potentially disruptive actions. It is mostly used
    # for client.send_message and such in the currently available contexts.

    mydata = None  # Is filled by discordbot with a handle to the contexts stored data
    # This is a dict that is saved and reloaded by dbcontext. Any item saved in this
    # should be safe for pickling/unpickling via the pickle module.
    # Any data that does not need to be persistent across restarts does NOT need to
    # be contained here - this is just an easy place to store persistent data.

    getglobal = None  # Can be used to read options set by the manage context,
    # which should apply globally to all contexts. basecontext handles reading
    # from global as part of getoption.

    addglobal = None  # Can be used to add a new variable to the list of options that global will allow setting.

    conn = None  # Filled later with an aiohttp ClientSession for all our HTTP calls.

    recordclass = StreamRecord  # Class to instantiate API data with.

    sleeptime = 60  # How many seconds for the update loop to sleep for between updates

    maxlistens = 100  # The maximum amount of listens per server

    @property
    def apiurl(self):
        """URL to call to find online streams"""
        raise NotImplementedError("apiurl must be overridden in the subclass")

    @property
    def channelurl(self):
        """URL to call to get information on a single stream"""
        raise NotImplementedError("apiurl must be overridden in the subclass")

    @property
    def streamurl(self):
        """URL for going to watch the stream"""
        raise NotImplementedError("apiurl must be overridden in the subclass")

    def __init__(self, instname=None):
        # There are two values set by dbcontext after initializing the class:
        # self.mydata - contains the persistent data for this instance.
        # self.client - is a LimitedClient instance. It gives partial access to the running Discord.Client.
        if instname:
            self.name = instname
        else:
            self.name = self.defaultname
        self.parsed = parsed  # This should be replaced in the subclass
        self.lastupdate = lastupdate  # This should be replaced in the subclass
        self.defaultdata = {"AnnounceDict": {}, "Servers": {}, "COver": {}, "SavedMSG": {}}
        # This is merged into the dict that dbcontext creates for this context on load,
        # which is then stored in the mydata variable above.
        # Basically, it just sets up some default structures for use later. It can be
        # an empty dict, but these two options are currently used by every context to
        # store their info, and it's recommended to keep that usage the same if you're
        # doing a similar API based watch context, or at least the servers the same for
        # what servers to respond in and what channel to respond to in that server if
        # possible for your usage.

        # The first keeps streams to search for, with a !set! of servers that want that
        # info. For example, the twitch context would have info like this
        # AnnounceDict
        #   |-"AngriestPat"
        #       |-<ServerID>
        #   |-"WoolieVersus"
        #       |-<ServerID>
        #       |-<ServerID2>

        # The second keeps a dict of servers, that holds the dict with the options
        # they set, such as the channel to talk in, who they listen to, etc.
        # Servers
        #   |-<ServerID>
        #       |"AnnounceChannel": <ChannelID>
        #       |"Listens": set("AngriestPat","WoolieVersus")
        #   |-<ServerID2>
        #       |"AnnounceChannel": <ChannelID2>
        #       |"Listens": set("WoolieVersus")
        #       |"MSG": delete

        # Now there's a third, COver, which overriddes certain settings or acts as a
        # flag for the server in the context.
        # COver
        #  |-<ServerID> #Server ID for the settings
        #      |"Stop": True #Set of stop command used, unset by Listen.
        #      |-<recordid> #Stream to override context setting for
        #          |-"Option": #Holds a dict to hold option overrides in
        #              |-<optionname>: <optionvalue> #Holds the new value for the given option
        #              |-"Channel": <ChannelID> #Channel to announce in instead of listen channel

        # And now a fourth, SavedMSG. This is a dict that holds the discord ID of any
        # announcement messages saved. It's a dict of server ID, that each hold a
        # dict of <recordid>:<messageid>
        # SavedMSG
        #  |-<ServerID> #Server ID these messages are for
        #      |<Stream1>:<messageid>
        #      |<Stream2>:<messageid2>
        #  |-<ServerID2>
        #      |<Stream2>:<messageid3>

        # Again, these are not requirements, but recommended to simplify things. It means being able to subclass the
        # existing classes and use them mostly as is, and time savers are always nice.

    def savedata(self):
        """Used by dbcontext to get temporary data from the class prior to restart. If temp data is found on start, it
        will be sent to loaddata shortly after the bot starts, but before the background task updatewrapper is started.
        Return MUST evaluate as True but otherwise can be anything that pickle can handle, and will be returned as is.
        We return a partial dict from parsed, limited only to streams that are being watched. For twitch, this will be
        ALL of parsed, since it only REQUESTS streams that are being watched. Also includes a timestamp when the data
        was saved, checked when it's loaded.

        :return: Returns the data to be pickled, or False if there is no data to save. For basecontext, the return is a
        tuple with datetime.datetime.now, and the parsed dict.
        """
        data = {k: v for k, v in self.parsed.items() if k in self.mydata['AnnounceDict']}
        # print("savedata",data)
        if len(data) == 0:
            data["dbcontext"] = True
        if data:  # This should always be True now as we added a record if there weren't any.
            curtime = datetime.datetime.now(datetime.timezone.utc)
            return curtime, data
        return False

    def loaddata(self, saveddata):
        """Loads data previously saved by savedata and reintegrates it into self.parsed. Includes a check that the data
        is less than an hour old, and discards it if it is.

        :rtype: bool
        :type saveddata: (datetime.datetime,dict,dict)
        :param saveddata: A tuple with the time the data was saved, and a dict of streams that were online to be set as
        the parsed data.
        """
        curtime = datetime.datetime.now(datetime.timezone.utc)
        # If the saveddata is less than an hour old, we use it
        if (curtime - saveddata[0]) < datetime.timedelta(hours=1):
            if saveddata[1] == {"dbcontext": True}:
                # TODO This is empty, so we can ignore it, but we need to redo the updatewrapper to allow that.
                #  Possibly by setting self.lastupdate to some value that it could check. Maybe init to -4 so it
                #  immediately trips the 'API Down' status? Or -3 so it gets one more shot.
                pass
            self.parsed.update(saveddata[1])
            print(self.name, "loaded data successfully")
        else:
            print(self.name, "discarded old saveddata")
        return False

    async def getrecordid(self, record):
        """Gets the name of the record used to uniquely id the stream. Generally, record['name'] or possibly
        record['id']. Used to store info about the stream, such as who is watching and track announcement messages.
        MUST be overriden!

        :rtype: str
        :param record: A full stream record as returned by the API.
        :return: A string with the record's unique name.
        """
        raise NotImplementedError("getrecordid must be overridden in subclass!")

    async def savednames(self) -> AsyncGenerator[str]:
        """Yields all unique stream names which have a message id stored.
        """
        # This gets the name of any stream that has a saved msg. Used when first started to validate old SavedMSGs
        # savedstreams = set(
        #     [item for sublist in [self.mydata['SavedMSG'][k] for k in self.mydata['SavedMSG']] for item in sublist])
        found = set()
        for server in self.mydata['SavedMSG']:
            for stream in self.mydata['SavedMSG'][server]:
                if stream not in found:
                    yield stream
                    found.add(stream)

    async def savedids(self, recordname: str = None) -> AsyncGenerator[int]:
        """Returns a list of all message ids from SavedMSG. May be limited to one recordname

        :type recordname: str
        :param recordname: Name of record to grab all saved IDs for.
        """
        # This gets the guildid and msgid for any guild with a savedmsg for recordname and puts them into a new dict
        # which gets put into min(allsaved.values())
        # allsaved = {k: v[recordname] for (k, v) in self.mydata['SavedMSG'].items() if recordname in v}
        for server in self.mydata['SavedMSG']:
            for stream in self.mydata['SavedMSG'][server]:
                if recordname is None or stream == recordname:
                    yield self.mydata['SavedMSG'][server][stream]

    async def getmsgid(self, guildid, recordid):
        """Gets the snowflake for the message we used to announce the stream in the guild.

        :rtype: int | None
        :type guildid: int
        :type recordid: str
        :param guildid: Snowflake for the guild to find the announcement for.
        :param recordid: Name of the stream to find the announcement for.
        :return: The snowflake for the announcement message.
        """
        try:
            # We can't just use a .get(recordid,None) here because guildid might not exist and would still KeyError
            return self.mydata['SavedMSG'][guildid][recordid]
        except KeyError:  # Guild has no saved messages, or none for that record
            return None

    async def setmsgid(self, guildid, recordid, message: discord.Message = None):
        """Sets the snowflake for the message we used to announce the stream in the guild.

        :type guildid: int
        :type recordid: str
        :type message: discord.Message
        :param guildid: Snowflake for the guild to set the announcement for.
        :param recordid: Name of the stream to set the announcement for.
        :param message: The Message instance that we are moving from SavedMSG and the cache.
        """
        if guildid not in self.mydata['SavedMSG']:
            self.mydata['SavedMSG'][guildid] = {}
        self.mydata['SavedMSG'][guildid][recordid] = message.id
        await self.client.cacheadd(message)

    async def rmmsg(self, guildid, recordid, message: discord.Message = None, messageid: int = None):
        """Removes the saved message for the stream from SavedMSG and the cache. The messageid parameter is ignored by
        cacheremove if the message is provided. If neither is provided, it will attempt to grab the messageid from
        SavedMSG.

        :type guildid: int
        :type recordid: str
        :type message: discord.Message
        :type messageid: int
        :param guildid: Snowflake for the guild to set the announcement for.
        :param recordid: Name of the stream to set the announcement for.
        :param message: The Message instance that we are moving from SavedMSG and the cache.
        :param messageid: The snowflake for the announcement message.
        """
        oldid = None
        try:
            oldid = self.mydata['SavedMSG'][guildid].pop(recordid, None)
        except KeyError:  # Nothing saved for that stream, ignore it.
            pass
        if message is None and messageid is None:
            messageid = oldid
        if message or messageid:
            await self.client.cacheremove(message=message, messageid=messageid)

    async def resolvechannel(self, guildid, recordid=None, channelid=None):
        """Get the channel associated with this guild and recordid, or get the TextChannel instance for the given
         channelid.

        :rtype: discord.TextChannel | None
        :type guildid: int
        :type recordid: str
        :type channelid: int
        :param guildid: snowflake of guild
        :param recordid: String with the record name
        :param channelid: snowflake of channel - overrides any other option.
        :return: TextChannel instance or None if not found.
        """
        # If we're supplied with the channelid, use it to grab our TextChannel.
        if channelid:  # Used for channel override things currently.
            return self.client.get_channel(channelid)
        mydata = self.mydata  # Ease of use/potentially speed
        # Otherwise, try to look it up using a stream record and guild id
        if recordid:  # We have a stream name, see if it has an override
            try:
                newchan = mydata['COver'][guildid][recordid]['Option']['Channel']
                return self.client.get_channel(newchan)
            except KeyError:
                pass
        # No record given, or we failed to find a channel override for that record
        try:
            return self.client.get_channel(mydata["Servers"][guildid]["AnnounceChannel"])
        except KeyError:
            pass  # No announcement channel set
        # See if we have set the channel globally. If not, it returns None which
        # calling functions should check for.
        glob = await self.getglobal(guildid, 'Channel')
        return glob

    @staticmethod
    async def validatechannel(channelid, guild):
        """Resolves a Channel instance from the given id. The ID string can be a channel mention or the discord ID.

        :type channelid: str
        :type guild: discord.Guild
        :rtype: discord.Member | discord.User | None
        :param channelid: A string with the channel mention string, or the channel id.
        :param guild: discord Guild instance to search in. If not provided return can only be a User instance.
        :return: Searches the guild for the given channelid and returns the Channel instance, or None if not found.
        """
        # This is a mention string so we need to remove the mention portion of it.
        if channelid.startswith('<#'):
            channelid = channelid[2:-1]
        if '#' in channelid:
            founduser = discord.utils.find(lambda m: str(m) == channelid, guild.channels)
        else:
            founduser = discord.utils.find(lambda m: str(m.id) == channelid, guild.channels)
        return founduser

    async def getoption(self, guildid, option, recordid=None):
        """Gets the value for the option given, checking in order for one set on the stream, the module, or globally.

        :type guildid: int
        :type option: str
        :type recordid: str
        :rtype: None | str | bool | discord.Role
        :param guildid: Integer representing the snowflake of the Guild we're retrieving this option for.
        :param option:  String with the name of the option to retrieve.
        :param recordid: String with the name of the record to check for a stream override for the option.
        :return: None if no option with that name, or the value of option-dependant type that represents its current
        setting
        """
        mydata = self.mydata
        if recordid:
            try:  # Try and read the streams override option
                return mydata['COver'][guildid][recordid]['Option'][option]
            except KeyError:
                pass  # No override set for that stream, try the next place.
        try:  # Try to read an override for the option
            return mydata["COver"][guildid][option]
        except KeyError:
            pass  # No override set, try next.
        try:  # Try to read this guild's option in it's data
            return mydata["Servers"][guildid][option]
        except KeyError:
            pass  # Given option not set for this server, try the next place.
        # See if we have set the option globally. If not, it also handles the
        # default option value, or None if it doesn't have that either.
        glob = await self.getglobal(guildid, option)
        return glob

    async def setoption(self, guildid, optname, setting=None):
        """Sets or clears an option for the server.

        :type guildid: int
        :type optname: str
        :type setting: object
        :param guildid: The discord snowflake for the server this setting is for.
        :param optname: The name of the option group we're setting.
        :param setting: The value to set the option to, or None to clear. Type is dependant on the setting group.
        """
        mydata = self.mydata
        # If we have no setting, try and delete it.
        if setting is None:
            try:
                del mydata["Servers"][guildid][optname]
            except KeyError:  # Doesn't exist, so no need to do anything
                pass
            return True  # We're done here, leave
        # If we're actually setting one, we need to ensure the upper dicts exist
        if "Servers" not in mydata:
            mydata["Servers"] = {}
        if guildid not in mydata["Servers"]:
            mydata["Servers"][guildid] = {}
        else:
            # Finally, set the option group to the provided settings.
            mydata["Servers"][guildid][optname] = setting
        return True

    async def setstreamoption(self, guildid, optname, recordid, setting=None):
        """Sets or clears an option for the given stream for the given server.

        :type guildid: int
        :type optname: str
        :type recordid: str
        :type setting: str | int | bool | None
        :param guildid: The discord snowflake for the server this setting is for.
        :param optname: The name of the option group we're setting.
        :param recordid: The name of the stream this setting is for.
        :param setting: The value to set the option to, or None to clear. Type is dependant on the setting group.
        """
        mydata = self.mydata
        # We have no setting, try and delete it.
        if setting is None:
            try:
                del mydata['COver'][guildid][recordid]['Option'][optname]
            except KeyError:  # Doesn't exist, so no need to do anything
                pass
            return True  # We're done here, leave
        # We need to make sure all our needed dicts are created
        if 'COver' not in mydata:
            mydata['COver'] = {}
        if guildid not in mydata['COver']:
            mydata['COver'][guildid] = {}
        if recordid not in mydata['COver'][guildid]:
            mydata['COver'][guildid][recordid] = {}
        if 'Option' not in mydata['COver'][guildid][recordid]:
            mydata['COver'][guildid][recordid]['Option'] = {}
        # Now we know they exist, set the Option section to override our setting for the given option
        mydata['COver'][guildid][recordid]['Option'][optname] = setting
        return True

    @staticmethod
    async def streamtime(dur, offset=None, longtime=False):
        """Function to generate a string to say how long stream has lasted.

        :type dur: datetime.timedelta
        :type offset: int
        :type longtime: bool
        :rtype: str
        :param dur: timedelta representing the length of time.
        :param offset: Number of minutes to subtract from the duration, if supplied. Adjusts for the lapse between the
        time the stream goes offline, and when we generate this message.
        :param longtime: Do we want to use the long form of 'X hours, Y minutes', or the short form of 'Xh:YYm'
        :return: a string with the time the stream has ran for, in a long or short format.
        """
        if offset:
            dur -= datetime.timedelta(minutes=offset)
        hours, remainder = divmod(dur.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        if longtime:
            retstr = ""
            if hours:
                retstr += str(int(hours)) + " hour"
                if hours == 1:
                    retstr += ", "
                else:
                    retstr += "s, "
            retstr += str(int(minutes)) + " minute"
            if minutes == 1:
                retstr += "."
            else:
                retstr += "s."
            return retstr
        else:
            return "{0}h:{1:02d}m".format(int(hours), int(minutes))

    @staticmethod
    async def longertime(snowflake, rectime):
        """Finds the longer of two durations - the time since the snowflake, and the time since the stream came online,
        from getrectime. Returns a datetime.timedelta object.

        :type snowflake: int
        :type rectime: datetime.timedelta
        :rtype: datetime.timedelta
        :param snowflake: Integer representing a discord Snowflake
        :param rectime: A full stream record as returned by the API
        :return: The longer duration between when the snowflake was created and the time contained in the record.
        """
        dur = datetime.datetime.utcnow() - discord.utils.snowflake_time(snowflake)
        return max(rectime, dur)

    async def makemsg(self, record):
        """Short string to announce the stream is online, with stream URL.

        :rtype: str
        :type record: StreamRecord
        :param record: A full stream record as returned by the API
        :return: String with a short message and the link to watch the stream.
        """
        # Note we purposely stop the embed for the link - if we want an embed
        # we'll generate one ourself which is more useful than the default ones.
        return record.name + " has come online! Watch them at <" + self.streamurl.format(record.name) + ">"

    async def agetstream(self, recordid, headers=None):
        """Call our API with the getchannel URL formatted with the channel name. This is typically more detailed than
        the stream info provided by the online checks. Generalized to hopefully not need overriding by subclasses.

        :type recordid: str
        :type headers: dict
        :rtype: StreamRecord | bool | int | None
        :param recordid: String with the name of the stream, used to format the URL.
        :param headers: Headers to be passed on to the API call.
        :return: A dict with the information for the stream, exact content depends on the API. If acallapi failed, the
        error it returned is returned.
        """
        record = await self.acallapi(self.channelurl.format(recordid), headers)
        if record:  # We succeeded in calling the API, so transform the data into a StreamRecord.
            return self.recordclass(record, True)
        else:  # The call failed for some reason, so pass the error along.
            return record

    agetstreamoffline = agetstream

    async def acallapi(self, url, headers=None):
        """Calls the API at the given URL, with optional headers, and interprets the result via the JSON library.
        Returns the interpreted JSON on success, None if the attempt timed out, 0 if the API says the name wasn't found,
        and False if any other error occurs.

        :type url: str
        :type headers: dict
        :rtype: dict | bool | int | None
        :param url: URL to call
        :param headers: Headers to send with the request
        :return: The interpreted JSON result of the call if the call succeeded. On failure, the return will be None if
        the call timed out, 0 if a 404 error occured, or False for any other error.
        """
        # header is currently only needed by twitch, where it contains the API
        # key. For other callers, it is None.
        record = False  # Used for the return - default of False means it failed.
        try:
            async with self.conn.get(url, headers=headers) as resp:
                # print("acallapi",resp.status)
                if resp.status == 200:  # Success
                    buff = await resp.text()
                    # print(buff)
                    if buff:
                        record = json.loads(buff)  # Interpret the received data as JSON
                elif resp.status == 404:  # Not found
                    record = 0  # 0 means no matching record - still false
                elif resp.status == 401:  # Unauthorized
                    # Workaround for twitch, this causes it to re-request an Oauth
                    # token since ours is apparently bad.
                    try:
                        del self.mydata['OAuth']
                    except KeyError:  # Doesn't exist, ignore.
                        pass
                    record = False  # Ensure we don't return a record.
        # Ignore connection errors, and we can try again next update
        except aiohttp.ClientConnectionError:
            record = False  # Low level connection problems per aiohttp docs.
        except aiohttp.ClientConnectorError:
            record = False  # Also a connection problem.
        except aiohttp.ServerDisconnectedError:
            record = False  # Also a connection problem.
        except aiohttp.ServerTimeoutError:
            record = False  # Also a connection problem.
        except asyncio.TimeoutError:  # Exceeded the timeout we set for our connection.
            # Note the different return - timeouts explicitly return None so the
            # calling code can check if it wants to differentiate it.
            record = None
        except json.JSONDecodeError:  # Error in reading JSON - bad response from server?
            if buff.startswith("<!DOCTYPE html>"):
                # We got an HTML document instead of a JSON response. piczel does this
                # during maintenence, and it's not valid for anyone else either so might
                # as well catch it here, so we can supress this error.
                # Putting it here in the except instead of above means it only matters if
                # JSON decoding failed. Maybe it wouldn't always.
                return False  # We failed, return a false
            print("JSON Error in", self.name, "buff:", buff)  # Log this, since it shouldn't happen.
            record = False  # This shouldn't happen since status == 200
        return record

    async def updateparsed(self):
        """Calls the API and updates our parsed variable with the dict of currently online streams. Generalized so it
        should work for many APIs. Picarto and Piczel use this as-is.

        :rtype: tuple[bool, dict]
        :return: True on success, False if any error occurs.
        """
        updated = False  # Default value for success/failed
        newparsed = {}
        buff = await self.acallapi(self.apiurl)
        if buff:  # Any errors would return False (or None) instead of a buffer
            # Grab the new streams and store them in newparsed.
            newparsed = {await self.getrecordid(item): item for item in buff}
            updated = True  # Parse finished, we updated fine.
        # Update the tracking class with result of this attempt
        self.lastupdate.record(updated)
        return updated, newparsed

    async def updatewrapper(self, conn):
        """Sets a function to be run continuously every self.sleeptime seconds until the bot is closed. Handles errors
        that propagate outside of the called function to ensure the task doesn't stop prematurely.

        :type conn: aiohttp.ClientSession
        :param conn: ClientSession instance to be used for any HTTP calls, shared by all contexts.
        :return:
        """
        # Data validation should go here if needed for your mydata dict. This is
        # CURRENTLY only called once, when the bot is first started, but this may
        # change in future versions if the client needs to be redone.
        self.conn = conn  # Set our ClientSession reference for connections.
        # While we wait for the client to login, we can check our APIs
        try:
            if not self.parsed:  # We didn't have saved data loaded, so scrape
                updated, newrecs = await self.updateparsed()  # Start our first API scrape
                if updated:  # Update succeeded.
                    for stream in newrecs:  # Convert the JSON dicts into StreamRecords
                        self.parsed[stream] = self.recordclass(newrecs[stream])
                else:
                    print("Initial update of", self.name, "failed.")
                    if updated is False:
                        pass  # Generic error, do nothing here.
                    elif updated == 0:
                        print("Call had a 404 error.")
                    elif updated is None:
                        print("Call timed out.")
            else:
                # We make a record called dbcontext when saving if no other records exist, so we need to remove that.
                temp = self.parsed.pop("dbcontext", None)
                # It is possible though unlikely this is an ACTUAL stream, so if it's not True add it back in.
                # We could check for isinstance(StreamRecord) but this is easier and won't need changing on class change
                if temp and temp is not True:
                    self.parsed["dbcontext"] = temp
        except asyncio.CancelledError:
            # Task was cancelled, stop execution.
            return
        except Exception as error:
            # We catch any errors that happen on the first update and log them
            # It shouldn't happen, but we need to catch it or our wrapper would
            # break.
            print(self.name, "initial update error", self.name, repr(error))
        # Logs our starting info for debugging/check purposes
        print("Start", self.name, len(self.parsed))
        # By the time that's done our client should be setup and ready to go.
        # but we wait to make absolutely sure.
        await self.client.wait_until_ready()  # Don't start until client is ready
        # The above makes sure the client is ready to read/send messages and is
        # fully connected to discord. Usually, it is best to leave it in.
        # Now our client is ready and connected, let's check if our saved messages
        # are still online. If not, we need to pass it to removemsg.
        # Note that if the initial update fails, e.g. due to the API being down, this WILL remove all stream messages.
        # Waiting until the API updates successfully might be the best option, but that'd require too much reworking of
        # the update task, and this way they'll get announced when the API comes back. Also with the savedata function
        # now implemented it'll usually skip the first update anyway, and thus every stream would still be 'online'.
        # Step 1: Get a list of all stream names with a saved message
        async for stream in self.savednames():  # Now handled by an async generator
            # Step 2: Check if the stream is offline: not in self.parsed.
            if stream not in self.parsed:  # No longer online
                # print("savedstreams removing",stream)
                # Step 3: Send it to removemsg to edit/delete the message for everyone.
                await self.removemsg(record=None, recordid=stream)
        # If the stream is still online, the message for it will be updated in
        # 5 minutes, same as if it were just announced.
        # while not loop keeps a background task running until client closing
        while not self.client.is_closed():
            try:
                await asyncio.sleep(self.sleeptime)  # task runs every sleeptime seconds, set above
                await self.updatetask()  # The function that actually performs anything
            # This NEEDS to be first, as it must take priority
            # This could be Exception, or BaseException if Python 3.8+
            except asyncio.CancelledError:
                # Task was cancelled, stop execution.
                return
            # Error handling goes here. For now, we just print the error to console
            # then continue. We do NOT ignore BaseException errors - those stop us
            # since we're likely being shut down.
            except Exception as error:
                print(self.name, "wrapper:", repr(error))
                traceback.print_tb(error.__traceback__)

    async def updatetask(self):
        """Updates the API information and performs any necessary tasks with
        that info. This should handle the actual work portion of updating,
        with the wrapper merely ensuring that this is called and that errors
        are caught safely, without prematurely exiting the task.
        """
        if not self.client.is_closed():  # Don't run if client is closed.
            mydata = self.mydata  # Ease of use and speed reasons
            # oldlist = self.parsed  # Keep a reference to the old list
            updated, newparsed = await self.updateparsed()
            if not updated:
                # Updating from the API failed for some reason, likely it's down
                # Did it fail five times? If so, we should update messages.
                if self.lastupdate.failed == 5:
                    print(self.name, "API is down!")
                    for stream in self.parsed:
                        if stream in mydata['AnnounceDict']:
                            # Update messages with info that the API is down
                            await self.updatemsg(self.parsed[stream], True)
                return
            # print("Old Count:", len(oldlist),"Updated Count:", len(self.parsed))
            oldset = set(self.parsed)  # Set of names from current dict
            newset = set(newparsed)  # Set of names from new dict
            # Compare the old list and the new list to find new/removed items
            newstreams = newset - oldset  # Streams that just came online
            oldstreams = oldset - newset  # Streams that have gone offline
            curstreams = newset - newstreams  # Streams online that are not new
            # Stores the current UTC aware time
            curtime = datetime.datetime.now(datetime.timezone.utc)
            # Search through streams that have gone offline
            # DBCOffline is used to track streams that have gone offline or
            # have stayed online. Once the counter has hit a certain threshold
            # the stream is marked as needing announcements deleted/updated.
            for gone in oldstreams:
                # We only do this for streams someone is watching. Otherwise they
                # get dropped immediately.
                if gone in mydata['AnnounceDict']:
                    record = self.parsed[gone]  # Record from last update
                    if record.offlinetime:  # Was offline in a previous check
                        # print("removemsg",record,curtime)
                        # Check if streams been gone longer than offlinetime
                        if (curtime - record.offlinetime) >= datetime.timedelta(seconds=offlinetime):
                            # It's long enough that it's not a temporary disruption and send it to be removed.
                            # print("Removing",gone)
                            await self.removemsg(record)  # Need to potentially remove messages
                            del self.parsed[gone]
                    else:
                        # Stream is newly offline, record the current time
                        record.offlinetime = curtime
                        # We also update the stream to mark it potentially offline
                        await self.updatemsg(record)
                else:
                    del self.parsed[gone]
            for new in newstreams:
                # This is a new stream, see if someone is watching for it
                record = self.recordclass(newparsed[new])
                self.parsed[new] = record
                if new in mydata['AnnounceDict']:
                    # print("I should announce",record)
                    await self.announce(record)
                    # Store the current time in the new record
                    record.onlinetime = curtime
            for cur in curstreams:
                # Get the current record from our dict.
                record = self.parsed[cur]
                # TODO Change this to only update if stream is being watched? I could keep a separate timer that updates
                #  the unwatched streams every X minutes?
                # Update the record with the new information.
                record.update(newparsed[cur])
                if cur in mydata['AnnounceDict']:  # Someone is watching this stream
                    record.offlinetime = None  # Stream is online so remove the offlinetime value.
                    if record.onlinetime:  # This will exist most of the time.
                        # If it's been longer than updatetime seconds, update the stream
                        if (curtime - record.onlinetime) > datetime.timedelta(seconds=updatetime):
                            # print("I should update",record)
                            # It's time to update the stream
                            await self.updatemsg(record)
                            # Store the current time in the new record
                            record.onlinetime = curtime
                    else:
                        # The initial update doesn't set this, so we set it here.
                        record.onlinetime = curtime

    async def removemsg(self, record, serverlist=None, recordid=None):
        """Removes or edits the announcement message(s) for streams that have gone offline.

        :type record: StreamRecord | None
        :type serverlist: list[int]
        :type recordid: str
        :param record: A full stream record as returned by the API. Can be None if recordid is provided.
        :param serverlist: Snowflake for the server in which to give this announcement.
        :param recordid: String with the name of the stream, used if the full record is unavailable.
        """
        # Sending None for record is supported, in order to allow edit/removal of
        # offline streams - ie after the bot was offline. recordid MUST be given in
        # that case.
        mydata = self.mydata  # Ease of use and speed reasons
        # If we were provided with a record id, we don't need to find it.
        oldestid = None
        if not recordid:
            recordid = record.name
        else:  # If we don't have a record, we don't need to generate oldestid as it wouldn't be used anyway.
            try:
                oldestid = min([x async for x in self.savedids(recordid)])  # Find the id with the lowest value
                # We use that lowest value to help calculate how long the stream has
                # been running for. Ideally we'd always get that info from the API,
                # but it's not always available (like in picarto's), so we may need
                # to use the time the message was created instead.
            except ValueError:
                # min had no saved messages, we don't have any saved messages to update.
                # So we can just stop now and save time.
                return
        # We weren't given a list of servers to use, so grab the list of all servers who watch this stream
        if not serverlist:
            serverlist = mydata['AnnounceDict'][recordid]
        for server in serverlist:
            # Try to retreive our saved id
            msgid = await self.getmsgid(server, recordid)
            # We don't have a saved message for this, so do nothing.
            if not msgid:
                continue
            msgopt = await self.getoption(server, "MSG", recordid)
            # Check what we need to do based on the message type.
            if msgopt == "static":  # We don't do anything with static messages.
                await self.rmmsg(server, recordid, messageid=msgid)
                continue
            oldmess = await self.client.cacheget(msgid)
            if not oldmess:
                channel = await self.resolvechannel(server, recordid)
                if channel:  # We may not have a channel if we're no longer in the guild/channel
                    try:
                        oldmess = await channel.fetch_message(msgid)
                    except (discord.NotFound, discord.HTTPException, discord.Forbidden):
                        pass  # If it failed there's not much we can do about it. Either it's already gone or no access.
                else:
                    continue
            if not oldmess:  # We still didn't find the message, may be deleted.
                continue
            if msgopt == "edit":  # We should edit the message to say they're not online
                newembed = None
                # Simple would not have an old embed to use.
                if len(oldmess.embeds) > 0:
                    newembed = oldmess.embeds[0].to_dict()
                    if 'image' in newembed:  # Is there a stream preview?
                        # Delete preview as they're not online
                        del newembed['image']
                    # If we have the record, this is an online edit so we can update the time.
                    if record:
                        # We use oldest id to get the longest possible time this stream ran
                        # This matches how updatemsg sets the time.
                        newembed['title'] = await record.streammsg(oldestid, offset=True)
                    # If we don't, this is an offline edit. We can't get the time stream ran for, so just edit
                    # the current stored time and use that.
                    else:
                        newembed['title'] = newembed['title'].replace("running", "lasted")
                    newembed = discord.Embed.from_dict(newembed)
                newmsg = recordid + " is no longer online. Better luck next time!"
                try:
                    await oldmess.edit(content=newmsg, embed=newembed, suppress=False)
                except (discord.NotFound, discord.HTTPException, discord.Forbidden):
                    pass  # If it failed there's not much we can do about it. Either it's already gone or no access.
                except aiohttp.ServerDisconnectedError:  # Server disconnected attempting to update
                    pass  # Nothing we can do but ignore it. May setup retry logic later
                except aiohttp.ClientConnectorError:  # Connection failed
                    pass  # Again, not much to do.
                await self.client.cacheremove(messageid=msgid)
            # We should delete the message
            elif msgopt == "delete":
                try:
                    await oldmess.delete()
                except (discord.NotFound, discord.HTTPException, discord.Forbidden):
                    pass  # If it failed there's not much we can do about it. Either it's already gone or no access.
                except aiohttp.ServerDisconnectedError:  # Server disconnected attempting to update
                    pass  # Nothing we can do but ignore it. May setup retry logic later
                except aiohttp.ClientConnectorError:  # Connection failed
                    pass  # Again, not much to do.
            # Remove the msg from the list, we won't update it anymore.
            await self.rmmsg(server, recordid, messageid=msgid)

    async def updatemsg(self, record, apidown=False):
        """Updates an announcement with the current stream info, including run time.

        :type record: StreamRecord
        :type apidown: bool
        :param record: A full stream record as returned by the API
        :param apidown: Boolean which says if the API is currently down - message is adjusted if it is.
        """
        recordid = record.name  # Keep record name cached
        mydata = self.mydata  # Ease of use and speed reasons
        try:
            oldestid = min([x async for x in self.savedids(recordid)])  # Find the id with the lowest value
            # We use that lowest value to help calculate how long the stream has
            # been running for. Ideally we'd always get that info from the API,
            # but it's not always available (like in picarto's), so we may need
            # to use the time the message was created instead.
        except ValueError:  # No items in list - wrong/non-compareable types would be a TypeError.
            # min had no saved messages, we don't have any saved messages to update.
            # So we can just stop now and save time.
            return
        myembed = await record.makeembed(oldestid)
        noprev = await record.simpembed(oldestid)
        if apidown:
            apistring = "\n**The API appears to be down, unable to update.**"
            myembed.title += apistring
            noprev.title += apistring
        for server in mydata['AnnounceDict'][recordid]:
            # Get the saved msg for this server
            msgid = await self.getmsgid(server, recordid)
            # If we don't have a saved message, we can't update. May be deleted.
            # May not have been announced.
            if not msgid:
                continue
            # Get the options set for type of message, and if messages are edited
            typeopt = await self.getoption(server, "Type", recordid)
            # If Type is simple, there's nothing to edit so skip it.
            if typeopt == "simple":
                continue
            msgopt = await self.getoption(server, "MSG", recordid)
            # If MSG option is static, we don't update.
            if msgopt == "static":
                continue
            # Try and grab the old message we saved when posting originally
            oldmess = await self.client.cacheget(msgid)
            if not oldmess:
                channel = await self.resolvechannel(server, recordid)
                if channel:  # We may not have a channel if we're no longer in the guild/channel
                    try:
                        oldmess = await channel.fetch_message(msgid)
                    except discord.NotFound:
                        # Remove the saved msg - it was deleted already.
                        await self.rmmsg(server, recordid, messageid=msgid)
                    except (discord.HTTPException, discord.Forbidden):
                        pass  # If it failed there's not much we can do about it. Either it's already gone or no access.
                else:
                    continue
            if not oldmess:  # We still didn't find the message, may be deleted.
                continue
            if oldmess:
                msg = oldmess.content  # The text of the message - always present.
                # If the stream appears to be offline now, edit the announcement slightly.
                if record.offlinetime:
                    msg = msg.replace("has come online! Watch them", "was online")
                else:  # Not offline, ensure the message shows they're online
                    # This only matters if stream was offline for a short while, but won't
                    # hurt anything if the message is already correct.
                    msg = msg.replace("was online", "has come online! Watch them")
                if typeopt == "noprev":
                    thisembed = noprev
                else:
                    # Need to check if stream is adult, and what to do if it is.
                    adult = await self.getoption(server, 'Adult', recordid)
                    if record.adult and (adult != 'showadult'):
                        # hideadult or noadult, same as noprev option
                        thisembed = noprev
                    else:
                        # Otherwise show the preview
                        # print("updatemsg adding embed")
                        thisembed = myembed
                try:
                    await oldmess.edit(content=msg, embed=thisembed, suppress=False)
                except discord.NotFound:  # If the message was deleted but we had it in our cache, this could happen.
                    # Remove the old message from our records - it's gone.
                    await self.rmmsg(server, recordid, messageid=msgid)
                except (discord.Forbidden, aiohttp.ServerDisconnectedError, aiohttp.ClientConnectorError):
                    continue  # Nothing we can do but ignore it and retry it later. We don't update the cached version!
                oldmess.content = msg
                oldmess.embeds[0] = thisembed
                await self.client.cacheadd(oldmess)

    async def announce(self, record, oneserv=None):
        """Announce a stream. Limit announcement to 'oneserv' if given.

        :type record: StreamRecord
        :type oneserv: int
        :param record: A full stream record as returned by the API
        :param oneserv: Snowflake for the server in which to give this announcement.
        """
        mydata = self.mydata  # Ease of use and speed reasons
        # Make the embeds and the message for our announcement - done once no
        # matter how many servers we need to send it too. Note we should always
        # have at least one server, or else announce wouldn't have been called.
        myembed = await record.makeembed()  # Default style
        noprev = await record.simpembed()  # noprev style
        msg = await self.makemsg(record)
        recordid = record.name
        # We're going to iterate over a list of servers to announce on
        if oneserv:  # If given a server, that list is the one we were given
            # Generally, this is only used for the 'announce' command
            guildlist = [oneserv]
        else:  # Otherwise it's all servers that the stream has listed as listening
            guildlist = mydata['AnnounceDict'][recordid]
        # print("Made guildlist",guildlist,":",oneserv)
        for server in guildlist:
            # print("announce. found a server")
            if await self.getoption(server, 'Stop', recordid):
                # Channel was stopped, do not announce
                continue
            # print("announce. Wasn't stopped")
            adult = await self.getoption(server, 'Adult', recordid)
            if record.adult and (adult == 'noadult'):
                # This is an adult stream and channel does not allow those. Skip it.
                continue
            # print("announce. Not adult, or adult allowed")
            sentmsg = None  # Will hold the Message instance if sending succeeds.
            try:
                channel = await self.resolvechannel(server, recordid)
                if channel:  # Might not be in server anymore, so no channel
                    # At this point we've passed enough tests that the message
                    # is going to be sent
                    msgtype = await self.getoption(server, "Type", recordid)
                    notifyrole: discord.Role = await self.getoption(server, "Notify")
                    # print("announce notify",repr(notifyrole))
                    notemsg = ""
                    # revert = False
                    # If server is using notifications, mention it
                    if notifyrole:
                        # The bug that caused this seems to have been fixed.
                        # # If the role isn't mentionable, make it so to avoid a bug
                        # if not notifyrole.mentionable:
                        #     try:
                        #         await notifyrole.edit(mentionable=True)
                        #         revert = True
                        #     except discord.Forbidden:
                        #         pass
                        notemsg = notifyrole.mention + " "
                    # print("msgtype",msgtype)
                    if msgtype == "simple":  # simple type, no embed
                        sentmsg = await channel.send(notemsg + msg)
                    elif ((msgtype == "noprev")  # Embed without preview type
                          # default type, but adult stream and hide adult is set
                          or (record.adult and (adult == 'hideadult'))):
                        sentmsg = await channel.send(notemsg + msg, embed=noprev)
                    else:
                        # Default stream type, full embed with preview
                        sentmsg = await channel.send(notemsg + msg, embed=myembed)
                    # Again, no longer needed as bug was fixed.
                    # if revert:  # We need to revert the mentionable change - we MUST have a notifyrole if this is true
                    #     try:
                    #         await notifyrole.edit(mentionable=False)
                    #     except discord.Forbidden:
                    #         pass
            except KeyError as e:
                # We should've prevented any of these, so note that it happened.
                # Note there aren't even any key indices left in the above code
                # It'd have to have raised out of one of the awaits.
                print(self.name, "announce message keyerror:", repr(e))
                pass
            except discord.Forbidden:
                # We don't have permission to talk in the channel.
                pass
            # print("Sent",sentmsg)
            if sentmsg:
                await self.setmsgid(server, recordid, sentmsg)

    async def detailannounce(self, recordid, oneserv=None):
        """Provides a more detailed announcement of a stream for the detail command

        :type recordid: str
        :type oneserv: int
        :param recordid: A stream name to create a detailed announcement for.
        :param oneserv: Snowflake for the server in which to give this announcement.
        """
        # We should only call this with a specific server to respond to
        if not oneserv:
            return
        # Check we have a channel FIRST, to avoid an unneeded API call.
        channel = await self.resolvechannel(oneserv, recordid)
        if not channel:  # No channel was set, so we have nowhere to put the message.
            raise ChannelNotSet()
        # If we already have this record and it's a detailed record, use it instead.
        if recordid in self.parsed and self.parsed[recordid].detailed:
            record = self.parsed[recordid]
        else:
            record = await self.agetstream(recordid)
        # record is only none if the timeout was reached.
        if record is None:
            msg = "Timeout reached attempting API call; it is not responding. Please try again later."
            if not self.lastupdate:  # Note if the API update failed
                msg += "\n**Last attempt to update API also failed. API may be down.**"
            await channel.send(msg)
            return
        # Non-timeout error happened.
        if record is False:
            try:
                msg = "Sorry, I failed to load information about that channel due to an error. Please wait and try " \
                      "again later. "
                if not self.lastupdate:  # Note if the API update failed. Probably caught by the timeout error but JIC
                    msg += "\n**Last attempt to update API failed. API may be down.**"
                await channel.send(msg)
            except KeyError:  # Nothing left to have this but keep it for now.
                pass
            return  # Only announce on that server, then stop.
        if record == 0:  # API call returned a Not Found response
            msg = "The API found no users by the name. Check the name and spelling for errors and try again."
            # API being down wouldn't be the cause of this, so we're commenting these out. May reinstate them later.
            # if not self.lastupdate :  # Note if the API update failed
            #    msg += "\n**Last attempt to update API failed. API may be down.**"
            await channel.send(msg)
            return
        showprev = True
        if record.adult and (not (await self.getoption(oneserv, 'Adult', recordid) == 'showadult')):
            # We need to not include the preview from the embed.
            showprev = False
        # myembed = await self.makedetailembed(record, showprev=showprev)
        myembed = await record.detailembed(showprev)
        if myembed:  # Make sure we got something, rather than None/False
            # If the server isn't showadult, AND this is an adult stream
            await channel.send(embed=myembed)

    async def handler(self, command, message):
        """Handler function which is called by getcontext when invoked by a user. Parses the command and responds as
        needed.

        :type command: list
        :type message: discord.Message
        :param command: List of strings which represent the contents of the message, split by the spaces.
        :param message: discord.Message instance of the message which invoked this handler.
        """
        # print("TemplateHandler:", command, message)
        # This has help show if no specific command was given, or the help command
        # was specifically given. Useful to tell users how to work your context.
        mydata = self.mydata  # Ease of use and speed reasons
        if len(command) > 0 and command[0] != 'help':
            if command[0] == 'channel':
                # This sets the channel to perform announcements/bot responses to.
                if message.channel_mentions:
                    # Ensure the mentioned channel is in this guild, or else we don't accept it.
                    if message.channel_mentions[0].guild != message.guild:
                        await message.channel.send("I could not find " + message.channel_mentions[0].name +
                                                   " in this server.")
                        return
                    # Set the mentioned channel as the announcement channel
                    channelid = message.channel_mentions[0].id
                else:
                    # Set the channel the message was sent in as the announcement channel
                    channelid = message.channel.id
                if not (message.guild.id in mydata["Servers"]):
                    mydata["Servers"][message.guild.id] = {}  # Add data storage for server
                try:  # Try to delete the Stop override if it exists
                    del mydata['COver'][message.guild.id]['Stop']
                except KeyError:
                    pass  # If it doesn't, ignore it.
                mydata["Servers"][message.guild.id]["AnnounceChannel"] = channelid
                channel = await self.resolvechannel(message.guild.id, channelid=channelid)
                msg = "Ok, I will now use " + channel.mention + " for announcements."
                # Do we have permission to talk in that channel?
                if not channel.permissions_for(channel.guild.me).send_messages:
                    msg += "\nI **do not** have permission to send messages in that channel! Announcements will fail " \
                           "until permission is granted. "
                await message.channel.send(msg)
                return
            elif command[0] == 'stop':
                # Stop announcing - we set an override option named Stop to true
                if 'COver' not in mydata:  # We need to make the section
                    mydata['COver'] = {}  # New dict
                if message.guild.id not in mydata['COver']:  # Make server in section
                    mydata['COver'][message.guild.id] = {}
                # Set the override. Announce checks for this before announcing
                mydata['COver'][message.guild.id]['Stop'] = True
                msg = "Ok, I will stop announcing on this server."
                await message.channel.send(msg)
                return
            elif command[0] == 'resume':
                # Unset the Stop override - nothing else needed.
                try:  # Try to delete the Stop override if it exists
                    del mydata['COver'][message.guild.id]['Stop']
                except KeyError:
                    pass  # If it doesn't, ignore it.
                channel = await self.resolvechannel(message.guild.id)
                if channel:
                    msg = "I will resume announcements to " + channel.mention + "."
                else:
                    msg = "No announcement channel has been set, please set one with listen."
                await message.channel.send(msg)
                return
            elif command[0] == 'option':  # Moved to function
                await self.option(command, message)
                return
            elif command[0] == 'streamoption':  # Moved to function
                await self.streamoption(command, message)
                return
            elif command[0] == 'list':  # Moved to function
                await self.list(command, message)
                return
            elif command[0] == 'announce':  # Moved to function
                await self.announceall(command, message)
                return
            elif command[0] == 'add':  # Moved to function
                await self.add(command, message)
                return
            elif command[0] == 'remove':  # Moved to function
                await self.remove(command, message)
                return
            elif command[0] == 'detail':
                if len(command) == 1:  # No stream given
                    await message.channel.send("You must specify a stream name to show the detailed record for.")
                else:
                    try:
                        await self.detailannounce(command[1], message.guild.id)
                    except ChannelNotSet:
                        await message.channel.send(
                            "You must specify an announcement channel via the channel command before calling "
                            "detailannounce")
                return
        else:  # No extra command given, or unknown command
            # This is your help area, which should give your users an idea how to use
            # your context.
            if len(command) > 1:
                # This is for help with a specific command in this context
                if command[1] == 'option':
                    msg = "The following options are available:"
                    msg += "\nAnnouncement Type options:"
                    msg += "\ndefault: sets announcements messages to the default embedded style with preview."
                    msg += "\nnoprev: Use default embed style announcement but remove the stream preview image."
                    msg += "\nsimple: Use a non-embedded announcement message with just a link to the stream."
                    msg += "\nAnnouncement Editing options:"
                    msg += "\ndelete: Same as edit, except announcement is deleted when the stream goes offline."
                    msg += "\nedit: default option. Viewers and other fields are updated periodically. Message is " \
                           "changed when stream is offline. "
                    msg += "\nstatic: messages are not edited or deleted ever."
                    if self.name != 'twitch':  # Twitch doesn't have adult settings, so ignore.
                        msg += "\nAdult stream options:"
                        msg += "\nshowadult: default option. Adult streams are shown normally."
                        msg += "\nhideadult: Adult streams are announced but not previewed."
                        msg += "\nnoadult: Adult streams are not announced. Streams that are marked adult after " \
                               "announcement will have their previews disabled. "
                        msg += "\nThe adult options CAN NOT 100% shield your users from adult content. Forgetful " \
                               "streamers, API errors, bugs in the module, and old adult previews cached by the " \
                               "streaming site/discord/etc. may allow adult content through. "
                    await message.channel.send(msg)
            # The general help goes here - it should list commands or some site that
            # has a list of them
            else:
                msg = "The following commands are available for " + self.name + ":"
                msg += "\nlisten: starts announcing new streams in the channel it is said. Optionally, mention a " \
                       "channel and that channel will be used instead. "
                msg += "\nstop: stops announcing streams, edits to existing announcements will still occur."
                msg += "\nresume: resumes announcing streams."
                msg += "\noption <option(s)>: sets one or more space separated options. See help option for details " \
                       "on available options. "
                msg += "\nstreamoption <name> <option(s)>: overrides one or more space separated options for the " \
                       "given stream. If no options are provided, lists any overrides currently set. "
                msg += "\nadd <names>: adds new streams to announce, seperated by a space (any trailing commas are " \
                       "removed). Streams past the server limit of " + str(self.maxlistens) + " will be ignored. "
                msg += "\announce: immediately announces any online streams that were not previously announced."
                msg += "\nremove <names>: removes multiple new streams at once, seperated by a space."
                msg += "\ndetail <name>: Provides details on the given stream, including multi-stream participants, " \
                       "if applicable. Please note that certain options that affect announcements, like stop and " \
                       "noadult, are ignored. However, adult streams WILL NOT show a preview unless showadult is set. "
                msg += "\nlist: Lists the current announcement channel and all watched streams. Certain " \
                       "options/issues are also included when relevant. "
                msg += "\nSome commands/responses will not work unless an announcement channel is set."
                msg += "\nPlease note that all commands, options and stream names are case sensitive!"
                if not self.lastupdate:  # Note if the API update failed
                    msg += "\n**The last attempt to update the API failed!** The API may be down. This will cause " \
                           "certain commands to not work properly. Announcements will resume normally once the API " \
                           "is connectable. "
                await message.channel.send(msg)
            return

    async def add(self, command, message):
        """Adds streams to the list of watched streams for a guild.

        :param command: Command list passed from handler
        :param message: The discord.Message instance that invoked the handler.
        """
        mydata = self.mydata
        if not (message.guild.id in mydata["Servers"]):
            # Haven't created servers info dict yet, make a dict.
            mydata["Servers"][message.guild.id] = {}
        if not ("Listens" in mydata["Servers"][message.guild.id]):
            # No listens added yet, make a set
            mydata["Servers"][message.guild.id]["Listens"] = set()
        announced = False
        added = set()
        msg = ""
        notfound = set()
        # We're going to be setting a stream override, so make sure the needed dicts are in place.
        if message.channel_mentions:  # Channel mention, so make an override
            if message.channel_mentions[0].guild != message.guild:
                await message.channel.send("I could not find " + message.channel_mentions[0].name +
                                           " in this server.")
                return
            if 'COver' not in mydata:  # We need to make the section
                mydata['COver'] = {}  # New dict
            if message.guild.id not in mydata['COver']:
                mydata['COver'][message.guild.id] = {}
        for newstream in command[1:]:
            # print(newstream)
            if len(mydata["Servers"][message.guild.id]["Listens"]) >= self.maxlistens:
                msg += "Too many listens - limit is " + str(self.maxlistens) + " per server. Did not add " + newstream\
                       + " or later streams."
                break
            # If the name ends with a comma, strip it off. This allows
            # to copy/paste the result of the list command into add
            # to re-add all those streams.
            if newstream.endswith(','):
                newstream = newstream[:-1]
            newrecordid = ""  # String that holds the corrected stream name.
            # This is a channel mention, so don't try to add it as a stream
            if newstream.startswith('<#') and newstream.endswith('>'):
                pass  # We don't set newrecordid so it'll get skipped
            # Need to match case with the API name, so test it first
            # If we already are watching it, it must be the correct name.
            # OR if the stream is in parsed, it must be the correct name.
            elif (newstream not in mydata["AnnounceDict"]) and (newstream not in self.parsed):
                newrecord = await self.agetstreamoffline(newstream)
                # print(newrecord)
                if newrecord is None:
                    msg = "Timeout occured attempting to contact the API. Please try your request again later. "
                    # If a timeout occured we can't continue the loop - it'll just keep failing.
                    break
                if not newrecord:
                    notfound.add(newstream)
                else:
                    newrecordid = newrecord.name
            else:
                newrecordid = newstream
            # Stream does not exist on service, so do not add.
            if newrecordid:
                # This marks the stream as being listened to by the server
                if not (newrecordid in mydata["AnnounceDict"]):
                    mydata["AnnounceDict"][newrecordid] = set()
                mydata["AnnounceDict"][newrecordid].add(message.guild.id)
                # This marks the server as listening to the stream
                mydata["Servers"][message.guild.id]["Listens"].add(newrecordid)
                if message.channel_mentions:  # Channel mention, so make an override
                    if newrecordid not in mydata['COver'][message.guild.id]:
                        mydata['COver'][message.guild.id][newrecordid] = {}
                    # Set this servers stream override for this stream to the mentioned channel.
                    await self.setstreamoption(message.guild.id, 'Channel', newrecordid, message.channel_mentions[0].id)
                else:  # If we're not SETTING an override, delete it.
                    await self.setstreamoption(message.guild.id, 'Channel', newrecordid)
                added.add(newrecordid)
                # Haven't announced a stream yet and stream is online
                if (not announced) and (newrecordid in self.parsed):
                    try:
                        # Don't announce if we already have one
                        if not (await self.getmsgid(message.guild.id, newrecordid)):
                            await self.announce(self.parsed[newrecordid], message.guild.id)
                            announced = True  # We announced a stream, don't do another
                    except KeyError:
                        # traceback.print_tb(e.__traceback__)
                        pass  # Channel wasn't in dict, not online, ignore.
                    except ChannelNotSet:
                        pass
        if added:
            added = [*["**" + item + "**" for item in added if item in self.parsed],
                     *[item for item in added if item not in self.parsed]]
            added.sort()
            msg += "Ok, I am now listening to the following (**online**) streamers: " + ", ".join(added)
        if notfound:
            msg += "\nThe following streams were not found and could not be added: " + ", ".join(notfound)
        if not msg:
            msg += "Unable to add any streams due to unknown error."
        if not self.lastupdate:  # Note if the API update failed
            msg += "\n**The last attempt to update the API failed**, the API may be down. Please try your command " \
                   "again later. "
        channel = await self.resolvechannel(message.guild.id)
        if not channel:
            msg += "\nYou must set an announcement channel via the channel command before announcements will work!"
        await message.channel.send(msg)
        return

    async def list(self, command, message):
        """List options and current list of watched streams

        :param command: Command list passed from handler
        :param message: The discord.Message instance that invoked the handler.
        """
        mydata = self.mydata
        channel = await self.resolvechannel(message.guild.id)
        if channel:
            msg = "I am currently announcing in " + channel.mention + "."
        else:
            msg = "I am not currently set to announce streams in a channel. **Many commands will not work " \
                  "unless this is set!** "
        try:
            # Create list of watched streams, bolding online ones.
            newlist = []
            for item in mydata["Servers"][message.guild.id]["Listens"]:
                newitem = item
                if item in self.parsed:  # Stream is online
                    newitem = "**" + item + "**"
                try:  # See if we have an override set, and add it if so.
                    chan = await self.resolvechannel(message.guild.id,
                                                     channelid=mydata['COver'][message.guild.id][item]
                                                     ['Option']['Channel'])
                    if chan:
                        newitem += ":" + chan.mention
                except KeyError:
                    pass  # We may not have an override set, so ignore it.
                newlist.append(newitem)
            newlist.sort()
            msg += " Announcing for (**online**) streamers: " + ", ".join(newlist)
        except KeyError:  # If server doesn't even have a Listens, no watches
            msg += " No streams are currently set to be watched"
        msg += ".\nAnnouncement type set to "
        # Check our announcement type - default/noprev/simple.
        atype = await self.getoption(message.guild.id, 'Type')
        msg += atype + " and "
        # Check our message type - edit/delete/static.
        msgtype = await self.getoption(message.guild.id, 'MSG')
        msg += msgtype + " messages."
        # Do we show streams marked as adult? Not all streams support this
        adult = await self.getoption(message.guild.id, 'Adult')
        if adult == 'showadult':
            msg += " Adult streams are shown normally."
        elif adult == 'hideadult':
            msg += " Adult streams are shown without previews."
        elif adult == 'noadult':
            msg += " Adult streams will not be announced."
        else:  # There's only 3 valid options, this shouldn't activate
            # But ya know JIC.
            msg += "**WARNING!** Unknown option set for Adult streams! Please reset the adult option!"
        if not self.lastupdate:  # Note if the API update failed
            msg += "\n**Last " + str(self.lastupdate.failed) + " attempt(s) to update API failed.**"
        if await self.getoption(message.guild.id, 'Stop'):
            msg += "\nMessages are currently stopped via the stop command."
        await message.channel.send(msg)

    async def option(self, command, message):
        """Sets or clears one or more options for the server.

        :param command: Command list passed from handler
        :param message: The discord.Message instance that invoked the handler.
        """
        if len(command) == 1:
            msg = "No option provided. Please use the help menu for info on how to use the option command."
            await message.channel.send(msg)
            return
        msg = ""
        setopt = set()
        unknown = False
        for newopt in command[1:]:
            newopt = newopt.lower()
            if newopt == 'clear':  # Clear all out options
                for group in ('Type', 'MSG', 'Adult', 'Notify'):
                    await self.setoption(message.guild.id, group)
                setopt.add(newopt)
            elif newopt in ("default", "noprev", "simple"):
                await self.setoption(message.guild.id, "Type", newopt)
                setopt.add(newopt)
            elif newopt in ("delete", "edit", "static"):
                await self.setoption(message.guild.id, "MSG", newopt)
                setopt.add(newopt)
            elif newopt in ("showadult", "hideadult", "noadult"):
                await self.setoption(message.guild.id, "Adult", newopt)
                setopt.add(newopt)
            elif newopt in ("notify", "notifyoff"):
                if newopt == "notify":
                    await self.setoption(message.guild.id, "Notify", None)
                else:
                    await self.setoption(message.guild.id, "Notify", False)
            else:
                unknown = True
        if setopt:
            msg += "Options set: " + ", ".join(setopt) + ". "
        if unknown:
            msg += "One or more unknown options found. Please check the help menu for available options."
        await message.channel.send(msg)

    async def streamoption(self, command, message):
        """Sets or clears one or more options for a single watched stream in the server. If no options are given, it
        shows the currently set options for the given stream.

        :param command: Command list passed from handler
        :param message: The discord.Message instance that invoked the handler.
        """
        mydata = self.mydata
        if len(command) < 2:
            msg = "Command requires a stream name, or a stream name and option(s). Please use the help menu " \
                  "for info on how to use the streamoption command. "
            await message.channel.send(msg)
            return
        # If we're not listening to it right now, don't set the override.
        # This avoids mismatched capitalization from the user setting the
        # override on the wrong name.
        record = command[1]  # Name of stream
        if not (message.guild.id in mydata["Servers"]
                and record in mydata["Servers"][message.guild.id]["Listens"]):
            msg = record + "is not in your list of watched streams. Check spelling and capitalization and " \
                           "try again. "
            await message.channel.send(msg)
            return
        if len(command) == 2:  # No options given, just show current options
            msg = "No overrides exist for the given stream; all options will default to the server wide settings."
            try:
                options = {}
                # Copy the Options from the override to here,
                # we need to make a slight edit
                options.update(mydata['COver'][message.guild.id][record]['Option'])
                # print("streamoption",options)
                if 'Channel' in options:
                    foundchan = await self.resolvechannel(message.guild.id, channelid=options['Channel'])
                    if foundchan:
                        options['Channel'] = foundchan.mention
                msg = "\n".join([str(i[0]) + ": " + str(i[1]) for i in options.items()])
                msg = "The following overrides are set (Option: Setting) :\n" + msg
            except KeyError:
                pass
            await message.channel.send(msg)
            return
        msg = ""
        setopt = set()
        unknown = False
        for newopt in command[2:]:
            # Valid options are all lower case, or channel mentions, which have no
            # letters in them.
            newopt = newopt.lower()
            if newopt == 'clear':  # Clear all stream options
                try:
                    del mydata['COver'][message.guild.id][record]
                except KeyError:
                    pass
                setopt.add(newopt)
            # This is a channel mention, set the channel override
            elif newopt.startswith('<#') and newopt.endswith('>'):
                # Technically this might not be a valid channel if someone just types it up manually, though an
                # actual channel mention will always be a real channel, even if the bot can't necessarily see it
                chan = await self.validatechannel(newopt, message.guild)
                if chan:
                    await self.setstreamoption(message.guild.id, 'Channel', record, int(newopt[2:-1]))
                    setopt.add(newopt)
                else:
                    msg += "I was unable to find channel " + newopt + ". "
            elif newopt in ("default", "noprev", "simple"):
                await self.setstreamoption(message.guild.id, "Type", record, newopt)
                setopt.add(newopt)
            elif newopt in ("delete", "edit", "static"):
                await self.setstreamoption(message.guild.id, "MSG", record, newopt)
                setopt.add(newopt)
            elif newopt in ("showadult", "hideadult", "noadult"):
                await self.setstreamoption(message.guild.id, "Adult", record, newopt)
                setopt.add(newopt)
            elif newopt in ("notify", "notifyoff"):
                if newopt == "notify":
                    await self.setstreamoption(message.guild.id, "Notify", record, None)
                else:
                    await self.setstreamoption(message.guild.id, "Notify", record, False)
            else:
                # We had at least one unknown option
                unknown = True
        if setopt:
            msg += "Options set: " + ", ".join(setopt) + ". "
        if unknown:
            msg += "One or more unknown options found. Please check the help menu for available options."
        await message.channel.send(msg)

    async def remove(self, command, message):
        """Removes streams from the list of watched streams for a guild.

        :param command: Command list passed from handler
        :param message: The discord.Message instance that invoked the handler.
        """
        mydata = self.mydata
        if not (message.guild.id in mydata["Servers"]):
            # Haven't created servers info dict yet
            await message.channel.send("No streams are being listened to yet!")
            return
        if not ("Listens" in mydata["Servers"][message.guild.id]):
            # No listens added yet
            await message.channel.send("No streams are being listened to yet!")
            return
        added = set()
        msg = ""
        notfound = set()
        for newstream in command[1:]:
            # If the name ends with a comma, strip it off. This allows
            # to copy/paste the result of the list command into remove
            # to remove all those streams.
            if newstream.endswith(','):
                newstream = newstream[:-1]
            # print(newstream)
            try:
                mydata["AnnounceDict"][newstream].remove(message.guild.id)
                added.add(newstream)
                # If no one is watching that stream anymore, remove it
                if not mydata["AnnounceDict"][newstream]:
                    mydata["AnnounceDict"].pop(newstream, None)
            except ValueError:
                notfound.add(newstream)
                pass  # Value not in list, don't worry about it
            except KeyError:
                notfound.add(newstream)
                pass  # Value not in list, don't worry about it
            try:
                mydata["Servers"][message.guild.id]["Listens"].remove(newstream)
            except ValueError:
                pass  # Value not in list, don't worry about it
            except KeyError:
                pass  # Value not in list, don't worry about it
            # If 'delete' option set, delete any announcement for that stream.
            if ("MSG" in mydata["Servers"][message.guild.id]) and (
                    mydata["Servers"][message.guild.id]["MSG"] == "delete"):
                # This will delete announcement and clear savedmsg for us
                try:
                    await self.removemsg(parsed[newstream], [message.guild.id])
                except KeyError:  # If stream not online, parsed won't have record.
                    pass
            else:
                # We still need to remove any savedmsg and cached Message we have for this stream.
                await self.rmmsg(message.guild.id, newstream)
            # And remove any overrides for the stream
            try:
                del mydata['COver'][message.guild.id][command[1]]
            except KeyError:  # If any of those keys don't exist, it's fine
                pass  # Ignore it, because the override isn't set.
        if added:
            msg += "Ok, I will no longer announce the following streamers: " + ", ".join(added)
        if notfound:
            msg += "\nThe following streams were not found and could not be removed: " + ", ".join(notfound)
        if not msg:
            msg += "Unable to remove any streams due to unknown error."
        await message.channel.send(msg)

    async def announceall(self, command, message):
        """Gives announcements for any online streams missing them. Usually due to the bot being offline when the stream
        came online, though recent improvements should limit that.

        :param command: Command list passed from handler
        :param message: The discord.Message instance that invoked the handler.
        """
        mydata = self.mydata
        clive = 0  # Channels that are live
        canno = 0  # Channels that were announced
        # Iterate over all this servers' listens
        if not (message.guild.id in mydata["Servers"] and
                "Listens" in mydata["Servers"][message.guild.id]):
            await message.channel.send("Server is not listening to any streams!")
            return
        for item in mydata["Servers"][message.guild.id]["Listens"]:  # Iterate over servers watched streams
            if item in self.parsed:  # Stream is online
                clive = clive + 1  # Count of live watched streams
                # Make sure we have a savedmsg, we're going to need it
                if not (message.guild.id in mydata['SavedMSG']):
                    mydata['SavedMSG'][message.guild.id] = {}
                # Stream isn't listed, announce it
                if item not in mydata['SavedMSG'][message.guild.id]:
                    # print("Announcing",item)
                    await self.announce(self.parsed[item], message.guild.id)
                    canno = canno + 1  # Count of live watched streams that needed an announcement
        msg = "Found " + str(clive) + " live stream(s), found " + str(
            canno) + " stream(s) that needed an announcement."
        if await self.getoption(message.guild.id, 'Stop'):
            msg += "\nStop is currently enabled for this server - no announcements have been made. The " \
                   "'resume' command must be used to re-enable announcements. "
        if not self.lastupdate:  # Note if the API update failed
            msg += "\n**The last attempt to update API failed.** The API may be down. This will cause delays " \
                   "in announcing streams. Streams will be announced/edited/removed as needed when the API " \
                   "call succeeds. "
        await message.channel.send(msg)
