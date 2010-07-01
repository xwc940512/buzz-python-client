#!/usr/bin/python
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import buzz
import optparse
import unittest
import time
from pprint import pprint
try:
  import yaml
except (ImportError):
  sys.stderr.write('Please install PyYAML.\n')
  exit(1)

GOOGLEPLEX_LATITUDE = '37.420233'
GOOGLEPLEX_LONGITUDE = '-122.08333'

global CONFIG_PATH

# For the most part, these tests do not rely on any specific piece of data
# being returned by the API.  Mostly they verify that an exception has not
# been thrown.  Not ideal, but better than needlessly brittle tests.

class MainTest(unittest.TestCase):
  def setUp(self):
    self.test_config = buzz.CLIENT_CONFIG
    self.oauth_consumer_key = self.test_config['oauth_consumer_key']
    self.oauth_consumer_secret = self.test_config['oauth_consumer_secret']
    self.oauth_token_key = self.test_config['oauth_token_key']
    self.oauth_token_secret = self.test_config['oauth_token_secret']

    self.buzz_testing_id = str(self.test_config['testing_id'])
    self.buzz_testing_account = str(self.test_config['testing_account'])
    self.buzz_target_id = str(self.test_config['target_id'])
    self.buzz_target_account = str(self.test_config['target_account'])
    self.buzz_post_id = str(self.test_config['post_id'])

    self.client = buzz.Client()
    self.client.build_oauth_consumer(
      self.oauth_consumer_key, self.oauth_consumer_secret
    )
    self.client.build_oauth_access_token(
      self.oauth_token_key, self.oauth_token_secret
    )

  def clear_posts(self):
    # Make sure we don't have any posts
    posts = self.client.posts()
    for post in posts:
      self.client.delete_post(post)

  def create_test_post(self):
    post = buzz.Post(content="This is a test post.")
    self.client.create_post(post)
    time.sleep(0.3)
    return self.client.posts().data[0]

  def test_auth_required(self):
    client = buzz.Client()
    try:
      client.person().data
      assert False, "Authorization should have been required."
    except:
      assert True, "Great, it worked."

  def test_anonymous_consumer(self):
    client = buzz.Client()
    client.use_anonymous_oauth_consumer()
    client.oauth_scopes.append(buzz.FULL_ACCESS_SCOPE)
    request_token = \
      client.fetch_oauth_request_token('http://example.com/callback/')
    assert request_token.key, "Request token key missing."
    assert request_token.secret, "Request token secret missing."
    assert client.build_oauth_authorization_url(), \
      "Could not build authorization URL"

  def test_registered_consumer(self):
    client = buzz.Client()
    client.build_oauth_consumer(
      self.oauth_consumer_key, self.oauth_consumer_secret
    )
    client.oauth_scopes.append(buzz.FULL_ACCESS_SCOPE)
    request_token = \
      client.fetch_oauth_request_token('http://example.com/callback/')
    assert request_token.key, "Request token key missing."
    assert request_token.secret, "Request token secret missing."
    assert client.build_oauth_authorization_url(), \
      "Could not build authorization URL"

  def test_person_me(self):
    result = self.client.person()
    person = result.data
    assert person, "Could not obtain reference to the token's account."
    assert person.name, \
      "Could not obtain reference to the account's display name."
    assert person.uri, \
      "Could not obtain reference to the account's profile link."

  def test_person_other(self):
    result = self.client.person(self.buzz_testing_id)
    person = result.data
    assert person, "Could not obtain reference to the token's account."
    assert person.name, \
      "Could not obtain reference to the account's display name."
    assert person.uri, \
      "Could not obtain reference to the account's profile link."

  def test_person_me_without_auth(self):
    client = buzz.Client()
    try:
      client.person()
      assert False, "Authorization should have been required."
    except:
      assert True, "Great, it worked."

  def test_person_other_without_auth(self):
    client = buzz.Client()
    try:
      client.person(self.buzz_testing_id)
      assert False, "Authorization should have been required."
    except:
      assert True, "Great, it worked."

  def test_followers_me(self):
    result = self.client.followers()
    followers = result.data
    assert isinstance(followers, list), \
      "Should have been able to get the list of followers."

  def test_followers_other(self):
    client = buzz.Client()
    result = client.followers(self.buzz_testing_id)
    followers = result.data
    assert isinstance(followers, list), \
      "Should have been able to get the list of followers."

  def test_following_me(self):
    result = self.client.following()
    following = result.data
    assert isinstance(following, list), \
      "Should have been able to get the list of people being followed."

  def test_following_other(self):
    client = buzz.Client()
    result = client.following(self.buzz_testing_id)
    following = result.data
    assert isinstance(following, list), \
      "Should have been able to get the list of people being followed."

  def test_follow(self):
    person = self.client.person(self.buzz_target_id).data
    person.follow()
    # Give the API time to catch up
    time.sleep(0.3)
    followers = self.client.followers(self.buzz_target_id).data
    assert self.buzz_testing_id in [follower.id for follower in followers], \
      "Should have been able to find the account in followers list."
    following = self.client.following(self.buzz_testing_id).data
    assert self.buzz_target_id in [followee.id for followee in following], \
      "Should have been able to find the target in following list."
    self.client.unfollow(self.buzz_target_id)

  def test_unfollow(self):
    person = self.client.person(self.buzz_target_id).data
    person.follow()
    person.unfollow()
    # Give the API time to catch up
    time.sleep(0.3)
    followers = self.client.followers(self.buzz_target_id).data
    assert not self.buzz_testing_id in [
      follower.id for follower in followers
    ], "Should not have been able to find the account in followers list."
    following = self.client.following(self.buzz_testing_id).data
    assert not self.buzz_target_id in [
      followee.id for followee in following
    ], "Should not have been able to find the target in following list."

  def test_follow_without_auth(self):
    client = buzz.Client()
    try:
      client.follow(self.buzz_target_id)
      assert False, "Authorization should have been required."
    except:
      assert True, "Great, it worked."

  def test_unfollow_without_auth(self):
    client = buzz.Client()
    try:
      client.unfollow(self.buzz_target_id)
      assert False, "Authorization should have been required."
    except:
      assert True, "Great, it worked."

  def test_search_location(self):
    result = self.client.search(latitude=GOOGLEPLEX_LATITUDE,
        longitude=GOOGLEPLEX_LONGITUDE, radius='10')
    posts = result.data
    assert isinstance(posts, list), \
      "Could not obtain reference to the account's posts."
    assert len(posts) > 0, "Not enough posts."
    for post in posts:
      assert isinstance(post, buzz.Post), \
        "Could not obtain reference to the post."

  def test_search_query(self):
    result = self.client.search(query="google")
    posts = result.data
    assert isinstance(posts, list), \
      "Could not obtain reference to the account's posts."
    assert len(posts) > 0, "Not enough posts."
    for i, post in enumerate(posts):
      assert isinstance(post, buzz.Post), \
        "Could not obtain reference to the post."
      if i >= 5:
        break

  def test_posts_me(self):
    result = self.client.posts()
    posts = result.data
    assert isinstance(posts, list), \
      "Could not obtain reference to the account's posts."
    for post in posts:
      assert isinstance(post, buzz.Post), \
        "Could not obtain reference to the post."

  def test_posts_other(self):
    client = buzz.Client()
    result = client.posts(type_id='@public', user_id=self.buzz_testing_id)
    posts = result.data
    assert isinstance(posts, list), \
      "Could not obtain reference to the account's posts."
    for post in posts:
      assert isinstance(post, buzz.Post), \
        "Could not obtain reference to the post."

  def test_consumption_me(self):
    result = self.client.posts(type_id='@consumption')
    posts = result.data
    assert isinstance(posts, list), \
      "Could not obtain reference to the account's posts."
    for post in posts:
      assert isinstance(post, buzz.Post), \
        "Could not obtain reference to the post."

  def test_consumption_other(self):
    client = buzz.Client()
    try:
      client.posts(type_id='@consumption', user_id=self.buzz_testing_id).data
      assert False, "Consumption feeds should only be available for @me."
    except:
      assert True, "Great, it worked."

  def test_post(self):
    client = buzz.Client()
    result = client.post(post_id=self.buzz_post_id)
    post = result.data
    assert isinstance(post, buzz.Post), \
      "Could not obtain reference to the post."

  def test_create_post(self):
    self.clear_posts()
    post = self.create_test_post()
    assert post.content == "This is a test post."
    assert isinstance(post, buzz.Post), \
      "Could not obtain reference to the post."

  def test_update_post(self):
    self.clear_posts()
    post = self.create_test_post()
    post.content = "This is updated content."
    self.client.update_post(post)
    time.sleep(0.3)
    post = self.client.posts().data[0]
    assert post.content == "This is updated content."
    assert isinstance(post, buzz.Post), \
      "Could not obtain reference to the post."

  def test_delete_post(self):
    self.create_test_post()
    self.clear_posts()
    assert self.client.posts().data == []

  def test_comments(self):
    client = buzz.Client()
    result = client.comments(post_id=self.buzz_post_id)
    comments = result.data
    assert isinstance(comments, list), \
      "Could not obtain reference to the account's posts."
    for comment in comments:
      assert isinstance(comment, buzz.Comment), \
        "Could not obtain reference to the comment."

  def test_create_comment(self):
    self.clear_posts()
    post = self.create_test_post()
    comment = buzz.Comment(content="This is a test comment.", post_id=post.id)
    self.client.create_comment(comment)
    time.sleep(0.3)
    comments = post.comments().data
    assert isinstance(comments, list), \
      "Could not obtain reference to the account's posts."
    comment = comments[0]
    assert isinstance(comment, buzz.Comment), \
      "Could not obtain reference to the comment."
    assert comment.content == "This is a test comment."

  def test_update_comment(self):
    self.clear_posts()
    post = self.create_test_post()
    comment = buzz.Comment(content="This is a test comment.", post_id=post.id)
    self.client.create_comment(comment)
    time.sleep(0.3)
    comment = post.comments().data[0]
    comment.content = "This is updated content."
    self.client.update_comment(comment)
    time.sleep(0.3)
    comment = post.comments().data[0]
    assert comment.content == "This is updated content."

  def test_delete_comment(self):
    self.clear_posts()
    post = self.create_test_post()
    comment = buzz.Comment(content="This is a test comment.", post_id=post.id)
    self.client.create_comment(comment)
    time.sleep(0.3)
    comments = post.comments().data
    comment = comments[0]
    assert comments != []
    self.client.delete_comment(comment)
    time.sleep(0.3)
    comments = post.comments().data
    assert comments == []

  def test_like_post(self):
    post = self.client.post(post_id=self.buzz_post_id).data
    # We can only verify that this doesn't throw an error
    post.like()

  def test_unlike_post(self):
    post = self.client.post(post_id=self.buzz_post_id).data
    # We can only verify that this doesn't throw an error
    post.unlike()

  def test_post_likers(self):
    post = self.client.post(post_id=self.buzz_post_id).data
    likers = post.likers().data
    assert isinstance(likers, list), \
      "Should have been able to get the list of likers."

  # def test_liked_posts(self):
  #   posts = self.client.liked_posts().data

  def test_mute_post(self):
    post = self.client.post(post_id=self.buzz_post_id).data
    # We can only verify that this doesn't throw an error
    post.mute()

  def test_unmute_post(self):
    post = self.client.post(post_id=self.buzz_post_id).data
    # We can only verify that this doesn't throw an error
    post.unmute()

  # def test_muted_posts(self):
  #   posts = self.client.muted_posts().data

if __name__ == '__main__':
  unittest.main()
