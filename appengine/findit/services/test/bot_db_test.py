# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json

import cloudstorage as gcs
import mock

from waterfall.test import wf_testcase

from services import bot_db

VALID_BOT_DB = json.dumps([[
    'master1', {
        'builders': {
            'builder1': {
                'bot_type': 'builder',
                'testing': {
                    'platform': 'platform1'
                }
            },
            'builder2': {
                'bot_type': 'tester',
                'testing': {
                    'platform': 'platform2'
                }
            }
        }
    }
], [
    'master2', {
        'builders': {
            'builder3': {
                'bot_type': 'builder',
                'testing': {
                    'platform': 'platform2'
                }
            },
            'builder4': {
                'bot_type': 'tester',
                'testing': {
                    'platform': 'platform1'
                }
            }
        }
    }
]])


class BotDBTestCase(wf_testcase.WaterfallTestCase):

  class mockOpenFile(object):

    def __init__(self, content, exception=None):
      self._content = content
      self._exception = exception

    def read(self):
      if isinstance(self._exception, Exception):
        # pylint: disable=raising-bad-type
        raise self._exception
      return self._content

  @mock.patch.object(gcs, 'open', return_value=mockOpenFile(VALID_BOT_DB))
  def testBotDB(self, _):
    self.assertEquals(
        set([('master1', 'builder1'), ('master1', 'builder2'),
             ('master2', 'builder3'), ('master2', 'builder4')]),
        set(bot_db.GetBuilders()))
    self.assertEquals(
        set([('master1', 'builder1'), ('master1', 'builder2')]),
        set(bot_db.GetBuilders(['master1'])))
    self.assertEquals(
        set([('master1', 'builder1'), ('master2', 'builder3')]),
        set(bot_db.GetBuilders(bot_type_filter=['builder'])))
    self.assertEquals(
        set([('master1', 'builder1'), ('master2', 'builder4')]),
        set(bot_db.GetBuilders(platform_filter=['platform1'])))

  @mock.patch.object(
      gcs,
      'open',
      return_value=mockOpenFile(None, exception=gcs.Error('gcs is down')))
  def testBotDBException(self, _):
    with self.assertRaises(bot_db.BotDBException):
      _ = bot_db.GetBuilders(['master1'])
