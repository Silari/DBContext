# DBContext
A discord.py based bot with module loading functions - aka contexts. Currently, this bot allows for announcing for Picarto.TV, Twitch.TV, and Piczel.TV streams on discord servers. Each is configured independently, allowing for each type to occupy their own channel with their own options if desired. A template is provided to create new contexts. Essentially, each module handles any command that uses the module name - ie. any command starting with picarto is given to the picartocontext module to handle. The dbcontext module manages the client instance, and provides a persistent data storage location which is saved periodically to dbcontext.bin via pickling.

Modules should be simple, easy to use, and not require excessive permissions. This is not an administration bot, and does not ask for any permissions beyond reading, writing, and editing messages, embedding in messages, adding reactions and emojis, and adding mentions to messages. This is little more than what the average user has by default. It also asks for role management permissions to add/remove the role permitting users to use the bot, but is not required.

### Prerequisites
If you simply wish to add the current instance of dbcontext to your server, check the instructions on [the project wiki.](https://github.com/Silari/DBContext/wiki)

If you wish to run your own instance, you must use Python 3.6 or 3.7, and have installed discord.py version 1.2.5. Typically, this can be done easily via pip. 

Linux/OS X

`python3 -m pip install -U discord.py`

Windows

`py -3 -m pip install -U discord.py`

### Installation
You will need the main dbcontext.py file, basecontext.py, and the three class files (picartoclass.py, twitchclass.py, and piczelclass.py) in the same directory. You will also need the apitoken.py file, and edit it to include your api tokens for Discord and twitch. Running the dbcontext.py file will start the bot.

If you wish to write your own context module, see templatecontext.py or templateclass.py for a basic framework example. The three current contexts also make for good examples of subclassing basecontext - they share a large portion of their code, with most differences in a few helper functions that deal with the slight changes in how their APIs function. Picartoclass in particular shows how little new code one needs to add over basecontext to create a functional module.

# Links
* [Discord.py GitHub repository](https://github.com/Rapptz/discord.py)
* [Discord Developer Portal, for creating your own bot and API key](https://discordapp.com/developers/docs/intro)
* [Twitch Developer Portal, for obtaining a Twitch API key](https://dev.twitch.tv/)

# License
This project is licensed under the MIT License - see the [LICENSE](https://github.com/Silari/DBContext/blob/master/LICENSE) file for details.
