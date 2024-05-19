import discord
import os
import datetime
import random


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

RECENT_WINNER_TOLERANCE = 2
RECENT_AUDIO_TOLERANCE = 90

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
                tag_string = entry[1][1:-1]
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
                return ' (' +  entry[1] + ')'
        return ''

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

    def discord_post(self):
        post_body = self.tag_string() + self.series() + self.description() + self.writer()
        return discord.Embed(title = self.name(), url = self.link(), description = post_body)



def tagged_options(audios, tag):
    options = []
    for audio in audios:
        if tag in audio.tags():
            options.append(audio)
    return options



def random_audio(audios, tag=None):
    if tag is not None:
        options = tagged_options(audios,tag)
        if len(options) != 0:
            return random.choice(options)
        else:
            return None
    else:
        return random.choice(audios)

    





# import data from airtable
table = airtable_api.table('apprrNWlCwDHYj4wW', 'tblqwSpe5CdMuWHW6')
all_records = table.all()
all_audios = [Audio(entry) for entry in all_records]





@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

    # set all daily tasks running
    choose_winner.start()
    choose_daily_audio.start()




@client.event
async def on_message(message):
    if message.author == client.user:
        return


    if message.content.startswith('!masterlist'):
        embed = discord.Embed(title="Vel's Library Masterlist",
                       url="https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr",
                       description="here's the card catalogue!")
        await message.channel.send(embed=embed)



    if message.content.startswith('!dm masterlist'):
        await message.author.send("here's a link to the masterlist!")
        await message.delete()



    if message.content.startswith('!randomaudio'):
        msg = message.content
        leading, trailing = 1+msg.find('['), msg.find(']')
        if leading != 0:
            tag = msg[leading:trailing]
            audio = random_audio(all_audios,tag)
            if audio is not None:
                await message.channel.send(f"here's a random audio with the tag [{tag}]!")
                await message.channel.send(embed=audio.discord_post())
            else:
                await message.channel.send("no audios with the tag [" + tag + "] were found")
        else:
            audio =random_audio(all_audios)
            await message.channel.send(f"here's a random audio!")
            await message.channel.send(embed=audio.discord_post())




def choose_next_audio(options, recent):
    next = all_audios[1]
    breaker = 0
    while next.name() in recent and breaker < 45:
        next = random.choice(options)
        print(next.name())
        breaker += 1
    recent.append(next.name())
    recent.pop(0)
    print(recent)
    return next



def choose_next(options, recent):
    next = recent[0]
    i = 0
    while next in recent and i < 20:
        next = random.choice(options)
        print(next)
        i += 1
    recent.append(next)
    recent.pop(0)
    return next



#in utc
new_winner_time = datetime.time(hour=19, minute=57)
recent_winners = [None for i in range(RECENT_WINNER_TOLERANCE)]


@tasks.loop(time = new_winner_time)
async def choose_winner():
    guild = client.get_guild(GUILD)
    channel = client.get_channel(GENERAL)
    good_girl_role = guild.get_role(WINNER_ROLE)

    for member in good_girl_role.members:
        await member.remove_roles(good_girl_role)

    options = guild.get_role(OPTIONS_ROLE).members
    winner = choose_next(options, recent_winners)

    # need a check that not in the most recent N winners
    await channel.send(f'{winner.mention} is the good girl of the day!')
    await winner.add_roles(good_girl_role)




daily_audio_time = datetime.time(hour=16, minute=0)
times = [datetime.time(hour=19, minute=49,second = 0),datetime.time(hour=19, minute=49,second = 10),datetime.time(hour=19, minute=49,second = 20),datetime.time(hour=19, minute=49,second = 30)]

recent_audios = ['' for i in range(4)]


@tasks.loop(time = times)
async def choose_daily_audio():
    # sync with airtable data to pull any masterlist updates
    global table, all_records, all_audios
    table = airtable_api.table('apprrNWlCwDHYj4wW', 'tblqwSpe5CdMuWHW6')
    all_records = table.all()
    all_audios = [Audio(entry) for entry in all_records]
    all_audios = all_audios[1:6]

    guild = client.get_guild(GUILD)
    channel = client.get_channel(GENERAL)

    # need a check that not in the most recent N winners
    audio = choose_next_audio(all_audios,recent_audios)
    await channel.send(f"today's daily audio!")
    await channel.send(embed=audio.discord_post())





@client.event
async def on_member_join(member):
    await member.send("Welcome to the Library! Here is a link to the masterlist.")
    embed = discord.Embed(title="Vel's Library Masterlist",
                       url="https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr",
                       description="here's the card catalogue!")
    await member.send(embed=embed)





# want basic commands for vel's links !twitter !reddit !twitch !youtube !pornhub
# daily balatro seed 
# !posts and !lives schedules
# remove deep audios 




client.run(TOKEN)
