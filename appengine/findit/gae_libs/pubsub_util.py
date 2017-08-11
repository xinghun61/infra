# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64

import httplib2
from googleapiclient import discovery
from oauth2client import client as oauth2client

PUBSUB_SCOPES = [
    'https://www.googleapis.com/auth/pubsub',
]


def CreatePubSubClient():  # pragma: no cover.
  credentials = oauth2client.GoogleCredentials.get_application_default()
  if credentials.create_scoped_required():
    credentials = credentials.create_scoped(PUBSUB_SCOPES)
  http = httplib2.Http()
  credentials.authorize(http)
  return discovery.build('pubsub', 'v1', http=http)


def PublishMessagesToTopic(messages_data, topic):  # pragma: no cover.
  messages = []
  for message_data in messages_data:
    messages.append({'data': base64.b64encode(message_data)})
  return CreatePubSubClient().projects().topics().publish(
      topic=topic, body={'messages': messages}).execute()


def PullMessagesFromSubscription(subscription_name, max_messages=10):
  """Pulls a list of messages from a Pub/Sub subscription."""
  subscription = CreatePubSubClient().projects().subscriptions()
  results = subscription.pull(
      subscription=subscription_name,
      body={'returnImmediately': True, 'maxMessages': max_messages}).execute()

  if not results:
    return []

  ack_ids = [result['ackId'] for result in results['receivedMessages']]
  messages = [result['message'] for result in results['receivedMessages']]
  # Acknowledge received messages. If you do not acknowledge, Pub/Sub will
  # redeliver the message.
  subscription.acknowledge(
      subscription=subscription_name, body={'ackIds': ack_ids}).execute()
  return messages
