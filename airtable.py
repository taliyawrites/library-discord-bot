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
		return [entry[1] for entry in list(fields.items())]

	def name(self):
		data = self.parsed_data()
		return data[0]

	def tags(self):
		data = self.parsed_data()
		return parse_tags(data[1])



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
table = api.table('appGfIG1VbgtT1pMF', 'tblUXtT3fkV2MT5bn')
all_records = table.all()


all_audios = [Audio(entry) for entry in all_records]


print(random_audio(all_audios,'degradation').name())
print(random_audio(all_audios,'pregnant').name())
print(random_audio(all_audios).name())
print(random_audio(all_audios,'straight people'))

