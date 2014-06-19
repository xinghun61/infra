# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import textwrap
import unittest

from infra.services.gnumbd.support import data

class TestCommitTimestamp(unittest.TestCase):
  def testBasic(self):
    TS = '1399330903 -0700'
    t = data.CommitTimestamp.from_raw(TS)
    self.assertEqual(1399330903, t.secs)
    self.assertEqual(7, t.hours)
    self.assertEqual(0, t.mins)
    self.assertEqual('-', t.sign)
    self.assertEqual('-0700', t.tz_str)
    self.assertEqual(TS, str(t))
    self.assertEqual("CommitTimestamp(1399330903, '-', 7, 0)", repr(t))

  def testError(self):
    with self.assertRaises(Exception):
      data.CommitTimestamp.from_raw(' 1000 +0700')
    with self.assertRaises(Exception):
      data.CommitTimestamp.from_raw('1000 +0700 ')
    with self.assertRaises(Exception):
      data.CommitTimestamp.from_raw('1000  +0700')
    with self.assertRaises(Exception):
      data.CommitTimestamp.from_raw('cat -0700')
    with self.assertRaises(Exception):
      data.CommitTimestamp.from_raw('1000 =0700')
    with self.assertRaises(Exception):
      data.CommitTimestamp.from_raw('1000 +x100')
    with self.assertRaises(Exception):
      data.CommitTimestamp.from_raw('1000 +010x')

  def testEquality(self):
    TS = '1399330903 -0700'
    t = data.CommitTimestamp.from_raw(TS)
    self.assertEqual(t, t)
    self.assertIs(t, t)

    t2 = data.CommitTimestamp.from_raw(TS)
    self.assertEqual(t, t2)
    self.assertIsNot(t, t2)

    self.assertNotEqual(t, t.alter(sign='+'))

  def testToDict(self):
    TS = '1399330903 -0700'
    t = data.CommitTimestamp.from_raw(TS)
    self.assertEqual(t.to_dict(), {
        'secs': 1399330903, 'sign': '-', 'hours': 7, 'mins': 0})

  def testAlter(self):
    TS = '1399330903 -0700'
    t = data.CommitTimestamp.from_raw(TS)
    self.assertEqual(str(t.alter(hours=20, sign='+')), '1399330903 +2000')


class TestCommitUser(unittest.TestCase):
  def testBasic(self):
    USER = 'Bob Boberton <bob@chromium.org> 1399330903 -0700'
    u = data.CommitUser.from_raw(USER)
    self.assertEqual(u.email, 'bob@chromium.org')
    self.assertEqual(u.user, 'Bob Boberton')
    self.assertEqual(u.timestamp, data.CommitTimestamp(1399330903, '-', 7, 0))
    self.assertEqual(str(u), USER)
    self.assertEqual(
        repr(u), (
            "CommitUser('Bob Boberton', 'bob@chromium.org', "
            "CommitTimestamp(1399330903, '-', 7, 0))"
        )
    )

    USER = 'Bob Boberton  < bob@chromium.org> 1399330903 -0700'
    u = data.CommitUser.from_raw(USER)
    self.assertEqual(u.email, ' bob@chromium.org')
    self.assertEqual(u.user, 'Bob Boberton ')
    self.assertEqual(str(u), USER)

  def testError(self):
    with self.assertRaises(Exception):
      USER = 'Bob Boberton <bob@chromium.org>  1399330903 -0700'
      data.CommitUser.from_raw(USER)
    with self.assertRaises(Exception):
      USER = 'Bob Boberton <bob@chromium.org 1399330903 -0700'
      data.CommitUser.from_raw(USER)
    with self.assertRaises(Exception):
      USER = 'Bob Boberton bob@chromium.org> 1399330903 -0700'
      data.CommitUser.from_raw(USER)
    with self.assertRaises(Exception):
      USER = ' <bob@chromium.org> 1399330903 -0700'
      data.CommitUser.from_raw(USER)
    with self.assertRaises(Exception):
      USER = '<bob@chromium.org> 1399330903 -0700'
      data.CommitUser.from_raw(USER)
    with self.assertRaises(Exception):
      USER = 'Bob <> 1399330903 -0700'
      data.CommitUser.from_raw(USER)

  def testToDict(self):
    USER = 'Bob Boberton <bob@chromium.org> 1399330903 -0700'
    u = data.CommitUser.from_raw(USER)
    self.assertEqual(u.to_dict(), {
        'user': 'Bob Boberton', 'email': 'bob@chromium.org',
        'timestamp': data.CommitTimestamp(1399330903, '-', 7, 0)})

  def testEquality(self):
    USER = 'Bob Boberton <bob@chromium.org> 1399330903 -0700'
    u = data.CommitUser.from_raw(USER)
    self.assertEqual(u, u)
    self.assertIs(u, u)

    u2 = data.CommitUser.from_raw(USER)
    self.assertEqual(u, u2)
    self.assertIsNot(u, u2)

    self.assertNotEqual(u, u.alter(user='Catty Catterson'))

  def testAlter(self):
    USER = 'Bob Boberton <bob@chromium.org> 1399330903 -0700'
    u = data.CommitUser.from_raw(USER)
    self.assertEqual(u, u.alter(user='Bob Boberton'))

    USER = 'Bob Boberton <roberton@chromium.org> 1399330903 -0700'
    u2 = data.CommitUser.from_raw(USER)
    nu = u2.alter(email='bob@chromium.org')
    self.assertEqual(u, nu)

    self.assertEqual(u2.alter(timestamp=u2.timestamp.alter(secs=100)).timestamp,
                     data.CommitTimestamp.from_raw('100 -0700'))


class TestCommitData(unittest.TestCase):
  def testBasic(self):
    COMMIT = textwrap.dedent("""\
    tree b966f77e58b8a3cf7c02dd0271a4d636c0857af4
    parent 1b346cb5145e1fe4c074611e335d8ac96e18c686
    parent ab8d80f57839fb03674c0fc69ff5ccf2145fa6e2
    author Bob Boberton <bob@chromium.org> 1399330903 -0700
    committer Jane January <jane@chromium.org> 1399330903 -0700

    Cool commit message
    """)
    self.maxDiff = 10000
    d = data.CommitData.from_raw(COMMIT)
    self.assertEqual(d.to_dict(), {
        'tree': 'b966f77e58b8a3cf7c02dd0271a4d636c0857af4',
        'parents': ('1b346cb5145e1fe4c074611e335d8ac96e18c686',
                    'ab8d80f57839fb03674c0fc69ff5ccf2145fa6e2'),
        'author': data.CommitUser(
            'Bob Boberton', 'bob@chromium.org',
            data.CommitTimestamp(1399330903, '-', 7, 0)),
        'committer': data.CommitUser(
            'Jane January', 'jane@chromium.org',
            data.CommitTimestamp(1399330903, '-', 7, 0)),
        'message_lines': ('Cool commit message',),
        'footer_lines': (),
        'other_header_lines': ()
    })
    self.assertEqual(
        repr(d),
        "CommitData('b966f77e58b8a3cf7c02dd0271a4d636c0857af4', "
        "('1b346cb5145e1fe4c074611e335d8ac96e18c686', "
        "'ab8d80f57839fb03674c0fc69ff5ccf2145fa6e2'), "
        "CommitUser('Bob Boberton', 'bob@chromium.org', "
        "CommitTimestamp(1399330903, '-', 7, 0)), "
        "CommitUser('Jane January', 'jane@chromium.org', "
        "CommitTimestamp(1399330903, '-', 7, 0)), (), "
        "('Cool commit message',), ())"
    )
    self.assertEqual(str(d), COMMIT)

  def testFooters(self):
    COMMIT = textwrap.dedent("""\
    tree b966f77e58b8a3cf7c02dd0271a4d636c0857af4
    author Bob Boberton <bob@chromium.org> 1399330903 -0700
    committer Jane January <jane@chromium.org> 1399330903 -0700

    Cool commit message
    with: misleading footers

    Xenophobe: False
    Cool-Footer: 100
    Double-Awesome: 100
    Cool-Footer: Redux
    """)
    d = data.CommitData.from_raw(COMMIT)
    self.assertEqual(d, d)
    self.assertNotEqual(d, {})
    self.assertDictContainsSubset({
        'tree': 'b966f77e58b8a3cf7c02dd0271a4d636c0857af4',
        'author': data.CommitUser(
            'Bob Boberton', 'bob@chromium.org',
            data.CommitTimestamp(1399330903, '-', 7, 0)),
        'committer': data.CommitUser(
            'Jane January', 'jane@chromium.org',
            data.CommitTimestamp(1399330903, '-', 7, 0))
    }, d.to_dict())
    self.assertSequenceEqual(
        d.message_lines, ['Cool commit message', 'with: misleading footers'])
    self.assertSequenceEqual(
        d.footer_lines,
        [('Xenophobe', 'False'), ('Cool-Footer', '100'),
         ('Double-Awesome', '100'), ('Cool-Footer', 'Redux')])
    self.assertEqual(d.footers, {
        'Cool-Footer': ('100', 'Redux'),
        'Double-Awesome': ('100',),
        'Xenophobe': ('False',),
    })
    self.assertSequenceEqual(['Xenophobe', 'Cool-Footer', 'Double-Awesome'],
                             d.footers.keys())
    self.assertEqual(str(d), COMMIT)

  def testMisleadingFooters(self):
    COMMIT = textwrap.dedent("""\
    tree b966f77e58b8a3cf7c02dd0271a4d636c0857af4
    author Bob Boberton <bob@chromium.org> 1399330903 -0700
    committer Jane January <jane@chromium.org> 1399330903 -0700

    Cool commit message
    with: misleading footers
    """)
    d = data.CommitData.from_raw(COMMIT)
    self.assertDictContainsSubset({
        'tree': 'b966f77e58b8a3cf7c02dd0271a4d636c0857af4',
        'author': data.CommitUser(
            'Bob Boberton', 'bob@chromium.org',
            data.CommitTimestamp(1399330903, '-', 7, 0)),
        'committer': data.CommitUser(
            'Jane January', 'jane@chromium.org',
            data.CommitTimestamp(1399330903, '-', 7, 0)),
    }, d.to_dict())
    self.assertSequenceEqual(
        d.message_lines, ['Cool commit message', 'with: misleading footers'])
    self.assertSequenceEqual(
        d.footer_lines, [])
    self.assertEqual(d.footers, {})

  def testAlter(self):
    TREE1 = "tree b966f77e58b8a3cf7c02dd0271a4d636c0857af4\n"

    TREE2 = "tree deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\n"

    POSTFIX = textwrap.dedent("""\
    author Bob Boberton <bob@chromium.org> 1399330903 -0700
    committer Jane January <jane@chromium.org> 1399330903 -0700

    Cool commit message
    with: misleading footers
    """)

    d = data.CommitData.from_raw(TREE1 + POSTFIX)
    d2 = data.CommitData.from_raw(TREE2 + POSTFIX)

    self.assertEqual(
        d.alter(tree='deadbeefdeadbeefdeadbeefdeadbeefdeadbeef'), d2)

    HEADERS = textwrap.dedent("""\
    tree b966f77e58b8a3cf7c02dd0271a4d636c0857af4
    author Bob Boberton <bob@chromium.org> 1399330903 -0700
    committer Jane January <jane@chromium.org> 1399330903 -0700
    meep happytimes

    Cool commit message
    with: misleading footers
    """)
    self.assertEqual(str(d.alter(other_headers={'meep': ['happytimes']})),
                     HEADERS)

  def testAlterReorder(self):
    PREFIX = textwrap.dedent("""\
    tree b966f77e58b8a3cf7c02dd0271a4d636c0857af4
    author Bob Boberton <bob@chromium.org> 1399330903 -0700
    committer Jane January <jane@chromium.org> 1399330903 -0700

    Cool commit message
    with: misleading footers

    """)
    COMMIT = PREFIX + textwrap.dedent("""\
    Xenophobe: False
    Cool-Footer: 100
    Double-Awesome: 100
    Cool-Footer: Redux
    """)
    NEW_COMMIT = PREFIX + textwrap.dedent("""\
    Xenophobe: False
    Cool-Footer: 100
    Cool-Footer: Redux
    Double-Awesome: 100
    """)
    d = data.CommitData.from_raw(COMMIT)
    nd = data.CommitData.from_raw(NEW_COMMIT)
    self.assertEqual(d, d)
    self.assertNotEqual(d, nd)

  def testAlterAdd(self):
    PREFIX = textwrap.dedent("""\
    tree b966f77e58b8a3cf7c02dd0271a4d636c0857af4
    author Bob Boberton <bob@chromium.org> 1399330903 -0700
    committer Jane January <jane@chromium.org> 1399330903 -0700

    Cool commit message
    with: misleading footers

    """)
    COMMIT = PREFIX + textwrap.dedent("""\
    Xenophobe: False
    Cool-Footer: 100
    Double-Awesome: 100
    Cool-Footer: Redux
    """)
    NEW_COMMIT = PREFIX + textwrap.dedent("""\
    Cool-Footer: 100
    Cool-Footer: Redux
    Double-Awesome: 100
    Fungus: neat!
    """)
    d = data.CommitData.from_raw(COMMIT)
    nd = data.CommitData.from_raw(NEW_COMMIT)

    f = {'Fungus': ('neat!',)}
    f['Xenophobe'] = None
    self.assertEqual(d.alter(footers=f), nd)

  def testAlterDel(self):
    PREFIX = textwrap.dedent("""\
    tree b966f77e58b8a3cf7c02dd0271a4d636c0857af4
    author Bob Boberton <bob@chromium.org> 1399330903 -0700
    committer Jane January <jane@chromium.org> 1399330903 -0700

    Cool commit message
    with: misleading footers

    """)
    COMMIT = PREFIX + textwrap.dedent("""\
    Xenophobe: False
    Cool-Footer: 100
    Double-Awesome: 100
    Cool-Footer: Redux
    """)
    NEW_COMMIT = PREFIX[:-1]
    d = data.CommitData.from_raw(COMMIT)
    nd = data.CommitData.from_raw(NEW_COMMIT)
    to_nuke = {k: None for k in d.footers}
    to_nuke['Non-exist'] = None
    self.assertEqual(d.alter(footers=to_nuke), nd)

  def testAlterAppend(self):
    PREFIX = textwrap.dedent("""\
    tree b966f77e58b8a3cf7c02dd0271a4d636c0857af4
    author Bob Boberton <bob@chromium.org> 1399330903 -0700
    committer Jane January <jane@chromium.org> 1399330903 -0700

    Cool commit message
    with: misleading footers

    """)
    COMMIT = PREFIX + textwrap.dedent("""\
    Xenophobe: False
    Cool-Footer: 100
    Double-Awesome: 100
    Cool-Footer: Redux
    """)
    NEW_COMMIT = PREFIX + textwrap.dedent("""\
    Xenophobe: False
    Cool-Footer: 100
    Cool-Footer: Redux
    Cool-Footer: Sweet
    Double-Awesome: 100
    """)
    d = data.CommitData.from_raw(COMMIT)
    nd = data.CommitData.from_raw(NEW_COMMIT)
    self.assertEqual(
        d.alter(
            footers={'Cool-Footer': d.footers['Cool-Footer'] + ('Sweet',)}
        ),
        nd)

  def testOtherHeaders(self):
    COMMIT = textwrap.dedent("""\
    tree b966f77e58b8a3cf7c02dd0271a4d636c0857af4
    parent 1b346cb5145e1fe4c074611e335d8ac96e18c686
    author Bob Boberton <bob@chromium.org> 1399330903 -0700
    committer Jane January <jane@chromium.org> 1399330903 -0700
    generation 300
    apple-sauce cat food
    generation 100

    Cool commit message
    with: misleading footers
    """)
    c = data.CommitData.from_raw(COMMIT)
    expect = collections.OrderedDict()
    expect['generation'] = ('300', '100')
    expect['apple-sauce'] = ('cat food',)
    self.assertEqual(c.other_headers, expect)
    self.assertEqual(str(c), COMMIT)

  # Error cases
  def testDupTree(self):
    COMMIT = textwrap.dedent("""\
    tree b966f77e58b8a3cf7c02dd0271a4d636c0857af4
    tree b966f77e58b8a3cf7c02dd0271a4d636c0857af4
    parent 1b346cb5145e1fe4c074611e335d8ac96e18c686
    author Bob Boberton <bob@chromium.org> 1399330903 -0700
    committer Jane January <jane@chromium.org> 1399330903 -0700

    Cool commit message
    with: misleading footers
    """)
    with self.assertRaises(data.UnexpectedHeader):
      data.CommitData.from_raw(COMMIT)

  def testDupUser(self):
    COMMIT = textwrap.dedent("""\
    tree b966f77e58b8a3cf7c02dd0271a4d636c0857af4
    parent 1b346cb5145e1fe4c074611e335d8ac96e18c686
    author Bob Boberton <bob@chromium.org> 1399330903 -0700
    author Bob Boberton <bob@chromium.org> 1399330903 -0700
    committer Jane January <jane@chromium.org> 1399330903 -0700

    Cool commit message
    with: misleading footers
    """)
    with self.assertRaises(data.UnexpectedHeader):
      data.CommitData.from_raw(COMMIT)

  def testPartial(self):
    COMMIT = textwrap.dedent("""\
    tree deadbeefdeadbeefdeadbeefdeadbeefdeadbeef
    """)
    with self.assertRaises(data.PartialCommit):
      data.CommitData.from_raw(COMMIT)

  def testEmpty(self):
    with self.assertRaises(data.PartialCommit):
      data.CommitData.from_raw('')
