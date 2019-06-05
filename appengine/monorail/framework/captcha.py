# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A simple python interface to ReCAPTCHA."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import logging
import urllib
import urllib2

from services import secrets_svc


def Verify(remote_ip, response):
  """Check the user's guess at a captcha solution.

  Args:
    remote_ip: user's IP address.
    challenge: The captcha challenge presented to the user.
    guess: The user's response to the captcha.

  Returns:
    A pair (correct, error_msg) where error_msg will indicate
    why a response was deemed incorrect. It is logged so that
    you can see, e.g., if you have the wrong private key.
  """
  # If the use did not enter anything, that is always incorrect
  if not response:
    logging.info('response was blank')
    return False, 'incorrect-captcha-sol'

  resp = _AskRecaptcha(remote_ip, response)
  if not resp['success']:
    if 'error-codes' in resp:
      return False, resp['error-codes']
    else:
      return False, 'incorrect-captcha-sol'

  return True, ''


def _AskRecaptcha(remote_ip, response):
  """Ask the ReCAPTCHA backend to verify the user's guess."""
  recaptcha_server_request = urllib2.Request(
      url='https://www.google.com/recaptcha/api/siteverify',
      data=urllib.urlencode({
          'secret': secrets_svc.GetRecaptchaPrivateKey(),
          'remoteip': remote_ip,
          'response': response}),
      headers={
          'Content-type': 'application/x-www-form-urlencoded',
          'User-agent': 'reCAPTCHA Python'})
  recaptcha_server_response = urllib2.urlopen(recaptcha_server_request)
  resp = json.loads(recaptcha_server_response.read())
  recaptcha_server_response.close()

  return resp

