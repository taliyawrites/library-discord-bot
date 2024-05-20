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
                return 'Tags: ' + entry[1]
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
            if entry[0]=='General Date':
                return '\n Date: ' + entry[1]
        return ''

    def series(self):
        for entry in self.parsed_data():
            if entry[0]=='Series Name':
                return '\n Series: ' + entry[1]
        return ''

    def writer(self):
        for entry in self.parsed_data():
            if entry[0]=='Scriptwriter':
                if entry[1] != 'Vel':
                    return '\n Scriptwriter: ' + entry[1]
        return ''

    def description(self):
        for entry in self.parsed_data():
            if entry[0]=='Description':
                return '\n Description: ' + entry[1]
        return ''

    def discord_post(self):
        post_body = self.tag_string() + self.date() + self.writer() + self.series() + self.description()
        return discord.Embed(title = self.name(),url = self.link(),description = post_body)