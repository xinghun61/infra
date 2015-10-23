# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import json
import unittest

from infra.libs.gitiles import gitiles
from infra.tools.cros_pin import pinfile

import mock

def h(v):
  return hashlib.sha1(v).hexdigest()


class TestPinfile(unittest.TestCase):

  _CFG = pinfile.Config('TestConfig',
      ('repository', 'path'),
      ('path', 'to', 'pins.json'),
      ('mywaterfall',))

  _MOCK_PINFILE = '{"test": "foo", "release": "bar"}'
  _CHROMITE_REPO = 'https://example.com/fake'

  def setUp(self):
    self._patchers = []
    self._pinfile = self._MOCK_PINFILE

    self._open = mock.mock_open(read_data=self._pinfile)

    self._write_out = ''
    def fake_write(data):
      self._write_out = self._write_out + data
    self._open().write = mock.Mock(side_effect=fake_write)

    for patchme, m in (
        ('__builtin__.open', self._open),
        ('infra.libs.gitiles.gitiles.Repository', mock.DEFAULT),
        ):
      p = mock.patch(patchme, m)
      self._patchers.append(p)

    for p in self._patchers:
      p.start()

    self._gitiles = gitiles.Repository(self._CHROMITE_REPO)
    self._editor = pinfile.Editor('checkout_path', self._gitiles)
    self._f = self._editor.load(self._CFG)

  def tearDown(self):
    for p in reversed(self._patchers):
      p.stop()

  def _assertWroteJSON(self, **kw):
    self.assertEqual(json.loads(self._write_out), kw)

  def testUpdatesPinSuccessfully(self):
    pu = self._f.update('test', version=h('baz'))
    self.assertEqual(pu, pinfile.PinUpdate(name='test', fr='foo', to=h('baz')))
    self._assertWroteJSON(test=h('baz'), release='bar')

  def testUpdateIsNoneForSameValue(self):
    self._editor._validate = False
    pu = self._f.update('test', version='foo')
    self.assertIsNone(pu)

  def testUpdatesPinToToTSuccessfully(self):
    self._editor._gitiles.ref_info.return_value = {
        'commit': 'baz',
    }
    pu = self._f.update('test')
    self.assertEqual(pu, pinfile.PinUpdate(name='test', fr='foo', to='baz'))
    self._assertWroteJSON(test='baz', release='bar')

  def testUpdateRejectsNewPinWithoutCreate(self):
    self.assertRaises(pinfile.ReadOnlyError,
        self._f.update, 'newpin', create=False, version=h('baz'))

  def testUpdateWithInvalidCommitHash(self):
    self._editor._gitiles.ref_info.side_effect = gitiles.GitilesError
    self.assertRaises(pinfile.InvalidPinError,
        self._f.update, 'test', version='baz')

  def testUpdateWithInvalidGitilesCommit(self):
    self._editor._gitiles.ref_info.side_effect = gitiles.GitilesError
    self.assertRaises(pinfile.InvalidPinError,
        self._f.update, 'test', version=h('baz'))

  def testRemoveDeletesPin(self):
    pu = self._f.remove('test')
    self.assertEqual(pu, pinfile.PinUpdate(name='test', fr='foo', to=None))
    self._assertWroteJSON(release='bar')

    pu = self._f.remove('asdf')
    self.assertIsNone(pu)
    self._assertWroteJSON(release='bar')

  def testIterPins(self):
    self.assertEqual(set(self._f.iterpins()),
                     set([('test', 'foo'), ('release', 'bar')]))

  def testLoad(self):
    m = mock.mock_open(read_data='{"foo": "bar"}')
    with mock.patch('__builtin__.open', m):
      self.assertEqual(set(self._f.iterpins()),
                       set([('foo', 'bar')]))

