import random
import os
import re
import logging
import datetime

import praw
import requests
import redis

comment_template = """[irrelevant xkcd]({url})


^(If the linked comic is in fact relevant, I appologize. I'm just a bot!)
"""


logging.basicConfig(format='%(asctime)s::%(levelname)s:%(message)s', filename='bot.log', level=logging.INFO)
r = redis.StrictRedis(host='localhost', port=6379, db=0)

url='http://xkcd.com/{num}'

pattern = re.compile(r'\[.*relevant.*xkcd.*\]\(.*\)')
notpattern = re.compile(r'\[.*irrelevant.*xkcd.*\]\(.*\)')

u = os.getenv('REDDIT_USERNAME', 'irrelevant-xkcd_bot')
p = os.getenv('REDDIT_PASSWORD', '')
secret = os.getenv('REDDIT_SECRET', '')
mode = os.getenv('BOT_MODE', 'development')

subreddit = 'all' if mode == 'production' else 'irxkcdbot'

def get_new_comics():
  r.set('most_recent', requests.get('https://xkcd.com/info.0.json').json().get('num'))
  r.set('last_update', datetime.date.today())
  logging.info('updated most recent comic to %s', r.get('most_recent'))

def check_for_new_comics():
  if r.get('last_update') is not None and r.get('most_recent') is not None:
    last_update = datetime.date(*map(lambda s: int(s), r.get('last_update').split('-')))
    if datetime.date.today() - last_update > datetime.timedelta(0):
      get_new_comics()
  else:
    get_new_comics()

def respond_to_comment(comment, reply_to):
  check_for_new_comics()

  parent_id = reply_to.fullname 
  child_id = comment.fullname

  comic = url.format(num=random.randint(1, int(r.get('most_recent'))))
  logging.info('responding to comment %s with comic %s', parent_id, comic)
  try:
    reply_to.reply(comment_template.format(url=comic))
  except praw.exceptions.APIException as e:
    logging.warning('error when replying to comment. error code %s, message: %s', e.error_type, e.message)
  else:
    r.set(parent_id, '{}-{}'.format(comic, child_id)) # record which child triggered the response originally


if __name__ == '__main__':
  check_for_new_comics()

  bot = praw.Reddit(user_agent='irrelevant-xkcd_bot v0.1',
                  client_id='P_0YD6qB3ysJOQ',
                  client_secret=secret,
                  username=u,
                  password=p)

  msg = 'irrelevant xkcd bot starting up! Comics 1-{} will be served.'.format(r.get('most_recent'))
  print msg
  logging.info(msg)

  for comment in bot.subreddit(subreddit).stream.comments():
    s = comment.body.lower()
    if pattern.search(s) and not notpattern.search(s):
      # We're responding to the parent here, the "child" is the 'relevant xkcd' link, the parent is the material with the relevant xkcd
      reply_to = comment.parent()
      reply_to_id = reply_to.fullname

      lock = r.get(reply_to_id) # check if this comment already has an irrelevant xkcd before replying
      if lock is None:
        respond_to_comment(comment, reply_to)
      else:
        logging.info('comment %s has already been responded to with comic %s', reply_to_id, lock.split('-')[0])


