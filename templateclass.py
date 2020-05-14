# context to monitor an API for streams/uploads/etc.

# Note this module is INTENTIONALLY broken. Save it as your version then fix the
# syntax errors by inputting the proper values/commands/etc. Every single item in
# the class except __init__ NEEDS changes to work properly.

# import json  # Interpreting json results - updateparsed most likely needs this.
import discord  # The discord API module. Most useful for making Embeds
import asyncio  # Use this for sleep, not time.sleep.
import time  # Attaches to thumbnail URL to avoid discord's overly long caching
import datetime  # Stream durations, time online, etc.
import basecontext  # Base class for our API based context
import traceback  # Handles printing tracebacks for exceptions

parsed = {}  # Dict with key == 'user_name', filled by basecontext.updateparsed
lastupdate = basecontext.Updated()  # Class that tracks if update succeeded - empty if not successful


class TemplateContext(basecontext.APIContext):
    defaultname = "template"  # This is used to name this context and is the command
    # URL for going to watch the stream, gets called as self.streamurl.format(await self.getrecordid(record))
    streamurl = "http://www.example.com/{0}"
    # URL to call to update the list of online streams, used by updateparsed
    apiurl = "http://www.example.com/api/v1/"
    # URL to call to get detailed information about a specific channel, used by agetchannel
    channelurl = apiurl + "/channel/{0}"

    def __init__(self, instname=None):
        # Init our base class
        basecontext.APIContext.__init__(self, instname)
        # Our parsed is going to be the global parsed in our module, instead of the
        # basecontext parsed. This gets shared with ALL instances of this class.
        # Primarily this will sharing API response data with all instances.
        self.parsed = parsed  # Removing any of this isn't recommended.
        self.lastupdate = lastupdate  # Tracks if last API update was successful.
        # Adding stuff below here is fine, obviously.

    async def savedata(self):
        """Used by dbcontext to get temporary data from the class prior to restart. If temp data is found on start, it
        will be sent to loaddata shortly after the bot starts, but before the background task updatewrapper is started.
        Return MUST evaluate as True but otherwise can be anything that pickle can handle, and will be returned as is.
        """
        return False

    async def loaddata(self, saveddata):
        """Loads data previously saved by savedata and reintegrates it into self.parsed. Includes a check that the data
        is less than an hour old, and discards it if it is.
        """
        return True

    # Called to update the API data by basecontext's updatetask. When it's finished
    # parsed should have the current list of online channels.
    async def updatewrapper(self, conn):
        """Sets a function to be run continuously every 60 seconds until the bot
        is closed."""
        # Data validation should go here if needed for your mydata dict. This is
        # CURRENTLY only called once, when the bot is first started, but this may
        # change in future versions if the client needs to be redone.
        self.conn = conn  # Set our ClientSession reference for connections.
        # While we wait for the client to login, we can check our APIs
        try:
            if not self.parsed:  # We didn't have saved data loaded, so scrape
                await self.updateparsed()  # Start our first API scrape
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
        # while not loop keeps a background task running until client closing
        while not self.client.is_closed():
            try:
                await asyncio.sleep(60)  # task runs every 60 seconds
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

    async def updateparsed(self):
        """Updates the API information and performs any necessary tasks with
           that info. This should handle the actual work portion of updating,
           with the wrapper merely ensuring that this is called and that errors
           are caught safely, without prematurely exiting the task."""
        # basecontexts version can handle many cases now that it's been generalized
        # If you don't need any special handling of the call or output, can be deleted
        # Otherwise, this is where the bulk of your actual updating will go.
        pass

    # Gets the detailed information about a stream. Used for makedetailmsg.
    # It returns a stream record.
    async def agetstream(self, recordid, headers=None):
        # basecontexts version can handle most cases now that it's been generalized
        # If you don't need any special handling of the call or output, can be deleted
        # To see an example of overriding, look at piczel class, which needs to
        # modify the return a bit before passing it along.
        return await self.acallapi(self.channelurl.format(recordid), headers)

    async def getrecordid(self, record):
        # Should return the name of the record used to uniquely id the stream.
        # Generally, record['name'] or possibly record['id']. Used to store info about
        # the stream, such as who is watching and track announcement messages.
        return record['name']
