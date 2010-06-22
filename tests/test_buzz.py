import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import buzz
import time
from pprint import pprint
try:
  import yaml
except (ImportError):
  sys.stderr.write('Please install PyYAML.\n')
  exit(1)

OAUTH_CONFIG = yaml.load(open('oauth.yaml').read())

OAUTH_CONSUMER_KEY = OAUTH_CONFIG['oauth_consumer_key']
OAUTH_CONSUMER_SECRET = OAUTH_CONFIG['oauth_consumer_secret']
OAUTH_TOKEN_KEY = OAUTH_CONFIG['oauth_token_key']
OAUTH_TOKEN_SECRET = OAUTH_CONFIG['oauth_token_secret']

BUZZ_TESTING_ID = '110842231205170942808'
BUZZ_TESTING_ACCOUNT = 'buzzapitesting'
BUZZ_TARGET_ID = '107807692475771887386'
BUZZ_TARGET_ACCOUNT = 'hikingfan'
BUZZ_POST_ID = 'tag:google.com,2010:buzz:z12wdlxi2pmnwj5df23bihy5mkqmuvbpa04'

CLIENT = buzz.Client()
CLIENT.build_oauth_consumer(OAUTH_CONSUMER_KEY, OAUTH_CONSUMER_SECRET)
CLIENT.build_oauth_access_token(OAUTH_TOKEN_KEY, OAUTH_TOKEN_SECRET)

def clear_posts():
  # Make sure we don't have any posts
  posts = CLIENT.posts()
  for post in posts:
    CLIENT.delete_post(post)

def create_test_post():
  post = buzz.Post(content="This is a test post.")
  CLIENT.create_post(post)
  time.sleep(0.3)
  return CLIENT.posts().data[0]

# For the most part, these tests do not rely on any specific piece of data
# being returned by the API.  Mostly they verify that an exception has not
# been thrown.  Not ideal, but better than needlessly brittle tests.

def test_auth_required():
  client = buzz.Client()
  try:
    client.person().data
    assert False, "Authorization should have been required."
  except:
    assert True, "Great, it worked."

def test_anonymous_consumer():
  client = buzz.Client()
  client.use_anonymous_oauth_consumer()
  client.oauth_scopes.append(buzz.FULL_ACCESS_SCOPE)
  request_token = \
    client.fetch_oauth_request_token('http://example.com/callback/')
  assert request_token.key, "Request token key missing."
  assert request_token.secret, "Request token secret missing."
  assert client.build_oauth_authorization_url(), \
    "Could not build authorization URL"

def test_registered_consumer():
  client = buzz.Client()
  client.build_oauth_consumer(OAUTH_CONSUMER_KEY, OAUTH_CONSUMER_SECRET)
  client.oauth_scopes.append(buzz.FULL_ACCESS_SCOPE)
  request_token = \
    client.fetch_oauth_request_token('http://example.com/callback/')
  assert request_token.key, "Request token key missing."
  assert request_token.secret, "Request token secret missing."
  assert client.build_oauth_authorization_url(), \
    "Could not build authorization URL"

def test_person_me():
  result = CLIENT.person()
  person = result.data
  assert person, "Could not obtain reference to the token's account."
  assert person.name, \
    "Could not obtain reference to the account's display name."
  assert person.uri, \
    "Could not obtain reference to the account's profile link."

def test_person_other():
  result = CLIENT.person(BUZZ_TESTING_ID)
  person = result.data
  assert person, "Could not obtain reference to the token's account."
  assert person.name, \
    "Could not obtain reference to the account's display name."
  assert person.uri, \
    "Could not obtain reference to the account's profile link."

def test_person_me_without_auth():
  client = buzz.Client()
  try:
    client.person()
    assert False, "Authorization should have been required."
  except:
    assert True, "Great, it worked."

def test_person_other_without_auth():
  client = buzz.Client()
  try:
    client.person(BUZZ_TESTING_ID)
    assert False, "Authorization should have been required."
  except:
    assert True, "Great, it worked."

def test_followers_me():
  result = CLIENT.followers()
  followers = result.data
  assert isinstance(followers, list), \
    "Should have been able to get the list of followers."

def test_followers_other():
  client = buzz.Client()
  result = client.followers(BUZZ_TESTING_ID)
  followers = result.data
  assert isinstance(followers, list), \
    "Should have been able to get the list of followers."

def test_following_me():
  result = CLIENT.following()
  following = result.data
  assert isinstance(following, list), \
    "Should have been able to get the list of people being followed."

def test_following_other():
  client = buzz.Client()
  result = client.following(BUZZ_TESTING_ID)
  following = result.data
  assert isinstance(following, list), \
    "Should have been able to get the list of people being followed."

def test_follow():
  person = CLIENT.person(BUZZ_TARGET_ID).data
  person.follow()
  # Give the API time to catch up
  time.sleep(0.3)
  followers = CLIENT.followers(BUZZ_TARGET_ID).data
  assert BUZZ_TESTING_ID in [follower.id for follower in followers], \
    "Should have been able to find the account in followers list."
  following = CLIENT.following(BUZZ_TESTING_ID).data
  assert BUZZ_TARGET_ID in [followee.id for followee in following], \
    "Should have been able to find the target in following list."
  CLIENT.unfollow(BUZZ_TARGET_ID)

def test_unfollow():
  person = CLIENT.person(BUZZ_TARGET_ID).data
  person.follow()
  person.unfollow()
  # Give the API time to catch up
  time.sleep(0.3)
  followers = CLIENT.followers(BUZZ_TARGET_ID).data
  assert not BUZZ_TESTING_ID in [follower.id for follower in followers], \
    "Should not have been able to find the account in followers list."
  following = CLIENT.following(BUZZ_TESTING_ID).data
  assert not BUZZ_TARGET_ID in [followee.id for followee in following], \
    "Should not have been able to find the target in following list."

def test_follow_without_auth():
  client = buzz.Client()
  try:
    client.follow(BUZZ_TARGET_ID)
    assert False, "Authorization should have been required."
  except:
    assert True, "Great, it worked."

def test_unfollow_without_auth():
  client = buzz.Client()
  try:
    client.unfollow(BUZZ_TARGET_ID)
    assert False, "Authorization should have been required."
  except:
    assert True, "Great, it worked."

def test_posts_me():
  result = CLIENT.posts()
  posts = result.data
  assert isinstance(posts, list), \
    "Could not obtain reference to the account's posts."
  for post in posts:
    assert isinstance(post, buzz.Post), \
      "Could not obtain reference to the post."

def test_posts_other():
  client = buzz.Client()
  result = client.posts(type_id='@public', user_id=BUZZ_TESTING_ID)
  posts = result.data
  assert isinstance(posts, list), \
    "Could not obtain reference to the account's posts."
  for post in posts:
    assert isinstance(post, buzz.Post), \
      "Could not obtain reference to the post."

def test_consumption_me():
  result = CLIENT.posts(type_id='@consumption')
  posts = result.data
  assert isinstance(posts, list), \
    "Could not obtain reference to the account's posts."
  for post in posts:
    assert isinstance(post, buzz.Post), \
      "Could not obtain reference to the post."

def test_consumption_other():
  client = buzz.Client()
  try:
    client.posts(type_id='@consumption', user_id=BUZZ_TESTING_ID).data
    assert False, "Consumption feeds should only be available for @me."
  except:
    assert True, "Great, it worked."

def test_post():
  client = buzz.Client()
  result = client.post(post_id=BUZZ_POST_ID)
  post = result.data
  assert isinstance(post, buzz.Post), \
    "Could not obtain reference to the post."

def test_create_post():
  clear_posts()
  post = create_test_post()
  assert post.content == "This is a test post."
  assert isinstance(post, buzz.Post), \
    "Could not obtain reference to the post."

def test_update_post():
  clear_posts()
  post = create_test_post()
  post.content = "This is updated content."
  CLIENT.update_post(post)
  time.sleep(0.3)
  post = CLIENT.posts().data[0]
  assert post.content == "This is updated content."
  assert isinstance(post, buzz.Post), \
    "Could not obtain reference to the post."

def test_delete_post():
  create_test_post()
  clear_posts()
  assert CLIENT.posts().data == []

def test_comments():
  client = buzz.Client()
  result = client.comments(post_id=BUZZ_POST_ID)
  comments = result.data
  assert isinstance(comments, list), \
    "Could not obtain reference to the account's posts."
  for comment in comments:
    assert isinstance(comment, buzz.Comment), \
      "Could not obtain reference to the comment."

def test_create_comment():
  clear_posts()
  post = create_test_post()
  comment = buzz.Comment(content="This is a test comment.", post_id=post.id)
  CLIENT.create_comment(comment)
  time.sleep(0.3)
  comments = post.comments().data
  assert isinstance(comments, list), \
    "Could not obtain reference to the account's posts."
  comment = comments[0]
  assert isinstance(comment, buzz.Comment), \
    "Could not obtain reference to the comment."
  assert comment.content == "This is a test comment."

def test_update_comment():
  clear_posts()
  post = create_test_post()
  comment = buzz.Comment(content="This is a test comment.", post_id=post.id)
  CLIENT.create_comment(comment)
  time.sleep(0.3)
  comment = post.comments().data[0]
  comment.content = "This is updated content."
  CLIENT.update_comment(comment)
  time.sleep(0.3)
  comment = post.comments().data[0]
  assert comment.content == "This is updated content."

def test_delete_comment():
  clear_posts()
  post = create_test_post()
  comment = buzz.Comment(content="This is a test comment.", post_id=post.id)
  CLIENT.create_comment(comment)
  time.sleep(0.3)
  comments = post.comments().data
  comment = comments[0]
  assert comments != []
  CLIENT.delete_comment(comment)
  time.sleep(0.3)
  comments = post.comments().data
  assert comments == []

def test_like_post():
  post = CLIENT.post(post_id=BUZZ_POST_ID).data
  # We can only verify that this doesn't throw an error
  post.like()

def test_unlike_post():
  post = CLIENT.post(post_id=BUZZ_POST_ID).data
  # We can only verify that this doesn't throw an error
  post.unlike()

def test_post_likers():
  post = CLIENT.post(post_id=BUZZ_POST_ID).data
  likers = post.likers().data
  assert isinstance(likers, list), \
    "Should have been able to get the list of likers."

# def test_liked_posts():
#   posts = CLIENT.liked_posts().data

def test_mute_post():
  post = CLIENT.post(post_id=BUZZ_POST_ID).data
  # We can only verify that this doesn't throw an error
  post.mute()

def test_unmute_post():
  post = CLIENT.post(post_id=BUZZ_POST_ID).data
  # We can only verify that this doesn't throw an error
  post.unmute()

# def test_muted_posts():
#   posts = CLIENT.muted_posts().data
