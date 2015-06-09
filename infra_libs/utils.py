# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json


def read_json_as_utf8(filename=None, text=None):
  """Read and deserialize a json file or string.

  This function is different from json.load and json.loads in that it
  returns utf8-encoded string for keys and values instead of unicode.

  Args:
    filename (str): path of a file to parse
    text (str): json string to parse

  ``filename`` and ``text`` are mutually exclusive. ValueError is raised if
  both are provided.
  """

  if filename is not None and text is not None:
    raise ValueError('Only one of "filename" and "text" can be provided at '
                     'the same time')

  if filename is None and text is None:
    raise ValueError('One of "filename" and "text" must be provided')

  def to_utf8(obj):
    if isinstance(obj, dict):
      return {to_utf8(key): to_utf8(value) for key, value in obj.iteritems()}
    if isinstance(obj, list):
      return [to_utf8(item) for item in obj]
    if isinstance(obj, unicode):
      return obj.encode('utf-8')
    return obj

  if filename:
    with open(filename, 'rb') as f:
      obj = json.load(f)
  else:
    obj = json.loads(text)

  return to_utf8(obj)
