import os
import random

from pyairtable import Api
from dotenv import load_dotenv


load_dotenv()
api = Api(os.getenv('AIRTABLE_TOKEN'))



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
			if entry[0]=='General Date':
				return entry[1]
		return ''

	def series(self):
		for entry in self.parsed_data():
			if entry[0]=='Series Name':
				return entry[1]
		return ''

	def writer(self):
		for entry in self.parsed_data():
			if entry[0]=='Scriptwriter':
				return entry[1]
		return 'Vel'

	def description(self):
		for entry in self.parsed_data():
			if entry[0]=='Description':
				return entry[1]
		return ''

	# def discord_post(self):
    #     title, url, description = '','',''
    #     for entry in self.parsed_data():
    #         if entry[0]=='Title':
    #             title = entry[1]
    #         elif entry[0]=='Post Link':
    #             url = entry[1]
    #         elif entry[0]=='Tags':
    #             description = entry[1]
    #     return discord.Embed(title = title,url = url,description = description)




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



# print(random_audio(all_audios,'degradation').name())
# print(random_audio(all_audios).name())
# print(random_audio(all_audios,'straight people'))

audio = random.choice(all_audios)
print(audio.name())
print(audio.tags())
print(audio.link())
print(audio.date())
print(audio.series())
print(audio.writer())
print(audio.description())




