#twitch context for discord bot for twitch API access.

import aiohttp
import urllib.request as request #Send HTTP requests
import json
import discord
import asyncio

parsed = {} #Dict with key == 'user_name'
defaultdata = {"AnnounceDict":{},"Servers":{},"Games":{}}
name = "twitch"
client = None #Is filled by discordbot with a handle to the discord client instance
mydata = None #Is filled by discordbot with a handle to the contexts stored data

import apitoken
twitchheader = apitoken.twitchheader

savedmsg = {} #Dict with Servers

def connect() :
    global parsed
    newrequest = request.Request('https://api.twitch.tv/helix/streams',headers=twitchheader)
    newconn = request.urlopen(newrequest)
    buff = newconn.read()
    parsed = {item['user_name']:item for item in json.loads(buff)['data']}
    return True

#Don't use - this fails due to too many calls needed to get all running streams
def gatherall() :
    global parsed
    morerecords = True
    after = None
    found = {}
    while morerecords :
        current = 'https://api.twitch.tv/helix/streams?first=100'
        if after :
            current += '&after=' + after
        newrequest = request.Request(current,headers=twitchheader)
        newconn = request.urlopen(newrequest)
        buff = newconn.read()
        loaded = json.loads(buff)
        found.update({item['user_name']:item for item in loaded['data']})
        after = loaded['pagination']['cursor']
        if after == None :
            morerecords = False
        #print(len(found), after)
    parsed = found
    return True

#Gets the detailed information about a channel, non-async. only for testing.
def getchannel(channelname) :
    try :
        newrequest = request.Request('https://api.twitch.tv/helix/users?login=' + channelname,headers=twitchheader)
        newconn = request.urlopen(newrequest)
        buff = newconn.read()
        if not buff :
            return False
        detchan = json.loads(buff)
        return detchan['data'][0]
    except :
        return False

#Gets the detailed information about a channel, may be offline or online
async def agetchannel(channelname) :
    try :
        async with aiohttp.request('GET','https://api.twitch.tv/helix/users?login=' + channelname,headers=twitchheader) as resp :
            buff = await resp.text()
            if not buff :
                return False
            detchan = json.loads(buff)
            resp.close()
        return detchan['data'][0]
    except :
        return False

#Gets the detailed information about a running stream
async def checkonline(channelname) :
    try :
        async with aiohttp.request('GET','https://api.twitch.tv/helix/streams?user_login=' + channelname,headers=twitchheader) as resp :
            buff = await resp.text()
            if not buff :
                return False
            detchan = json.loads(buff)
            resp.close()
        return detchan['data'][0]
    except :
        return False

#Gets the name of the game with gameid. Uses a caching system to prevent
#unneeded lookups.
async def getgame(gameid) :
    #For now, we just dont' know
    if gameid in mydata['Games'] :
        return mydata['Games'][gameid]
    try :
        async with aiohttp.request('GET','https://api.twitch.tv/helix/games?id=' + gameid,headers=twitchheader) as resp :
            buff = await resp.text()
            if not buff :
                return False
            detchan = json.loads(buff)['data'][0]
            resp.close()
        mydata['Games'][gameid] = detchan['name']
        return detchan['name']
    except Exception as e:
        print(repr(e))
        return "Error getting game name: gameid"
    #Find the name of the game using the twitch API here
    return "No name found: gameid"

#Can't get all live streams, far too many. Need to set up a different method
#Get all the currently watched streams (keys in AnnounceDict) and use the get
#streams API call with &user_login=<key1>&user_login=<key2> etc. max of 100
#for each request
#Return should be a list of only the ones that are online. So very similar to
#the picarto return, once the multiple requests are joined up.

def splitgroup(grouplist) :
    count = 0
    while count < len(grouplist) :
        yield [x for x in grouplist][count:count+100]
        count += 100

async def updateparsed() :
    global parsed
    apiurl = 'https://api.twitch.tv/helix/streams?user_login='
    found = {}
    for checkgroup in splitgroup(mydata['AnnounceDict']) :
        #print("Group:",checkgroup)
        newrequest = request.Request(apiurl + "&user_login=".join(checkgroup),headers=twitchheader)
        newconn = request.urlopen(newrequest)
        buff = newconn.read()
        #print("Buff:",buff)
        loaded = json.loads(buff)
        found.update({item['user_name']:item for item in loaded['data']})
    parsed = found

async def makeembed(rec) :
    description = rec['title']
    myembed = discord.Embed(title=rec['user_name'] + " has come online!",url="https://twitch.tv/" + rec['user_name'],description=description)
    myembed.add_field(name="Game: " + await getgame(rec['game_id']),value="Viewers: " + str(rec['viewer_count']),inline=True)
    #myembed.add_field(name=value,value="Gaming: " + ("Yes" if rec['gaming'] else "No"),inline=True)
    myembed.set_image(url=rec['thumbnail_url'].replace("{width}","848").replace("{height}","480"))
    return myembed

async def simpembed(rec) :
    description = rec['title']
    noprev = discord.Embed(title=rec['user_name'] + " has come online!",url="https://twitch.tv/" + rec['user_name'],description=description)
    noprev.add_field(name="Game: " + await getgame(rec['game_id']),value="Viewers: " + str(rec['viewer_count']),inline=True)
    return noprev

async def updatewrapper() :
    await client.wait_until_ready() #Don't start until client is ready
    #print("Starting connect")
    await updateparsed() #Start our first Twitch scrape
    print("Start Twitch:",len(parsed))
    #print(mydata)
    while not client.is_closed() :
        try :
            await asyncio.sleep(60) # task runs every 60 seconds
            await updatetwitch()
        except Exception as error :
            print("Twrap:", repr(error))
        except asyncio.CancelledError :
            #Task was cancelled, so just stop.
            pass

async def updatetwitch() :
    if not client.is_closed(): #Keep running until client stops
        oldlist = parsed
        await updateparsed()
        oldset = set(oldlist)
        newset = set(parsed)
        #print("Old:",oldset,"New:",newset)
        #Compare the old list and the new list to find new/removed items
        newchans = newset - oldset #Channels that just came online
        oldchans = oldset - newset #Channels that have gone offline
        curchans = newset - newchans #Channels online that are not new - update
        removed = [] #List of channels too old and thus removed
        #Search through channels that have gone offline
        for gone in oldchans :
            rec = oldlist[gone] #Record from last update
            if 'PWOffline' in rec : #Has been offline in a previous check
                rec['PWOffline'] += 1
            else :
                rec['PWOffline'] = 1 #Has just gone offline
            if rec['PWOffline'] < 10 :
                #If the channel has not been gone the last ten updates, add it
                parsed[gone] = rec
            else :
                #Otherwise we assume it's not a temporary disruption and add it
                #to our list of channels that have been removed
                removed.append(gone)
        for new in newchans :
            #This should always be the case as our list is built FROM announcedict
            if new in mydata['AnnounceDict'] :
                rec = parsed[new]
                #print("I should announce",rec)
                await announce(rec)
        for new in curchans :
            if new in mydata['AnnounceDict'] : #Someone is watching this channel
                oldrec = oldlist[new]
                rec = parsed[new]
                #print("I should announce",rec)
                if 'PWOffline' in oldrec : #Has been offline in a previous check
                    if oldrec['PWOffline'] >= 4 :
                        #Update the channel every 5 minutes.
                        await updatemsg(rec)
                    else :
                        rec['PWOffline'] = oldrec['PWOffline'] + 1
                else :
                    rec['PWOffline'] = 1 #Has just gone offline
        for old in removed :
            if old in mydata['AnnounceDict'] : #Someone is watching this channel
                #print("Removing",old)
                rec = oldlist[old]
                await removemsg(rec) #Need to remove those messages from savedmsg
    return

async def removemsg(rec) :
    for server in mydata['AnnounceDict'][rec['name']] :
        try :
            #We should edit the message to say they're not online
            if not ("MSG" in mydata["Servers"][server]) or mydata["Servers"][server]["MSG"] == "edit" :
                channel = client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                oldmess = await channel.fetch_message(savedmsg[server][rec['name']])
                #newembed = discord.Embed.from_data(oldmess.embeds[0])
                #New method for discord.py 1.0+
                newembed = oldmess.embeds[0]
                newmsg = rec['name'] + " is no longer online. Better luck next time!"
                await oldmess.edit(content=newmsg,embed=newembed)
            #We should delete the message
            elif mydata["Servers"][server]["MSG"] == "delete" :
                channel = client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                oldmess = await channel.fetch_message(savedmsg[server][rec['name']])
                await oldmess.delete()
        except Exception as e :
            #print("RM",repr(e))
            pass
        #Remove the msg from the list, we won't update it anymore.
        try : #They might not have a message saved, ignore that
            del savedmsg[server][rec['name']]
        except :
            pass

async def updatemsg(rec) :
    #print("Updating",rec['name'])
    myembed = await makeembed(rec)
    noprev = await simpembed(rec)
    for server in mydata['AnnounceDict'][rec['name']] :
        #If Type is simple, don't do this
        if "Type" in mydata["Servers"][server] and mydata["Servers"][server]["Type"] == "simple" :
            pass
        #If MSG option is static, we don't update.
        elif "MSG" in mydata["Servers"][server] and mydata["Servers"][server]["MSG"] == "static" :
            pass
        else :
            #Try and grab the old message we saved when posting originally
            oldmess = None
            try :
                channel = client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                oldmess = await channel.fetch_message(savedmsg[server][rec['name']])
            except KeyError as e:
                #print("1",repr(e))
                pass #Server no longer has an announce channel set, or message
                #wasn't sent for this channel. Possibly bot was offline.
            except Exception as e:
                #Can happen if message was deleted - NOT FOUND status code 404
                #print("2",repr(e))
                pass
            if oldmess :
                try :
                    channel = client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
                    if "Type" in mydata["Servers"][server] and mydata["Servers"][server]["Type"] == "noprev" :
                            await oldmess.edit(content=oldmess.content,embed=noprev)
                    else :
                        await oldmess.edit(content=oldmess.content,embed=myembed)
                except Exception as e:
                    #print("3",repr(e))
                    pass

async def announce(rec,oneserv=None) :
    '''Announce a twitch stream. Limit announcement to 'server' if given.'''
    myembed = await makeembed(rec)
    noprev = await simpembed(rec)
    msg = rec['user_name'] + " has come online! Watch them at <" + "https://twitch.tv/" + rec['user_name'] + ">"
    if oneserv :
        try :
            channel = client.get_channel(mydata["Servers"][oneserv]["AnnounceChannel"])
            if "Type" in mydata["Servers"][oneserv] :
                if mydata["Servers"][oneserv]["Type"] == "simple" :
                    sentmsg = await channel.send(msg)
                elif mydata["Servers"][oneserv]["Type"] == "noprev" :
                    sentmsg = await channel.send(msg,embed=noprev)
                else :
                    sentmsg = await channel.send(msg,embed=myembed)
            else :
                sentmsg = await channel.send(msg,embed=myembed)
        except KeyError :
            pass
        if sentmsg :
            if not (oneserv in savedmsg) :
                savedmsg[oneserv] = {}
            savedmsg[oneserv][rec['user_name']] = sentmsg.id
        return #Only announce on that server, then stop.
    for server in mydata['AnnounceDict'][rec['user_name']] :
        try :
            channel = client.get_channel(mydata["Servers"][server]["AnnounceChannel"])
            if "Type" in mydata["Servers"][server] :
                if mydata["Servers"][server]["Type"] == "simple" :
                    sentmsg = await channel.send(msg)
                elif mydata["Servers"][server]["Type"] == "noprev" :
                    sentmsg = await channel.send(msg,embed=noprev)
                else :
                    sentmsg = await channel.send(msg,embed=myembed)
            else :
                sentmsg = await channel.send(msg,embed=myembed)
            #await channel.send(msg)
        except KeyError :
            pass #Server has no announcement channel set
        if sentmsg :
            if not (server in savedmsg) :
                savedmsg[server] = {}
            savedmsg[server][rec['user_name']] = sentmsg.id

async def detailannounceoffline(name,oneserv=None) :
    rec = await agetchannel(name)
    if not rec :
        try :
            msg = "Sorry, I failed to load information about that channel from twitch. Check your spelling and try again."
            channel = client.get_channel(mydata["Servers"][oneserv]["AnnounceChannel"])
            await channel.send(msg)
        except KeyError :
            pass
        return
    description = rec['description'][:150]
    myembed = discord.Embed(title=rec['display_name'] + " is not currently streaming.",description=description)
    myembed.add_field(name="Viewers:",value=rec['view_count'])
    myembed.set_thumbnail(url=rec['profile_image_url'])
    if oneserv :
        try :
            channel = client.get_channel(mydata["Servers"][oneserv]["AnnounceChannel"])
            await channel.send(embed=myembed)
        except KeyError :
            pass
        return #Only announce on that server, then stop.

async def detailannounce(name,oneserv=None) :
    #For now we should only call this with a specific server to respond to
    if not oneserv :
        return
    rec = await checkonline(name)
    if not rec :
        #Stream isn't online, attempt to get offline info
        await detailannounceoffline(name,oneserv)
        return
    description = rec['title']
    myembed = discord.Embed(title=rec['user_name'] + " has come online!",url="https://twitch.tv/" + rec['user_name'],description=description)
    myembed.add_field(name="Game: " + await getgame(rec['game_id']),value="Viewers: " + str(rec['viewer_count']),inline=True)
    #myembed.add_field(name=value,value="Gaming: " + ("Yes" if rec['gaming'] else "No"),inline=True)
    myembed.set_image(url=rec['thumbnail_url'].replace("{width}","848").replace("{height}","480"))
    msg = rec['user_name'] + " has come online! Watch them at <" + "https://twitch.tv/" + rec['user_name'] + ">"
    noprev = discord.Embed(title=rec['user_name'] + " has come online!",url="https://twitch.tv/" + rec['user_name'],description=description)
    noprev.add_field(name="Game: " + await getgame(rec['game_id']),value="Viewers: " + str(rec['viewer_count']),inline=True)
    if oneserv :
        try :
            channel = client.get_channel(mydata["Servers"][oneserv]["AnnounceChannel"])
            await channel.send(embed=myembed)
        except KeyError :
            pass
        return #Only announce on that server, then stop.

#Checks that needed structures exist
#twitch context handler
async def handler(command, message) :
    #print("THandler:", command, message)
    if len(command) > 0 and command[0] != 'help' :
        if command[0] == 'listen' :
            #Set the channel the message was sent in as the Announce channel
            if not (message.guild.id in mydata["Servers"]) :
                mydata["Servers"][message.guild.id] = {} #Add data storage for server
            mydata["Servers"][message.guild.id]["AnnounceChannel"] = message.channel.id
            msg = "Ok, I will now start announcing in this server, using this channel."
            await message.channel.send(msg)
        elif command[0] == 'stop' :
            #Stop announcing - just remove the AnnounceChannel option
            try :
                del mydata["Servers"][message.guild.id]["AnnounceChannel"]
            except KeyError :
                pass #Not listening, so skip
            msg = "Ok, I will stop announcing on this server."
            await message.channel.send(msg)
        elif command[0] == 'option' :
            if len(command) == 1 :
                msg = "No option provided. Please use the help menu for info on how to use the option command."
                await message.channel.send(msg)
                return
            msg = ""
            setopt = set()
            unknown = False
            for newopt in command[1:] :
                if newopt in ("default","noprev","simple") :
                    if not (message.guild.id in mydata["Servers"]) :
                        #Haven't created servers info dict yet, make a dict.
                        mydata["Servers"][message.guild.id] = {}
                    mydata["Servers"][message.guild.id]["Type"] = newopt
                    setopt.add(newopt)
                    #await message.channel.send(msg)
                elif newopt in ("delete","edit","static") :
                    if not (message.guild.id in mydata["Servers"]) :
                        #Haven't created servers info dict yet, make a dict.
                        mydata["Servers"][message.guild.id] = {}
                    mydata["Servers"][message.guild.id]["MSG"] = newopt
                    setopt.add(newopt)
                    #await message.channel.send(msg)
                else :
                    unknown = True #msg = "Unknown option provided. Please use the help menu for info on how to use the option command."
                    #await message.channel.send(msg)
            if setopt :
                msg += "Options set: " + ", ".join(setopt) + ". "
            if unknown :
                msg += "One or more unknown options found. Please check the help menu for available options."
            await message.channel.send(msg)
        elif command[0] == 'list' :
            #List options and current listening channels
            msg = ""
            try :
                msg = "I am currently announcing in " + client.get_channel(mydata["Servers"][message.guild.id]["AnnounceChannel"]).name + "."
            except KeyError :
                msg = "I am not currently set to announce streams in a channel."
            try :
                #Create list of watched channels, bolding online ones.
                newlist = [*["**" + item + "**" for item in mydata["Servers"][message.guild.id]["Listens"] if item in parsed], *[item for item in mydata["Servers"][message.guild.id]["Listens"] if not item in parsed]]
                newlist.sort()
                msg += " Announcing for (**online**) streamers: " + ", ".join(newlist)
            except :
                msg += " No streamers are currently set to be watched."
            msg += ".\nAnnouncement type set to "
            try :
                if not ('Type' in mydata["Servers"][message.guild.id]) :
                    msg += "default with "
                else :
                    msg += mydata["Servers"][message.guild.id]['Type'] + " with "
            except KeyError :
                msg += "default with "
            try :
                if not ('MSG' in mydata["Servers"][message.guild.id]) :
                    msg += "edit messages."
                else :
                    msg += mydata["Servers"][message.guild.id]['MSG'] + " messages."
            except KeyError :
                msg += "edit messages."
            await message.channel.send(msg)
        elif command[0] == 'add' :
            if not (message.guild.id in mydata["Servers"]) :
                #Haven't created servers info dict yet, make a dict.
                mydata["Servers"][message.guild.id] = {}
            if not ("Listens" in mydata["Servers"][message.guild.id]) :
                #No listens added yet, make a set
                mydata["Servers"][message.guild.id]["Listens"] = set()
            if len(mydata["Servers"][message.guild.id]["Listens"]) >= 100 :
                    msg = "Too many listens already - limit is 100 per server."
                    await message.channel.send(msg)
                    return
            #Need to match case with the twitch name, so test it first
            if not command[1] in mydata["AnnounceDict"] :
                newrec = await agetchannel(command[1])
                if not newrec :
                    msg = "No twitch stream found with that user name. Please check spelling and try again."
                    await message.channel.send(msg)
                    return
                else :
                    command[1] = newrec["display_name"]
                    #Haven't used this channel anywhere before, make a set for it
                    mydata["AnnounceDict"][command[1]] = set()
            #This marks the channel as being listened to by the server
            mydata["AnnounceDict"][command[1]].add(message.guild.id)
            #This marks the server as listening to the channel
            mydata["Servers"][message.guild.id]["Listens"].add(command[1])
            msg = "Ok, I will now announce when " + command[1] + " comes online."
            await message.channel.send(msg)
            try :
                #Announce the given user is online if the record exists.
                #Only happens if another server is already watching them,
                #but can still happen. DO NOT REMOVE.
                await announce(parsed[command[1]],message.guild.id)
            except KeyError : #If they aren't online, silently fail.
                pass
        elif command[0] == 'addmult' :
            if not (message.guild.id in mydata["Servers"]) :
                #Haven't created servers info dict yet, make a dict.
                mydata["Servers"][message.guild.id] = {}
            if not ("Listens" in mydata["Servers"][message.guild.id]) :
                #No listens added yet, make a set
                mydata["Servers"][message.guild.id]["Listens"] = set()
            added = set()
            msg = ""
            notfound = set()
            for newchan in command[1:] :
                if len(mydata["Servers"][message.guild.id]["Listens"]) >= 100 :
                    msg += "Too many listens - limit is 100 per server. "
                    break
                #Need to match case with the twitch name, so test it first
                if not newchan in mydata["AnnounceDict"] :
                    newrec = await agetchannel(command[1])
                    if not newrec :
                        notfound.add(newchan)
                    else :
                        newchan = newrec["display_name"]
                    #Haven't used this channel anywhere before, make a set for it
                    mydata["AnnounceDict"][newchan] = set()
                if newrec :
                    #This marks the channel as being listened to by the server
                    mydata["AnnounceDict"][newchan].add(message.guild.id)
                    #This marks the server as listening to the channel
                    mydata["Servers"][message.guild.id]["Listens"].add(newchan)
                    added.add(newchan)
            if newlist :
                newlist = [*["**" + item + "**" for item in added if item in parsed], *[item for item in added if not item in parsed]]
                newlist.sort()
                msg += "Ok, I am now listening to the following (**online**) streamers: " + ", ".join(newlist)
            if notfound :
                msg += "\nThe following channels were not found and could not be added: " + ", ".join(notfound)
            if not msg :
                msg += "Unable to add any channels due to unknown error."
            await message.channel.send(msg)
        elif command[0] == 'remove' :
            if command[1] in mydata["AnnounceDict"] :
                try :
                    mydata["AnnounceDict"][command[1]].remove(message.guild.id)
                    #If no one is watching that channel anymore, remove it
                    #This saves on calls to the twitch API for watched channels
                    if not mydata["AnnounceDict"][command[1]] :
                        mydata["AnnounceDict"].pop(command[1],None)
                except ValueError :
                    pass #Value not in list, don't worry about it
                except KeyError :
                    pass #Value not in list, don't worry about it
                try :
                    mydata["Servers"][message.guild.id]["Listens"].remove(command[1])
                except ValueError :
                    pass #Value not in list, don't worry about it
                except KeyError :
                    pass #Value not in list, don't worry about it
            msg = "Ok, I will no longer announce when " + command[1] + " comes online."
            await message.channel.send(msg)
        elif command[0] == 'detail' :
            if len(command) == 1 : #No channel given
                await message.channel.send("You need to specify a user!")
            else :
                await detailannounce(command[1],message.guild.id)
    #if command[0] == 'help' :
    else : #No extra command given, or unknown command
        if len(command) > 1 :
            if command[1] == 'option' :
                msg = "The following options:"
                msg += "\ndefault: sets announcements messages to the default embedded style with preview."
                msg += "\nnoprev: Use default embed style announcement but remove the stream preview image."
                msg += "\nsimple: Use a non-embedded announcement message with just a link to the stream."
                msg += "\nAnnouncement Editing options:"
                msg += "\ndelete: Same as edit, except announcement is deleted when the channel goes offline."
                msg += "\nedit: default option. Viewers and other fields are updated periodically. Message is changed when channel is offline."
                msg += "\nstatic: messages are not edited or deleted ever."
                await message.channel.send(msg)
                #msg += "\n"
        else :
            msg = "The following commands are available for twitch:"
            msg += "\nlisten: starts announcing new streams in the channel it is said."
            msg += "\nstop: stops announcing streams and removes the announcement channel."
            msg += "\noption: sets ONE of the following options: default, noprev, simple. See help option for details."
            msg += "\nadd <name>: adds a new streamer to announce. Limit of 100 channels per server."
            msg += "\naddmult <names>: adds multiple new streams at once, seperated by a space. Channels past the server limit will be ignored."
            msg += "\nremove <name>: removes a streamer from announcements."
            msg += "\ndetail <name>: Provides details on the given channel. Note that offline streams lack info."
            msg += "\nlist: Lists the current announcement channel and all listened streamer."
            msg += "\nSome commands/responses will not work unless an announcement channel is set."
            msg += "\nPlease note that all commands, options and channel names are case sensitive!"
            await message.channel.send(msg)
