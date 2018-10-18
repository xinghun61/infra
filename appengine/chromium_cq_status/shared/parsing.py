# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json

from shared.config import (
  DEFAULT_QUERY_SIZE,
  MAXIMUM_QUERY_SIZE,
  RIETVELD_TIMESTAMP_FORMATS,
)
from shared.utils import to_unix_timestamp

def parse_timestamp(value):
  if not value:
    return None
  return datetime.utcfromtimestamp(float(value))

def parse_record_key(value):
  try:
    long(value)
  except ValueError:
    return value or None
  raise ValueError('Numeric key values are reserved for keyless entries')

def parse_cqstats_key(value):
  if not value:
    return None
  return long(value)

def parse_string(value):
  return value or ''

def parse_strings(value):
  if not value:
    return []
  return value.split(',')

def parse_fields(value):
  if not value:
    return {}
  fields_json = json.loads(value)
  if not isinstance(fields_json, dict):
    raise ValueError('fields parameter must be JSON dictionary')
  return fields_json

def parse_non_negative_integer(value):
  n = int(value)
  if n < 0:
    raise ValueError('Non negative integer expected')
  return n

def parse_cursor(value):
  return value or None

def parse_query_count(value):
  if not value:
    return DEFAULT_QUERY_SIZE
  count = parse_non_negative_integer(value)
  return min(count, MAXIMUM_QUERY_SIZE)

def use_default(parser, default_value):
  def new_parser(value):
    if not value:
      return default_value
    return parser(value)
  return new_parser

def parse_request(request, validators):
  unknown_parameters = set(request.arguments()) - set(validators.keys())
  if unknown_parameters:
    raise ValueError('Unexpected parameters: %s' % ' '.join(unknown_parameters))
  data = {}
  for parameter, validator in validators.items():
    data[parameter] = validator(request.get(parameter))
  return data

def parse_url_tags(url_tags):
  if not url_tags:
    return []
  return filter(len, url_tags.split('/'))

def parse_rietveld_timestamp(timestamp_string):
  """Converts a Rietveld timestamp into a unix timestamp."""
  for rietveld_ts_format in RIETVELD_TIMESTAMP_FORMATS:
    try:
      return to_unix_timestamp(
          datetime.strptime(timestamp_string, rietveld_ts_format))
    except ValueError:
      pass
  return None
