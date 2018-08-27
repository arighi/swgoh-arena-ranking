#!/usr/bin/env python3

import sys
import re
import sys
import traceback
import discord
import asyncio
import logging
import pickle
import config
from datetime import datetime, date
from collections import OrderedDict

copyright_info = "Bot designed by: Andrea Righi (https://github.com/arighi/swgoh-arena-ranking)"

client = discord.Client()

SAVE_FILE = 'players.dat'

help_info = """
Examples:

    - add user "Andrea" to a group "EU_people":
    $add EU_people Andrea

    - remove user "Andrea" from group "EU_people":
    $remove EU_people Andrea

    - show today's ranking
    $ranking

    - show the list of people defined in group "EU_people":
    $show EU_people

    - show bot invitation link (use the link to invite this bot to your Discord server):
    $invite

{0}
""".format(copyright_info)

def exception_hook(exc_type, exc_value, exc_traceback):
    logging.error(format_exception(exc_type, exc_value, exc_traceback))

def start_logger(log_stream=sys.stdout, loglevel=logging.INFO, syslog_facility=None):
    """
    Configure the logger object
    """
    try:
        logging.basicConfig(level=loglevel, stream=log_stream, \
                            datefmt='%a, %d %b %Y %H:%M:%S', \
                            format='%(asctime)s ' + ': %(message)s')
        if syslog_facility is not None:
            facility = eval("logging.handlers.SysLogHandler.%s" % syslog_facility)
            my_logger = logging.getLogger()
            handler = logging.handlers.SysLogHandler(address='/dev/log', facility=facility)
            my_logger.addHandler(handler)
    except Exception as e:
        sys.stderr.write(format_exception(e) + '\n')
        sys.exit(1)

def rotate(l, x):
    return l[-x:] + l[:-x]

class Players:
    def __init__(self):
        self._players = {}
        self.load()

    def load(self):
        try:
            self._players = pickle.load(open(SAVE_FILE, "rb"))
        except:
            self._players = {}

    def save(self):
        pickle.dump(self._players, open(SAVE_FILE, "wb"))

    def get_groups(self, channel_id):
        if channel_id in self._players:
            return self._players[channel_id]
        else:
            return None

    def get_items(self, channel_id, group):
        if channel_id in self._players:
           if group in self._players[channel_id]:
                return list(self._players[channel_id][group])
        return None

    def _add(self, channel_id, group, name):
        items = self._players[channel_id][group]
        if len(items) == 0:
            self._players[channel_id][group].update({name : 1})
        else:
            days = (datetime.date(datetime.now()) - date(2000, 1, 1)).days
            rotation = -(days % len(items))
            l = rotate(list(items), rotation)
            l.append(name)
            self._players[channel_id][group].clear()
            rotation = -(days % len(l))
            for name in rotate(l, -rotation):
                self._players[channel_id][group].update({name: 1})

    def add(self, channel_id, group, name):
        if not channel_id in self._players:
            self._players[channel_id] = {}
        if not group in self._players[channel_id]:
            self._players[channel_id][group] = OrderedDict()
        self._add(channel_id, group, name)
        self.save()

    def _remove(self, channel_id, group, name):
        items = self._players[channel_id][group]
        if len(items) == 1:
            del self._players[channel_id][group][name]
        else:
            days = (datetime.date(datetime.now()) - date(2000, 1, 1)).days
            rotation = -(days % len(items))
            l = rotate(list(items), rotation)
            l.remove(name)
            self._players[channel_id][group].clear()
            rotation = -(days % len(l))
            for name in rotate(l, -rotation):
                self._players[channel_id][group].update({name: 1})

    def remove(self, channel_id, group, name):
        try:
            self._remove(channel_id, group, name)
            if len(self._players[channel_id][group]) == 0:
                del self._players[channel_id][group]
            if len(self._players[channel_id]) == 0:
                del self._players[channel_id]
            self.save()
        except KeyError:
            pass

players = Players()

@client.event
async def on_ready():
    logging.info('Logged in as %s (<@%s>)' % (client.user.name, client.user.id))

def show_group(channel_id, group_name):
    items = players.get_items(channel_id, group_name)
    logging.info("items: " + str(items))
    days = (datetime.date(datetime.now()) - date(2000, 1, 1)).days
    return "GROUP " + group_name + ': ' + ', '.join(rotate(items, -(days % len(items))))

@client.event
async def on_message(message):
    if message.author.id == config.BOTID:
        return
    channel_id = str(message.channel.id)
    logging.info("channel %s: request from %s (id = %s): %s" %
                 (str(message.channel), str(message.author), message.author.id, message.content))

    # Parse message
    if message.content == '$help':
        await client.send_message(message.channel, help_info)
    elif message.content.startswith('$invite'):
        await client.send_message(message.channel, 'Invite URL: ' + \
                'https://discordapp.com/oauth2/authorize?&client_id=' + client.user.id + \
                '&scope=bot&permissions=0')
    elif message.content == '$channel_id':
        await client.send_message(message.channel, "channel_id = %s" % channel_id)
    elif message.content.startswith('$ranking'):
        now = datetime.now().strftime("%a %b %d %Y")
        msg = '-\n'
        logging.info("groups = %s" % players.get_groups(channel_id))
        for group_name in sorted(players.get_groups(channel_id)):
            logging.info('group = ' + group_name)
            msg += show_group(channel_id, group_name)
            msg += "\n-\n"
        msg += copyright_info + "\n"
        logging.info("sending: " + msg)

        em = discord.Embed(title=">>> TODAY'S RANKING: %s <<<" % now,
                           description=msg, color=0x00ff00)
        em.set_author(name='SWGOH daily rotation', icon_url=client.user.default_avatar_url)
        await client.send_message(message.channel, embed=em)
    elif message.content.startswith('$show'):
        m = re.match('^\$show (.*)$', message.content)
        if m:
            group_name = m.group(1)
            items = players.get_items(channel_id, group_name)
            if items is None:
                await client.send_message(message.channel, "Group %s is empty" % m.group(1))
            else:
                now = datetime.now().strftime("%a %b %d %Y")
                msg = show_group(channel_id, group_name)
                em = discord.Embed(title=">>> TODAY'S RANKING: %s <<<" %
                                   now, description=msg, color=0x00ff00)
                em.set_author(name='SWGOH daily rotation', icon_url=client.user.default_avatar_url)
                logging.info("sending: " + msg)
                await client.send_message(message.channel, embed=em)
    elif message.content.startswith('$add'):
        m = re.match('^\$add (.*) (.*)', message.content)
        if m:
            group_name = m.group(1)
            user_id = "<@%s>" % m.group(2)
            players.add(channel_id, group_name, user_id)
            await client.send_message(message.channel,
                    'OK, player %s added to group %s' % (user_id, group_name))
        else:
            await client.send_message(message.channel,
                        'ERROR: bad syntax, use "$add GROUP_NAME USER_ID"')
    elif message.content.startswith('$remove'):
        m = re.match('^\$remove (.*) (.*)', message.content)
        if m:
            group_name = m.group(1)
            user_id = "<@%s>" % m.group(2)
            players.remove(channel_id, group_name, user_id)
            await client.send_message(message.channel,
                    'OK, player %s removed from group %s' % (user_id, group_name))
        else:
            await client.send_message(message.channel,
                        'ERROR: bad syntax, use "$remove GROUP_NAME USER_ID"')

def main():
    start_logger(log_stream=open('activity.log', 'a'))
    sys.excepthook = exception_hook
    client.run(config.TOKEN)

if __name__ == '__main__':
    main()
