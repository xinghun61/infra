# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import requests
import sys


def extract_json_data(issue_num): # pragma: no cover
  json_data_url = "https://codereview.chromium.org/api/%s?messages=true" \
                                                    %str(issue_num)
  raw_data = requests.get(json_data_url)
  json_data = raw_data.json()
  return json_data


def contains_lgtm(json_data):
  for message in json_data["messages"]:
    if message["approval"]:
      return True
  return False


def contains_tbr(json_data):
  description = json_data["description"]
  return any(
        not line.strip().startswith('>') and re.search(r'^TBR=.*', line)
        for line in description.splitlines())
