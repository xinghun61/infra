# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import webapp2
from google.appengine.ext import ndb

class FrameworkAbortError(Exception):
  def __init__(self, response):
    super(FrameworkAbortError, self).__init__()
    self.response = response

def _default(obj):
  if isinstance(obj, datetime.datetime):
    return str(obj)

  if isinstance(obj, ndb.Model):
    return obj.to_dict()
    model_dict = obj.to_dict()
    model_dict['id'] = obj.key.id()
    return model_dict

  if isinstance(obj, ndb.Key):
    return obj.urlsafe()
    
  raise TypeError('%s is not JSON serializable' % str(obj))

def success(result=None):
  if result is None:
    result = {}

  response = webapp2.Response()
  response.headers['Content-Type'] = 'application/json'
  response.write(json.dumps({
    'status': 'OK',
    'result': result
  }, default=_default))
  return response

def failure(message, code='UNIDENTIFIED ERROR'):
  response = webapp2.Response()
  response.status = 400 # TODO(nbharadw) change this based on error
  response.headers['Content-Type'] = 'application/json'
  response.write(json.dumps({
    'status': 'ERROR',
    'code': code,
    'message': message,
  }, default=_default))
  return response

def abort(*args, **kwargs):
  raise FrameworkAbortError(failure(*args, **kwargs))
