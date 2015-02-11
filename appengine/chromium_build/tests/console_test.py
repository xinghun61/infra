#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import app

from tests import cb


class ConsoleTestCase(cb.CbTestCase):
  def test_console_handler(self):
    self.save_page(localpath='chromium/sheriff.js',
                   content='document.write(\'sheriff1\')')
    self.save_page(localpath='chromium/sheriff_webkit.js',
                   content='document.write(\'sheriff2\')')
    self.save_page(localpath='chromium/sheriff_memory.js',
                   content='document.write(\'sheriff3\')')
    self.save_page(localpath='chromium/sheriff_nacl.js',
                   content='document.write(\'sheriff4\')')
    self.save_page(localpath='chromium/sheriff_perf.js',
                   content='document.write(\'sheriff5\')')
    self.save_page(localpath='chromium/sheriff_cros_mtv.js',
                   content='document.write(\'sheriff6, sheriff7\')')
    self.save_page(localpath='chromium/sheriff_cros_nonmtv.js',
                   content='document.write(\'sheriff8\')')
    exp_console = self.read_file('exp_console.html')
    in_console = {'content': self.read_file('in_console.html')}
    act_console = app.console_handler(
        unquoted_localpath='chromium/console',
        remoteurl='http://build.chromium.org/p/chromium/console',
        page_data=in_console)['content']

    # Uncomment if deeper inspection is needed of the returned console.
    # This is also useful if changing the site layout and you need to
    # 'retrain' the test expectations.
    # self.write_file('exp_console.html', act_console)

    self.assertEquals(exp_console, act_console,
                      'Unexpected console output found')

  def test_console_handler_utf8(self):
    self.save_page(localpath='chromium/sheriff.js',
                   content='document.write(\'sheriff1\')')
    self.save_page(localpath='chromium/sheriff_webkit.js',
                   content='document.write(\'sheriff2\')')
    self.save_page(localpath='chromium/sheriff_memory.js',
                   content='document.write(\'sheriff3\')')
    self.save_page(localpath='chromium/sheriff_nacl.js',
                   content='document.write(\'sheriff4\')')
    self.save_page(localpath='chromium/sheriff_perf.js',
                   content='document.write(\'sheriff5\')')
    self.save_page(localpath='chromium/sheriff_cros_mtv.js',
                   content='document.write(\'sheriff6, sheriff7\')')
    self.save_page(localpath='chromium/sheriff_cros_nonmtv.js',
                   content='document.write(\'sheriff8\')')
    exp_console = self.read_file('exp_console.html')
    in_console = {'content': self.read_file('in_console.html')}
    act_console = app.console_handler(
        unquoted_localpath='chromium/console',
        remoteurl='http://build.chromium.org/p/chromium/console',
        page_data=in_console)['content']

    # Uncomment if deeper inspection is needed of the returned console.
    # This is also useful if changing the site layout and you need to
    # 'retrain' the test expectations.
    # self.write_file('exp_console.html', act_console)

    self.assertEquals(exp_console, act_console,
                      'Unexpected console output found')

  def test_parse_master(self):
    in_console = {'content': self.read_file('in_console.html')}
    app.parse_master(
        localpath='chromium/console',
        remoteurl='http://build.chromium.org/p/chromium/console',
        page_data=in_console)
    test_revision = '314671'
    rowdata = app.get_and_cache_rowdata('chromium/console/' + test_revision)
    summary = app.get_and_cache_pagedata('chromium/console/summary')['content']

    act_row = {}
    exp_row = {}
    for item in ['rev', 'name', 'status', 'comment']:
      # We only want to test specific values in rowdata, so we create a new
      # hash that has just those values.
      act_row[item] = rowdata[item]
      # Uncomment if deeper inspection is needed of the returned console.
      # This is also useful if changing the site layout and you need to
      # 'retrain' the test expectations.
      # self.write_file('exp_%s.html' % item,
      #                 act_row[item].encode('utf-8'))
      # self.write_file('exp_summary.html',
      #                 summary.encode('utf-8'))
      exp_row[item] = self.read_file('exp_%s.html' % item).decode('utf-8')
    exp_summary = self.read_file('exp_summary.html').decode('utf-8')
    self.assertEquals(exp_row, act_row, 'Unexpected row data found')
    self.assertEquals(exp_summary, summary, 'Unexpected build summary found')

  def test_parse_master_utf8(self):
    in_console = {'content': self.read_file('in_console.html')}
    app.parse_master(
        localpath='chromium/console',
        remoteurl='http://build.chromium.org/p/chromium/console',
        page_data=in_console)
    test_revision = '314921'
    rowdata = app.get_and_cache_rowdata('chromium/console/' + test_revision)
    summary = app.get_and_cache_pagedata('chromium/console/summary')['content']

    act_row = {}
    exp_row = {}
    for item in ['rev', 'name', 'status', 'comment']:
      # We only want to test specific values in rowdata, so we create a new
      # hash that has just those values.
      act_row[item] = rowdata[item]
      # Uncomment if deeper inspection is needed of the returned console.
      # This is also useful if changing the site layout and you need to
      # 'retrain' the test expectations.
      # self.write_file('exp_%s.html' % item,
      #                 act_row[item].encode('utf-8'))
      # self.write_file('exp_summary.html',
      #                 summary.encode('utf-8'))
      exp_row[item] = self.read_file('exp_%s.html' % item).decode('utf-8')
    exp_summary = self.read_file('exp_summary.html').decode('utf-8')

    self.assertEquals(exp_row, act_row, 'Unexpected row data found')
    self.assertEquals(exp_summary, summary, 'Unexpected build summary found')

  def test_console_merger(self):
    for master in ['linux', 'mac']:
      page_data = {'content': self.read_file('in_%s.html' % master)}
      app.parse_master(
          localpath='chromium.%s/console' % master,
          remoteurl='http://build.chromium.org/p/chromium.%s/console' % master,
          page_data=page_data)

    # Get the expected and real output, compare.
    app.console_merger(
        'chromium/console', '', {},
        masters_to_merge=[
            'chromium.linux',
            'chromium.mac',
        ],
        num_rows_to_merge=20)
    actual_console = app.get_and_cache_pagedata('chromium/console')['content']

    # Uncomment if deeper inspection is needed of the returned console.
    # import logging
    # logging.debug('foo')
    # self.write_file('exp_merged.html', actual_console)
    # import code
    # code.interact(local=locals())

    self.assertEquals(
        self.read_file('exp_merged.html').decode('utf-8'),
        actual_console, 'Unexpected console output found')

  def test_console_merger_splitrevs(self):
    for master in ['linux', 'mac']:
      page_data = {'content': self.read_file('in_%s.html' % master)}
      app.parse_master(
          localpath='chromium.%s/console' % master,
          remoteurl='http://build.chromium.org/p/chromium.%s/console' % master,
          page_data=page_data)

    # Get the expected and real output, compare.
    app.console_merger(
        'chromium/console', '', {},
        masters_to_merge=[
            'chromium.linux',
            'chromium.mac',
        ],
        num_rows_to_merge=20)
    act_merged = app.get_and_cache_pagedata('chromium/console')['content']

    # Uncomment if deeper inspection is needed of the returned console.
    # import logging
    # logging.debug('foo')
    # self.write_file('exp_merged.html', act_merged)
    # import code
    # code.interact(local=locals())

    self.assertEquals(self.read_file('exp_merged.html'), act_merged,
                      'Unexpected console output found')
