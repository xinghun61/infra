# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json

def parse_timestamp(value): # pragma: no cover
  if not value:
    return None
  return datetime.utcfromtimestamp(float(value))

def parse_key(value): # pragma: no cover
  try:
    long(value)
  except ValueError:
    return value or None
  raise ValueError('Numeric key values are reserved for keyless entries')

def parse_tags(value): # pragma: no cover
  if not value:
    return []
  return value.split(',')

def parse_fields(value): # pragma: no cover
  if not value:
    return {}
  fields_json = json.loads(value)
  if type(fields_json) != dict:
    raise ValueError('fields parameter must be JSON dictionary')
  return fields_json

def parse_non_negative_integer(value): # pragma: no cover
  n = int(value)
  if n < 0:
    raise ValueError('Non negative integer expected')
  return n

def parse_cursor(value): # pragma: no cover
  return value or None

def use_default(parser, default_value): # pragma: no cover
  def new_parser(value):
    if not value:
      return default_value
    return parser(value)
  return new_parser

def parse_request(request, validators): # pragma: no cover
  unknown_parameters = set(request.arguments()) - set(validators.keys())
  if unknown_parameters:
    raise ValueError('Unexpected parameters: %s' % ' '.join(unknown_parameters))
  data = {}
  for parameter, validator in validators.items():
    data[parameter] = validator(request.get(parameter))
  return data

def parse_url_tags(url_tags): # pragma: no cover
  if not url_tags:
    return []
  return filter(len, url_tags.split('/'))
