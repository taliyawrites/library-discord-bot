### Library Discord Bot

#### Commands
- `!randomaudio` randomly chosen audio from the masterlist
- `!randomaudio [tag]` specify desired tag in square brackets
- `!daily` for the randomly chosen audio of the day
- `!dm` bot will DM you the masterlist
- `!masterlist`
- `!schedule` audio posting schedule
- `!lives` info about live recordings
- `!socials`
- `!balatro` daily seed

#### Other Functionality
- chooses one random audio per day and posts it at 1pm
- chooses one random user to be highlighted with the "good girl" role for the day
- commands work both in the server and in DMs

#### Using Bot
1. download code and copy it to a designated directory
2. enter tokens and discord IDs to make your .env file according to .env.example
3. [set up python virtual environment](https://discordpy.readthedocs.io/en/stable/intro.html#virtual-environments) in this directory
4. run with `$ py -3 library-bot.py` on windows or `$ python3 library-bot.py` on mac/linux
