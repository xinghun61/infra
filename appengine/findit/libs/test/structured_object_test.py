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
  _value_type = _ObjectA


class _DictOfInt(structured_object.TypedDict):
  # This is just for testing purpose. In practice we should use dict directly.
  _value_type = int


class _ListOfObjectA(structured_object.TypedList):
  _element_type = _ObjectA


class _ListOfStr(structured_object.TypedList):
  # This is just for testing purpose. In practice we should use list directly.
  _element_type = str


class _ObjectC(structured_object.StructuredObject):
  da = _DictOfObjectA
  la = _ListOfObjectA
  d = _DictOfInt
  l = _ListOfStr


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

  def testToSerializable(self):
    obj_a = _ObjectA()
    obj_a.v = 1
    obj_b = _ObjectB()
    obj_b.v = {'key': 'value'}
    obj_b.a = obj_a
    data = obj_b.ToSerializable()
    expected_data = {'a': {'v': 1}, 'v': {'key': 'value'}}
    self.assertDictEqual(expected_data, data)

  def testToSerializableForNoneValue(self):
    obj_a = _ObjectA(v=None)
    self.assertDictEqual({'v': None}, obj_a.ToSerializable())

  def testFromSerializableNone(self):
    obj_b = _ObjectB.FromSerializable(None)
    self.assertIsNone(obj_b)

  def testFromSerializable(self):
    data = {'a': {'v': 1}, 'v': {'key': 'value'}}
    obj_b = _ObjectB.FromSerializable(data)
    self.assertDictEqual({'key': 'value'}, obj_b.v)
    self.assertEqual(1, obj_b.a.v)

  def testFromSerializableAssertionOnList(self):
    with self.assertRaises(AssertionError):
      _ObjectA.FromSerializable(['v'])

  def testFromSerializableAssertionOnUndefinedAttribute(self):
    with self.assertRaises(AssertionError):
      _ObjectA.FromSerializable({'undefined': 1})

  def testFromSerializableAssertionOnMissingAttributeValue(self):
    obj_a = _ObjectA.FromSerializable({})
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
    obj_b1 = _ObjectB.FromSerializable(data)
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
    d = obj_a.ToSerializable()
    self.assertTrue(d['v'] is f)

    obj_a.v = 10
    d = obj_a.ToSerializable()
    self.assertEqual(10, d['v'])

    with self.assertRaises(AssertionError):
      obj_a.v = 'this wrong type should trigger an assertion'

  def testCustomizedTypeValidationForStructuredObject(self):
    f = _Future()
    obj_b = _ObjectB(
        type_validation_func=lambda _, x: isinstance(x, _Future),
        v={'a': 'b'},
        a=f)
    d = obj_b.ToSerializable()
    self.assertDictEqual({'a': 'b'}, d['v'])
    self.assertTrue(d['a'] is f)

    obj_b.a = _ObjectA(v=1)
    d = obj_b.ToSerializable()
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

  def testComplexTypesToSerializable(self):
    obj_a1 = _ObjectA()
    obj_a1.v = 1
    obj_a2 = _ObjectA()
    obj_a2.v = 2

    obj_c = _ObjectC()
    obj_c.da = _DictOfObjectA()
    obj_c.da['a1'] = obj_a1
    obj_c.da['a2'] = obj_a2
    obj_c.la = _ListOfObjectA()
    obj_c.la.append(obj_a2)
    obj_c.la.insert(0, obj_a1)
    obj_c.d = _DictOfInt()
    obj_c.d['a1'] = 1
    obj_c.d['a2'] = 2
    obj_c.l = _ListOfStr()
    obj_c.l.extend(['a', 'b'])

    expected_dict = {
        'da': {
            'a1': {
                'v': 1
            },
            'a2': {
                'v': 2
            }
        },
        'la': [{
            'v': 1
        }, {
            'v': 2
        }],
        'd': {
            'a1': 1,
            'a2': 2
        },
        'l': ['a', 'b']
    }
    self.assertEqual(expected_dict, obj_c.ToSerializable())

  def testComplexTypesFromSerializable(self):
    data_dict = {
        'da': {
            'a1': {
                'v': 1
            },
            'a2': {
                'v': 2
            }
        },
        'la': [{
            'v': 1
        }, {
            'v': 2
        }],
        'd': {
            'a1': 1,
            'a2': 2
        },
        'l': ['a', 'b']
    }

    obj_c = _ObjectC.FromSerializable(data_dict)
    self.assertEqual(data_dict, obj_c.ToSerializable())

  def testBaseSerializableObjectEqual(self):
    data_dict = {
        'da': {
            'a1': {
                'v': 1
            },
            'a2': {
                'v': 2
            }
        },
        'la': [{
            'v': 1
        }, {
            'v': 2
        }],
        'd': {
            'a1': 1,
            'a2': 2
        },
        'l': ['a', 'b']
    }

    obj_c1 = _ObjectC.FromSerializable(data_dict)
    obj_c2 = _ObjectC.FromSerializable(data_dict)
    self.assertEqual(obj_c1, obj_c2)

  def testBaseSerializableObjectNotEqual(self):
    obj_a1 = _ObjectA()
    obj_a1.v = 1
    obj_a2 = _ObjectA()
    obj_a2.v = 2

    da = _DictOfObjectA()
    da['a1'] = obj_a1
    da['a2'] = obj_a2

    la = _ListOfObjectA()
    la.append(obj_a1)
    la.append(obj_a2)

    self.assertTrue(da != la)

  def testTypedDictFromSerializableNone(self):
    self.assertIsNone(_DictOfObjectA.FromSerializable(None))

  def testTypedListFromSerializableNone(self):
    self.assertIsNone(_ListOfObjectA.FromSerializable(None))