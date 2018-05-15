# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Testable functions for Luci_check."""

import base64
import datetime
import json
import os
import requests
import zlib

from google.protobuf import text_format

import infra.tools.luci_check.project_pb2 as proj


GET_MASTER_URL = (
    'https://ci.chromium.org/prpc/milo.Buildbot/GetCompressedMasterJSON')


class Checker(object):
  def __init__(self, console_def_url, masters):
    self.console_def_url = console_def_url
    self.masters = masters
    self.master_data = {}

  @staticmethod
  def get_master(name):  # pragma: no cover
    print 'Loading %s from Milo' % name
    headers = {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    }
    data = json.dumps({
        'name': name,
        'noEmulation': True,
        'excludeDeprecated': False,
    })
    r = requests.post(GET_MASTER_URL, data=data, headers=headers)
    if r.status_code == 401:
      return False
    o = json.loads(r.content[4:])
    data = zlib.decompress(o['data'].decode('base64'), zlib.MAX_WBITS | 16)
    return json.loads(data)

  def get_console_def(self):  # pragma: no cover
    r = requests.get(self.console_def_url + '?format=TEXT')
    return text_format.Parse(base64.b64decode(r.text), proj.Project())

  @staticmethod
  def output_luci_milo(console_def):
    # TODO(hinoka): This should probably go in results json, or a separate
    #               logdog stream.
    print '============='
    print 'luci-milo.cfg'
    print '============='
    print 'logo_url: "%s"' % console_def.logo_url
    print
    for header in console_def.headers:
      print 'headers {'
      print '  id: "%s"' % header.id  # Move ID up top.
      header.id = ""
      for line in text_format.MessageToString(
          header, as_utf8=True, use_index_order=False).split('\n'):
        if line:
          print '  ' + line
      print '}'
      print
    for console in console_def.consoles:
      print 'consoles {'
      print '  header_id: "%s"' % console.header_id
      console.header_id = ""
      for line in text_format.MessageToString(
          console, as_utf8=True).split('\n'):
        if line:
          print '  ' + line
      print '}'
      print
    print '================='
    print 'end luci-milo.cfg'
    print '================='

  def check(self):
    for name, bucket, _ in self.masters:
      data = self.get_master(name)
      data['bucket'] = bucket
      self.master_data[name] = data

    console_def = self.get_console_def()
    original_console_def = console_def.__deepcopy__()
    for console in console_def.consoles:
      print 'Processing %s...' % console.id,
      master = self.master_data.get(console.id)
      if not master:  # TODO(hinoka): Process the main console.
        print 'Not found'
        continue

      luci_cfg_builders = set(
          builder.name[0].split('/')[2] for builder in console.builders)
      modified = datetime.datetime.strptime(
          master['Modified'], '%Y-%m-%dT%H:%M:%S.%fZ')
      buildbot_builders = set()
      if modified > datetime.datetime.now() - datetime.timedelta(hours=1):
        # Only look at masters that have not been turned down.
        # Turned down masters have no builders.
        buildbot_builders = set(master['builders'].keys())
      plus = buildbot_builders - luci_cfg_builders

      # Add in all the new builders.
      for builder in plus:
        new_builder = console.builders.add()
        new_builder.name.append('buildbot/%s/%s' % (console.id, builder))

      # For CI, make sure that:
      # * All buildbot builders exist in luci-milo.cfg.
      # * All buildbot builders have their luci builders next to them.
      # * If a buildbot builder was deleted, remove it from luci-milo.cfg.
      if 'tryserver' not in console.id:
        for builder in console.builders:
          if (len(builder.name) != 2
              and not builder.name[0].startswith('buildbucket')):
            name = builder.name[0].split('/')[2]
            builder.name.append('buildbucket/%s/%s' % (master['bucket'], name))

          # Remove buildbot variant if the buildbot builder was deleted.
          if len(builder.name) == 2 and builder.name[0].startswith('buildbot'):
            name = builder.name[0].split('/')[2]
            if name not in master['builders']:
              del builder.name[0]
      print 'Ok'

    rc = 0
    if console_def != original_console_def:
      print 'Found diffs!'
      rc = 1
    self.output_luci_milo(console_def)  # Print new config file to output.
    return rc
