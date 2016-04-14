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
