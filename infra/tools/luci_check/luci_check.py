# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Testable functions for Luci_check."""

import base64
import requests

from google.protobuf import text_format

import infra.tools.luci_check.project_pb2 as proj


MASTER_URL = 'https://chrome-build-extract.appspot.com/get_master/'


class Checker(object):
  def __init__(self, console_def_url):
    self.console_def_url = console_def_url

  @staticmethod
  def get_master(name):  # pragma: no cover
    url = MASTER_URL + name
    r = requests.get(url)
    if r.status_code == 401:
      return False
    return r.json()

  def get_console_def(self):  # pragma: no cover
    r = requests.get(self.console_def_url + '?format=TEXT')
    return text_format.Parse(base64.b64decode(r.text), proj.Project())

  def check(self):
    console_def = self.get_console_def()
    ok = True
    for console in console_def.consoles:
      print 'Processing %s...' % console.id,
      master = self.get_master(console.id)
      if master is False:
        print 'Not found'
        continue
      luci_cfg_builders = set(
          builder.name[0].split('/')[2] for builder in console.builders)
      buildbot_builders = set(master['builders'].keys())
      minus = luci_cfg_builders - buildbot_builders
      plus = buildbot_builders - luci_cfg_builders
      if plus or minus:
        print 'DIFF FOUND'
        for builder in plus:
          print '  + %s' % builder
        for builder in minus:
          print '  - %s' % builder
        ok = False
      else:
        print 'OK'
    return 0 if ok else 1

