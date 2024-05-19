import random

options = range(20)
recent = [None for i in range(5)]

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

for i in range(10):
	choose_next(options,recent)
	print(recent)


