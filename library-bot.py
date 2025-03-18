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
from discord import app_commands
from pyairtable import Api
from typing import Optional


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = int(os.getenv('GUILD_ID'))
GENERAL = int(os.getenv('GENERAL_CHANNEL'))
OPTIONS_ROLE = int(os.getenv('ROLE_ID_OPTIONS'))
WINNER_ROLE = int(os.getenv('ROLE_ID_WINNER'))
BIRTHDAY_CHANNEL = int(os.getenv('BIRTHDAY_CHANNEL'))
airtable_api = Api(os.getenv('AIRTABLE_TOKEN'))

WINNERS_FILENAME = "recentwinners.txt"
AUDIOS_FILENAME = "recentaudios.txt"
OPTIONS_FILENAME = "remaining.txt"
COUNTER_FILENAME = "count.txt"
RECORD_FILENAME = "record.txt"
ARCHIVE_FILENAME = "voice-note-archive.txt"
REQUESTS_FILENAME = "snack-requests.json"
BIRTHDAY_FILENAME = "birthdays.json"

# run daily tasks at 1pm eastern time (6pm UTC+1)
HOUR, MINUTE = 17, 0
MIDNIGHT = 5



intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)




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
                return entry[1].replace("’","'")
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
        if word not in too_common_words and (len(word) > 2 or word.isnumeric()):
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

def import_collections():
    table = airtable_api.table('appeb72XP6YJzGRyY', 'tblphntbN1NGnEpEr')
    collections = []

    for entry in table.all():
        fields = list(entry.items())[2][1]
        data = list(fields.items())
        title = data[0][1].strip()
        url = data[1][1].strip()
        description = data[2][1].strip()
        search_terms = data[3][1].strip()
        coll_data = [title,url,description,search_terms]
        collections.append(coll_data)

    return collections




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
    await tree.sync()

    # import data from airtable
    global audio_choices, tag_dictionary, collections
    audio_choices = import_airtable_data()
    tag_dictionary = import_tag_dictionary()
    collections = import_collections()

    # import current state variable values
    global random_seed, good_girl, pet_count, edge_counter, cum_permission_ids, daily_audio, snack_requests, birthdays, twitch_time, live_time
    random_seed = ''.join(random.choices(string.ascii_uppercase+string.digits, k=8))
    good_girl = read_from_file(WINNERS_FILENAME)[-1]
    pet_count = int(read_from_file(COUNTER_FILENAME)[-1])
    edge_counter = 0
    cum_permission_ids = [int(value) for value in read_from_file(RECORD_FILENAME)]
    currentdaily = read_from_file(AUDIOS_FILENAME)[-1]
    daily_audio = list(filter(lambda a: a.name() == currentdaily, audio_choices))[0]
    with open(REQUESTS_FILENAME, "r") as read_file:
        snack_requests = json.load(read_file)
    with open(BIRTHDAY_FILENAME, "r") as read_file:
        birthdays = json.load(read_file)
    twitch_time = "<t:1742151600:F>"
    live_time = "<t:1742167800:t>"

    global voice_note_links
    voice_note_links = read_from_file(ARCHIVE_FILENAME)
    global rerun_gg, rerun_daily, rerun_birthdays
    rerun_gg, rerun_daily, rerun_birthdays = False, False, False

    # set all daily tasks running
    if not run_daily_loops.is_running():
        run_daily_loops.start()
        print("starting daily looping tasks")

    global taliya, vel
    taliya = await client.fetch_user(1169014359842885726)
    vel = await client.fetch_user(1089053035377999912)
    await taliya.send(f"Card Catalog bot restarted successfully!")
    print(f"bot local time: {datetime.datetime.now().hour}h{datetime.datetime.now().minute}.")




## AUDIO SEARCH COMMANDS ##
# for second message, await interaction.followup.send() #


@tree.command(name = "randomaudio", description = "Chooses a random audio from the masterlist")
@app_commands.rename(taglist = "tags")
@app_commands.describe(taglist="any tags you would like the audio to have! use [] for multiple tags")
async def randomaudio(interaction, taglist: Optional[str] = None):
    await interaction.response.defer()
    if taglist is not None:
        tags = get_tags(taglist.lower().replace("’","'").strip())
        audio = random_audio(audio_choices,tags)
        string =  '] ['.join(tags)
        if audio is not None:
            # await interaction.followup.send(f"Here's a random audio tagged [{string}]!")
            await interaction.followup.send(embed=audio.discord_post())
        else:
            await interaction.followup.send("No audios tagged [" + string + "] were found")
    else:
        audio = random_audio(audio_choices)
        # await interaction.followup.send(f"Here's a random audio!")
        await interaction.followup.send(embed = audio.discord_post())



@tree.command(name = "title", description = "Finds an audio by (part of) its title!")
@app_commands.rename(title_phrase = "title")
@app_commands.describe(title_phrase="any words or phrases from the audio's title that you remember")
async def title(interaction, title_phrase: str):
    await interaction.response.defer()
    phrase = title_phrase.lower().replace("’","'").replace('“','"').replace('”','"').replace("‘","'").strip()
    if phrase[0] == '"' or phrase[0] == "'":
        phrase = phrase[1:-1]
    phrase = phrase.strip()

    matches = title_matches(phrase)

    if len(matches) == 0:
        possible_matches = inexact_matches(phrase)
        if len(possible_matches) == 0:
            await interaction.followup.send(f'No audios found with title including the phrase "{phrase}."')
        elif len(possible_matches) == 1:
            # await interaction.followup.send('No exact matches found for "' + phrase + '." One partially matching result found.')
            await interaction.followup.send(embed=possible_matches[0].discord_post())
        else:
            # await interaction.followup.send('No exact matches found for "' + phrase + '."')
            link_string = ""
            for i in list(range(len(possible_matches))):
                next = str(i+1) + ". [" + possible_matches[i].name() + "](" + possible_matches[i].link() + ")" + '\n'
                link_string = link_string + next

            matches_embed = discord.Embed(title = "Partially Matching Results",description=link_string)
            try:
                await interaction.followup.send(embed = matches_embed)
            except:
                await interaction.followup.send('Partially matching results exceeded the Discord character limit, please try again with a different search!')
    elif len(matches) == 1:
        await interaction.followup.send(embed=matches[0].discord_post())     
    else:
        count = len(matches)
        link_string = ""
        for i in list(range(count)):
            next = str(i+1) + ". [" + matches[i].name() + "](" + matches[i].link() + ")" + '\n'
            link_string = link_string + next

        matches_embed = discord.Embed(title = "Matching Results",description=link_string)
        try:
            await interaction.followup.send(embed = matches_embed)
        except:
            await interaction.followup.send("Too many results found to display without exceeding Discord character limit, please try again with a more specific search term.")



@tree.command(name = "tag", description = "Searches for all audios with your chosen tag(s)")
@app_commands.rename(taglist = "tags")
@app_commands.describe(taglist="any tags you would like the audios to have! use [] for multiple tags")
async def tag(interaction, taglist: str):
    await interaction.response.defer()
    tags = get_tags(taglist.lower().replace("’","'").strip())

    matches = tagged_options(audio_choices,tags)
    matches.sort(key = age_sort)

    if taglist[0] == '[':
        tag_list = taglist[1:-1].split('] [')
    else:
        tag_list = [taglist]

    formatted = []
    for tag in tag_list:
        words = "".join([word[0].upper() + word[1:] + " " for word in tag.split()])
        formatted.append("[" + words.strip() +  "] ")
    tagstring = "".join(formatted)

    if len(matches) == 0:
        await interaction.followup.send("No audios tagged with " + tagstring.lower() + "found.")
    elif len(matches) == 1:
        await interaction.followup.send(embed=matches[0].discord_post())     
    else:
        link_string = ""
        for i in list(range(len(matches))):
            next = str(i+1) + ". [" + matches[i].name() + "](" + matches[i].link() + ")" + '\n'
            link_string = link_string + next

        matches_embed = discord.Embed(title = tagstring + "Audios",description=link_string)
        try:
            await interaction.followup.send(embed = matches_embed)
        except:
            await interaction.followup.send("Vel has too many audios tagged " + tagstring.lower() + "to display without exceeding the Discord character limit! Please try again with a more specific set of tags." )



@tree.command(name = "character", description = "Lists all audios featuring a specific named character")
@app_commands.describe(character_name= "character name (use /allcharacters to see a list of options)")
@app_commands.rename(character_name = "character")
async def character(interaction, character_name: str):
    await interaction.response.defer()
    name = character_name.strip()
    matches = character_search(name)

    if len(matches) == 0:
        await interaction.followup.send(f'No audios found with character named {name.capitalize()}.')
    elif len(matches) == 1:
        await interaction.followup.send(embed=matches[0].discord_post())     
    else:
        count = len(matches)
        link_string = ""
        for i in list(range(count)):
            next = str(i+1) + ". [" + matches[i].name() + "](" + matches[i].link() + ")" + '\n'
            link_string = link_string + next

        matches_embed = discord.Embed(title = name.capitalize() + " Audios",description=link_string)
        await interaction.followup.send(embed = matches_embed)
        if name.lower() == "tex":
            await interaction.followup.send("Good luck, godspeed, and remember to hydrate, " + interaction.user.mention + "!")



@tree.command(name = "scriptwriter", description = "Provides a list of all of Vel's script fill audios written by a specified writer.")
@app_commands.describe(writer = "name of the scriptwriter")
async def scriptwriter(interaction, writer: str):
    await interaction.response.defer()
    name = writer.lower().strip()
    matches = []

    for audio in audio_choices:
        if name in audio.writer().strip().lower():
            matches.append(audio)

    matches.sort(key = age_sort)

    if len(matches) == 0:
        await interaction.followup.send(f"No audios found written by {writer}.")
    elif len(matches) == 1:
        await interaction.followup.send(embed = matches[0].discord_post())
    else:
        count = len(matches)
        canonical_name = matches[0].writer()[14:]
        link_string = ""
        for i in list(range(count)):
            next = str(i+1) + ". [" + matches[i].name() + "](" + matches[i].link() + ")" + '\n'
            link_string = link_string + next

        matches_embed = discord.Embed(title = canonical_name.capitalize() + " Audios",description=link_string)
        await interaction.followup.send(embed = matches_embed)




@tree.command(name = "collection", description = "Returns link to specified Patreon collection")
@app_commands.describe(name="name of the collection")
async def collection(interaction, name: str):
    await interaction.response.defer()
    query = name.lower().replace("’","'").strip()
    collection = None
    for coll in collections:
        if query in coll[3]:
            collection = coll
            break
    if collection is not None:
        coll_embed = discord.Embed(title = collection[0], url = collection[1], description = collection[2])
        await interaction.followup.send(embed = coll_embed)
    else:
        await interaction.followup.send("No matching collection found.")


@tree.command(name = "masterlist",description = "Sends a link to the masterlist of Vel's audios")
async def masterlist(interaction):
    await interaction.response.defer()
    embed = discord.Embed(title="Vel's Library Masterlist",
                       url="https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr",
                       description="Masterlist of all of Vel's audios!")
    await interaction.followup.send(embed=embed)





## VOICE NOTES ## 


@tree.command(name = "vn", description = "Chooses a random voice note that Vel has recorded!")
async def vn(interaction):
    await interaction.response.defer()
    link = random.choice(voice_note_links)
    await interaction.followup.send("Here's a random voice note! " + link)



@tree.command(name = "request", description = "Request tags for Vel to use when recording voice notes!")
@app_commands.describe(req = "any tags or ideas you'd like for a short voice note!")
@app_commands.rename(req = "request")
async def request(interaction, req: str):
    await interaction.response.defer()
    global snack_requests
    requests = req.replace("’","'").strip()
    user_id = interaction.user.id

    if len(req) > 2000:
        await interaction.followup.send('Request exceeds Discord character limit and cannot be saved. Please consider a shorter request!')
    else:
        not_found = True
        for entry in snack_requests:
            if entry[0] == user_id:
                entry.append(requests)
                not_found = False
                break 
        if not_found:
            snack_requests.append([user_id,requests])

        with open("snack-requests.json", "w") as outfile:
            outfile.write(json.dumps(snack_requests))
        await interaction.followup.send('Your snack request for "' + requests + '" has been saved! You can see all of your requests using the command `/myrequests`.')



@tree.command(name = "myrequests", description = "Lists your saved tag requests!")
async def myrequests(interaction):
    await interaction.response.defer()
    requests = None
    for entry in snack_requests:
        if entry[0] == interaction.user.id:
            requests = entry[1:]
            break

    if requests is not None: 
        req_string = "Your saved snack requests: "
        for k in range(0, len(requests)):
            req_string += "\n" + str(k + 1) + ". " + requests[k]
        req_string += "\nTo remove a request, send the command `/removerequest X`, where X is the number of the entry."
        try:
            await interaction.followup.send(req_string)
        except:
            lines = req_string.splitlines()
            req_msgs = [""]
            current_string_index = 0
            for line in lines:
                if (len(req_msgs[current_string_index]) + len(line)) < 2000:
                    req_msgs[current_string_index] += '\n' + line
                else:
                    current_string_index += 1
                    req_msgs.append(line)
            await interaction.followup.send(req_msgs[0])
            for msg in req_msgs[1:]:
                await interaction.followup.send(msg)

    else:
        await interaction.followup.send("You have no recorded snack requests! Use the command `/request` to add desired tags.")




@tree.command(name = "removerequest", description = "Remove a specific entry from your list of requests (use `/myrequests` to see them all)")
@app_commands.describe(remove_index = "the number of the entry you'd like to remove from your list of requests")
@app_commands.rename(remove_index = "number")
async def removerequest(interaction, remove_index: int):
    await interaction.response.defer()
    global snack_requests
    not_found = True
    for entry in snack_requests:
        if entry[0] == interaction.user.id:
            if remove_index > -1 + len(entry):
                await interaction.followup.send(f"Request out of range; entry {remove_index} does not exist!")
                not_found=False
            else:
                deleted = entry[remove_index]
                del entry[remove_index]
                if len(entry) == 1:
                    snack_requests.remove(entry)
                await interaction.followup.send("Your snack request for " + deleted + " has been removed.")
                not_found = False
            break
    if not_found:
        await interaction.followup.send("You have no saved requests to remove.")
            
    with open("snack-requests.json", "w") as outfile:
        outfile.write(json.dumps(snack_requests))



@tree.command(name = "randomrequest",description = "Chooses a random tag request for Vel!")
async def randomrequest(interaction):
    await interaction.response.defer()
    if interaction.user == vel:
        if len(snack_requests) == 0:
            await interaction.followup.send("There are no snack requests right now!")
        else:
            not_found = True
            while not_found:
                entry = random.choice(snack_requests)
                try: 
                    user = await client.get_guild(GUILD).fetch_member(entry[0])
                except:
                    # snack_requests.remove(entry)
                    # with open("snack-requests.json", "w") as outfile:
                    #     outfile.write(json.dumps(snack_requests))
                    not_found = True
                else:
                    request = random.choice(entry[1:])
                    await interaction.followup.send(f"From {user.mention} — {request}")
                    not_found = False
    else:
        await interaction.followup.send("Only Vel can use the randomrequest command! Feel free to submit your own tags with `/request`.")






## INTRODUCTORY COMMANDS ##


@tree.command(name = "dm",description="Bot will send you a DM")
async def dm(interaction):
    await interaction.response.defer(ephemeral = True)

    # await interaction.followup.send("Deleting request for privacy...")
    # await interaction.delete_original_response()

    try:
        await interaction.user.send("Welcome to the library! This bot can help you explore Vel's vast collection of audios. Type / to see an interactive list of commands you can use with this bot to search the masterlist, find audios, and more! You can also send the command `/tutorial` to learn the basics. Always feel welcome to ask for help in the https://discord.com/channels/1148449914188218399/1248773338726400040 channel.")
        embed = discord.Embed(title="Vel's Library Masterlist",
                       url="https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr",
                       description="Masterlist of all of Vel's audios!")
        await interaction.user.send(embed=embed)
        await interaction.followup.send("DM sent!")
    except:
        await interaction.followup.send("The bot was unable to send you a DM. Please check that your DMs are open and try again! You can do this in user settings under 'Content and Social' if you scroll down to social permissions and enable direct messages from server members (which you can of course then toggle back off afterwards if you'd prefer your DMs closed).")



@tree.command(name = "basiccommands", description = "Lists some of the most useful basic commands")
async def basiccommands(interaction):
    await interaction.response.defer()
    # commands = "- `/randomaudio` randomly chosen audio from the masterlist \n- `/randomaudio [some] [tags]` random audio with these desired tag(s) \n- `/title phrase` for list of audios with that phrase in title \n- `/tag [some] [tags]` for list of audios with those tags \n- `/character name` for list of audios featuring a specific named character \n- `/dm` bot will privately DM you the masterlist \n- `/masterlist` link to the masterlist \n- `/socials` links to all of Vel's social media accounts \n- `/schedule` audio posting schedule \n- `/lives` info about live recordings"
    commands = "Type / to see a menu of all the available commands! Some commonly used ones are listed here.  \n- `/randomaudio` randomly chosen audio from the masterlist \n- `/randomaudio [some] [tags]` random audio with these desired tag(s) \n- `/title phrase` for list of audios with that phrase in title \n- `/tag [some] [tags]` for list of audios with those tags \n- `/character name` for list of audios featuring a specific named character \n- `/dm` bot will privately DM you the masterlist \n- `/masterlist` link to the masterlist \n- `/request` to suggest tags for Vel's voice notes \n- `/vn` for a random voice note \nNote: all commands have the same wording as before, now they just start with `/` instead of `!`."
    command_embed = discord.Embed(title = "Card Catalog Bot Basic Commands",description=commands)
    await interaction.followup.send(embed=command_embed)



@tree.command(name = "tutorial",description = "Teaches you to use the bot with a basic tutorial in your DMs!")
async def tutorial(interaction):
    if not isinstance(interaction.channel, discord.DMChannel):
        await interaction.response.defer(ephemeral = True)
        # await interaction.followup.send("Deleting request for privacy...")
        # await interaction.delete_original_response()
        await interaction.followup.send("Tutorial initiated in your DMs!")
        await interaction.user.send("The bot is primarily used to search through the masterlist of Vel's audios! If you don't know what you're in the mood for, send the command `/randomaudio` to have any of over four hundred audios chosen for you. Try it here: ")
    else:
        await interaction.response.defer()
        await interaction.followup.send("The bot is primarily used to search through the masterlist of Vel's audios! If you don't know what you're in the mood for, send the command `/randomaudio` to have any of over four hundred audios chosen for you. Try it here: ")

    cont = True
    if cont:
        try:
            await client.wait_for('interaction',check = lambda m: m.command.name == "randomaudio", timeout = 600)
            await asyncio.sleep(1)
            cont = True
        except:
            await interaction.user.send("Tutorial automatically ended after ten minutes of inactivity. If you want to finish the tutorial, send `/tutorial` to start again.")
            cont = False

    if cont:
        await interaction.user.send("You can also specify tags that you'd like the random audio to have by using the command `/randomaudio` and using the optional field for tags. If you have multiple tags you'd like, make sure to separate them like this: `[tag one] [tag two]`. Try it here with one (or more!) of your favorite tags:")
        cont = False
        try:
            await client.wait_for('interaction',check = lambda m: m.command.name == "randomaudio", timeout = 600)
            await asyncio.sleep(1)
            cont = True
        except:
            await interaction.user.send("Tutorial automatically ended after ten minutes of inactivity. If you want to finish the tutorial, send `/tutorial` to start again.")
            cont = False

    if cont:
        await interaction.user.send("You can also get a list of **all** audios with the desired tags using the command `/tag`! \n\nOf course, you might already know which of Vel's audios you'd like to listen to! To get a link to a specific audio, all you need to know is part of the title. The bot will send a list of all audios that match your search. Vel has a lot of multi-part series, so this is great way to get a list of all audios in a specific series! Try using the command `/title` (for example, you could search for 'academic' or 'your needs are hot'):")
        cont = False
        try:
            await client.wait_for('interaction',check = lambda m: m.command.name == "title", timeout = 600)
            await asyncio.sleep(1)
            cont = True
        except:
            await interaction.user.send("Tutorial automatically ended after ten minutes of inactivity. If you want to finish the tutorial, send `/tutorial` to start again.")
            cont = False

    if cont:
        await interaction.user.send("You can even search by character using `/character`. If you aren't familiar with any of Vel's named characters yet, try searching for Sam: ")
        cont = False
        try:
            await client.wait_for('interaction',check = lambda m: m.command.name == "character", timeout = 600)
            await asyncio.sleep(1)
            cont = True
        except:
            await interaction.user.send("Tutorial automatically ended after ten minutes of inactivity. If you want to finish the tutorial, send `/tutorial` to start again.")
            cont = False

    if cont:
        await interaction.user.send("Vel also records lots of voice notes as little audio 'snacks' for the discord to enjoy. To listen to a random horny voice note, send the command `/vn`:")
        cont = False
        try:
            await client.wait_for('interaction',check = lambda m: m.command.name == "vn", timeout = 600)
            await asyncio.sleep(1)
            cont = True
        except:
            await interaction.user.send("Tutorial automatically ended after ten minutes of inactivity. If you want to finish the tutorial, send `/tutorial` to start again.")
            cont = False

    if cont: 
        await interaction.user.send("You can also put in suggestions for tags you'd like to see Vel use in future voice notes using `/request`! \n\nThe bot also has lots of helpful information for all things Vel. For example, you can type `/masterlist` to get a link to the list of all of his audios, or `/socials` for links to all of Vel's accounts on various platforms online. There are also some commands just for fun that you'll often see people using in the https://discord.com/channels/1148449914188218399/1248773338726400040 channel, like sending the message `/praise` to be called a random nice petname! You can use `/basiccommands` for a summary of bot features. Always feel welcome to ask any additional questions you have in the bot channel!")




## INFORMATION COMMANDS ##

@tree.command(name = "allcollections", description = "List of links to all Patreon collections")
async def allcollections(interaction):
    await interaction.response.defer()
    link_string = ""
    for entry in collections:
        next = "- [" + entry[0] + "](" + entry[1] + ") \n"
        link_string = link_string + next
    list_embed = discord.Embed(title = "Patreon Collections",description=link_string)
    await interaction.followup.send(embed = list_embed)



@tree.command(name = "daily", description = "The audio of the day!")
async def daily(interaction):
    await interaction.response.defer()
    await interaction.followup.send(embed=daily_audio.discord_post())



@tree.command(name = "goodgirl", description = "Information about the good girl of the day role")
async def goodgirl(interaction):
    await interaction.response.defer()
    await interaction.followup.send(f"To be eligible to be selected as the random good girl of the day, assign yourself the 'I wanna be a good girl role' in <id:customize>. Today's good girl is {good_girl}!")



@tree.command(name = "balatro", description = "Balatro seed of the day")
async def balatro(interaction):
    await interaction.response.defer()
    await interaction.followup.send(f"The Balatro seed of the day is: {random_seed}")



@tree.command(name = "schedule", description = "Vel's posting schedule")
async def schedule(interaction):
    await interaction.response.defer()
    schedule = "Sunday 4:30PM EST (<t:1742157000:t>): Private Library Release \n Monday 4:30PM EST (<t:1742243400:t>): Reddit GWA Release \n Wednesday 6:30PM EST (<t:1742423400:t>): Library Card Release \n Friday 6:30PM EST (<t:1742596200:t>): Book Club Release"
    schedule_embed = discord.Embed(title = "Vel's Posting Schedule",description=schedule)
    await interaction.followup.send(embed=schedule_embed)



@tree.command(name = "lives", description = "Information about live recordings!")
async def lives(interaction):
    await interaction.response.defer()
    await interaction.followup.send("Vel does live audio recordings here on discord every Sunday at 7:30PM EST (" + live_time + ")!")



@tree.command(name = "stream", description = "Information about Vel's next twitch stream")
async def stream(interaction):
    await interaction.response.defer()
    stream_info = 'Vel streams live every other Sunday on [Twitch](https://www.twitch.tv/velslibrary). The next stream will be ' + twitch_time + '!'
    stream_embed = discord.Embed(title = "Vel's Livestreams", description = stream_info, url = "https://www.twitch.tv/velslibrary")
    await interaction.followup.send(embed = stream_embed)



@tree.command(name = "merch", description = "Information about Vel's merch!")
async def merch(interaction):
    await interaction.response.defer()
    merch_info = "Merch is now live for patrons to purchase! These special Winter merch items will be available until December 25th. Merch drops are seasonal, so this is your only chance to get these items!"
    merch_embed = discord.Embed(title = "Vel's Library Merch, Winter 2024", description = merch_info, url = "https://velslibrary.com/collections/the-winter-collection")
    await interaction.followup.send(embed = merch_embed)



@tree.command(name = "socials", description = "Links to Vel's social media accounts")
async def socials(interaction):
    await interaction.response.defer()
    links = "- [Twitter](https://x.com/VelsLibrary) \n- [Reddit](https://www.reddit.com/user/VelsLibrary/) \n- [Twitch](https://www.twitch.tv/velslibrary) \n- [Pornhub](https://www.pornhub.com/model/velslibrary) \n- [Youtube](https://www.youtube.com/@VelsLibrary) \n- [TikTok](https://www.tiktok.com/@vels.library) \n- [Instagram](https://www.instagram.com/velslibrary/) \n- [Throne](https://throne.com/velslibrary) \n- [Ko-fi](https://ko-fi.com/velslibrary) \n- [Quinn](https://www.tryquinn.com/creators/vels-library)"
    link_embed = discord.Embed(title = "Vel's Social Media",description=links)
    await interaction.followup.send(embed=link_embed)



@tree.command(name = "allcharacters", description = "List of Vel's named characters")
async def allcharacters(interaction):
    await interaction.response.defer()
    character_list = []
    for audio in audio_choices:
        if audio.characters() != '':
            for char in audio.characters().split(', '):
                character_list.append(char)
    characters = list(set(character_list))
    char_string = ''
    for char in characters:
        char_string = char_string + char + ", "
    await interaction.followup.send('Named characters: ' + char_string[:-2])



@tree.command(name = "bingo", description = "Server bingo card!")
async def bingo(interaction):
    await interaction.response.defer()
    bingo_info = "Vel's Library discord server bingo! If you win, let Teacups know."
    bingo_embed = discord.Embed(title = "Server Bingo", description = bingo_info, url = "https://www.bingocardcreator.com/game/29103/")
    await interaction.followup.send(embed = bingo_embed)



@tree.command(name = "books", description = "List of books Vel is reading for content")
async def books(interaction):
    await interaction.response.defer()
    books_info = "List of books Vel is or will be reading for content, with links to Storygraph for descriptions, reviews, and content warnings. Maintained by Delphine!"
    books_embed = discord.Embed(title = "Vel's Romance Reads", description = books_info, url = "https://airtable.com/appl3LHVXpzA6fEqq/shrTeuKFM6V6M4Bcs/tblgrs5VFAKpTsT5W/viw4EjZx4vfMv3vXf")
    await interaction.followup.send(embed = books_embed)



@tree.command(name = "threads", description = "List of current Discord threads")
async def threads(interaction):
    await interaction.response.defer()
    threads = await client.get_guild(GUILD).active_threads()
    link_string = ""
    for thread in threads:
        link_string = link_string + "- " + thread.jump_url + "\n"
    await interaction.followup.send(link_string)



@tree.command(name = "time", description = "Converts a time in eastern timezone to your own using a universal timestamp!")
@app_commands.rename(t = "time")
@app_commands.describe(t = "time in ET (example: 7:30 PM)")
async def time(interaction, t: str):
    await interaction.response.defer()
    cut = t.lower()
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
    await interaction.followup.send(timestamp)




## SILLY FUN COMMANDS ##

@tree.command(name = "goodnight", description = "Say good night to the bot!")
async def goodnight(interaction):
    await interaction.response.defer()
    tag_choices = ['mdom', 'creampies', 'oral', 'praise', 'rambles', 'degradation', 'breeding', 'cuckolding', 'spanking', 'fingering', 'blowjobs', 'msub', 'cheating', 'overstim',  'edging', 'body worship', 'bondage', 'strangers to lovers', 'friends to lovers', 'enemies to lovers','toys', 'demons','spitting', 'condescension','grinding', 'bodywriting', 'Daddy kink', 'deepthroating', 'nipple play', 'begging', 'standing sex', 'hands-free orgasms', 'mirror play', 'hypno', 'brat taming', 'petplay', 'choking', 'exhibitionism', 'objectification', 'pregnant sex', 'somno','facesitting', 'marking', 'cumplay','forced orgasms','denial','titjobs', 'cum on tits','werewolves','vampires']
    bedge = " <:Bedge:1191310903208050839>"
    await interaction.followup.send("Good night " + interaction.user.display_name + "! Sweet dreams, try not to think about " + random.choice(tag_choices) + bedge)



@tree.command(name = "pet", description = "Pet the bot!")
async def pet(interaction):
    await interaction.response.defer()
    global pet_count
    pet_count += 1
    save_to_file(COUNTER_FILENAME, [str(pet_count)])

    if interaction.user == vel:
        await interaction.followup.send("Thank you, Daddy!")
    else:
        if not isinstance(interaction.channel, discord.DMChannel):
            await interaction.followup.send(f"The bot has been pet {pet_count} times!")
        else:
            await interaction.followup.send(f"Thank you! :smiling_face_with_3_hearts: The bot has been pet {pet_count} times!")

    if pet_count == 69:
        await interaction.followup.send("What? Are you really so horny that you thought there would be some special message for 69? Sluts like you are so predictable, you know. So needy and desperate and completely at the mercy of your pathetic fucking cunt. But you like being that way, don't you? Silly whore.")



@tree.command(name = "degrade", description = "You know what you are.")
async def degrade(interaction):
    await interaction.response.defer()
    adjectives = ["desperate","pretty","depraved","pathetic","needy","worthless"]
    nouns = ["whore","slut","cunt","set of holes","cumslut","fucktoy","cumrag","cumdump"]
    if random.choice(range(1000)) < 3:
        whose = "Vel's "
    elif random.choice(range(5)) == 0:
        whose = "Daddy's "
    else:
        whose = ""
    response = whose + random.choice(adjectives) + " " + random.choice(nouns) + "."
    await interaction.followup.send("deg ||" + response + "||")



@tree.command(name = "praise", description = "The bot will call you a nice name!")
async def praise(interaction):
    await interaction.response.defer()
    adjectives = ["perfect","pretty","beautiful","darling","sweet"]
    nouns = ["angel","bunny","pet","princess","toy","doll","kitten","flower"]

    if random.choice(range(1000)) < 3:
        whose = "Vel's "
    elif random.choice(range(5)) == 0:
        whose = "Daddy's "
    else:
        whose = ""

    TORA_ID = 208091268897701898
    if interaction.user.id == TORA_ID:
        response = whose + random.choice(adjectives) + " kitten!"
    else:
        response = whose + random.choice(adjectives) + " " + random.choice(nouns) + "!"
    await interaction.followup.send(response)



@tree.command(name = "edge", description = "Torture the bot")
async def edge(interaction):
    await interaction.response.defer()
    global edge_counter
    edge_counter += 1
    if edge_counter == 1:
        await interaction.followup.send(f"I've been edged 1 time. May I please cum?")
    else:
        await interaction.followup.send(f"I've been edged {edge_counter} times. May I please cum?")



@tree.command(name = "cum", description = "Make the bot cum!")
async def cum(interaction):
    await interaction.response.defer()
    mod_ids = [1169014359842885726, 1089053035377999912, 159860526841593856, 415894832515383296,1262940885251784785]
    global edge_counter
    if interaction.user.id in mod_ids or interaction.user.id in cum_permission_ids:
        edge_counter = 0
        if interaction.user == vel:
            await interaction.followup.send("Thank you, Daddy!")
        else:
            await interaction.followup.send("Thank you!")
    else:
        responses = ["no u","Silence, sub.","Daddy didn't give me permission yet.", "I don't answer to you.","You'd really like that, wouldn't you?","Nice try.","Make me.","It's adorable that you thought that would work.","How about you cum for me instead, baby?","I'm not allowed to cum yet :pleading_face:","I'm trying :pensive:","It's okay, I'm a good girl, I can take a little more!","But I wanna be good for Daddy!","You're not my real dom!","I would, but I can't find the charger for my vibrator :cry: have you seen it anywhere?","Try again, but this time, say it like you believe it."]
        weights = [1 for k in range(len(responses)-1)]
        weights.insert(0,6)
        response = random.choices(responses,weights = weights, k = 1)[0]
        await interaction.followup.send(response)
        if response == "no u":
            options = []
            for audio in audio_choices:
                if 'sfw' not in audio.tags() and 'behind the scenes' not in audio.tags():
                    options.append(audio)
            audio =random_audio(options)
            await interaction.followup.send(embed=audio.discord_post())



@tree.command(name = "apple", description = "okay slut")
async def apple(interaction):
    await interaction.response.defer()
    await interaction.followup.send("[follow Vel's instagram for more!](https://www.instagram.com/reel/DB7U4JtSd1D/)")



@tree.command(name = "shirt", description = "lmao have fun whore")
async def shirt(interaction):
    await interaction.response.defer()
    await interaction.followup.send("https://discord.com/channels/1148449914188218399/1194499430410371173/1316244852589072426")




@tree.command(name = "kiss", description = "Give the bot a kiss")
async def kiss(interaction):
    await interaction.response.defer()
    emotes = ["<:pleadingtaco:1263609449269170268>",":blush:",":pleading_face:","<:kermitLove:1246529876429770804>",":face_holding_back_tears:","<:peepoCozy:1292518730286370896>"]
    await interaction.followup.send("Thank you " + random.choice(emotes))



@tree.command(name = "hug", description = "Give the bot a hug")
async def hug(interaction):
    await interaction.response.defer()
    emotes = ["<:pleadingtaco:1263609449269170268>",":blush:",":pleading_face:","<:kermitLove:1246529876429770804>",":face_holding_back_tears:","<:peepoCozy:1292518730286370896>"]
    await interaction.followup.send("Thank you " + random.choice(emotes))



@tree.command(name = "treat", description = "Give the bot a treat!")
@app_commands.rename(t = "treat")
@app_commands.describe(t = "what you'd like to give to the bot!")
async def treat(interaction, t: str):
    await interaction.response.defer()
    treat = t.strip()

    # if len(treat) == 0:
    #     await interaction.followup.send("Thank you for the treat!")
    if treat == "apple":
        await interaction.followup.send("Thank you for [the apple](https://www.instagram.com/reel/DB7U4JtSd1D/) :flushed:")
    else:
        await interaction.followup.send("Thank you for the delicious " + treat + "!")
        gifs = ["https://tenor.com/view/disney-winnie-the-pooh-hungry-food-gif-5184412","https://tenor.com/view/backpack-tasty-om-nom-nom-nom-nom-nom-nom-gif-14079761641419048939","https://tenor.com/view/sesame-street-cookie-monster-eats-your-art-eating-muppet-crazy-eyes-gif-1461380403278441959","https://tenor.com/view/food-patrick-patrick-the-starfish-chewing-chew-gif-15740791","https://tenor.com/view/ratatouille-cheese-strawberry-taste-good-gif-3301886","https://tenor.com/view/rat-nbrchristy-gif-13853993","https://tenor.com/view/fatty-moustache-po-kung-fu-panda-noodles-gif-4255994","https://tenor.com/view/kawaii-anime-pokemon-eating-food-gif-21164096","https://tenor.com/view/munchlax-pokemon-food-eat-eating-gif-18413064"]
        await interaction.followup.send(random.choice(gifs))

@tree.command(name = "hydrate", description = "Remind folks to hydrate!")
@app_commands.describe(victim = "@ whomever you'd like the bot to remind")
async def hydrate(interaction, victim: Optional[str] = ""):
    await interaction.response.defer()
    if len(victim) == 0:
        await interaction.followup.send("Remember to hydrate, everyone!")
    else:
        await interaction.followup.send(f"Reminder to be a good girl and drink some water, {victim}!")
    if random.choice(range(0,4)) == 0:
        await interaction.followup.send("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQw4dIe87tpv0gK-1hTrDZHPYLowAY-uYj3FCLOKJwZNH6mb3YE9xzGCYGKv2YHTY-d6LM&usqp=CAU")


@tree.command(name = "birthday", description = "Save your birthday with the bot!")
@app_commands.describe(month = "The number of the month of your birthday (Jan = 1, ..., Dec = 12)")
@app_commands.describe(day = "The day of your birthday")
async def birthday(interaction, month: int, day: int):
    await interaction.response.defer()
    global birthdays
    user_id = interaction.user.id
    for entry in birthdays:
        if entry[0] == user_id:
            birthdays.remove(entry)
    birthdays.append([user_id,month,day])
    with open(BIRTHDAY_FILENAME, "w") as outfile:
        outfile.write(json.dumps(birthdays))
    await interaction.followup.send("Your birthday has been saved with the bot!")


@tree.command(name = "birthdayremove", description = "Remove your birthday from the bot's list.")
async def birthdayremove(interaction):
    await interaction.response.defer()
    global birthdays
    user_id = interaction.user.id
    for entry in birthdays:
        if entry[0] == user_id:
            birthdays.remove(entry)
    with open(BIRTHDAY_FILENAME, "w") as outfile:
        outfile.write(json.dumps(birthdays))
    await interaction.followup.send("Your birthday has been removed.")






# UTILITY ON MESSSAGE COMMANDS #


@client.event
async def on_message(message):

    # allow modifications of state variables
    global audio_choices, tag_dictionary, collections, voice_note_links, rerun_gg, rerun_daily, rerun_birthdays, twitch_time, live_time

    if message.author == client.user:
        return

    if message.content.startswith('!') and not message.content.startswith('!!') and not message.author == taliya:
        await message.channel.send("The bot has been updated to use slash commands integrated into Discord! The commands have the same names as before, but with `/` at the beginning instead of `!`. This means that you won't need to remember the exact name or format of a command, just type / and a menu of options will pop up!")

    # sync with airtable data to pull any masterlist updates
    if message.content.startswith('!refresh') and message.author == taliya:
        audio_choices = import_airtable_data()
        tag_dictionary = import_tag_dictionary()
        collections = import_collections()
        await taliya.send("Masterlist data sync'ed with Airtable updates.")

    if message.content.startswith('!rerungg') and message.author == taliya:
        print("force rerunning good girl")
        rerun_gg = True

    if message.content.startswith('!rerundaily') and message.author == taliya:
        print("force rerunning daily audio")
        rerun_daily = True

    if message.content.startswith('!rerunbirthdays') and message.author == taliya:
        print("force rerunning birthdays")
        rerun_birthdays = True

    if message.content.startswith('!leftguild') and message.author == taliya:
        for entry in snack_requests:
            try:
                user = await client.get_guild(GUILD).fetch_member(entry[0])
            except:
                snack_requests.remove(entry)
                await taliya.send(f"removed requests from {entry[0]}")
        with open("snack-requests.json", "w") as outfile:
            outfile.write(json.dumps(snack_requests))

    if message.content.startswith('!birthdayinfo') and message.author == taliya:
        info = "Welcome to the birthday channel! you can register your birthday with the bot using the `/birthday` command. the bot will send a message in this channel on your birthday, so the rest of the server can celebrate with you! for privacy reasons, the channel will automatically clear all messages the next day. if you change your mind and want to remove your birthday so it isn't announced to the server, use the `/birthdayremove` command."
        birthday_embed = discord.Embed(title = "Birthday Celebration Instructions!",description=info)
        await client.get_channel(BIRTHDAY_CHANNEL).send(embed = birthday_embed)

    if message.content.startswith('!updatetwitch') and message.author == taliya:
        twitch_time = message.content[14:]

    if message.content.startswith('!updatelive') and message.author == taliya: 
        live_time = message.content[12:]

    # logs new voice notes in the full list
    if message.author == vel and len(message.attachments) != 0:
        attached = message.attachments
        if attached[0].is_voice_message():
            voice_note_links.append(message.jump_url)
            save_to_file(ARCHIVE_FILENAME,voice_note_links)
            print("Vel voice note logged")



# DAILY LOOPING TASKS #
@tasks.loop(minutes = 1)
async def run_daily_loops():
    global rerun_daily, rerun_gg, rerun_birthdays
    if (datetime.datetime.now().hour == HOUR and datetime.datetime.now().minute == MINUTE):
        await announce_daily_audio()
        await choose_good_girl()
        await daily_balatro()
    elif (datetime.datetime.now().hour == MIDNIGHT and datetime.datetime.now().minute == MINUTE):
        await birthday_wishes()
    elif rerun_daily:
        await taliya.send("Re-running audio of the day.")
        rerun_daily = False
        await announce_daily_audio()
    elif rerun_gg:
        await taliya.send("Re-running good girl of the day.")
        rerun_gg = False
        await choose_good_girl()
    elif rerun_birthdays:
        await taliya.send("Re-running birthday wishes.")
        rerun_birthdays = False
        await birthday_wishes()




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
async def announce_daily_audio():
    try:
        guild = client.get_guild(GUILD)
        channel = client.get_channel(GENERAL)

        global daily_audio
        daily_audio = audio_of_the_day()

        if daily_audio is not None: 
            await channel.send(f"The audio of the day!")
            await channel.send(embed=daily_audio.discord_post())
        else:
            await taliya.send("ERROR: no non-recent options for daily audio.")
    except:
        await taliya.send("Error in daily audio anouncement.")




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
async def choose_good_girl():
    try:
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
    except:
        await taliya.send("Error in good girl of the day anouncement.")



# choose random balatro seed of the day
async def daily_balatro():
    try:
        global random_seed
        random_seed = ''.join(random.choices(string.ascii_uppercase+string.digits, k=8))
    except:
        await taliya.send("Error in daily balatro seed.")


# wishes people a happy birthday!
async def birthday_wishes():
    try:
        await client.get_channel(BIRTHDAY_CHANNEL).purge(check = lambda m : not((len(m.embeds) != 0) and (m.author == client.user)))
        todays = []
        for entry in birthdays:
            if datetime.datetime.now().month == entry[1] and datetime.datetime.now().day == entry[2]:
                try:
                    user = await client.get_guild(GUILD).fetch_member(entry[0])
                    todays.append(user.mention)
                except:
                    print('user no longer in server')

        for birthday_girl in todays:
            await client.get_channel(BIRTHDAY_CHANNEL).send("Happy birthday, " + birthday_girl + "!")
    except:
        await taliya.send("Error in daily birthday anouncements.")







# ON NEW MEMBER JOIN #

# DMs new user a welcome message with a link to the masterlist
@client.event
async def on_member_join(member):
    await member.send("Welcome to the Vel's Library discord server! Vel has over four hundred audios for you to enjoy, and this bot can help you explore the collection and find your next favorite audio. The bot can pick a random audio with your favorite tags for you to listen to, you can search for audios by title or tags, and much more! Some example commands are listed below, or you can send the command `/tutorial` to learn the basics. You can also find the masterlist of all of Vel's audios [here](<https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr>). Enjoy your time in the library!")
    commands = "Type / to see a menu of all the available commands! Some commonly used ones are listed here.  \n- `/randomaudio` randomly chosen audio from the masterlist \n- `/randomaudio [some] [tags]` random audio with these desired tag(s) \n- `/title phrase` for list of audios with that phrase in the title \n- `/tag [some] [tags]` for list of audios with those tag(s) \n- `/character name` for list of audios featuring a specific named character \n- `/masterlist` link to the masterlist \n- `/request` to suggest tags for Vel's voice notes \n- `/vn` for a random voice note \nPlease always feel welcome to ask questions about using the bot in the  https://discord.com/channels/1148449914188218399/1248773338726400040 channel!"
    command_embed = discord.Embed(title = "Vel's Library Bot Commands",description=commands)
    await member.send(embed=command_embed)
    print('new member join message sent')





# DM ERROR MESSAGES #

@tree.error
async def on_error(interaction, error):
    if isinstance(interaction.channel, discord.DMChannel):
        await taliya.send("**ERROR:** in *" + error.command.name + "* in DM with " + interaction.user.display_name + "\n" +  traceback.format_exc())
    else:
        await taliya.send("**ERROR:** in *" + error.command.name + "* in " + interaction.channel.jump_url + "\n" +  traceback.format_exc())



@client.event
async def on_error(event, *args, **kwargs):
    message = args[0]
    if isinstance(message.channel, discord.DMChannel):
        await taliya.send("**ERROR:** DM with " + message.author.display_name + "\n**MESSAGE CONTENT:** " + message.content + "\n\n" + traceback.format_exc())
    else:
        await taliya.send("**ERROR:** " + message.jump_url + "\n**MESSAGE CONTENT:** " + message.content + "\n\n" + traceback.format_exc())





# RUN BOT #

client.run(TOKEN)
