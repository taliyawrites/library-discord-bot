import discord
import os
import datetime
import random
import string
import asyncio


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

REPEAT_WINNER_TOLERANCE = 2
REPEAT_AUDIO_TOLERANCE = 90

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


client = discord.Client(intents=intents)




test_time = datetime.time(hour=14, minute=0) # in utc 
new_winner_time, daily_audio_time, daily_balatro_time = test_time, test_time, test_time
# new_winner_time = datetime.time(hour=14, minute=0)
# daily_audio_time = datetime.time(hour=15, minute=0)
# daily_balatro_time = datetime.time(hour=8, minute=0)



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

    def allowed_choice(self):
        if 'sfw' in self.tags() or 'behind the scenes' in self.tags():
            return False
        elif self.name() == 'A Pool Party Turns Into a Fucking Competition' or self.name() == 'I Brought a Friend to Help Spoil You':
            return False
        else:
            return True






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






def import_airtable_data():
    table = airtable_api.table('apprrNWlCwDHYj4wW', 'tblqwSpe5CdMuWHW6')
    all_audios = [Audio(entry) for entry in table.all()]

    allowed = []
    for audio in all_audios:
        if audio.allowed_choice():
            allowed.append(audio)

    return allowed








@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

    # import data from airtable
    global audio_choices
    audio_choices = import_airtable_data()

    # set all daily tasks running
    choose_winner.start()
    choose_daily_audio.start()
    daily_balatro.start()




@client.event
async def on_message(message):
    if message.author == client.user:
        return


    if message.content.startswith('!masterlist'):
        embed = discord.Embed(title="Vel's Library Masterlist",
                       url="https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr",
                       description="here's the card catalogue!")
        await message.channel.send(embed=embed)



    if message.content.startswith('!dm'):
        await message.author.send("Here's a link to the masterlist!")
        embed = discord.Embed(title="Vel's Library Masterlist",
                       url="https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr",
                       description="here's the card catalogue!")
        await message.author.send(embed=embed)
        await message.delete()



    if message.content.startswith('!randomaudio'):
        msg = message.content
        leading, trailing = 1+msg.find('['), msg.find(']')
        if leading != 0:
            tag = msg[leading:trailing]
            audio = random_audio(audio_choices,tag)
            if audio is not None:
                await message.channel.send(f"here's a random audio with the tag [{tag}]!")
                await message.channel.send(embed=audio.discord_post())
            else:
                await message.channel.send("no audios with the tag [" + tag + "] were found")
        else:
            audio =random_audio(audio_choices)
            await message.channel.send(f"here's a random audio!")
            await message.channel.send(embed=audio.discord_post())

    if message.content.startswith('!daily'):
        await message.channel.send(f"here's a link to the audio of the day!")
        await message.channel.send(embed=daily_audio.discord_post())



    if message.content.startswith('!balatro'):
        await message.channel.send(f"the Balatro seed of the day is: {random_seed}")

    if message.content.startswith('!schedule'):
        # schedule = "Sunday 4:30PM EST: Private Library Release \n Monday 4:30PM EST: Reddit GWA Release \n Wednesday 6:30PM EST: Library Card Release \n Every other Thursday 4:30PM EST: Reddit GWA Release \n Friday 6:30PM EST: Book Club Release"
        schedule = "Sunday 4:30PM EST (<t:1716755400:t>): Private Library Release \n Monday 4:30PM EST (<t:1716841800:t>): Reddit GWA Release \n Wednesday 6:30PM EST (<t:1717021800:t>): Library Card Release \n Every other Thursday 4:30PM EST (<t:1717101000:t>): Reddit GWA Release \n Friday 6:30PM EST (<t:1717194600:t>): Book Club Release"
        schedule_embed = discord.Embed(title = "Vel's Posting Schedule",description=schedule)
        await message.channel.send(embed=schedule_embed)

    if message.content.startswith('!live'):
        await message.channel.send("Vel does live audio recordings here on discord every Sunday at 7:30PM EST (<t:1716766200:t>)!")

    if message.content.startswith('!social'):
        # await message.channel.send("here are links to all of Vel's socials")
        links = "[twitter](https://x.com/VelsLibrary) \n [reddit](https://www.reddit.com/user/VelsLibrary/) \n [twitch](https://www.twitch.tv/velslibrary) \n [pornhub](https://www.pornhub.com/model/velslibrary) \n [youtube](https://www.youtube.com/@VelsLibrary)"
        link_embed = discord.Embed(title = "Vel's Socials",description=links)
        await message.channel.send(embed=link_embed)


    # if message.content.startswith('!getrole'):
    #     msg = await message.channel.send("React to this message to get the 'I wanna be a good girl' role!")
    #     try:
    #         reaction, user = await client.wait_for('reaction_add', timeout = 20)
    #     except asyncio.TimeoutError:
    #         await message.channel.send('timeout')
    #     else:
    #         await message.channel.send(reaction.emoji)





def choose_next(options, recent):
    next = random.choice(options)
    breaker = 0
    while next in recent and breaker < 45:
        next = random.choice(options)
        breaker += 1
    recent.append(next)
    recent.pop(0)
    return next


recent_winners = [None for i in range(REPEAT_WINNER_TOLERANCE)]


@tasks.loop(time = new_winner_time)
async def choose_winner():
    guild = client.get_guild(GUILD)
    channel = client.get_channel(GENERAL)
    good_girl_role = guild.get_role(WINNER_ROLE)

    await asyncio.sleep(5)
    for member in good_girl_role.members:
        await member.remove_roles(good_girl_role)

    options = guild.get_role(OPTIONS_ROLE).members
    winner = choose_next(options, recent_winners)

    await channel.send(f'{winner.mention} is the good girl of the day!')
    await winner.add_roles(good_girl_role)



def choose_next_audio(options, recent):
    next = random.choice(options)
    breaker = 0
    while next.name() in recent and breaker < 45:
        next = random.choice(options)
        breaker += 1
    recent.append(next.name())
    recent.pop(0)
    return next



recent_audios = ['' for i in range(REPEAT_AUDIO_TOLERANCE)]

@tasks.loop(time = daily_audio_time)
async def choose_daily_audio():
    # sync with airtable data to pull any masterlist updates
    audio_choices = import_airtable_data()

    guild = client.get_guild(GUILD)
    channel = client.get_channel(GENERAL)

    global daily_audio
    daily_audio = choose_next_audio(audio_choices,recent_audios)
    await channel.send(f"The audio of the day!")
    await channel.send(embed=daily_audio.discord_post())



@tasks.loop(time=daily_balatro_time)
async def daily_balatro():
    global random_seed
    random_seed = ''.join(random.choices(string.ascii_uppercase+string.digits, k=8))




@client.event
async def on_member_join(member):
    await member.send("Welcome to the Library! Here is a link to the masterlist.")
    embed = discord.Embed(title="Vel's Library Masterlist",
                       url="https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr",
                       description="here's the card catalogue!")
    await member.send(embed=embed)







client.run(TOKEN)
