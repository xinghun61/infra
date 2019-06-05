# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for template_helpers module."""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import unittest

from framework import pbproxy_test_pb2
from framework import template_helpers


class HelpersUnitTest(unittest.TestCase):

  def testDictionaryProxy(self):

    # basic in 'n out test
    item = template_helpers.EZTItem(label='foo', group_name='bar')

    self.assertEquals('foo', item.label)
    self.assertEquals('bar', item.group_name)

    # be sure the __str__ returns the fields
    self.assertEquals("EZTItem({'group_name': 'bar', 'label': 'foo'})",
                      str(item))

  def testPBProxy(self):
    """Checks that PBProxy wraps protobuf objects as expected."""
    # check that protobuf fields are accessible in ".attribute" form
    pbe = pbproxy_test_pb2.PBProxyExample()
    pbe.nickname = 'foo'
    pbe.invited = False
    pbep = template_helpers.PBProxy(pbe)
    self.assertEqual(pbep.nickname, 'foo')
    # _bool suffix converts protobuf field 'bar' to None (EZT boolean false)
    self.assertEqual(pbep.invited_bool, None)

    # check that a new field can be added to the PBProxy
    pbep.baz = 'bif'
    self.assertEqual(pbep.baz, 'bif')

    # check that a PBProxy-local field can hide a protobuf field
    pbep.nickname = 'local foo'
    self.assertEqual(pbep.nickname, 'local foo')

    # check that a nested protobuf is recursively wrapped with a PBProxy
    pbn = pbproxy_test_pb2.PBProxyNested()
    pbn.nested = pbproxy_test_pb2.PBProxyExample()
    pbn.nested.nickname = 'bar'
    pbn.nested.invited = True
    pbnp = template_helpers.PBProxy(pbn)
    self.assertEqual(pbnp.nested.nickname, 'bar')
    # _bool suffix converts protobuf field 'bar' to 'yes' (EZT boolean true)
    self.assertEqual(pbnp.nested.invited_bool, 'yes')

    # check that 'repeated' lists of items produce a list of strings
    pbn.multiple_strings.append('1')
    pbn.multiple_strings.append('2')
    self.assertEqual(pbnp.multiple_strings, ['1', '2'])

    # check that 'repeated' messages produce lists of PBProxy instances
    pbe1 = pbproxy_test_pb2.PBProxyExample()
    pbn.multiple_pbes.append(pbe1)
    pbe1.nickname = '1'
    pbe1.invited = True
    pbe2 = pbproxy_test_pb2.PBProxyExample()
    pbn.multiple_pbes.append(pbe2)
    pbe2.nickname = '2'
    pbe2.invited = False
    self.assertEqual(pbnp.multiple_pbes[0].nickname, '1')
    self.assertEqual(pbnp.multiple_pbes[0].invited_bool, 'yes')
    self.assertEqual(pbnp.multiple_pbes[1].nickname, '2')
    self.assertEqual(pbnp.multiple_pbes[1].invited_bool, None)

  def testFitTextMethods(self):
    """Tests both FitUnsafeText with an eye on i18n."""
    # pylint: disable=anomalous-unicode-escape-in-string
    test_data = (
        u'This is a short string.',

        u'This is a much longer string. '
        u'This is a much longer string. '
        u'This is a much longer string. '
        u'This is a much longer string. '
        u'This is a much longer string. '
        u'This is a much longer string. '
        u'This is a much longer string. '
        u'This is a much longer string. '
        u'This is a much longer string. '
        u'This is a much longer string. ',

        # This is a short escaped i18n string
        '\xd5\xa1\xd5\xba\xd5\xa1\xd5\xaf\xd5\xab'.decode('utf-8'),

        # This is a longer i18n string
        '\xd5\xa1\xd5\xba\xd5\xa1\xd5\xaf\xd5\xab '
        '\xe6\x88\x91\xe8\x83\xbd\xe5\x90\x9e '
        '\xd5\xa1\xd5\xba\xd5\xa1\xd5\xaf\xd5\xab '
        '\xe6\x88\x91\xe8\x83\xbd\xe5\x90\x9e '
        '\xd5\xa1\xd5\xba\xd5\xa1\xd5\xaf\xd5\xab '
        '\xe6\x88\x91\xe8\x83\xbd\xe5\x90\x9e '
        '\xd5\xa1\xd5\xba\xd5\xa1\xd5\xaf\xd5\xab '
        '\xe6\x88\x91\xe8\x83\xbd\xe5\x90\x9e '.decode('utf-8'),

        # This is a longer i18n string that was causing trouble.
        '\u041d\u0430 \u0431\u0435\u0440\u0435\u0433\u0443'
        ' \u043f\u0443\u0441\u0442\u044b\u043d\u043d\u044b\u0445'
        ' \u0432\u043e\u043b\u043d \u0421\u0442\u043e\u044f\u043b'
        ' \u043e\u043d, \u0434\u0443\u043c'
        ' \u0432\u0435\u043b\u0438\u043a\u0438\u0445'
        ' \u043f\u043e\u043b\u043d, \u0418'
        ' \u0432\u0434\u0430\u043b\u044c'
        ' \u0433\u043b\u044f\u0434\u0435\u043b.'
        ' \u041f\u0440\u0435\u0434 \u043d\u0438\u043c'
        ' \u0448\u0438\u0440\u043e\u043a\u043e'
        ' \u0420\u0435\u043a\u0430'
        ' \u043d\u0435\u0441\u043b\u0430\u0441\u044f;'
        ' \u0431\u0435\u0434\u043d\u044b\u0439'
        ' \u0447\u0451\u043b\u043d \u041f\u043e'
        ' \u043d\u0435\u0439'
        ' \u0441\u0442\u0440\u0435\u043c\u0438\u043b\u0441\u044f'
        ' \u043e\u0434\u0438\u043d\u043e\u043a\u043e.'
        ' \u041f\u043e \u043c\u0448\u0438\u0441\u0442\u044b\u043c,'
        ' \u0442\u043e\u043f\u043a\u0438\u043c'
        ' \u0431\u0435\u0440\u0435\u0433\u0430\u043c'
        ' \u0427\u0435\u0440\u043d\u0435\u043b\u0438'
        ' \u0438\u0437\u0431\u044b \u0437\u0434\u0435\u0441\u044c'
        ' \u0438 \u0442\u0430\u043c, \u041f\u0440\u0438\u044e\u0442'
        ' \u0443\u0431\u043e\u0433\u043e\u0433\u043e'
        ' \u0447\u0443\u0445\u043e\u043d\u0446\u0430;'
        ' \u0418 \u043b\u0435\u0441,'
        ' \u043d\u0435\u0432\u0435\u0434\u043e\u043c\u044b\u0439'
        ' \u043b\u0443\u0447\u0430\u043c \u0412'
        ' \u0442\u0443\u043c\u0430\u043d\u0435'
        ' \u0441\u043f\u0440\u044f\u0442\u0430\u043d\u043d\u043e'
        '\u0433\u043e \u0441\u043e\u043b\u043d\u0446\u0430,'
        ' \u041a\u0440\u0443\u0433\u043e\u043c'
        ' \u0448\u0443\u043c\u0435\u043b.'.decode('utf-8'))

    for unicode_s in test_data:
      # Get the length in characters, not bytes.
      length = len(unicode_s)

      # Test the FitUnsafeText method at the length boundary.
      fitted_unsafe_text = template_helpers.FitUnsafeText(unicode_s, length)
      self.assertEqual(fitted_unsafe_text, unicode_s)

      # Set some values that test FitString well.
      available_space = length // 2
      max_trailing = length // 4
      # Break the string at various places - symmetric range around 0
      for i in range(1-max_trailing, max_trailing):
        # Test the FitUnsafeText method.
        fitted_unsafe_text = template_helpers.FitUnsafeText(
            unicode_s, available_space - i)
        self.assertEqual(fitted_unsafe_text[:available_space - i],
                         unicode_s[:available_space - i])

      # Test a string that is already unicode
      u_string = u'This is already unicode'
      fitted_unsafe_text = template_helpers.FitUnsafeText(u_string, 100)
      self.assertEqual(u_string, fitted_unsafe_text)

      # Test a string that is already unicode, and has non-ascii in it.
      u_string = u'This is already unicode este\\u0301tico'
      fitted_unsafe_text = template_helpers.FitUnsafeText(u_string, 100)
      self.assertEqual(u_string, fitted_unsafe_text)

  def testEZTError(self):
    errors = template_helpers.EZTError()
    self.assertFalse(errors.AnyErrors())

    errors.error_a = 'A'
    self.assertTrue(errors.AnyErrors())
    self.assertEquals('A', errors.error_a)

    errors.SetError('error_b', 'B')
    self.assertTrue(errors.AnyErrors())
    self.assertEquals('A', errors.error_a)
    self.assertEquals('B', errors.error_b)

  def testBytesKbOrMb(self):
    self.assertEqual('1023 bytes', template_helpers.BytesKbOrMb(1023))
    self.assertEqual('1.0 KB', template_helpers.BytesKbOrMb(1024))
    self.assertEqual('1023 KB', template_helpers.BytesKbOrMb(1024 * 1023))
    self.assertEqual('1.0 MB', template_helpers.BytesKbOrMb(1024 * 1024))
    self.assertEqual('98.0 MB', template_helpers.BytesKbOrMb(98 * 1024 * 1024))
    self.assertEqual('99 MB', template_helpers.BytesKbOrMb(99 * 1024 * 1024))
