# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from infra.libs.git2 import config_ref

from infra.libs.git2.test import test_util

META_REF = 'refs/metaconfig'

class ExampleRef(config_ref.ConfigRef):
  CONVERT = {
    'interval': lambda self, val: float(val),
    'pending_tag_prefix': lambda self, val: str(val),
    'pending_ref_prefix': lambda self, val: str(val),
    'enabled_refglobs': lambda self, val: map(str, list(val)),
  }
  DEFAULTS = {
    'interval': 5.0,
    'pending_tag_prefix': 'refs/pending-tags',
    'pending_ref_prefix': 'refs/pending',
    'enabled_refglobs': [],
  }
  REF = META_REF


class TestConfigRef(test_util.TestBasis):
  def writeConfig(self, config_data):
    def inner():
      g = self.repo.git
      if g('rev-parse', META_REF).stdout.strip() != META_REF:
        g('checkout', META_REF)
      else:
        g('checkout', '--orphan', 'config')
      g('rm', '-rf', '.')
      with open('config.json', 'w') as f:
        f.write(config_data)
      g('add', 'config.json')
      self.repo.git_commit('a bad config file')
      g('update-ref', META_REF, 'HEAD')
    self.repo.run(inner)

  def testNonExist(self):
    r = self.mkRepo()
    c = ExampleRef(r)
    self.assertEqual(c.current, c.DEFAULTS)
    self.assertEqual(c['interval'], c.DEFAULTS['interval'])

  def testExistsBad(self):
    self.writeConfig("not valid config")
    r = self.mkRepo()
    c = ExampleRef(r)
    c.evaluate()
    self.assertEqual(c.current, c.DEFAULTS)

    self.writeConfig("[]")
    self.capture_stdio(r.run, 'fetch')
    c.evaluate()
    self.assertEqual(c.current, c.DEFAULTS)

  def testExistsGood(self):
    self.writeConfig('{"interval": 100}')
    r = self.mkRepo()
    c = ExampleRef(r)
    self.assertAlmostEqual(c['interval'], 100.0)

    self.writeConfig('{"interval": "cat"}')
    self.capture_stdio(r.run, 'fetch')
    c.evaluate()
    self.assertAlmostEqual(c['interval'], 100.0)
