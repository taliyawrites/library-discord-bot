import random
import string



WINNERS_FILENAME = "recentwinners.txt"
AUDIOS_FILENAME = "recentaudios.txt"

WINNER_TOLERANCE = 20
AUDIO_TOLERANCE = 90

winners = open(WINNERS_FILENAME,"w")
for x in range(WINNER_TOLERANCE):
	winners.write('0\n')
winners.close()


audios = open(AUDIOS_FILENAME,"w")
for x in range(AUDIO_TOLERANCE):
	audios.write('0\n')
audios.close()

