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
ROLE = int(os.getenv('ROLE_ID'))
api = Api(os.getenv('AIRTABLE_TOKEN'))


intents = discord.Intents.default()
intents.message_content = True
intents.members = True


client = discord.Client(intents=intents)





# this is too simplistic because airtable omits empty fields!!!!!!!
# will need to search through entry for "Tags", "Link", etc
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
        return discord.Embed(title = self.name(),url = self.link(),description = post_body)



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
table = api.table('apprrNWlCwDHYj4wW', 'tblqwSpe5CdMuWHW6')
all_records = table.all()
all_audios = [Audio(entry) for entry in all_records]





@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

    # set all daily tasks running
    choose_winner.start()




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






#in utc
time = datetime.time(hour=22, minute=50)

@tasks.loop(time = time)
async def choose_winner():
    guild = client.get_guild(GUILD)
    channel = client.get_channel(GENERAL)
    role = guild.get_role(ROLE)
    members = role.members
    choice = random.choice(members)
    # need a check that not in the most recent N winners
    await channel.send(f'{choice.display_name} is the user of the day')
    # maybe give them a special role and name color for the day
    # should also send notification
    # more changes






@client.event
async def on_member_join(member):
    await member.send("Welcome to the Library! Here is a link to the masterlist.")
    embed = discord.Embed(title="Vel's Library Masterlist",
                       url="https://airtable.com/apprrNWlCwDHYj4wW/shrb4mT61rtxVW04M/tblqwSpe5CdMuWHW6/viwM1D86nvAQFsCMr",
                       description="here's the card catalogue!")
    await member.send(embed=embed)






client.run(TOKEN)
