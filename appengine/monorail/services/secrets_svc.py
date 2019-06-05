# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A set of functions that provide persistence for secret keys.

These keys are used in generating XSRF tokens, calling the CAPTCHA API,
and validating that inbound emails are replies to notifications that
we sent.

Unlike other data stored in Monorail, this is kept in the GAE
datastore rather than SQL because (1) it never needs to be used in
combination with other SQL data, and (2) we may want to replicate
issue content for various off-line reporting functionality, but we
will never want to do that with these keys.  A copy is also kept in
memcache for faster access.

When no secrets are found, a new Secrets entity is created and initialized
with randomly generated values for XSRF and email keys.

If these secret values ever need to change:
(1) Make the change on the Google Cloud Console in the Cloud Datastore tab.
(2) Flush memcache.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from google.appengine.api import memcache
from google.appengine.ext import ndb

import settings
from framework import framework_helpers


GLOBAL_KEY = 'secrets_singleton_key'


class Secrets(ndb.Model):
  """Model for representing secret keys."""
  # Keys we use to generate tokens.
  xsrf_key = ndb.StringProperty(required=True)
  email_key = ndb.StringProperty(required=True)

  # Keys for other APIs that we use.
  recaptcha_public_key = ndb.StringProperty()
  recaptcha_private_key = ndb.StringProperty()


def MakeSecrets():
  """Make a new Secrets model with random values for keys."""
  secrets = Secrets(id=GLOBAL_KEY)
  secrets.xsrf_key = framework_helpers.MakeRandomKey()
  secrets.email_key = framework_helpers.MakeRandomKey()
  # Note that recaptcha keys are not generated.  An admin
  # will need to set them via the Google Cloud Console.
  return secrets


def GetSecrets():
  """Get secret keys from memcache or datastore. Or, make new ones."""
  secrets = memcache.get(GLOBAL_KEY)
  if secrets:
    return secrets

  secrets = Secrets.get_by_id(GLOBAL_KEY)
  if not secrets:
    secrets = MakeSecrets()
    secrets.put()

  memcache.set(GLOBAL_KEY, secrets)
  return secrets


def GetXSRFKey():
  """Return a secret key string used to generate XSRF tokens."""
  return GetSecrets().xsrf_key


def GetEmailKey():
  """Return a secret key string used to generate email tokens."""
  return GetSecrets().email_key


def GetRecaptchaPublicKey():
  """Return our public API key for reCAPTCHA."""
  if settings.local_mode:
    return '6LebzNMSAAAAAMY8b_FaZvp8wymUO5Jsa0pIX7HO'

  result = GetSecrets().recaptcha_public_key
  if not result:
    logging.warn('No recaptcha_public_key set.  Get one at recaptcha.net.')
    logging.warn('Store it in Cloud Datastore via the Google Cloud Console.')

  return result


def GetRecaptchaPrivateKey():
  """Return our private API key for reCAPTCHA."""
  if settings.local_mode:
    return '6LebzNMSAAAAAHNVNiP2I7aNMv2AmxY5nReE2LZ4'

  result = GetSecrets().recaptcha_private_key
  if not result:
    logging.warn('No recaptcha_private_key set.  Get one at recaptcha.net.')
    logging.warn('Store it in Cloud Datastore via the Google Cloud Console.')

  return result
