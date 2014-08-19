# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit test for trees module."""
import unittest

from appengine.trooper_o_matic import trees
from appengine.trooper_o_matic.tests import testing_common

URLFETCH_RESPONSES = {
    ('https://chromium.googlesource.com/chromium/tools/build/+'
     '/master/scripts/slave/gatekeeper_trees.json?format=text'): {
         # pylint: disable=C0301
         'content': 'ewogICAgImJsaW5rIjogewogICAgICAgICJidWlsZC1kYiI6ICJibGlua19idWlsZF9kYi5qc29uIiwKICAgICAgICAibWFzdGVycyI6IFsKICAgICAgICAgICAgImh0dHBzOi8vYnVpbGQuY2hyb21pdW0ub3JnL3AvY2hyb21pdW0ud2Via2l0IgogICAgICAgIF0sCiAgICAgICAgIm9wZW4tdHJlZSI6IHRydWUsCiAgICAgICAgInBhc3N3b3JkLWZpbGUiOiAiLmJsaW5rX3N0YXR1c19wYXNzd29yZCIsCiAgICAgICAgInJldmlzaW9uLXByb3BlcnRpZXMiOiAiZ290X3JldmlzaW9uLGdvdF93ZWJraXRfcmV2aXNpb24iLAogICAgICAgICJzZXQtc3RhdHVzIjogdHJ1ZSwKICAgICAgICAic3RhdHVzLXVybCI6ICJodHRwczovL2JsaW5rLXN0YXR1cy5hcHBzcG90LmNvbSIsCiAgICAgICAgInRyYWNrLXJldmlzaW9ucyI6IHRydWUKICAgIH0sCiAgICAiY2hyb21pdW0iOiB7CiAgICAgICAgImJ1aWxkLWRiIjogIndhdGVyZmFsbF9idWlsZF9kYi5qc29uIiwKICAgICAgICAibWFzdGVycyI6IFsKICAgICAgICAgICAgImh0dHBzOi8vYnVpbGQuY2hyb21pdW0ub3JnL3AvY2hyb21pdW0iLAogICAgICAgICAgICAiaHR0cHM6Ly9idWlsZC5jaHJvbWl1bS5vcmcvcC9jaHJvbWl1bS5jaHJvbWUiLAogICAgICAgICAgICAiaHR0cHM6Ly9idWlsZC5jaHJvbWl1bS5vcmcvcC9jaHJvbWl1bS5jaHJvbWl1bW9zIiwKICAgICAgICAgICAgImh0dHBzOi8vYnVpbGQuY2hyb21pdW0ub3JnL3AvY2hyb21pdW0uZ3B1IiwKICAgICAgICAgICAgImh0dHBzOi8vYnVpbGQuY2hyb21pdW0ub3JnL3AvY2hyb21pdW0ubGludXgiLAogICAgICAgICAgICAiaHR0cHM6Ly9idWlsZC5jaHJvbWl1bS5vcmcvcC9jaHJvbWl1bS5tYWMiLAogICAgICAgICAgICAiaHR0cHM6Ly9idWlsZC5jaHJvbWl1bS5vcmcvcC9jaHJvbWl1bS5tZW1vcnkiLAogICAgICAgICAgICAiaHR0cHM6Ly9idWlsZC5jaHJvbWl1bS5vcmcvcC9jaHJvbWl1bS53aW4iCiAgICAgICAgXSwKICAgICAgICAib3Blbi10cmVlIjogdHJ1ZSwKICAgICAgICAicGFzc3dvcmQtZmlsZSI6ICIuc3RhdHVzX3Bhc3N3b3JkIiwKICAgICAgICAic2V0LXN0YXR1cyI6IHRydWUsCiAgICAgICAgInN0YXR1cy11cmwiOiAiaHR0cHM6Ly9jaHJvbWl1bS1zdGF0dXMuYXBwc3BvdC5jb20iLAogICAgICAgICJ0cmFjay1yZXZpc2lvbnMiOiB0cnVlCiAgICB9LAogICAgIm5vbi1jbG9zZXJzIjogewogICAgICAgICJtYXN0ZXJzIjogWwogICAgICAgICAgICAiaHR0cHM6Ly9idWlsZC5jaHJvbWl1bS5vcmcvcC9jaHJvbWl1bS5sa2dyIiwKICAgICAgICAgICAgImh0dHBzOi8vYnVpbGQuY2hyb21pdW0ub3JnL3AvY2hyb21pdW0ucGVyZiIsCiAgICAgICAgICAgICJodHRwczovL2J1aWxkLmNocm9taXVtLm9yZy9wL2NsaWVudC5saWJ2cHgiCiAgICAgICAgXQogICAgfQp9Cg==',
         'statuscode': 200,
     }
}


class TreesTest(unittest.TestCase):

  def setUp(self):
    testing_common.StubUrlfetch(URLFETCH_RESPONSES)

  def testTreesUrlFetch(self):
    masters = trees.GetMastersForTree('chromium')
    self.assertEqual(['chromium',
                      'chromium.chrome',
                      'chromium.chromiumos',
                      'chromium.gpu',
                      'chromium.linux',
                      'chromium.mac',
                      'chromium.memory',
                      'chromium.win'],
                     masters)


if __name__ == '__main__':
  unittest.main()
