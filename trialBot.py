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
        return [entry[1] for entry in list(fields.items())]

    def name(self):
        data = self.parsed_data()
        return data[1]

    def tags(self):
        data = self.parsed_data()
        # # convert string of tags "[a] [b] [c] [d]" into a list {a,b,c,d}
        # tag_string = self.parsed_data()[3]
        # tags = tag_string[1:-1]
        # return tags.split('][')
        return parse_tags(data[3])

    def link(self):
        data = self.parsed_data()
        return data[5]



def parse_tags(tag_string):
    # convert string of tags "[a] [b] [c] [d]" into a list {a,b,c,d}
    tags = tag_string[1:-1]
    return tags.split('] [')



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
            return "no audios with the tag [" + tag + "] were found"
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
            # need to code in an exception for no audio found string 
            await message.channel.send(f"here's a random audio with the tag [{tag}]!")
            embed = discord.Embed(title=audio.name(),
                       url=audio.link(),
                       description='audio yay')
            await message.channel.send(embed=embed)
        else:
            audio =random_audio(all_audios)
            await message.channel.send(f"here's a random audio!")
            embed = discord.Embed(title=audio.name(),
                       url=audio.link(),
                       description='audio yay')
            await message.channel.send(embed=embed)






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
