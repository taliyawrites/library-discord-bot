# This example requires the 'message_content' intent.

import discord
import os
import datetime
import random

from dotenv import load_dotenv
from discord.ext import tasks

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = int(os.getenv('GUILD_ID'))
GENERAL = int(os.getenv('GENERAL_CHANNEL'))
ROLE = int(os.getenv('ROLE_ID'))


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)



@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

    # for guild in client.guilds:
    #     print(f'{guild.name}')
    #     members = '\n - '.join([member.name for member in guild.members])
    #     print(f'Guild Members:\n - {members}')

    #     for role in guild.roles:
    #         print(f'{role.name} users')
    #         for member in role.members:
    #             print(member.display_name)

    choose_winner.start()




@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')
        # await message.author.send('Hi!')

    if message.content.startswith('!myroles'):
        roles = [str(role.name) for role in message.author.roles]
        await message.channel.send(roles)

    if message.content.startswith('!dm masterlist'):
        await message.author.send("here's a link to the masterlist!")
        await message.delete()

    if message.content.startswith('!randomaudio'):
        msg = message.content
        leading, trailing = msg.find('['), 1+msg.find(']')
        if leading != -1:
            tag = msg[leading:trailing]
            await message.channel.send(f"here's a random audio with the tag {tag}!")
        else:
            await message.channel.send("here's a random audio!")



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



@client.event
async def on_reaction_add(reaction, user):
    await reaction.message.channel.send(user.display_name)



@client.event
async def on_member_join(member):
    await member.send("Welcome to the Library! Here are some onboarding materials.")



client.run(TOKEN)
