import os
import datetime
import random
import string
import asyncio


WINNERS_FILENAME = "recentwinners.txt"
AUDIOS_FILENAME = "recentaudios.txt"



def read_from_file(filename):
	f = open(filename)
	lines = f.read().splitlines()
	f.close()
	return lines

def save_to_file(filename, list):
	padded = []
	for x in list:
		padded.append(x + "\n")
	f = open(filename,"w")
	for line in padded:
		f.write(line)
	f.close()
	return None



def choose_next_winner(options):
	recent = read_from_file(WINNERS_FILENAME)
	next_one = random.choice(options)

	breaker = 0

	while next_one in recent and breaker < 45:
		print(next_one)
		next_one = random.choice(options)
		breaker += 1

	recent.append(next_one)
	recent.pop(0)

	save_to_file(WINNERS_FILENAME,recent)
	return next_one


options = ["1","2","3","4","5"]


print(choose_next_winner(options))