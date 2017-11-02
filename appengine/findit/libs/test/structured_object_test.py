# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from libs import structured_object


class _ObjectA(structured_object.StructuredObject):  # pragma: no cover.
  v = int
  _unused = 2

  def __init__(self, *args, **kwargs):
    super(_ObjectA, self).__init__(*args, **kwargs)
    self._private_attribute = 10

  @property
  def unused(self):
    return 4


class _ObjectB(structured_object.StructuredObject):
  v = dict
  a = _ObjectA


class _DictOfObjectA(structured_object.TypedDict):
  value_type = _ObjectA


class _DictOfInt(structured_object.TypedDict):
  # This is just for testing purpose. In practice we should use dict directly.
  value_type = int


class _ListOfObjectA(structured_object.TypedList):
  element_type = _ObjectA


class _ListOfStr(structured_object.TypedList):
  # This is just for testing purpose. In practice we should use list directly.
  element_type = str


class _Future(object):
  pass


class SerilizableObjectTest(unittest.TestCase):

  def testAttributeCached(self):
    self.assertFalse(hasattr(_ObjectA, '_dynamic_definitions'))
    attributes = _ObjectA._GetDefinedAttributes()
    expected_attributes = {'v': int}
    self.assertDictEqual(expected_attributes, attributes)
    self.assertTrue(hasattr(_ObjectA, '_dynamic_definitions'))
    cached_attributes = _ObjectA._dynamic_definitions
    self.assertDictEqual(expected_attributes, cached_attributes)
    attributes = _ObjectA._GetDefinedAttributes()
    self.assertTrue(attributes is cached_attributes)

  def testToDict(self):
    obj_a = _ObjectA()
    obj_a.v = 1
    obj_b = _ObjectB()
    obj_b.v = {'key': 'value'}
    obj_b.a = obj_a
    data = obj_b.ToDict()
    expected_data = {'a': {'v': 1}, 'v': {'key': 'value'}}
    self.assertDictEqual(expected_data, data)

  def testToDictForNoneValue(self):
    obj_a = _ObjectA(v=None)
    self.assertDictEqual({'v': None}, obj_a.ToDict())

  def testFromDict(self):
    data = {'a': {'v': 1}, 'v': {'key': 'value'}}
    obj_b = _ObjectB.FromDict(data)
    self.assertDictEqual({'key': 'value'}, obj_b.v)
    self.assertEqual(1, obj_b.a.v)

  def testFromDictAssertionOnList(self):
    with self.assertRaises(AssertionError):
      _ObjectA.FromDict(['v'])

  def testFromDictAssertionOnUndefinedAttribute(self):
    with self.assertRaises(AssertionError):
      _ObjectA.FromDict({'undefined': 1})

  def testFromDictAssertionOnMissingAttributeValue(self):
    obj_a = _ObjectA.FromDict({})
    self.assertIsNone(obj_a.v)

  def testNotEqualForDifferentObjectType(self):
    obj_a = _ObjectA(v=1)
    self.assertNotEqual(obj_a, 'not a string object')

  def testNotEqualForAttributeValue(self):
    obj_a1 = _ObjectA(v=1)
    obj_a2 = _ObjectA(v=3)
    self.assertNotEqual(obj_a1, obj_a2)

  def testEqualForSameValues(self):
    data = {'a': {'v': 1}, 'v': {'key': 'value'}}
    obj_b1 = _ObjectB.FromDict(data)
    obj_b2 = _ObjectB(v={'key': 'value'}, a=_ObjectA(v=1))
    self.assertEqual(obj_b1, obj_b2)

  def testMultipeInstanceOfTheSameClass(self):
    obj_a1 = _ObjectA()
    obj_a1.v = 3
    obj_a2 = _ObjectA()
    obj_a2.v = 5
    self.assertEqual(3, obj_a1.v)
    self.assertEqual(5, obj_a2.v)

  def testSettingPrivateAttribute(self):
    obj_a = _ObjectA()
    obj_a._private_attribute = 30
    self.assertEqual(30, obj_a._private_attribute)

  def testUndefinedPublicAttribute(self):
    with self.assertRaises(AssertionError):
      obj_a = _ObjectA()
      setattr(obj_a, 'undefined', 'this should trigger an assertion')

  def testTypeValidationInSettingValue(self):
    with self.assertRaises(AssertionError):
      obj_a = _ObjectA()
      obj_a.v = 'not a string value'

  def testTypeValidationAcceptNoneAsValue(self):
    obj_a = _ObjectA()
    obj_a.v = None
    self.assertIsNone(obj_a.v)

  def testCustomizedTypeValidationForBuiltInType(self):
    f = _Future()
    obj_a = _ObjectA(
        type_validation_func=lambda _, x: isinstance(x, _Future), v=f)
    d = obj_a.ToDict()
    self.assertTrue(d['v'] is f)

    obj_a.v = 10
    d = obj_a.ToDict()
    self.assertEqual(10, d['v'])

    with self.assertRaises(AssertionError):
      obj_a.v = 'this wrong type should trigger an assertion'

  def testCustomizedTypeValidationForStructuredObject(self):
    f = _Future()
    obj_b = _ObjectB(
        type_validation_func=lambda _, x: isinstance(x, _Future),
        v={'a': 'b'},
        a=f)
    d = obj_b.ToDict()
    self.assertDictEqual({'a': 'b'}, d['v'])
    self.assertTrue(d['a'] is f)

    obj_b.a = _ObjectA(v=1)
    d = obj_b.ToDict()
    self.assertDictEqual({'v': 1}, d['a'])

    with self.assertRaises(AssertionError):
      obj_b.a = 'this wrong type should trigger an assertion'

  def testAccessingPrivateAttribute(self):
    obj_a = _ObjectA()
    self.assertEqual(10, obj_a._private_attribute)

  def testTypedDict(self):
    d = _DictOfObjectA()
    obj_a = _ObjectA()
    obj_a.v = 3
    d['a'] = obj_a
    self.assertEqual(obj_a, d['a'])

  def testTypedDictWithPrimitiveTypes(self):
    d = _DictOfInt()
    d['a'] = 1
    self.assertEqual(1, d['a'])

  def testTypedDictOtherType(self):
    with self.assertRaises(Exception):
      d = _DictOfObjectA()
      d[1] = 'a'

  def testTypedDictDel(self):
    d = _DictOfObjectA()
    obj_a = _ObjectA()
    obj_a.v = 3
    d['a'] = obj_a
    del d['a']
    self.assertIsNone(d.get('a'))

  def testTypedDictIter(self):
    d = _DictOfObjectA()
    obj_a = _ObjectA()
    obj_a.v = 3
    d['a'] = obj_a
    for value in d.values():
      self.assertTrue(isinstance(value, _ObjectA))

  def testTypedDictLen(self):
    d = _DictOfObjectA()
    self.assertEqual(0, len(d))

  def testTypedList(self):
    l = _ListOfObjectA()
    obj_a = _ObjectA()
    obj_a.v = 3
    l.append(obj_a)
    obj_a2 = _ObjectA()
    obj_a2.v = 1
    l[0] = obj_a2
    self.assertEqual(1, l[0].v)

  def testTypedListWithPrimitiveTypes(self):
    l = _ListOfStr()
    l.append('str1')
    l[0] = 'str2'
    self.assertEqual('str2', l[0])

  def testTypedListDel(self):
    l = _ListOfObjectA()
    obj_a = _ObjectA()
    obj_a.v = 3
    l.extend([obj_a])
    del l[0]
    self.assertEquals(0, len(l))

  def testTypedListInsert(self):
    l = _ListOfObjectA()
    obj_a = _ObjectA()
    obj_a.v = 3
    l.insert(0, obj_a)
    self.assertEqual(l[0], obj_a)

  def testTypedListInsertOtherType(self):
    with self.assertRaises(Exception):
      l = _ListOfObjectA()
      l.insert(0, 'b')
