# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from analysis.flag_manager import ParsingFlag
from analysis.flag_manager import FlagManager


class ParsingFlagTest(unittest.TestCase):

  def setUp(self):
    super(ParsingFlagTest, self).setUp()
    self.flag = ParsingFlag('test_flag', lambda line: 'turn on flag' in line,
                            value=False)

  def testParsingFlagNameProperty(self):
    """Tests the ``name`` property of ``ParsingFlag``"""
    self.assertEqual(self.flag.name, 'test_flag')

  def testParsingFlagValueProperty(self):
    """Tests the ``value`` property of ``ParsingFlag``"""
    self.assertFalse(self.flag.value)
    self.flag.TurnOn()
    self.assertTrue(self.flag.value)
    self.assertTrue(bool(self.flag))
    self.flag.TurnOff()
    self.assertFalse(self.flag.value)
    self.assertFalse(bool(self.flag))

  def testConditionallyTurnOn(self):
    """Tests that ``ConditionallyTurnOn`` turns on flag if conditions met."""
    self.assertFalse(bool(self.flag))
    self.flag.ConditionallyTurnOn('line: turn on flag')
    self.assertTrue(bool(self.flag))


class FlagManagerTest(unittest.TestCase):

  def setUp(self):
    super(FlagManagerTest, self).setUp()
    self.flag_manager = FlagManager()

  def testClearFlags(self):
    """Tests that ``ClearFlags`` deletes all flags."""
    self.flag_manager.Register('test', ParsingFlag('test_flag', value=True))
    self.assertEqual(len(self.flag_manager.flags), 1)
    self.flag_manager.ClearFlags()
    self.assertEqual(len(self.flag_manager.flags), 0)

  def testRegister(self):
    """Tests that ``Register`` add new flags with a certain group."""
    self.flag_manager.Register('dummy', ParsingFlag('dummy_flag', value=True))
    self.assertEqual(len(self.flag_manager.flag_groups['dummy']), 1)
    self.assertEqual(len(self.flag_manager.flags), 1)

  def testGetAllFlags(self):
    """Tests that ``GetAllFlags`` returns all registered flags."""
    flag1 = ParsingFlag('group_flag1', value=True)
    flag2 = ParsingFlag('group_flag2', value=True)
    self.flag_manager.Register('group1', flag1)
    self.flag_manager.Register('group2', flag2)
    self.assertListEqual(self.flag_manager.GetAllFlags(), [flag1, flag2])

  def testGetGroupFlags(self):
    """Tests that ``GetGroupFlags`` returns all flags with a certain group."""
    flag1 = ParsingFlag('group_flag1', value=True)
    flag2 = ParsingFlag('group_flag2', value=True)
    self.flag_manager.Register('group1', flag1)
    self.flag_manager.Register('group2', flag2)
    self.assertListEqual(self.flag_manager.GetGroupFlags('group1'), [flag1])
    self.assertListEqual(self.flag_manager.GetGroupFlags('group2'), [flag2])

  def testResetAllFlags(self):
    """Tests that ``ResetAllFlags`` turns off all the flags."""
    self.flag_manager.Register('group', ParsingFlag('dummy_flag1', value=True))
    self.flag_manager.Register('group', ParsingFlag('dummy_flag2', value=True))
    self.flag_manager.ResetAllFlags()
    for flag in self.flag_manager.GetAllFlags():
      self.assertFalse(flag.value)

  def testResetGroupFlags(self):
    """Tests that ``ResetGroupFlags`` turns off flags with a certain group."""
    self.flag_manager.Register('group1', ParsingFlag('dummy_flag1', value=True))
    self.flag_manager.Register('group2', ParsingFlag('dummy_flag2', value=True))
    self.flag_manager.ResetGroupFlags('group1')
    self.assertFalse(self.flag_manager.Get('dummy_flag1'))
    self.assertTrue(self.flag_manager.Get('dummy_flag2'))

  def testConditionallyTurnOnFlags(self):
    """Tests turning on flags if their conditions met."""
    self.flag_manager.Register(
        'group',
        ParsingFlag('flag1',
                    turn_on_condition=lambda line: 'flag1 marker' in line,
                    value=False))
    self.flag_manager.Register(
        'group',
        ParsingFlag('flag2',
                    turn_on_condition=lambda line: 'flag2 marker' in line,
                    value=False))
    line = 'line: flag1 marker flag2 marker'
    self.flag_manager.ConditionallyTurnOnFlags(line)
    self.assertTrue(bool(self.flag_manager.Get('flag1')))
    self.assertTrue(bool(self.flag_manager.Get('flag2')))

  def testDoNothingWhenConditionsNotMet(self):
    """Tests doing nothing if flag's condition is not met."""
    self.flag_manager.Register(
        'group',
        ParsingFlag('flag',
                    turn_on_condition=lambda line: 'flag marker' in line,
                    value=False))
    line = 'dummy line'
    self.flag_manager.ConditionallyTurnOnFlags(line)
    self.assertFalse(bool(self.flag_manager.Get('flag')))

  def testDoNothingWhenThereIsNoCondition(self):
    """Tests doing nothing if flag has empty condition."""
    self.flag_manager.Register(
        'group',
        ParsingFlag('flag', value=False))
    line = 'dummy line'
    self.flag_manager.ConditionallyTurnOnFlags(line)
    self.assertFalse(bool(self.flag_manager.Get('flag')))

  def testSettingFlag(self):
    """Tests using ``TurnOn`` and ``TurnOff`` to set flags."""
    self.flag_manager.Register('group', ParsingFlag('flag', value=False))
    self.flag_manager.TurnOn('flag')
    self.flag_manager.TurnOn('dummy_flag')
    self.assertTrue(self.flag_manager.Get('flag'))
    self.flag_manager.TurnOff('flag')
    self.flag_manager.TurnOff('dummy_flag')
    self.assertFalse(self.flag_manager.Get('flag'))
