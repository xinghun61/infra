# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Customized field object for working with issue tracker fields."""

class CustomizedField(object):
  OPERATOR_ADD = 'add'
  OPERATOR_REMOVE = 'remove'

  @staticmethod
  def ConvertFromDict(obj):
    """Converts a dict representatin to a customized field"""
    if type(obj) is CustomizedField:
      return obj
    assert 'fieldName' in obj
    assert 'fieldValue' in obj

    return CustomizedField(obj['fieldName'], obj['fieldValue'])

  def __init__(self, field_name, field_value):
    """Models a customized field in monorail

    Args:
      field_name (string): Key for the customized field
      field_value (string): Value for the customized field
      operator (string): One of (add, clear, remove) to indicate
        what the operation should be.

    Returns:
      (CustomizedField) A constructed CustomizedField.
    """
    self.field_name = field_name
    self.field_value = field_value
    self.operator = CustomizedField.OPERATOR_ADD
    self.derived = False  # Derived customized fields aren't supported.

  def to_dict(self):
    """Gets python dict suitable for a request."""
    return {
      'derived': self.derived,
      'fieldName': self.field_name,
      'fieldValue': self.field_value,
      'operator': self.operator,
    }
