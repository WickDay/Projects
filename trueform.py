# Installing dependencies:
#
# pip install --user dateutil nltk

import os
import sys
import re
import datetime
import dateutil.parser
import string
import nltk

# maximum number of items to display in each section
MAX_ITEMS_TO_DISPLAY = 20

#-------------------------------------------------------------------------------
# return an unified nltk corpus with words converted to lower case
def load_corpus():
    # download the required corpus data
    # concatenating multiple corpuses still doesn't cover the full english vocabulary
    nltk.download('words')
    nltk.download('wordnet')
    nltk.download('brown')
    nltk.download('reuters')

    from nltk.corpus import words
    from nltk.corpus import wordnet
    from nltk.corpus import brown
    from nltk.corpus import reuters

    vocabulary = set()
    vocabulary.update(words.words())
    vocabulary.update(wordnet.words())
    vocabulary.update(brown.words())
    vocabulary.update(reuters.words())

    return set(word.lower() for word in vocabulary)

#-------------------------------------------------------------------------------
# set of english words (lower case)
english_words = load_corpus()

# total messages posted (empty messages are not counted)
total_message_count = 0

# word -> word count
word_to_word_count = {}

# user -> message count
user_to_message_count = {}

# user -> login count
user_to_login_count = {}

# user -> login date
user_to_login_date = {}

# user -> online time
user_to_time_online = {}

# set of unusual words -> word count
unusual_words = {}

# hour of day -> number of messages
message_count_by_hour = {}

# day of week -> number of messages
message_count_by_day = {}

# set of urls posted in the chat
urls = set()

#-------------------------------------------------------------------------------
# converts a timediff object to a tuple of integers: days, hours, minutes
#
# https://stackoverflow.com/a/2119512
def days_hours_minutes(td):
    return td.days, td.seconds//3600, (td.seconds//60)%60

#-------------------------------------------------------------------------------
# check if string is ascii
#
# https://stackoverflow.com/a/32357552
def is_ascii(s):
    try:
        s.encode('ascii')
        return True  # string is ascii
    except:
        return False  # string is not ascii

#-------------------------------------------------------------------------------
# sort dictionary items in descending order based on their value
# a list with `max_count` of top items will be returned
def sort_by_value(data, max_count):
    return sorted(data.items(), reverse=True, key=lambda x: x[1])[:max_count]

#-------------------------------------------------------------------------------
# remove specific characters from the beginning of the username, if present
def sanitize_username(user):
    first_ch = user[0]
    if first_ch == '+' or first_ch == '%' or first_ch == '@':
        return user[1:]
    return user

#-------------------------------------------------------------------------------
# remove specific punctuation characters from a string
def remove_punctuation(text):
    for ch in '.,?!"*/()+-:':
        text = text.replace(ch, '')
    return text

#-------------------------------------------------------------------------------
# insert new item in a dict, or add value to an existing item
def add_or_insert(collection, key, value):
    if key in collection:
        collection[key] += value
    else:
        collection[key] = value

#-------------------------------------------------------------------------------
# returns a boolean indicating whether `s` is an url
def is_url(s):
    return s.startswith('https://') or s.startswith('http://') \
        or s.startswith('ftp://') or s.startswith('ftps://')

#-------------------------------------------------------------------------------
def parse_meta(line, current_date):
    # time is the first 5 characters of the line
    time = line[:5]

    # extract the user name
    user = line[10:].strip().split(' ')[0]

    # parse log time and combine it with the current date
    current_time = datetime.datetime.strptime(line[:5], '%H:%M').time()
    current_time = datetime.datetime.combine(current_date, current_time)

    if 'has joined' in line:
        # increment login count
        add_or_insert(user_to_login_count, user, 1)

        # record login date
        user_to_login_date[user] = current_time
    elif 'has quit' in line or 'has left' in line:
        if user in user_to_login_date:
            # get the time (in seconds) between the last login time and the current time
            session_time = (current_time - user_to_login_date[user]).seconds

            # record the session time for this user
            add_or_insert(user_to_time_online, user, session_time)

            # delete the user id from the active logins dictionary
            del user_to_login_date[user]
    elif 'is now known as':
        # extract new user name
        new_user = line[line.find(' known as ') + 10 :]
        if user in user_to_login_date:
            # update the login date with the new user name
            user_to_login_date[new_user] = user_to_login_date[user]
            # delete the record with the old user name
            del user_to_login_date[user]

#-------------------------------------------------------------------------------
def parse_message(line, current_date):
    global total_message_count

    # time is the first 5 characters of the line
    time = line[:5]

    # username and message comes after time
    try:
        user, message = line[7:].strip().split('> ', 1)
    except:
        # do not count empty messages
        return

    # filter out messages from evilbot
    if user == '+evilbot':
        return

    # increment message counter
    total_message_count += 1

    # clean up the user name from + @ % characters
    user = sanitize_username(user)

    # record user message count
    add_or_insert(user_to_message_count, user, 1)

    # record hourly activity
    add_or_insert(message_count_by_hour, time[:2], 1)

    # record daily activity
    add_or_insert(message_count_by_day, str(current_date.date()), 1)

    # tokenize message on whitespace or newline characters
    words = re.split(r'[\n\t ]', message)

    for word in words:
        # check if this word is a valid url
        if is_url(word):
            # insert url to the urls set
            urls.add(word)
        else:
            # ignore words with two or less characters
            if len(word) <= 2:
                continue

            # also ignore words with non ascii characters
            if not is_ascii(word):
                continue

            # increment word count
            add_or_insert(word_to_word_count, word, 1)

            # if word is not part of the common english vocabulary
            # record it as an unusual word
            token = remove_punctuation(word.lower())
            if token != '' and token not in english_words:
                add_or_insert(unusual_words, word, 1)

#-------------------------------------------------------------------------------
def display_results():
    # Many users log in and view the chat without commenting. Which users spent the most time in the logs?
    print('\nTop %d most active users by time spent online:' % MAX_ITEMS_TO_DISPLAY)
    for user, seconds in sort_by_value(user_to_time_online, MAX_ITEMS_TO_DISPLAY):
        td = datetime.timedelta(seconds=seconds)
        days, hours, minutes = days_hours_minutes(td)
        print('    %s (%d days, %d hours, %d minutes)' % (user, days, hours, minutes))

    # Which users logged in the most
    print('\nTop %d most active users by number of logins:' % MAX_ITEMS_TO_DISPLAY)
    for user, count in sort_by_value(user_to_login_count, MAX_ITEMS_TO_DISPLAY):
        print('    %s (%d logins)' % (user, count))

    # Find the most common words
    print('\nTop %d most common words:' % MAX_ITEMS_TO_DISPLAY)
    for word, count in sort_by_value(word_to_word_count, MAX_ITEMS_TO_DISPLAY):
        print('    %s (%d occurrences)' % (word, count))

    # Count the total number of written messages (only those with actual text content)
    print('\nTotal number of messages: %d' % total_message_count)

    # Summarize the users that posted the most messages
    print('\nTop %d posters:' % MAX_ITEMS_TO_DISPLAY)
    for user, count in sort_by_value(user_to_message_count, MAX_ITEMS_TO_DISPLAY):
        print('    %s (%d posts)' % (user, count))

    # Find and rank (by count) words not in an English dictionary
    print('\nTop %d unusual words:' % MAX_ITEMS_TO_DISPLAY)
    for word, count in sort_by_value(unusual_words, MAX_ITEMS_TO_DISPLAY):
        print('    %s (%d occurrences)' % (word, count))

    # Which hours of the day had the most messages
    print("\nMost active hours of the day:")
    for hour, count in sort_by_value(message_count_by_hour, 24):
        print('    %s:00 (%d messages)' % (hour, count))

    # Which days had the most traffic (or messages)
    print("\nTop %d most active days:" % MAX_ITEMS_TO_DISPLAY)
    for day, message_count in sort_by_value(message_count_by_day, MAX_ITEMS_TO_DISPLAY):
        print('    %s (%d messages)' % (day, message_count))

    # Find and list the URLs posted in the chat
    print('\nList of urls posted (%d of %d items shown):' % (MAX_ITEMS_TO_DISPLAY, len(urls)))
    for url in list(urls)[:MAX_ITEMS_TO_DISPLAY]:
        print('    ' + url)

#-------------------------------------------------------------------------------
def main():
    # optional filename can be passed as a command line argument
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        # if no filename is specified, the program attempts to read hackers.log in the current working directory
        filename = './hackers.log'

    # check if file exists
    if not os.path.isfile(filename):
        print('File not found: ' + filename)
        sys.exit(0)

    # open the file in read mode
    with open(filename, 'r', errors='replace') as f:
        # keeps track of the current date
        current_date = None

        # read the file line by line
        for line in f.readlines():
            # handle 'log opened' type of messages
            if line.startswith('--- Log opened'):
                current_date = dateutil.parser.parse(line[15:])

                # clear out the login dates dict
                user_to_login_date = {}
            # handle 'log closed' type of messages
            elif line.startswith('--- Log closed'):
                current_date = dateutil.parser.parse(line[15:])
            # handle 'day changed'
            elif line.startswith('--- Day changed'):
                current_date = dateutil.parser.parse(line[16:])
            # handle meta messages (ie: login, logout)
            elif line[6:9] == '-!-':
                parse_meta(line, current_date)
            # handle user messages
            elif line[6:].strip()[0] == '<':
                parse_message(line, current_date)

    display_results()

#-------------------------------------------------------------------------------
if __name__ == '__main__':
    main()
