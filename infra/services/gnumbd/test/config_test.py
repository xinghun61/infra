# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from infra.services.gnumbd.support import config_ref, git
from infra.services.gnumbd.test import git_test

class TestConfigRef(git_test.TestBasis):
  def writeConfig(self, config_data):
    ref = 'refs/metaconfig'
    def inner():
      g = self.repo.git
      if g('rev-parse', ref).stdout.strip() != ref:
        g('checkout', ref)
      else:
        g('checkout', '--orphan', 'config')
      g('rm', '-rf', '.')
      with open('config.json', 'w') as f:
        f.write(config_data)
      g('add', 'config.json')
      self.repo.git_commit('a bad config file')
      g('update-ref', ref, 'HEAD')
    self.repo.run(inner)

  def testNonExist(self):
    r = self.mkRepo()
    c = config_ref.ConfigRef(git.Ref(r, 'refs/metaconfig'))
    self.assertEqual(c.current, c.DEFAULTS)
    self.assertEqual(c['interval'], c.DEFAULTS['interval'])

  def testExistsBad(self):
    self.writeConfig("not valid config")
    r = self.mkRepo()
    c = config_ref.ConfigRef(git.Ref(r, 'refs/metaconfig'))
    c.evaluate()
    self.assertEqual(c.current, c.DEFAULTS)

    self.writeConfig("[]")
    self.capture_stdio(r.run, 'fetch')
    c.evaluate()
    self.assertEqual(c.current, c.DEFAULTS)

  def testExistsGood(self):
    self.writeConfig('{"interval": 100}')
    r = self.mkRepo()
    c = config_ref.ConfigRef(git.Ref(r, 'refs/metaconfig'))
    self.assertAlmostEqual(c['interval'], 100.0)

    self.writeConfig('{"interval": "cat"}')
    self.capture_stdio(r.run, 'fetch')
    c.evaluate()
    self.assertAlmostEqual(c['interval'], 100.0)
