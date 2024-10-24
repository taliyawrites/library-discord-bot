import discord
import os
import datetime
import random
import string
import asyncio
import time
import calendar
import traceback
import json


from dotenv import load_dotenv
from discord.ext import tasks
from pyairtable import Api


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = int(os.getenv('GUILD_ID'))
GENERAL = int(os.getenv('GENERAL_CHANNEL'))
OPTIONS_ROLE = int(os.getenv('ROLE_ID_OPTIONS'))
WINNER_ROLE = int(os.getenv('ROLE_ID_WINNER'))
airtable_api = Api(os.getenv('AIRTABLE_TOKEN'))

WINNERS_FILENAME = "recentwinners.txt"
AUDIOS_FILENAME = "recentaudios.txt"
OPTIONS_FILENAME = "remaining.txt"
COUNTER_FILENAME = "count.txt"
RECORD_FILENAME = "record.txt"
ARCHIVE_FILENAME = "voice-note-archive.txt"
REQUESTS_FILENAME = "snack-requests.json"

# run daily tasks at 1pm eastern time (6pm UTC+1)
HOUR, MINUTE = 17, 0



intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)




# AUDIO FUNCTIONS #


# AUDIO OBJECTS #
class Audio:
    def __init__(self, raw_data):
        self.raw_data = raw_data

    def parsed_data(self):
        # formats airtable data into list [name, tags, etc]
        fields = list(self.raw_data.items())[2][1]
        return list(fields.items())

    def name(self):
        for entry in self.parsed_data():
            if entry[0]=='Title':
                return entry[1]
        return 'WARNING: no name found'

    def tag_string(self):
        for entry in self.parsed_data():
            if entry[0]=='Tags':
                return entry[1] + '\n'
        return ''

    def tags(self):
        for entry in self.parsed_data():
            if entry[0]=='Tags':
                # convert string of tags "[a] [b] [c] [d]" into a list {a,b,c,d}
                raw_string = entry[1].strip()
                tag_string = raw_string[1:-1].lower()
                return tag_string.split('] [')
        return []

    def link(self):
        for entry in self.parsed_data():
            if entry[0]=='Post Link':
                return entry[1]
        return 'WARNING: no link found'

    def date(self):
        for entry in self.parsed_data():
            if entry[0]=='Simplified Date':
        #         return ' (' +  entry[1] + ')'
        # return ''
                datestring = entry[1]
                datelist = datestring.split('/')
                return [int(x) for x in datelist]

    def age(self):
        current = datetime.datetime.now()
        now = (current.year)*12 + current.month
        audiodate = self.date()
        date = audiodate[0] + audiodate[1]*12
        return (now - date)

    def date_long(self):
        for entry in self.parsed_data():
            if entry[0]=='General Date':
                datestring = entry[1]
                datelist = datestring.split('-')
                date_full = [int(x) for x in datelist]
        return date_full[0]*365 + date_full[1]*30 + date_full[2]

    def series(self):
        for entry in self.parsed_data():
            if entry[0]=='Series Name (if applicable)':
                return '\n Series: ' + entry[1] + '\n'
        return ''

    def writer(self):
        for entry in self.parsed_data():
            if entry[0]=='Scriptwriter':
                if entry[1] != 'Vel':
                    return 'Scriptwriter: ' + entry[1]
        return ''

    def description(self):
        for entry in self.parsed_data():
            if entry[0]=='Description':
                return '\n' + entry[1] + '\n \n'
        return ''

    def characters(self):
        for entry in self.parsed_data():
            if entry[0]=='Recurring Characters':
                return entry[1]
        return ''

    # format a post for the audio
    def discord_post(self):
        post_body = self.tag_string() + self.series() + self.description() + self.writer()
        return discord.Embed(title = self.name(), url = self.link(), description = post_body)

    # exclude certain audios from showing up as a random choice or the audio of the day
    def allowed_choice(self):
        if self.name() == 'A Pool Party Turns Into a Fucking Competition' or self.name() == 'I Brought a Friend to Help Spoil You':
            return False
        else:
            return True




# FILTERING AUDIOS BY TAG #

# extracts tag from !randomaudio request 
def get_tags(message):
    tag = message.strip()

    if len(tag) == 0:
        return None
    if tag[0] == '[':
        # works regardless of whether or not square brackets were used
        tags = tag[1:-1]
        tag_list = tags.split('] [')
    else:
        tag_list = [tag]

    # rewrite tags in canonical form
    return [tag_dictionary.get(t,t) for t in tag_list]

# select audios with a specified tag
def tagged_options(audios, tags):
    options = []
    for audio in audios:
        if sorted(list(set(audio.tags()).intersection(tags))) == sorted(tags):
            options.append(audio)
    return options

# choose a random audio, optional argument to specify a tag 
def random_audio(audios, tag=None):
    if tag is not None:
        options = tagged_options(audios,tag)
        if len(options) != 0:
            return random.choice(options)
        else:
            return None
    else:
        return random.choice(audios)





# SEARCHING THROUGH AUDIOS # 

# sort audios chronologically
def age_sort(audio):
    return audio.date_long()

# search to see if phrase appears in any titles
def title_matches(phrase):
    matching = []
    for audio in audio_choices:
        if phrase.lower() in audio.name().lower():
            matching.append(audio)
    matching.sort(key = age_sort)
    return matching

# search to see if any part of the phrase appears in any titles
def inexact_matches(phrase):
    matching = []
    closer_matches = []
    search_terms = phrase.split(" ")
    too_common_words = ["the","a","an","is","on","for","you","my","i","to","me","up","and","are","with","your","by","part","of"]
    search_words = []
    for word in search_terms:
        if word not in too_common_words and len(word) > 2:
            search_words.append(word)

    for audio in audio_choices:
        overlap = 0
        for word in search_words:
            if word in audio.name().lower():
                overlap += 1
        if overlap > 0:
            matching.append(audio)
        if overlap == len(search_words):
            closer_matches.append(audio)

    if len(closer_matches) != 0:
        closer_matches.sort(key = age_sort)
        return closer_matches
    else:
        matching.sort(key = age_sort)
        return matching
        

# search for matching character names
def character_search(name):
    matching = []
    for audio in audio_choices:
        if name.lower() in audio.characters().lower():
            matching.append(audio)
    matching.sort(key = age_sort)
    return matching






# IMPORTING AIRTABLE DATA FROM API #

# this will update daily when the random audio of the day is chosen
def import_airtable_data():
    table = airtable_api.table('apprrNWlCwDHYj4wW', 'tblqwSpe5CdMuWHW6')
    all_audios = [Audio(entry) for entry in table.all()]

    allowed = []
    for audio in all_audios:
        if audio.allowed_choice():
            allowed.append(audio)

    return allowed

def import_tag_dictionary():
    table = airtable_api.table('appeb72XP6YJzGRyY', 'tbltF1MithqYynsdU')
    dictionary = dict()

    for entry in table.all():
        fields = list(entry.items())[2][1]
        data = list(fields.items())
        tag = data[0][1].strip()
        canonical = data[1][1].strip()
        dictionary[tag] = canonical

    return dictionary




# READING AND WRITING TO FILE #

# extract list from text file
def read_from_file(filename):
    f = open(filename)
    lines = f.read().splitlines()
    f.close()
    return lines

# save list to text file
def save_to_file(filename, list):
    padded = []
    for x in list:
        padded.append(x + "\n")
    f = open(filename,"w")
    for line in padded:
        f.write(line)
    f.close()
    return None







### BOT FUNCTIONS ###




# LOGIN #

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')



# STARTUP #

@client.event
async def setup_hook():
    print("setup hook running")

    # import data from airtable
    global audio_choices, tag_dictionary
    audio_choices = import_airtable_data()
    tag_dictionary = import_tag_dictionary()

    # import current state variable values
    global random_seed, good_girl, pet_count, edge_counter, cum_permission_ids, daily_audio, snack_requests
    random_seed = ''.join(random.choices(string.ascii_uppercase+string.digits, k=8))
    good_girl = read_from_file(WINNERS_FILENAME)[-1]
    pet_count = int(read_from_file(COUNTER_FILENAME)[-1])
    edge_counter = 0
    cum_permission_ids = [int(value) for value in read_from_file(RECORD_FILENAME)]
    currentdaily = read_from_file(AUDIOS_FILENAME)[-1]
    daily_audio = list(filter(lambda a: a.name() == currentdaily, audio_choices))[0]
    with open(REQUESTS_FILENAME, "r") as read_file:
        snack_requests = json.load(read_file)

    global voice_note_links
    voice_note_links = read_from_file(ARCHIVE_FILENAME)

    # set all daily tasks running
    if not announce_daily_audio.is_running():
        announce_daily_audio.start()
    if not choose_good_girl.is_running():
        choose_good_girl.start()
    if not daily_balatro.is_running():
        daily_balatro.start()

    global taliya, vel
    taliya = await client.fetch_user(1169014359842885726)
    vel = await client.fetch_user(1089053035377999912)
    await taliya.send(f"Card Catalog bot restarted successfully!")
    print(f"bot local time: {datetime.datetime.now().hour}h{datetime.datetime.now().minute}.")




# ON MESSSAGE COMMANDS #

@client.event
async def on_message(message):

    # allow modifications of state variables
    global audio_choices, tag_dictionary, pet_count, edge_counter, voice_note_links, snack_requests

    if message.author == client.user:
        return

    # remove case-sensitivity
    msg = message.content.lower()


    # AUDIO COMMANDS # 

    # select a random audio, with the option to specify tags
    if msg.startswith('!randomaudio'):
        # # checking to see if the user specified a tag, use if leading != 0
        # leading, trailing = 1+msg.find('['), msg.find(']')
        # tag = msg[leading:trailing]
        tags = get_tags(msg[13:])
        if tags is not None:
            audio = random_audio(audio_choices,tags)
            string =  '] ['.join(tags)
            if audio is not None:
                await message.channel.send(f"Here's a random audio tagged [{string}]!")
                await message.channel.send(embed=audio.discord_post())
            else:
                await message.channel.send("No audios tagged [" + string + "] were found")
        else:
            audio =random_audio(audio_choices)
            await message.channel.send(f"Here's a random audio!")
            await message.channel.send(embed=audio.discord_post())

    # search for audio by title
    if msg.startswith('!title'):
        phrase = msg[7:].strip()

        if len(phrase) == 0:
            await message.channel.send("Please enter a search phrase after `!title`.")
            return

        if phrase[0] == '"' or phrase[0] == "'":
            phrase = phrase[1:-1]
        phrase = phrase.strip()

        matches = title_matches(phrase)

        if len(matches) == 0:
            possible_matches = inexact_matches(phrase)
            if len(possible_matches) == 0:
                await message.channel.send(f'No audios found with title including the phrase "{phrase}."')
            elif len(possible_matches) == 1:
                await message.channel.send('No exact matches found for "' + phrase + '." One partially matching result found.')
                await message.channel.send(embed=possible_matches[0].discord_post())
            else:
                await message.channel.send('No exact matches found for "' + phrase + '."')
                link_string = ""
                for i in list(range(len(possible_matches))):
                    next = str(i+1) + ". [" + possible_matches[i].name() + "](" + possible_matches[i].link() + ")" + '\n'
                    link_string = link_string + next

                matches_embed = discord.Embed(title = "Partially Matching Results",description=link_string)
                try:
                    await message.channel.send(embed = matches_embed)
                except:
                    await message.channel.send('Partially matching results exceeded the Discord character limit, please try again with a different search!')
        elif len(matches) == 1:
            await message.channel.send(embed=matches[0].discord_post())     
        else:
            count = len(matches)
            link_string = ""
            for i in list(range(count)):
                next = str(i+1) + ". [" + matches[i].name() + "](" + matches[i].link() + ")" + '\n'
                link_string = link_string + next

            matches_embed = discord.Embed(title = "Matching Results",description=link_string)
            try:
                await message.channel.send(embed = matches_embed)
            except:
                await message.channel.send("Too many results found to display without exceeding Discord character limit, please try again with a more specific search term.")

    # search for audio by tag(s)
    if msg.startswith('!tag'):
        tags = get_tags(msg[5:])
        if len(tags) == 0:
            await message.channel.send("Please enter a search phrase after `!tag`.")
            return

        matches = tagged_options(audio_choices,tags)
        matches.sort(key = age_sort)

        if len(matches) == 0:
            await message.channel.send("No audios tagged with " + msg[5:] + " found.")
        elif len(matches) == 1:
            await message.channel.send(embed=matches[0].discord_post())     
        else:
            link_string = ""
            for i in list(range(len(matches))):
                next = str(i+1) + ". [" + matches[i].name() + "](" + matches[i].link() + ")" + '\n'
                link_string = link_string + next

            matches_embed = discord.Embed(title = "Matching Results",description=link_string)
            try:
                await message.channel.send(embed = matches_embed)
            except:
                await message.channel.send("Too many results found to display without exceeding Discord character limit, please try again with a more specific set of tags.")

    # lists audios featuring specified named character
    if msg.startswith('!character'):
        name = msg[11:].strip()
        if len(name) == 0:
            await message.channel.send("Please specify a character name after `!character`.")
            return
        matches = character_search(name)

        if len(matches) == 0:
            await message.channel.send(f'No audios found with character named {name.capitalize()}.')
        elif len(matches) == 1:
            await message.channel.send(embed=matches[0].discord_post())     
        else:
            count = len(matches)
            link_string = ""
            for i in list(range(count)):
                next = str(i+1) + ". [" + matches[i].name() + "](" + matches[i].link() + ")" + '\n'
                link_string = link_string + next

            matches_embed = discord.Embed(title = name.capitalize() + " Audios",description=link_string)
            await message.channel.send(embed = matches_embed)

    # responds with a link to a random voice note
    if msg.startswith("!vn"):
        link = random.choice(voice_note_links)
        await message.channel.send("Here's a random voice note! " + link)


    if msg.startswith("!gn") or msg.startswith("!goodnight"):
        tag_choices = ['mdom', 'creampies', 'oral', 'praise', 'rambles', 'degradation', 'breeding', 'cuckolding', 'spanking', 'fingering', 'blowjobs', 'msub', 'cheating', 'overstim',  'edging', 'body worship', 'bondage', 'strangers to lovers', 'friends to lovers', 'enemies to lovers','toys', 'demons','spitting', 'condescension','grinding', 'bodywriting', 'Daddy kink', 'deepthroating', 'nipple play', 'begging', 'standing sex', 'hands-free orgasms', 'mirror play', 'hypno', 'brat taming', 'petplay', 'choking', 'exhibitionism', 'objectification', 'pregnant sex', 'somno','facesitting', 'marking', 'cumplay','forced orgasms','denial','titjobs', 'cum on tits']
        bedge = " <:Bedge:1191310903208050839>"
        if message.author == taliya:
            await message.channel.send("Good night " + message.author.display_name + "! Sweet dreams, try not to think about " + random.choice(tag_choices) + bedge)




    # INTRODUCTORY COMMANDS #

    # send link to the masterlist
    if msg.startswith('!masterlist'):
        embed = discord.Embed(title="Vel's Library Masterlist",
                       url="https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr",
                       description="Masterlist of all of Vel's audios!")
        await message.channel.send(embed=embed)

    # DM the user a link to the masterlist and then delete request for privacy
    if msg.startswith('!dm'):
        await message.author.send("Here's a link to the masterlist! Send the message `!allcommands` to learn how to use the bot to find audios and more.")
        embed = discord.Embed(title="Vel's Library Masterlist",
                       url="https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr",
                       description="Masterlist of all of Vel's audios!")
        await message.author.send(embed=embed)
        # delete the user's message requesting the DM 
        if not isinstance(message.channel, discord.DMChannel):
            await message.delete()

    # list all bot commands
    if msg.startswith('!allcommands'):
        commands = "- `!randomaudio` randomly chosen audio from the masterlist \n- `!randomaudio [some] [tags]` random audio with these desired tag(s) \n- `!title phrase` for list of audios with that phrase in title \n- `!tag [some] [tags]` for list of audios with those tags \n- `!character name` for list of audios featuring a specific named character \n- `!daily` for the randomly chosen audio of the day \n- `!dm` bot will privately DM you the masterlist \n- `!masterlist` link to the masterlist \n- `!socials` links to all of Vel's social media accounts \n- `!schedule` audio posting schedule \n- `!lives` info about live recordings \n- `!tutorial` to receive a DM teaching you to use the bot \n- `!goodgirl` to sign up for good girl role \n- `!stream` for information about the next twitch stream \n- `!balatro` for daily seed \n- `!merch` for information about merch drops \n- `!time H:MM AM/PM` to convert from eastern time to universal timestamp \n- `!pet`, `!edge`, and `!cum` to show the bot some love \n- `!praise` and `!degrade` to be called a nice/mean name \n- `!vn` for a random voice note \n- `!request` to save tags you'd like for snack requests \n- `!myrequests` to see a numbered list of all your saved requests \n- `!removerequest X` to remove request number X on your list \n- `!randomrequest` for a random tag request from anyone!"
        command_embed = discord.Embed(title = "Card Catalog Bot Commands",description=commands)
        await message.channel.send(embed=command_embed)

    # list fundamental commands
    if msg.startswith('!basiccommands'):
        commands = "- `!randomaudio` randomly chosen audio from the masterlist \n- `!randomaudio [some] [tags]` random audio with these desired tag(s) \n- `!title phrase` for list of audios with that phrase in title \n- `!tag [some] [tags]` for list of audios with those tags \n- `!character name` for list of audios featuring a specific named character \n- `!dm` bot will privately DM you the masterlist \n- `!masterlist` link to the masterlist \n- `!socials` links to all of Vel's social media accounts \n- `!schedule` audio posting schedule \n- `!lives` info about live recordings"
        command_embed = discord.Embed(title = "Card Catalog Bot Commands",description=commands)
        await message.channel.send(embed=command_embed)

    # guides the user through a tutorial of basic bot functionality
    if msg.startswith('!tutorial'):
        # delete the user's message requesting the DM 
        if not isinstance(message.channel, discord.DMChannel):
            await message.delete()
        
        cont = True
        if cont:
            await message.author.send("The bot is primarily used to search through the masterlist of Vel's audios! If you don't know what you're in the mood for, search `!randomaudio` to have any of over three hundred audios chosen for you. Try it here: ")
            try:
                await client.wait_for('message',check = lambda m: m.content.startswith("!randomaudio") and m.author == message.author, timeout = 300)
                await asyncio.sleep(1)
                cont = True
            except:
                await message.author.send("Tutorial automatically ended after ten minutes of inactivity. If you want to finish the tutorial, send `!tutorial` to start again.")
                cont = False

        if cont:
            await message.author.send("You can also specify tags that you'd like the random audio to have by sending a message with the format `!randomaudio [tag one] [tag two]`. Try it here with one (or more!) of your favorite tags:")
            cont = False
            try:
                await client.wait_for('message',check = lambda m: m.content.startswith("!randomaudio") and m.author == message.author, timeout = 300)
                await asyncio.sleep(1)
                cont = True
            except:
                await message.author.send("Tutorial automatically ended after ten minutes of inactivity. If you want to finish the tutorial, send `!tutorial` to start again.")
                cont = False

        if cont:
            await message.author.send("Of course, you might already know which of Vel's audios you'd like to listen to! To get a link to a specific audio, all you need to know is part of the title. The bot will send a list of all audios that match your search. Vel has a lot of multi-part series, so this is great way to get a list of all audios in a specific series! \n \nTry sending a message with the format `!title phrase`, where `phrase` is what you remember being in the title of the audio (for example, you could try `!title academic` or `!title need you to be mine`):")
            cont = False
            try:
                await client.wait_for('message',check = lambda m: m.content.startswith("!title") and m.author == message.author, timeout = 300)
                await asyncio.sleep(1)
                cont = True
            except:
                await message.author.send("Tutorial automatically ended after ten minutes of inactivity. If you want to finish the tutorial, send `!tutorial` to start again.")
                cont = False

        if cont:
            await message.author.send("You can even search by character name using `!character name`. If you aren't familiar with any of Vel's named characters yet, try searching for Sam: ")
            cont = False
            try:
                await client.wait_for('message',check = lambda m: m.content.startswith("!character") and m.author == message.author, timeout = 300)
                await asyncio.sleep(1)
                cont = True
            except:
                await message.author.send("Tutorial automatically ended after ten minutes of inactivity. If you want to finish the tutorial, send `!tutorial` to start again.")
                cont = False

        if cont:
            await message.author.send("Vel also records lots of voice notes as little audio 'snacks' for the discord to enjoy. To listen to a random voice note, send the command `!vn`:")
            cont = False
            try:
                await client.wait_for('message',check = lambda m: m.content.startswith("!vn") and m.author == message.author, timeout = 300)
                await asyncio.sleep(1)
                cont = True
            except:
                await message.author.send("Tutorial automatically ended after ten minutes of inactivity. If you want to finish the tutorial, send `!tutorial` to start again.")
                cont = False

        if cont: 
            await message.author.send("The bot also has lots of helpful information for all things Vel. For example, you can type `!masterlist` to get a link to the list of all of his audios, or `!socials` for links to all of Vel's accounts on various platforms online. There are also some commands just for fun that you'll often see people using in the https://discord.com/channels/1148449914188218399/1248773338726400040 channel, like sending the message `!praise` to be called a random nice petname! \n \nTo see a full list of everything the bot can do (or just refresh your memory in the future), you can send the message `!allcommands` for a summary of bot features. Enjoy your time in the library!")


    
    # saving tag requests with the bot
    if msg.startswith('!request'):
        request = msg[9:].strip()
        user_id = message.author.id

        if len(request) == 0:
            await message.channel.send("Please enter some tags after `!request`. Alternatively, to see your saved tags, send the command `!myrequests`; to get a random request, send the command `!randomrequest`.")
        else:
            not_found = True
            for entry in snack_requests:
                if entry[0] == user_id:
                    entry.append(request)
                    not_found = False
                    break 
            if not_found:
                snack_requests.append([user_id,request])

            with open("snack-requests.json", "w") as outfile:
                outfile.write(json.dumps(snack_requests))
            await message.channel.send("Your snack request for " + request + " has been saved! You can see all of your requests using the command `!myrequests`.")


    if msg.startswith('!myrequests'):
        user_id = message.author.id

        requests = None
        for entry in snack_requests:
            if entry[0] == user_id:
                requests = entry[1:]
                break

        if requests is not None: 
            req_string = "Your saved snack requests: "
            for k in range(0, len(requests)):
                req_string += "\n" + str(k + 1) + ". " + requests[k]
            req_string += "\nTo remove a request, send the command `!removerequest X`, where X is the number of the entry."
            await message.channel.send(req_string)

        else:
            await message.channel.send("You have no recorded snack requests! Use the command `!request` to add desired tags.")


    if msg.startswith('!removerequest'):
        try: 
            remove_index = int(msg[15:].strip())
        except: 
            await message.channel.send("Please specify the number of the request you'd like to remove. You can see all your requests (and their corresponding numeric label) using the command `!myrequests`.")
        else: 
            user_id = message.author.id
            not_found = True
            for entry in snack_requests:
                if entry[0] == user_id:
                    if remove_index > -1 + len(entry):
                        await message.channel.send(f"Request out of range; entry {remove_index} does not exist!")
                    else:
                        deleted = entry[remove_index]
                        del entry[remove_index]
                        if len(entry) == 1:
                            snack_requests.remove(entry)
                        await message.channel.send("Your snack request for " + deleted + " has been removed.")
                        not_found = False
                    break
            if not_found:
                await message.channel.send("You have no saved requests to remove.")
                    
            with open("snack-requests.json", "w") as outfile:
                outfile.write(json.dumps(snack_requests))


    if msg.startswith("!randomrequest"):
        if len(snack_requests) == 0:
            await message.channel.send("There are no snack requests right now!")
        else:
            entry = random.choice(snack_requests)
            user = await client.get_guild(GUILD).fetch_member(entry[0])
            request = random.choice(entry[1:])
            await message.channel.send(f"From {user.display_name} — {request}")



    # INFORMATION COMMANDS #

    # links to the chosen audio of the day
    if msg.startswith('!daily'):
        await message.channel.send("Here's a link to the audio of the day!")
        await message.channel.send(embed=daily_audio.discord_post())

    # explains how to sign up for wanna be the good girl of the day role
    if msg.startswith('!goodgirl'):
        await message.channel.send(f"To be eligible to be selected as the random good girl of the day, assign yourself the 'I wanna be a good girl role' in <id:customize>. Today's good girl is {good_girl}!")

    # replies with the balatro daily seed
    if msg.startswith('!balatro'):
        await message.channel.send(f"The Balatro seed of the day is: {random_seed}")

    # responds with Vel's release schedule
    if msg.startswith('!schedule'):
        # schedule = "Sunday 4:30PM EST: Private Library Release \n Monday 4:30PM EST: Reddit GWA Release \n Wednesday 6:30PM EST: Library Card Release \n Every other Thursday 4:30PM EST: Reddit GWA Release \n Friday 6:30PM EST: Book Club Release"
        schedule = "Sunday 4:30PM EST (<t:1716755400:t>): Private Library Release \n Monday 4:30PM EST (<t:1716841800:t>): Reddit GWA Release \n Wednesday 6:30PM EST (<t:1717021800:t>): Library Card Release \n Every other Thursday 4:30PM EST (<t:1717101000:t>): Reddit GWA Release \n Friday 6:30PM EST (<t:1717194600:t>): Book Club Release"
        schedule_embed = discord.Embed(title = "Vel's Posting Schedule",description=schedule)
        await message.channel.send(embed=schedule_embed)

    # information about live recordings
    if msg.startswith('!live'):
        await message.channel.send("Vel does live audio recordings here on discord every Sunday at 7:30PM EST (<t:1728862200:t>)!")

    # information about live twitch streams
    if msg.startswith('!stream'):
        # stream_info = 'Vel streams live every other Sunday on [Twitch](https://www.twitch.tv/velslibrary). The next stream, "How Vel Does Vel Know Vel?" (quizzing the librarian himself on how well he knows his own content), will be <t:1722799800:F>! The next stream will be <t:1724009400:F>!'
        stream_info = 'Vel is taking a short break from streaming on [Twitch](https://www.twitch.tv/velslibrary)!'
        stream_embed = discord.Embed(title = "Vel's Livestreams", description = stream_info, url = "https://www.twitch.tv/velslibrary")
        await message.channel.send(embed = stream_embed)

    # information about merch drops
    if msg.startswith('!merch'):
        # merch_info = "Merch is now live for patrons to purchase! To access the store, use password ||goodgirl||. These items will be available until <t:1723089540:F>. Merch drops are seasonal, so this is your only chance to get these!"
        merch_info = "The summer merch drop has ended, but new merch will likely be available this winter!"
        merch_embed = discord.Embed(title = "Vel's Library Merch, Summer 2024", description = merch_info, url = "https://vel-1-shop.fourthwall.com/")
        await message.channel.send(embed = merch_embed)

    # list of links to all of Vel's social media accounts and profiles
    if msg.startswith('!social'):
        links = "- [Twitter](https://x.com/VelsLibrary) \n- [Reddit](https://www.reddit.com/user/VelsLibrary/) \n- [Twitch](https://www.twitch.tv/velslibrary) \n- [Pornhub](https://www.pornhub.com/model/velslibrary) \n- [Youtube](https://www.youtube.com/@VelsLibrary) \n- [TikTok](https://www.tiktok.com/@vels.library) \n- [Instagram](https://www.instagram.com/velslibrary/) \n- [Throne](https://throne.com/velslibrary) \n- [Ko-fi](https://ko-fi.com/velslibrary) \n- [Quinn](https://www.tryquinn.com/creators/vels-library)"
        link_embed = discord.Embed(title = "Vel's Social Media",description=links)
        await message.channel.send(embed=link_embed)

    # links to Vel's quinn audios
    if msg.startswith('!quinn'):
        quinn_info = "Listen to Vel's exclusive Quinn audios here!"
        quinn_embed = discord.Embed(title = "Vel's Quinn Audios", description = quinn_info, url = "https://www.tryquinn.com/creators/vels-library")
        await message.channel.send(embed = quinn_embed)

    # list of character names as read from airtable data
    if msg.startswith('!allcharacters'):
        character_list = []
        for audio in audio_choices:
            if audio.characters() != '':
                for char in audio.characters().split(', '):
                    character_list.append(char)
        characters = list(set(character_list))
        char_string = ''
        for char in characters:
            char_string = char_string + char + ", "
        await message.channel.send('Named characters: ' + char_string[:-2])

    # information about server bingo 
    if msg.startswith('!bingo'):
        bingo_info = "Vel's Library discord server bingo! If you win, let Teacups know."
        bingo_embed = discord.Embed(title = "Server Bingo", description = bingo_info, url = "https://www.bingocardcreator.com/game/29103/")
        await message.channel.send(embed = bingo_embed)

    # information about romance books
    if msg.startswith('!book'):
        books_info = "List of books Vel is or will be reading for content, with links to Storygraph for descriptions, reviews, and content warnings. Maintained by Delphine!"
        books_embed = discord.Embed(title = "Vel's Romance Reads", description = books_info, url = "https://airtable.com/appl3LHVXpzA6fEqq/shrTeuKFM6V6M4Bcs/tblgrs5VFAKpTsT5W/viw4EjZx4vfMv3vXf")
        await message.channel.send(embed = books_embed)





    # UTILITY COMMANDS #

    # private command
    # sync with airtable data to pull any masterlist updates
    if msg.startswith('!refresh'):
        audio_choices = import_airtable_data()
        tag_dictionary = import_tag_dictionary()
        await taliya.send("Masterlist data sync'ed with Airtable updates.")

    # converts a time in eastern timezone into a universal timestamp
    if '!time' in msg:
        # input is in the format "!timestamp 3:00 PM" assumed eastern time
        cut = msg[(6 + msg.find("!time")):]
        end_index = max(cut.find("am"), cut.find("pm"))
        if end_index == -1:
            return "Please specify AM or PM."
        isAM = cut[end_index:(end_index+2)] == "am"

        time_string = cut[:end_index].strip()
        split = time_string.partition(":")

        if len(split[2]) != 0:
            hour, minute = int(split[0]), int(split[2])
        else:
            hour, minute = int(split[0]), 0

        if hour == 12:
            hour = 0

        if isAM:
            utc_hour = hour + 4
        else:
            utc_hour = hour + 4 + 12

        now = datetime.datetime.utcnow()
        if utc_hour < 24:
            utc_time = datetime.datetime(now.year, now.month, now.day, utc_hour, minute)
        else:
            utc_time = datetime.datetime(now.year, now.month, now.day + 1, utc_hour % 24, minute)

        epoch_time = calendar.timegm(utc_time.timetuple())
        timestamp = "<t:" + str(epoch_time) + ":t>"
        await message.channel.send(timestamp)

    # logs new voice notes in the full list
    if message.author == vel and len(message.attachments) != 0:
        attached = message.attachments
        if attached[0].is_voice_message():
            voice_note_links.append(message.jump_url)
            save_to_file(ARCHIVE_FILENAME,voice_note_links)





    # SILLY COMMANDS #

    # show the bot some love!
    if msg.startswith('!pet'):
        pet_count += 1
        save_to_file(COUNTER_FILENAME, [str(pet_count)])

        if message.author == vel:
            await message.channel.send("Thank you, Daddy!")
        else:
            if not isinstance(message.channel, discord.DMChannel):
                await message.channel.send(f"The bot has been pet {pet_count} times!")
            else:
                await message.channel.send(f"Thank you! :smiling_face_with_3_hearts: The bot has been pet {pet_count} times!")

        if pet_count == 69:
            await message.channel.send("What? Are you really so horny that you thought there would be some special message for 69? Sluts like you are so predictable, you know. So needy and desperate and completely at the mercy of your pathetic fucking cunt. But you like being that way, don't you? Silly whore.")

    # random degrading name, with 20% chance to pull the modifier "Daddy's" and 0.3% chance (legendary odds) to get "Vel's"
    if msg.startswith('!degrade'):
        adjectives = ["desperate","pretty","depraved","pathetic","needy","worthless"]
        nouns = ["whore","slut","bitch","cunt","set of holes","cumslut","fucktoy","cumrag","cumdump"]
        if random.choice(range(1000)) < 3:
            whose = "Vel's "
        elif random.choice(range(5)) == 0:
            whose = "Daddy's "
        else:
            whose = ""
        response = whose + random.choice(adjectives) + " " + random.choice(nouns) + "."
        await message.channel.send("deg ||" + response + "||")

    # random nice name, with 20% chance to pull the modifier "Daddy's" and 0.3% chance (legendary odds) to get "Vel's"
    if msg.startswith('!praise'):
        adjectives = ["perfect","pretty","beautiful","darling","sweet"]
        nouns = ["angel","bunny","pet","princess","toy","doll","kitten","flower"]

        if random.choice(range(1000)) < 3:
            whose = "Vel's "
        elif random.choice(range(5)) == 0:
            whose = "Daddy's "
        else:
            whose = ""

        TORA_ID = 208091268897701898
        if message.author.id == TORA_ID:
            response = whose + random.choice(adjectives) + " kitten!"
        else:
            response = whose + random.choice(adjectives) + " " + random.choice(nouns) + "!"
        await message.channel.send(response)

    # torture the bot
    if msg.startswith('!edge'):
        edge_counter += 1
        if edge_counter == 1:
            await message.channel.send(f"I've been edged 1 time. May I please cum?")
        else:
            await message.channel.send(f"I've been edged {edge_counter} times. May I please cum?")

    # returns a random choice of no responses unless from a random group of winners or mods
    if msg.startswith('!cum'):
        mod_ids = [1169014359842885726, 1089053035377999912, 159860526841593856, 415894832515383296]
        if '?' in msg:
            await message.channel.send("Try again, but this time, say it like you believe it.")
        elif message.author.id in mod_ids or message.author.id in cum_permission_ids:
            edge_counter = 0
            if message.author == vel:
                await message.channel.send("Thank you, Daddy!")
            else:
                await message.channel.send("Thank you!")
        else:
            responses = ["no u","Silence, sub.","Daddy didn't give me permission yet.", "I don't answer to you.","You'd really like that, wouldn't you?","Nice try.","Make me.","It's adorable that you thought that would work.","How about you cum for me instead, baby?","I'm not allowed to cum yet :pleading_face:","I'm trying :pensive:","It's okay, I'm a good girl, I can take a little more!","But I wanna be good for Daddy!","You're not my real dom!","I would, but my vibrator died :cry: you got any batteries?"]
            weights = [1 for k in range(len(responses)-1)]
            weights.insert(0,6)
            response = random.choices(responses,weights = weights, k = 1)[0]
            await message.channel.send(response)
            if response == "no u":
                options = []
                for audio in audio_choices:
                    if 'sfw' not in audio.tags() and 'behind the scenes' not in audio.tags():
                        options.append(audio)
                audio =random_audio(options)
                await message.channel.send(embed=audio.discord_post())








# DAILY LOOPING TASKS #


# AUDIO OF THE DAY #

# random choice of audios not in the recent list (imported from file)
def choose_next(options):
    recent = read_from_file(AUDIOS_FILENAME)
    choices = []

    for audio in options:
        if audio.name() not in recent:
            choices.append(audio)

    if len(choices) != 0:
        next_one = random.choice(choices)
    else:
        return None

    # add new choice to recent list and save to file
    recent.append(next_one.name())
    recent.pop(0)

    save_to_file(AUDIOS_FILENAME,recent)
    return next_one

# choose random audio from refreshed list of eligible options
def audio_of_the_day():
    # sync with airtable data to pull any masterlist updates
    global audio_choices
    audio_choices = import_airtable_data()

    daily_audio_options = []
    for audio in audio_choices:
        # ensure audio wasn't posted in the past four months
        nsfw = 'sfw' not in audio.tags() and 'behind the scenes' not in audio.tags()
        if audio.age() > 4 and nsfw:
            daily_audio_options.append(audio)  

    return choose_next(daily_audio_options)

# announce audio of the day
@tasks.loop(minutes = 1)
async def announce_daily_audio():
    if datetime.datetime.now().hour == HOUR and datetime.datetime.now().minute == MINUTE:
        guild = client.get_guild(GUILD)
        channel = client.get_channel(GENERAL)

        global daily_audio
        daily_audio = audio_of_the_day()

        if daily_audio is not None: 
            await channel.send(f"The audio of the day!")
            await channel.send(embed=daily_audio.discord_post())
        else:
            await taliya.send("ERROR: no non-recent options for daily audio.")




# GOOD GIRL OF THE DAY #

# choose random winner not in the recent list (imported from file)
def choose_next_winner(options):
    recent = read_from_file(WINNERS_FILENAME)
    choices = []

    for user in options:
        if user.name not in recent:
            choices.append(user)
    remaining = [user.name for user in choices]

    if len(choices) != 0:
        winner = random.choice(choices)
    else:
        return None

    # add new choice to recent list and save to file
    recent.append(winner.name)
    recent.pop(0)

    save_to_file(OPTIONS_FILENAME,remaining)
    save_to_file(WINNERS_FILENAME,recent)
    return winner, len(remaining)

# announce good girl of the day and assign appropriate role
@tasks.loop(minutes = 1)
async def choose_good_girl():
    if datetime.datetime.now().hour == HOUR and datetime.datetime.now().minute == MINUTE:
        global good_girl
        guild = client.get_guild(GUILD)
        channel = client.get_channel(GENERAL)
        good_girl_role = guild.get_role(WINNER_ROLE)

        await asyncio.sleep(6)
        for member in good_girl_role.members:
            # remove good girl role from yesterday's winner
            await member.remove_roles(good_girl_role)

        # choose new random winner for the day
        options = guild.get_role(OPTIONS_ROLE).members
        winner, remaining_number = choose_next_winner(options)
        if remaining_number == 10: 
            await taliya.send("Only ten remaining options for good girl of the day.")


        if datetime.datetime.now().month == 6 and datetime.datetime.now().day == 9:
            winner = await client.fetch_user(1241573320114049078)

        # send message and assign good girl role to winner
        if winner is not None:
            await channel.send(f'{winner.mention} is the good girl of the day!')
            await winner.add_roles(good_girl_role)
            good_girl = winner.display_name
        else:
            await taliya.send("ERROR: no non-recent options for good girl of the day.")

        # randomly assign cum permissions
        winners = random.sample(options, 6)
        global cum_permission_ids
        cum_permission_ids  = [user.id for user in winners]
        print(f"daily permissions assigned to: {winners[0].display_name}, {winners[1].display_name}, {winners[2].display_name}, {winners[3].display_name}, {winners[4].display_name}, and {winners[5].display_name}")
        save_to_file(RECORD_FILENAME,[str(ids) for ids in cum_permission_ids])

# choose random balatro seed of the day
@tasks.loop(minutes = 1)
async def daily_balatro():
    if datetime.datetime.now().hour == HOUR and datetime.datetime.now().minute == MINUTE:
        global random_seed
        random_seed = ''.join(random.choices(string.ascii_uppercase+string.digits, k=8))







# ON NEW MEMBER JOIN #

# DMs new user a welcome message with a link to the masterlist
@client.event
async def on_member_join(member):
    await member.send("Welcome to the Library! Vel has over three hundred audios to choose from, and you can use this bot to search through and explore all of Vel's content. It can pick a random audio with your favorite tags for you to listen to, you can search for audios by title, and more! To learn in detail how to use this bot to search for audios and find other information about Vel's content, send the message `!tutorial`. To just receive a quick summary of what the bot can do, send the message `!allcommands`.")
    embed = discord.Embed(title="Vel's Library Masterlist",
                   url="https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr",
                   description="Here's a link to the masterlist of all of Vel's audios. You can search and filter the masterlist for your favorite tags.")
    await member.send(embed=embed)
    print('new member join message sent')






# DM ERROR MESSAGES #

@client.event
async def on_error(event, *args, **kwargs):
    message = args[0]
    if isinstance(message.channel, discord.DMChannel):
        await taliya.send("**ERROR:** DM with " + message.author.display_name + "\n**MESSAGE CONTENT:** " + message.content + "\n\n" + traceback.format_exc())
    else:
        await taliya.send("**ERROR:** " + message.jump_url + "\n**MESSAGE CONTENT:** " + message.content + "\n\n" + traceback.format_exc())








# RUN BOT #

client.run(TOKEN)
