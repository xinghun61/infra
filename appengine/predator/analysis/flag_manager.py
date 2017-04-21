# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module handling flags while doing stream parsing.

``ParsingFlag`` has a name, a turn_on_condition function which returns a boolean
predicate and a boolean value. We say that a flag with the boolean value
``True`` is "on", and a flag with the boolean value ``False`` is "off".
The turn_on_condition function is used to check whether a flag should be turned
"on" while it is "off".

``FlagManager`` is a class for managing all the flags while doing stream
parsing. In order to be tracked during stream parsing, all flags must be
registered in ``FlagManager`` with a certain group (differentiate different
namespaces).

For example:


stacktrace = "blabla\nSUMMARY:\nblabla"
flag = ParsingFlag('after_summary_flag', lambda line: 'SUMMARY:' in line,
                   value=False)
flag_manager = FlagManager()
flag_manager.Register('stacktrace_group', flag)

for line in stacktrace.splitlines():
  flag_manager.ConditionallyTurnOnFlags(line)


The ``after_summary_flag`` will be turned on (set the value to True) when
parsing the second line, because the initial value of the flag is ``False`` and
the turn_on_condition function returns ``True`` for the second line.

The flag will stay "on", until ``flag.Off()`` is called to set the value to
``False`` explictly.
"""

from collections import defaultdict


class ParsingFlag(object):
  """Represents a flag in stream parsing.

  This object serves like a delegation to manipulate flag of object,
  turn_on_condition will be used to evaluate the flag value.
  """
  def __init__(self, name, turn_on_condition=None, value=False):
    """
    Args:
      name (str): Name of the flag.
      turn_on_condition (callable): The function takes a str line as input and
        returns a boolean value. When the flag is "off", this funtion can be
        called to check whether the flag should be turned on or not.
        Note, if the flag is "on", the return value of this function means "do
        nothing" and shouldn't affect the value of the flag.
      value (bool): Initial value of the flag.
    """
    self._name = name
    self._turn_on_condition = turn_on_condition or (lambda _: False)
    self._value = value

  @property
  def name(self):
    return self._name

  @property
  def value(self):
    return self._value

  def TurnOn(self):
    self._value = True

  def TurnOff(self):
    self._value = False

  def __nonzero__(self):
    return self._value

  __bool__ = __nonzero__

  def ConditionallyTurnOn(self, line):
    """When the flag is off, turns on it if turn_on_conditions met."""
    if not self._value and self._turn_on_condition(line):
      self.TurnOn()


class FlagManager(object):
  """A manager to track all the registered flags.

  FlagManager collects and manages flags based on group names. FlagManager takes
  care of manipulating flags during the stream parsing, including evaluating
  based on the turn_on_conditions of flags, and resetting flags.

  Note, flag manager only keeps distinct flags(with distinct flag name), and one
  flag cannot be registered with multiple groups.
  """

  def __init__(self):
    self.flag_groups = defaultdict(list)
    self.flags = {}

  def ClearFlags(self):
    """Deletes all the flags."""
    self.flag_groups = defaultdict(list)
    self.flags = {}

  def Register(self, group_name, flag):
    """Registers a flag with a group.

    Flags under the same group should have the same scope.
    For example, in stacktrace parsing, the scope of a flag like
    ``after_sumary_line`` is the whole stacktrace, so it should be under
    ``stacktrace_flags`` group, while the scope of
    ``callstack_top_frame_has_no_symbol`` is callstack, and it should be
    under ``callstack_flags`` group.
    """
    self.flag_groups[group_name].append(flag)
    self.flags[flag.name] = flag

  def GetAllFlags(self):
    """Returns all registered flags."""
    return self.flags.values()

  def GetGroupFlags(self, group_name):
    """Returns a certain group of flags."""
    return self.flag_groups.get(group_name, [])

  def ResetAllFlags(self):
    """Turns off all registered flags."""
    for flag in self.GetAllFlags():
      flag.TurnOff()

  def ResetGroupFlags(self, group_name):
    """Turns off a certain group of flags."""
    for flag in self.GetGroupFlags(group_name):
      flag.TurnOff()

  def ConditionallyTurnOnFlags(self, line):
    """Turns on "off" flags when turn_on_conditions are met."""
    for flag in self.GetAllFlags():
      flag.ConditionallyTurnOn(line)

  def Get(self, flag_name):
    """Gets the instance with flag_name."""
    return self.flags.get(flag_name)

  def TurnOn(self, flag_name):
    """Sets the instance with flag_name to True."""
    flag = self.flags.get(flag_name)
    if flag is None:
      return

    flag.TurnOn()

  def TurnOff(self, flag_name):
    """Sets the instance with flag_name to False."""
    flag = self.flags.get(flag_name)
    if flag is None:
      return

    flag.TurnOff()
