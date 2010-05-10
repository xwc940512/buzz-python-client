# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import urlparse
import cgi
import httplib
import string
import urllib
import re

import logging

sys.path.append('third_party')

import oauth

try:
  import simplejson
except (ImportError):
  # This is where simplejson lives on App Engine
  from django.utils import simplejson

API_PREFIX = "https://www.googleapis.com/buzz/v1"
READONLY_SCOPE = 'https://www.googleapis.com/auth/buzz.readonly'
FULL_ACCESS_SCOPE = 'https://www.googleapis.com/auth/buzz'

OAUTH_REQUEST_TOKEN_URI = \
  'https://www.google.com/accounts/OAuthGetRequestToken'
OAUTH_ACCESS_TOKEN_URI = \
  'https://www.google.com/accounts/OAuthGetAccessToken'
OAUTH_AUTHORIZATION_URI = \
  'https://sandbox.google.com/buzz/api/auth/OAuthAuthorizeToken'
# OAUTH_AUTHORIZATION_URI = \
#   'https://www.google.com/buzz/api/auth/OAuthAuthorizeToken'
# OAUTH_AUTHORIZATION_URI = \
#   'https://www.google.com/accounts/OAuthAuthorizeToken'

class RetrieveError(Exception):
  """
  This exception gets raised if there was some kind of HTTP or network error
  while accessing the API.
  """
  def __init__(self, uri, message):
    self._uri = uri
    self._message = message

  def __str__(self):
    return 'Could not retrieve \'%s\': %s' % (self._uri, self._message)

class JSONParseError(Exception):
  """
  This exception gets raised if the API sends data that does not match
  what the client was expecting.  If this exception is raised, it's typically
  a bug.
  """
  def __init__(self, dictionary, uri=None, exception=None):
    self._uri = uri
    self._dictionary = dictionary
    self._exception = exception

  def __str__(self):
    if self._uri:
      if self._exception and isinstance(self._exception, KeyError):
        return 'Parse failed for \'%s\': KeyError(%s) on %s' % (
          self._uri, str(self._exception), self._dictionary
        )
      else:
        return 'Parse failed for \'%s\': %s' % (self._uri, self._dictionary)
    else:
      if self._exception and isinstance(self._exception, KeyError):
        return 'Parse failed: KeyError(%s) on %s' % (
          str(self._exception), self._dictionary
        )
      else:
        return 'Parse failed: %s' % (self._dictionary)

def prune_json(json):
  # Follow Postel's law
  if isinstance(json, dict):
    if json.get('data'):
      json = json['data']
    if json.get('items'):
      json = json['items']
  else:
    raise TypeError('Expected dict: \'%s\'' % str(json))
  return json

class Client:
  def __init__(self):
    self._http_connection = None

    # OAuth state
    self.oauth_scopes = []
    self._oauth_http_connection = None
    self.oauth_consumer = None
    self.oauth_request_token = None
    self.oauth_access_token = None
    self._oauth_token_authorized = False
    self._oauth_signature_method_hmac_sha1 = \
      oauth.OAuthSignatureMethod_HMAC_SHA1()

  @property
  def http_connection(self):
    # if not self._http_connection:
    #   self._http_connection = httplib.HTTPSConnection('www.google.com')
    if not self._http_connection:
      self._http_connection = httplib.HTTPSConnection('www.googleapis.com')
    if self._http_connection.host != 'www.googleapis.com':
      raise ValueError("HTTPS Connection must be for 'www.googleapis.com'.")
    # if self._http_connection.port != 443:
    #   raise ValueError("HTTPS Connection must be for port 443.")
    return self._http_connection

  def build_oauth_consumer(self, key, secret):
    self.oauth_consumer = oauth.OAuthConsumer(key, secret)

  def build_oauth_request_token(self, key, secret):
    self.oauth_request_token = oauth.OAuthToken(key, secret)

  def build_oauth_access_token(self, key, secret):
    self.oauth_access_token = oauth.OAuthToken(key, secret)

  @property
  def oauth_http_connection(self):
    if not self._oauth_http_connection:
      self._oauth_http_connection = httplib.HTTPSConnection('www.google.com')
    if self._oauth_http_connection.host != 'www.google.com':
      raise ValueError("OAuth HTTPS Connection must be for 'www.google.com'.")
    # if self._oauth_http_connection.port != 443:
    #   raise ValueError("OAuth HTTPS Connection must be for port 443.")
    return self._oauth_http_connection

  def fetch_oauth_response(self, oauth_request):
    """Sends a signed request to Google's Accounts API."""
    # Transmit the OAuth request to Google
    if oauth_request.http_method != 'POST':
      raise ValueError("OAuthRequest HTTP method must be POST.")
    try:
      self.oauth_http_connection.request(
        oauth_request.http_method,
        oauth_request.http_url,
        body=oauth_request.to_postdata(),
        headers={
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      )
      response = self.oauth_http_connection.getresponse()
    except (httplib.BadStatusLine, httplib.CannotSendRequest):
      # Reset the connection
      if self._oauth_http_connection:
        self._oauth_http_connection.close()
      self._oauth_http_connection = None
      # Retry once
      self.oauth_http_connection.request(
        oauth_request.http_method,
        oauth_request.http_url,
        body=oauth_request.to_postdata(),
        headers={
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      )
      response = self.oauth_http_connection.getresponse()
    return response

  def fetch_oauth_request_token(self, callback_uri):
    """Obtains an OAuth request token from Google's Accounts API."""
    if not self.oauth_request_token:
      # Build and sign an OAuth request
      parameters = {
        'oauth_consumer_key': self.oauth_consumer.key,
        'oauth_timestamp': oauth.generate_timestamp(),
        'oauth_nonce': oauth.generate_nonce(),
        'oauth_version': oauth.OAuthRequest.version,
        'oauth_callback': callback_uri,
        'scope': ' '.join(self.oauth_scopes)
      }
      oauth_request = oauth.OAuthRequest(
        'POST',
        OAUTH_REQUEST_TOKEN_URI,
        parameters
      )
      oauth_request.sign_request(
        self._oauth_signature_method_hmac_sha1,
        self.oauth_consumer,
        token=None
      )
      response = self.fetch_oauth_response(oauth_request)
      if response.status == 200:
        # Create the token from the response
        self.oauth_request_token = oauth.OAuthToken.from_string(response.read())
      else:
        raise Exception('Failed to obtain request token:\n' + response.read())
    return self.oauth_request_token

  def build_oauth_authorization_url(self, token=None):
    if not token:
      token = self.oauth_request_token
    if not self.oauth_consumer:
      raise ValueError("Client is missing consumer.")
    auth_uri = OAUTH_AUTHORIZATION_URI + \
      "?oauth_token=" + token.key + \
      "&domain=" + self.oauth_consumer.key
    for scope in self.oauth_scopes:
      auth_uri += "&scope=" + scope
    return auth_uri

  def fetch_oauth_access_token(self, verifier=None, token=None):
    """Obtains an OAuth access token from Google's Accounts API."""
    if not self.oauth_access_token:
      if not token:
        token = self.oauth_request_token
      if not token:
        raise ValueError("A request token must be supplied.")
      # Build and sign an OAuth request
      parameters = {
        'oauth_consumer_key': self.oauth_consumer.key,
        'oauth_timestamp': oauth.generate_timestamp(),
        'oauth_nonce': oauth.generate_nonce(),
        'oauth_version': oauth.OAuthRequest.version,
        'oauth_token': token.key,
        'oauth_verifier': verifier
      }
      oauth_request = oauth.OAuthRequest(
        'POST',
        OAUTH_ACCESS_TOKEN_URI,
        parameters
      )
      oauth_request.sign_request(
        self._oauth_signature_method_hmac_sha1,
        self.oauth_consumer,
        token=token
      )
      response = self.fetch_oauth_response(oauth_request)
      if response.status == 200:
        # Create the token from the response
        self.oauth_access_token = oauth.OAuthToken.from_string(response.read())
      else:
        raise Exception('Failed to obtain access token:\n' + response.read())
    return self.oauth_access_token

  def build_oauth_request(self, http_method, http_url):
    # Query parameters have to be signed, and the OAuth library isn't smart
    # enough to do this automatically
    query = urlparse.urlparse(http_url)[4] # Query is 4th element of the tuple
    if query:
      qs_parser = None
      if hasattr(urlparse, 'parse_qs'):
        qs_parser = urlparse.parse_qs
      else:
        # Deprecated in 2.6
        qs_parser = cgi.parse_qs
      parameters = qs_parser(
        query,
        keep_blank_values=True,
        strict_parsing=True
      )
      for k, v in parameters.iteritems():
        parameters[k] = v[0]
    else:
      parameters = {}
    # Build the OAuth request, add in our parameters, and sign it
    oauth_request = oauth.OAuthRequest.from_consumer_and_token(
      self.oauth_consumer,
      token=self.oauth_access_token,
      http_method=http_method,
      http_url=http_url,
      parameters=parameters
    )
    oauth_request.sign_request(
      self._oauth_signature_method_hmac_sha1,
      self.oauth_consumer,
      token=self.oauth_access_token
    )
    return oauth_request

  def fetch_api_response(self, http_method, http_url, http_headers={}, \
                               http_connection=None, http_body=''):
    if not http_connection:
      http_connection = self.http_connection
    if not self.oauth_consumer:
      raise ValueError("Client is missing consumer.")
    http_headers.update({
      'Content-Length': len(http_body)
    })
    if self.oauth_access_token:
      # Build OAuth request and add OAuth header if we've got an access token
      oauth_request = self.build_oauth_request(http_method, http_url)
      http_headers.update(oauth_request.to_header())
    try:
      http_connection.request(http_method, http_url, headers=http_headers)
      response = http_connection.getresponse()
    except (httplib.BadStatusLine, httplib.CannotSendRequest):
      if http_connection and http_connection == self.http_connection:
        # Reset the connection
        http_connection.close()
        http_connection = None
        self._http_connection = None
        http_connection = self.http_connection
        # Retry once
        http_connection.request(http_method, http_url, headers=http_headers)
        response = http_connection.getresponse()
    return response

  def parse_person(self, json, api_endpoint=None):
    """Helper method for converting a person JSON structure."""
    try:
      if json.get('error'):
        self.parse_error(json, api_endpoint)
      return Person(json, client=self)
    except KeyError, e:
      raise JSONParseError(
        uri=api_endpoint,
        dictionary=json,
        exception=e
      )

  def parse_people(self, json, api_endpoint=None):
    """Helper method for converting a set of person JSON structures."""
    try:
      if json.get('error'):
        self.parse_error(json, api_endpoint)
      if isinstance(json, list):
        return [Person(post_json, client=self) for person_json in json]
      else:
        # The entire key is omitted when there are no results
        return []
    except KeyError, e:
      raise JSONParseError(
        uri=api_endpoint,
        dictionary=json,
        exception=e
      )

  def parse_posts(self, json, api_endpoint=None):
    """Helper method for converting a set of post JSON structures."""
    try:
      if json.get('error'):
        self.parse_error(json, api_endpoint)
      json = prune_json(json)
      if isinstance(json, list):
        return [Post(post_json, client=self) for post_json in json]
      else:
        # The entire key is omitted when there are no results
        return []
    except KeyError, e:
      raise JSONParseError(
        uri=api_endpoint,
        dictionary=json,
        exception=e
      )

  def parse_comments(self, json, api_endpoint=None):
    """Helper method for converting a set of comment JSON structures."""
    try:
      if json.get('error'):
        self.parse_error(json, api_endpoint)
      json = prune_json(json)
      if isinstance(json, list):
        return [Comment(comment_json, client=self) for comment_json in json]
      else:
        # The entire key is omitted when there are no results
        return []
    except KeyError, e:
      raise JSONParseError(
        uri=api_endpoint,
        dictionary=json,
        exception=e
      )

  def parse_error(self, json, api_endpoint=None):
    """Helper method for converting an error response to an exception."""
    raise RetrieveError(
      uri=api_endpoint,
      message=json['error'].get('message')
    )

  # People APIs

  def user(self, user_id='@me'):
    if isinstance(user_id, Person):
      # You'd think we could just return directly here, but sometimes a
      # Person object is incomplete, in which case this operation would
      # 'upgrade' to the full Person object.
      user_id = user_id.id
    if self.oauth_access_token:
      api_endpoint = API_PREFIX + ("/people/%s/@self" % user_id)
      api_endpoint += "?alt=json"
      response = self.fetch_api_response('GET', api_endpoint)
      json = simplejson.load(response)
      return self.parse_person(json, api_endpoint)
    else:
      raise ValueError("This client doesn't have an authenticated user.")

  # Post APIs

  def search(self, query=None, geocode=None):
    api_endpoint = API_PREFIX + "/activities/search?alt=json"
    if query:
      api_endpoint += "&q=" + urllib.quote_plus(query)
    if geocode:
      api_endpoint += "&geocode=" + urllib.quote(",".join(geocode))
    response = self.fetch_api_response('GET', api_endpoint)
    json = simplejson.load(response)
    return self.parse_posts(json, api_endpoint)

  def posts(self, type_id='@self', user_id='@me'):
    if isinstance(user_id, Person):
      user_id = user_id.id
    api_endpoint = API_PREFIX + "/activities/" + user_id + "/" + type_id
    api_endpoint += "?alt=json"
    response = self.fetch_api_response('GET', api_endpoint)
    json = simplejson.load(response)
    return self.parse_posts(json, api_endpoint)

  def comments(self, actor_id, post_id):
    if isinstance(actor_id, Person):
      actor_id = actor_id.id
    if isinstance(post_id, Post):
      post_id = post_id.id
    api_endpoint = API_PREFIX + "/activities/" + actor_id + \
      "/@self/" + post_id + "/@comments"
    api_endpoint += "?alt=json"
    response = self.fetch_api_response('GET', api_endpoint)
    json = simplejson.load(response)
    return self.parse_comments(json, api_endpoint)

  def likers(self, actor_id, post_id):
    if isinstance(actor_id, Person):
      actor_id = actor_id.id
    if isinstance(post_id, Post):
      post_id = post_id.id
    api_endpoint = API_PREFIX + "/activities/" + actor_id + \
      "/@self/" + post_id + "/@likers"
    api_endpoint += "?alt=json"
    response = self.fetch_api_response('GET', api_endpoint)
    json = simplejson.load(response)
    return self.parse_people(json, api_endpoint)

  # Likes
  def liked_posts(self, user_id=None):
    """Returns a collection of posts that a user has liked."""
    return None # self.posts(type_id='@liked', user_id)

  def like_post(self, actor_id, post_id):
    """
    Likes a post.
    """
    if isinstance(actor_id, Person):
      actor_id = actor_id.id
    if isinstance(post_id, Post):
      post_id = post_id.id
    api_endpoint = API_PREFIX + "/activities/" + actor_id + \
      "/@liked/" + post_id
    api_endpoint += "?alt=json"
    response = self.fetch_api_response('PUT', api_endpoint)
    json = simplejson.load(response)
    if json.get('error'):
      self.parse_error(self, json, api_endpoint)

  def unlike_post(self, actor_id, post_id):
    """
    Unlikes a post.
    """
    if isinstance(actor_id, Person):
      actor_id = actor_id.id
    if isinstance(post_id, Post):
      post_id = post_id.id
    api_endpoint = API_PREFIX + "/activities/" + actor_id + \
      "/@liked/" + post_id
    api_endpoint += "?alt=json"
    response = self.fetch_api_response('DELETE', api_endpoint)
    json = simplejson.load(response)
    if json.get('error'):
      self.parse_error(json, api_endpoint)

  # Mutes
  
  def muted_posts(self):
    """Returns a collection of posts that the current user has muted."""
    return self.posts(type_id='@muted', user_id='@me')

  def mute_post(self, actor_id, post_id):
    """
    Mutes a post.
    """
    if isinstance(actor_id, Person):
      actor_id = actor_id.id
    if isinstance(post_id, Post):
      post_id = post_id.id
    api_endpoint = API_PREFIX + "/activities/" + actor_id + \
      "/@muted/" + post_id
    api_endpoint += "?alt=json"
    response = self.fetch_api_response('PUT', api_endpoint)
    json = simplejson.load(response)
    if json.get('error'):
      self.parse_error(self, json, api_endpoint)

  def unmute_post(self, actor_id, post_id):
    """
    Unmutes a post.
    """
    if isinstance(actor_id, Person):
      actor_id = actor_id.id
    if isinstance(post_id, Post):
      post_id = post_id.id
    api_endpoint = API_PREFIX + "/activities/" + actor_id + \
      "/@muted/" + post_id
    api_endpoint += "?alt=json"
    response = self.fetch_api_response('DELETE', api_endpoint)
    json = simplejson.load(response)
    if json.get('error'):
      self.parse_error(json, api_endpoint)

  # # People
  #
  # def followers(self, user_id):
  #
  # def following(self, user_id):
  #
  # def follow(self, user_id):
  #
  # def unfollow(self, user_id):

  # OAuth debugging

  def oauth_token_info(self):
    """
    Returns information about the client's current access token.

    Allows a developer to verify that their token is valid.
    """
    api_endpoint = "https://www.google.com/accounts/AuthSubTokenInfo"
    if not self.oauth_access_token:
      raise ValueError("Client is missing access token.")
    response = self.fetch_api_response(
      'GET',
      api_endpoint,
      http_connection=self.oauth_http_connection
    )
    return response.read()

class Post:
  def __init__(self, json, client=None):
    self.client = client
    self.json = json
    self._likers = None
    self._comments = None

    # Follow Postel's law
    try:
      json = prune_json(json)
      self.id = json['id']
      if isinstance(json.get('content'), dict):
        self.content = json['content']['value']
      elif json.get('content'):
        self.content = json['content']
      elif json.get('object') and json['object'].get('content'):
        self.content = json['object']['content']
      if isinstance(json['title'], dict):
        self.title = json['title']['value']
      else:
        self.title = json['title']
      if isinstance(json.get('verb'), list):
        self.verb = json['verb'][0]
      elif json.get('verb'):
        self.verb = json['verb']
      elif isinstance(json.get('type'), list):
        self.verb = json['type'][0]
      elif json.get('type'):
        self.verb = json['type']
      if json.get('author'):
        self.actor = Person(json['author'], client=self.client)
      elif json.get('actor'):
        self.actor = Person(json['actor'], client=self.client)
      # TODO: handle timestamps
    except KeyError, e:
      raise JSONParseError(
        dictionary=json,
        exception=e
      )

  def __repr__(self):
    return "<Post[%s]>" % self.id

  @property
  def comments(self):
    if not self._comments:
      if self.client:
        self._comments = self.client.comments(self.actor.id, self.id)
      else:
        raise ValueError('Cannot get comments without a client reference.')
    return self._comments

  @property
  def likers(self):
    if not self._likers:
      if self.client:
        self._likers = self.client.likers(self.actor.id, self.id)
      else:
        raise ValueError('Cannot get likers without a client reference.')
    return self._likers

  def like(self, client=None):
    """Syntactic sugar for `client.like_post(post)`."""
    if not client:
      client = self.client
    return client.like_post(self.actor.id, self.id)

  def unlike(self, client=None):
    """Syntactic sugar for `client.unlike_post(post)`."""
    if not client:
      client = self.client
    return client.unlike_post(self.actor.id, self.id)

  def mute(self, client=None):
    """Syntactic sugar for `client.mute_post(post)`."""
    if not client:
      client = self.client
    return client.mute_post(self.actor.id, self.id)

  def unmute(self, client=None):
    """Syntactic sugar for `client.unmute_post(post)`."""
    if not client:
      client = self.client
    return client.unmute_post(self.actor.id, self.id)

class Comment:
  def __init__(self, json, client=None):
    self.client = client
    self.json = json
    # Follow Postel's law
    try:
      json = prune_json(json)
      self.id = json['id']
      if isinstance(json.get('content'), dict):
        self.content = json['content']['value']
      elif json.get('content'):
        self.content = json['content']
      elif json.get('object') and json['object'].get('content'):
        self.content = json['object']['content']
      if json.get('author'):
        self.actor = Person(json['author'], client=self.client)
      elif json.get('actor'):
        self.actor = Person(json['actor'], client=self.client)
      # TODO: handle timestamps
    except KeyError, e:
      raise JSONParseError(
        dictionary=json,
        exception=e
      )

  def __repr__(self):
    return "<Comment[%s]>" % self.id
  
  def post(self):
    # TODO
    return None

class Person:
  def __init__(self, json, client=None):
    self.client = client
    self.json = json
    # Follow Postel's law
    try:
      json = prune_json(json)
      self.uri = \
        json.get('uri') or json.get('profileUrl')
      if json.get('id'):
        self.id = json.get('id')
      else:
        self.id = re.search('/([^/]*?)$', self.uri).group(1)
      self.name = \
        json.get('name') or json.get('displayName')
      self.photo = \
        json.get('photoUrl') or json.get('thumbnailUrl')
      if json.get('urls'):
        self.uris = json.get('urls')
      if json.get('photos'):
        self.photos = json.get('photos')
    except KeyError, e:
      raise JSONParseError(
        dictionary=json,
        exception=e
      )

  def __repr__(self):
    return "<Person[%s]>" % self.id

  @property
  def posts(self):
    return self.client.posts(user_id=self.id)
