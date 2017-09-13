# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module provides a base class with a main feature to (de)serialize data.

The base class supports:
  * Serializable: can be serialized into de-serialized from a dict.
  * Type validation: define attributes with types, and is custom-validatable.
        None is an accepted value for all types.
  * Compositable: one object can contain other objects derived from the class.

One main usage of the base class is to define structured objects that are to be
serialized, transferred among different parts of a system or over http, and then
deserialized back to python objects.

A subclass should define "public" class-level attributes in the class instead of
within the constructor for an instance (if an instance changes the value of a
class-level attribute, the change is scoped to the instance itself and doesn't
impact the definition in the class), and those attributes will be serialized to
a dict or deserialized from a dict. The constructor in the subclass should
accept keyword parameters only, it must absorb those that are not defined
attributes and pass the remaining ones to the base class StructuredObject.

Examples:
1. Set values to an serializable object:
  class MyObjectA(StructuredObject):
    a = int
    b = str
    _unused = 'Private class attributes are allowed :), but not serialized :('

    def __init__(self, param='', **kwargs):
      super(MyObjectA, self).__init__(**kwargs)
      self._ok = 'Private instance attributes allowed :), but not serialized :('
      self._param = param
      # Uncomment line below will cause an Exception.
      # self.not_ok = 'Public instance attributes are not allowed :('

    @property
    def unused(self):
      return 'All properties are not serialized'

  There are two way to set the values of defined attributes:
      obj_a = MyObjectA()
      obj_a.a = 3
      obj_a.b = 'a string'
  or just simply:
      obj_a = MyObjectA(a=3, b='a string')

2. Serialize an object and deserialize:
  obj_a = MyObjectA(a=3, b='a string')
  data = obj_a.ToDict()
  assert data == {'a': 3, 'b': 'a string'}
  obj_a_copy = MyObjectA.FromDict(data)
  assert obj_a.a == obj_a_copy.a
  assert obj_a.b == obj_a_copy.b

3. Compositable:
  class MyObjectB(StructuredObject):
    v = dict
    o = MyObjectA

  obj_b = MyObjectB.FromDict(
      {'v': {'key': 'value'}, 'o': {'a': 3, 'b': 'a string'}})
  # obj_b = MyObjectB(v={'key': 'value'}, o=obj_a)
  assert obj_b.v == {'key': 'value'}
  assert obj_b.o.a == 3
  assert obj_b.o.b == 'a string'

4. Use customized type validation function.

  class Future1(object):
    pass

  class Future2(object):
    pass

  class MyObjectC(StructuredObject):
    v1 = dict
    v2 = list

  def ValidateTypes(attribute_name, attribute_value):
    # input: attribute name and its value.
    # output: bool. True if valid; otherwise False.
    valid_types = {
        'v1': Future1,
        'v2': Future2,
    }
    return isinstance(attribute_value, _Valid_types[attribute_name])

  obj_c = MyObjectC(type_validation_func=ValidateTypes,
                    v1=Future1(),
                    v2=Future2())
  assert isinstance(obj_c.v1, Future1), 'this should pass'
  assert isinstance(obj_c.v2, Future2), 'this should pass'
"""

import logging
import types


class StructuredObject(object):

  def __init__(self, type_validation_func=None, **kwargs):
    """Constructor.

    Args:
      type_validation_func (function): A customized function to validate whether
          a given attribute value is accepted or not. Its input is the attribute
          name and value, and its output is a True/False to indicate whether the
          value is accepted or not accepted respectively.
      kwargs (dict): All other keyword parameters are used to set values of
          defined attributes.
    """
    self._type_validation_func = type_validation_func
    self._data = {}
    for name, value in kwargs.iteritems():
      setattr(self, name, value)

  def __setattr__(self, name, value):
    """Intercepts attribute settings and validates types of attribute values."""
    if name.startswith('_'):  # Allow private instance attributes.
      object.__setattr__(self, name, value)
      return

    attribute_type = self._GetDefinedAttributes().get(name)
    assert attribute_type is not None, '%s.%s is undefined' % (
        self.__class__.__name__, name)
    if value is not None:
      if not self._type_validation_func:
        assert isinstance(
            value, attribute_type), ('%s.%s: expected type %s, but got %s' %
                                     (self.__class__.__name__, name,
                                      attribute_type.__name__,
                                      type(value).__name__))
      elif not isinstance(value, attribute_type):
        assert self._type_validation_func(name, value), (
            'Value of type %s for %s.%s failed a customized type validation' %
            (type(value).__name__, self.__class__.__name__, name))
    self._data[name] = value

  def __getattribute__(self, name):
    """Intercepts attribute access and returns values of defined attributes."""
    # __getattr__ won't work because dynamically-defined attributes are
    # expected to be in the class so that they are directly accessible and
    # __getattr__ won't be triggered.
    # __getattribute__ is always triggered upon accessing any attribute,
    # function, or method with a class instance, e.g. self.__class__ or
    # self._GetDefinedAttributes.
    # However, this function needs to access _GetDefinedAttributes with an
    # instance of the subclass. So we have to handle invocation of
    # _GetDefinedAttributes first to avoid infinite recursive invocation between
    # _GetDefinedAttributes and __getattribute__.
    if name.startswith('_'):
      return object.__getattribute__(self, name)
    if name in self._GetDefinedAttributes():
      return self._data[name]
    return object.__getattribute__(self, name)

  @classmethod
  def _GetDefinedAttributes(cls):
    """Returns a map from defined attributes to their types.

    Args:
      cls (class): The subclass.

    Returns:
      A dict from defined attributes to their types.
    """
    if not hasattr(cls, '_dynamic_definitions'):
      d = {}
      for name in dir(cls):
        if name.startswith('_'):
          continue  # Ignore private attributes.
        value = getattr(cls, name)
        if isinstance(value, property):
          continue  # Ignore properties.
        if type(value) in (types.MethodType, types.FunctionType):
          continue  # Ignore functions and methods.
        d[name] = value
      setattr(cls, '_dynamic_definitions', d)
    return cls._dynamic_definitions

  def ToDict(self):
    """Returns a dict into which all defined attributes are serialized."""
    data = {}
    defined_attributes = self._GetDefinedAttributes()
    for name, value_type in defined_attributes.iteritems():
      assert name in self._data, '%s.%s is not set' % (self.__class__.__name__,
                                                       name)
      value = self._data[name]
      if (value is not None and issubclass(value_type, StructuredObject) and
          not (self._type_validation_func and
               self._type_validation_func(name, value))):
        # Only encode the value if its defined type is StructuredObject AND
        # The customized type validation function doesn't accept its value.
        # If the validation function accepts the value, keep the value as is for
        # the caller code to do some customized processing later.
        value = value.ToDict()
      data[name] = value
    return data

  def __repr__(self):
    """Returns a string that represents this class instance."""
    return '%s(%r)' % (self.__class__.__name__, self.ToDict())

  @classmethod
  def FromDict(cls, data):
    """Deserializes the given data and returns an instance of this class.

    Args:
      cls  (class): The subclass.
      data (dict): The dict mapping from defined attributes to their values.

    Returns:
      An instance of the given class with attributes set to the given data.
    """
    assert isinstance(
        data, dict), ('Expecting a dict, but got %s' % type(data).__name__)
    defined_attributes = cls._GetDefinedAttributes()
    undefined_attributes = set(data.keys()) - set(defined_attributes.keys())
    assert len(undefined_attributes) == 0, ('%s not defined in %s' %
                                            (','.join(undefined_attributes),
                                             cls.__name__))
    instance = cls()
    for name, value_type in defined_attributes.iteritems():
      if name not in data:
        setattr(instance, name, None)
        logging.warning('Assigned None to %s.%s as it is missing in %r',
                        cls.__name__, name, data)
      else:
        value = data[name]
        if issubclass(value_type, StructuredObject):
          value = defined_attributes[name].FromDict(value)
        setattr(instance, name, value)
    return instance
