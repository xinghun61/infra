# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import json
import os
import shutil
import tempfile
import unittest

from infra.libs.gitiles import gitiles
from infra.tools.cros_pin import pinfile
from infra.tools.cros_pin.logger import LOGGER

import mock

def h(v):
  return hashlib.sha1(v).hexdigest()


class TestPinfile(unittest.TestCase):

  _CFG = pinfile.Config('TestConfig',
      ('repository', 'path'),
      ('path', 'to', 'pins.json'),
      ('mywaterfall',))

  _CHROMITE_REPO = 'https://example.com/fake'

  def setUp(self):
    self._patchers = []
    for patchme in (
        'infra.libs.gitiles.gitiles.Repository',
        'infra.tools.cros_pin.pinfile.Editor.File.load',
        'infra.tools.cros_pin.pinfile.Editor.File.save',
        ):
      p = mock.patch(patchme)
      self._patchers.append(p)

    for p in self._patchers:
      p.start()

    self._gitiles = gitiles.Repository(self._CHROMITE_REPO)
    self._editor = pinfile.Editor('checkout_path', self._gitiles)
    self._f = self._editor.load(self._CFG)

  def tearDown(self):
    for p in reversed(self._patchers):
      p.stop()

  def testUpdatesPinSuccessfully(self):
    self._f.load.return_value = {'test': 'foo', 'release': 'bar'}
    pu = self._f.update('test', version=h('baz'))
    self.assertEqual(pu, pinfile.PinUpdate(name='test', fr='foo', to=h('baz')))
    self._f.save.assert_called_with(test=h('baz'), release='bar')

  def testUpdateIsNoneForSameValue(self):
    self._f.load.return_value = {'test': 'foo', 'release': 'bar'}
    self._editor._validate = False
    pu = self._f.update('test', version='foo')
    self.assertIsNone(pu)
    self._f.save.assert_not_called()

  def testUpdatesPinToToTSuccessfully(self):
    self._f.load.return_value = {'test': 'foo', 'release': 'bar'}
    self._editor._validate = False
    self._editor._gitiles.ref_info.return_value = {
        'commit': 'baz',
    }
    pu = self._f.update('test')
    self.assertEqual(pu, pinfile.PinUpdate(name='test', fr='foo', to='baz'))
    self._f.save.assert_called_with(test='baz', release='bar')

  def testUpdateRejectsNewPinWithoutCreate(self):
    self._f.load.return_value = {}
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
    self._f.load.return_value = {'test': 'foo', 'release': 'bar'}
    pu = self._f.remove('test')
    self.assertEqual(pu, pinfile.PinUpdate(name='test', fr='foo', to=None))
    self._f.save.assert_called_with(release='bar')

    self._f.load.return_value = {'release': 'bar'}
    pu = self._f.remove('asdf')
    self.assertIsNone(pu)
    self._f.save.assert_not_called()

  def testIterPins(self):
    self._f.load.return_value = {'test': 'foo', 'release': 'bar'}
    self.assertEqual(set(self._f.iterpins()),
                     set([('test', 'foo'), ('release', 'bar')]))


class TestPinfileIO(unittest.TestCase):

  def setUp(self):
    self._dir = tempfile.mkdtemp()

    self._f = pinfile.Editor('fakepath', None).load(TestPinfile._CFG)
    self._f._path = os.path.join(self._dir, 'pinfile.json')

  def tearDown(self):
    shutil.rmtree(self._dir)

  def testLoadSave(self):
    self._f.save(foo='bar')
    self.assertEqual(self._f.load(), {'foo': 'bar'})
