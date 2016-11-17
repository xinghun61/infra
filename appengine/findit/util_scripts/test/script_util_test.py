# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import subprocess

from testing_utils import testing

import script_util


class ScriptUtilTest(testing.AppengineTestCase):

  # TODO(katesonia): Figure out a good way to work around cache.
  def testGetLocalGitCommandOutput(self):
    class _MockProcess(object):
      def __init__(self, command, *_):
        self.command = command

      def communicate(self, *_):
        return self.command, 'error'

      @property
      def returncode(self):
        return 1 if self.command == 'dummy' else 0

    self.mock(subprocess, 'Popen', lambda command, **_: _MockProcess(command))
    output = script_util.GetCommandOutput('command')
    self.assertEqual(output, 'command')

    self.assertRaisesRegexp(Exception, 'Error running command dummy: error',
                            script_util.GetCommandOutput, 'dummy')
