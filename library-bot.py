import discord
import os
import datetime
import random
import string
import asyncio
import time
import calendar
import traceback


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

# run daily tasks at 1pm eastern time (6pm UTC+1)
HOUR = 17
MINUTE = 0


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)







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





# extracts tag from !randomaudio request 
# works regardless of whether or not square brackets were used
def get_tags(message):
    msg = message.strip()
    tag = msg[13:].strip()

    if len(tag) == 0:
        return None
    if tag[0] == '[':
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

# search for matching character names
def character_search(name):
    matching = []
    for audio in audio_choices:
        if name.lower() in audio.characters().lower():
            matching.append(audio)
    matching.sort(key = age_sort)
    return matching








# import masterlist data from airtable API
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

currentwinner = read_from_file(WINNERS_FILENAME)[-1]
currentdaily = read_from_file(AUDIOS_FILENAME)[-1]
currentpetcount = int(read_from_file(COUNTER_FILENAME)[-1])




@client.event
async def on_ready():
    print(f'Logged in as {client.user}')



@client.event
async def setup_hook():
    print("setup hook running")

    # import data from airtable
    global audio_choices
    audio_choices = import_airtable_data()

    global tag_dictionary
    tag_dictionary = import_tag_dictionary()

    global daily_audio
    for audio in audio_choices:
        if audio.name() == currentdaily:
            daily_audio = audio

    global random_seed
    random_seed = ''.join(random.choices(string.ascii_uppercase+string.digits, k=8))

    global good_girl
    good_girl = currentwinner

    global pet_count, edge_counter, winner_ids
    pet_count = currentpetcount
    edge_counter = 0
    winner_ids = [0]

    # set all daily tasks running
    if not announce_daily_audio.is_running():
        announce_daily_audio.start()
    if not choose_good_girl.is_running():
        choose_good_girl.start()
    if not daily_balatro.is_running():
        daily_balatro.start()
    if not cum_permissions.is_running():
        cum_permissions.start()

    global taliya, vel
    taliya = await client.fetch_user(1169014359842885726)
    vel = await client.fetch_user(1089053035377999912)

    await taliya.send(f"Card Catalog bot restarted successfully at {datetime.datetime.now().hour}:{datetime.datetime.now().minute}!")



# ON MESSSAGE COMMANDS

@client.event
async def on_message(message):

    if message.author == client.user:
        return

    # remove case-sensitivity
    msg = message.content.lower()

    global audio_choices, tag_dictionary, pet_count, edge_counter

    if msg.startswith('!masterlist'):
        embed = discord.Embed(title="Vel's Library Masterlist",
                       url="https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr",
                       description="Masterlist of all of Vel's audios!")
        await message.channel.send(embed=embed)


    if msg.startswith('!dm'):
        await message.author.send("Here's a link to the masterlist! Send the message `!allcommands` to learn how to use the bot to find audios and more.")
        embed = discord.Embed(title="Vel's Library Masterlist",
                       url="https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr",
                       description="Masterlist of all of Vel's audios!")
        await message.author.send(embed=embed)
        # delete the user's message requesting the DM 
        if not isinstance(message.channel, discord.DMChannel):
            await message.delete()


    if msg.startswith('!randomaudio'):
        # # checking to see if the user specified a tag, use if leading != 0
        # leading, trailing = 1+msg.find('['), msg.find(']')
        # tag = msg[leading:trailing]
        tags = get_tags(msg)
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
            await message.channel.send(f'No audios found with title including the phrase "{phrase}."')
        elif len(matches) == 1:
            await message.channel.send(embed=matches[0].discord_post())     
        else:
            count = len(matches)
            await message.channel.send(str(count) + ' matches found for "' + phrase + '."')

            link_string = ""
            for i in list(range(count)):
                next = str(i+1) + ". [" + matches[i].name() + "](" + matches[i].link() + ")" + '\n'
                link_string = link_string + next

            matches_embed = discord.Embed(title = "Matching Results",description=link_string)
            await message.channel.send(embed = matches_embed)


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


    if msg.startswith('!daily'):
        await message.channel.send("Here's a link to the audio of the day!")
        await message.channel.send(embed=daily_audio.discord_post())


    if msg.startswith('!balatro'):
        await message.channel.send(f"The Balatro seed of the day is: {random_seed}")


    if msg.startswith('!schedule'):
        # schedule = "Sunday 4:30PM EST: Private Library Release \n Monday 4:30PM EST: Reddit GWA Release \n Wednesday 6:30PM EST: Library Card Release \n Every other Thursday 4:30PM EST: Reddit GWA Release \n Friday 6:30PM EST: Book Club Release"
        schedule = "Sunday 4:30PM EST (<t:1716755400:t>): Private Library Release \n Monday 4:30PM EST (<t:1716841800:t>): Reddit GWA Release \n Wednesday 6:30PM EST (<t:1717021800:t>): Library Card Release \n Every other Thursday 4:30PM EST (<t:1717101000:t>): Reddit GWA Release \n Friday 6:30PM EST (<t:1717194600:t>): Book Club Release"
        schedule_embed = discord.Embed(title = "Vel's Posting Schedule",description=schedule)
        await message.channel.send(embed=schedule_embed)


    if msg.startswith('!live'):
        await message.channel.send("Vel does live audio recordings here on discord every Sunday at 7:30PM EST (<t:1716766200:t>)!")


    if msg.startswith('!stream'):
        # stream_info = 'Vel streams live every other Sunday on [Twitch](https://www.twitch.tv/velslibrary). The next stream, "How Vel Does Vel Know Vel?" (quizzing the librarian himself on how well he knows his own content), will be <t:1722799800:F>!'
        stream_info = 'Vel streams live every other Sunday on [Twitch](https://www.twitch.tv/velslibrary). The next stream will be <t:1724009400:F>!'
        stream_embed = discord.Embed(title = "Vel's Livestreams", description = stream_info, url = "https://www.twitch.tv/velslibrary")
        await message.channel.send(embed = stream_embed)


    if msg.startswith('!merch'):
        merch_info = "Merch is now live for patrons to purchase! To access the store, use password ||goodgirl||. These items will be available until <t:1723089540:F>. Merch drops are seasonal, so this is your only chance to get these!"
        merch_embed = discord.Embed(title = "Vel's Library Merch, Summer 2024", description = merch_info, url = "https://vel-1-shop.fourthwall.com/")
        await message.channel.send(embed = merch_embed)


    if msg.startswith('!social'):
        # await message.channel.send("here are links to all of Vel's socials")
        links = "- [Twitter](https://x.com/VelsLibrary) \n- [Reddit](https://www.reddit.com/user/VelsLibrary/) \n- [Twitch](https://www.twitch.tv/velslibrary) \n- [Pornhub](https://www.pornhub.com/model/velslibrary) \n- [Youtube](https://www.youtube.com/@VelsLibrary)"
        link_embed = discord.Embed(title = "Vel's Socials",description=links)
        await message.channel.send(embed=link_embed)


    if msg.startswith('!goodgirl'):
        await message.channel.send(f"To be eligible to be selected as the random good girl of the day, assign yourself the 'I wanna be a good girl role' in <id:customize>. Today's good girl is {good_girl}!")


    # list all bot commands
    if msg.startswith('!allcommands'):
        commands = "- `!randomaudio` randomly chosen audio from the masterlist \n- `!randomaudio [some] [tags]` random audio with these desired tag(s) \n- `!title phrase` for list of audios with that phrase in title \n- `!character name` for list of audios featuring a specific named character \n- `!daily` for the randomly chosen audio of the day \n- `!dm` bot will privately DM you the masterlist \n- `!masterlist` link to the masterlist \n- `!schedule` audio posting schedule \n- `!lives` info about live recordings \n- `!socials` links to all of Vel's social media accounts \n- `!goodgirl` to sign up for good girl role \n- `!stream` for information about the next twitch stream \n- `!balatro` for daily seed \n- `!merch` for information about the upcoming merch drop \n- `!time H:MM AM/PM` to convert from eastern time to universal timestamp"
        command_embed = discord.Embed(title = "Card Catalog Bot Commands",description=commands)
        await message.channel.send(embed=command_embed)


    if msg.startswith('!refresh'):
        # sync with airtable data to pull any masterlist updates
        audio_choices = import_airtable_data()
        tag_dictionary = import_tag_dictionary()
        await taliya.send("Masterlist data sync'ed with Airtable updates.")


    if '!time' in msg:
        # input is in the format "!timestamp 3:00 PM" assumed eastern time
        timestamp = universal_time(msg)
        await message.channel.send(timestamp)


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


    if msg.startswith('!praise'):
        adjectives = ["perfect","pretty","beautiful","darling","sweet"]
        nouns = ["angel","bunny","pet","princess","toy","doll","kitten"]

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


    if msg.startswith('!edge'):
        edge_counter += 1
        if edge_counter == 1:
            await message.channel.send(f"I've been edged 1 time. May I please cum?")
        else:
            await message.channel.send(f"I've been edged {edge_counter} times. May I please cum?")


    if msg.startswith('!cum'):
        mod_ids = [1169014359842885726, 1089053035377999912, 159860526841593856, 415894832515383296]
        if message.author.id in mod_ids or message.author.id in winner_ids:
            edge_counter = 0
            await message.channel.send("Thank you!")
        else:
            responses = ["Silence, sub.","Daddy didn't give me permission yet.", "I don't answer to you.","You'd really like that, wouldn't you?","Nice try."]
            await message.channel.send(random.choice(responses))




def universal_time(eastern_timestring):
    cut = eastern_timestring[(6 + eastern_timestring.find("!time")):]
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
    stamp = "<t:" + str(epoch_time) + ":t>"
    return stamp







# DAILY LOOPING TASKS


# choose random audio from list of eligible options
# ensures choice not in the recent list (imported from file)
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
    return winner


@tasks.loop(minutes = 1)
async def choose_good_girl():
    if datetime.datetime.now().hour == HOUR and datetime.datetime.now().minute == MINUTE:
        global good_girl
        guild = client.get_guild(GUILD)
        channel = client.get_channel(GENERAL)
        good_girl_role = guild.get_role(WINNER_ROLE)

        await asyncio.sleep(10)
        for member in good_girl_role.members:
            # remove good girl role from yesterday's winner
            await member.remove_roles(good_girl_role)

        # choose new random winner for the day
        options = guild.get_role(OPTIONS_ROLE).members
        winner = choose_next_winner(options)

        if datetime.datetime.now().month == 6 and datetime.datetime.now().day == 9:
            winner = await client.fetch_user(1241573320114049078)

        # send message and assign good girl role to winner
        if winner is not None:
            await channel.send(f'{winner.mention} is the good girl of the day!')
            await winner.add_roles(good_girl_role)
            good_girl = winner.display_name
        else:
            await taliya.send("ERROR: no non-recent options for good girl of the day.")



@tasks.loop(minutes = 1)
async def daily_balatro():
    if datetime.datetime.now().hour == HOUR and datetime.datetime.now().minute == MINUTE:
        global random_seed
        random_seed = ''.join(random.choices(string.ascii_uppercase+string.digits, k=8))


@tasks.loop(minutes = 1)
async def cum_permissions():
    if datetime.datetime.now().hour == 15 and datetime.datetime.now().minute == 36:
        LIBRARY_CARD = 1148454184824360990
        guild = client.get_guild(GUILD)
        options = guild.get_role(LIBRARY_CARD).members

        winners = random.choices(options, 10)
        global winner_ids
        winner_ids  = [user.id for user in winners]
        winner_names = [user.display_name for user in winners]
        print(winner_names)




# ON NEW MEMBER JOIN

@client.event
async def on_member_join(member):
    await member.send("Welcome to the Library! You can use this bot to explore all of Vel's content. There are over three hundred audios to choose from, so send a message with the command `!randomaudio [desired tag]` to have the bot choose a random audio for you with whatever tag(s) you like. To learn how to use this bot to search for audios and learn other information about Vel's content, send the message`!allcommands`.")
    embed = discord.Embed(title="Vel's Library Masterlist",
                   url="https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr",
                   description="Here's a link to the masterlist of all of Vel's audios. You can search and filter the masterlist for your favorite tags.")
    await member.send(embed=embed)
    print('new member join message sent')







# DM ERROR MESSAGES

@client.event
async def on_error(event, *args, **kwargs):
    message = args[0]
    if isinstance(message.channel, discord.DMChannel):
        await taliya.send("**ERROR:** DM with " + message.author.display_name + "\n**MESSAGE CONTENT:** " + message.content + "\n\n" + traceback.format_exc())
    else:
        await taliya.send("**ERROR:** " + message.jump_url + "\n**MESSAGE CONTENT:** " + message.content + "\n\n" + traceback.format_exc())








# RUN BOT

client.run(TOKEN)

