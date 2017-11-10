# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import socket

from testing_utils import testing

from libs.irc_client import IRCClient

SERVER_RESPONSE = """
:verne.freenode.net NOTICE * :*** Looking up your hostname...
:verne.freenode.net NOTICE * :*** Checking Ident
:verne.freenode.net NOTICE * :*** Couldn't look up your hostname
:verne.freenode.net NOTICE * :*** No Ident response
:verne.freenode.net 001 findittest :Welcome to the freenode Internet Relay Chat Network findittest
:verne.freenode.net 005 findittest CHANTYPES=# EXCEPTS INVEX CHANMODE S=eIbq,k,flj,CFLMPQScgimnprstz CHANLIMIT=#:120 PREFIX=(ov)@+ MAXLIST=bqeI:100 MODES=4 NETWORK=freenode STATUSMSG=@+ CALLERID=g CASEMAPPING=rfc1459 :are supported by this server
:verne.freenode.net 005 findittest CHARSET=ascii NICKLEN=16 CHANNELLEN=50 TOPICLEN=390 DEAF=D FNC TARGMAX=NAMES:1,LIST:1,KICK:1,WHOIS:1,PRIVMSG:4,NOTICE:4,ACCEPT:,MONITOR: EXTBAN=$,ajrxz CLIENTVER=3.0 ETRACE WHOX KNOCK :are supported by this server
:verne.freenode.net 005 findittest SAFELIST ELIST=CTU CPRIVMSG CNOTICE :are supported by this server
:verne.freenode.net 375 findittest :- verne.freenode.net Message of the Day -
:verne.freenode.net 372 findittest :- Welcome to verne.freenode.net in Amsterdam, NL.
:verne.freenode.net 376 findittest :End of /MOTD command.
:findittest MODE findittest :+i
:findittest!~findittes@104.132.1.85 JOIN #chromium
:verne.freenode.net 353 findittest @ #chromium :findittest @someone
"""


class IRCClientTest(testing.AppengineTestCase):

  def setUp(self):
    super(IRCClientTest, self).setUp()
    # TODO(you): Find a more concise way to do the following three lines.
    self.mock_socket_obj = mock.Mock()
    self.mock_socket_obj.recv = mock.Mock(return_value=SERVER_RESPONSE)
    self.patch(
        'libs.irc_client.socket.socket',
        new=mock.Mock(return_value=self.mock_socket_obj))

  def testIRCClientTestDirectMessage(self):
    channel = '#chromium'
    nick = 'findittest'
    message = 'Foo bar baz\n\n'
    other_nick = 'someone'
    with IRCClient('irc.freenode.net', channel, nick, 'CulpritFinder') as i:
      i.SendMessage(message, other_nick)
    self.assertEqual(self.mock_socket_obj.sendall.call_args_list, [
        mock.call('USER %s %s %s : CulpritFinder\r\n' % (nick, nick, nick)),
        mock.call('NICK %s\r\n' % nick),
        mock.call('JOIN %s\r\n' % channel),
        mock.call('PRIVMSG %s :%s\r\n' % (other_nick, message)),
        mock.call('PART %s\r\n' % channel),
        mock.call('QUIT\r\n')
    ])

  def testIRCClientTestChannelMessage(self):
    channel = '#chromium'
    nick = 'findittest'
    message = 'Foo bar baz\n\n'
    with IRCClient('irc.freenode.net', channel, nick, 'CulpritFinder') as i:
      i.SendMessage(message)
    self.assertEqual(self.mock_socket_obj.sendall.call_args_list, [
        mock.call('USER %s %s %s : CulpritFinder\r\n' % (nick, nick, nick)),
        mock.call('NICK %s\r\n' % nick),
        mock.call('JOIN %s\r\n' % channel),
        mock.call('PRIVMSG %s :%s\r\n' % (channel, message)),
        mock.call('PART %s\r\n' % channel),
        mock.call('QUIT\r\n')
    ])

  def testIRCClientTestConnectTimeout(self):
    channel = '#chromium'
    nick = 'findittest'
    # After a number of retries, the exception must be let through.
    self.mock_socket_obj.recv.side_effect = socket.timeout
    with self.assertRaises(socket.timeout):
      with IRCClient('irc.freenode.net', channel, nick, 'CulpritFinder') as _:
        # Unreachable by design, as we are testing the context manager's
        # __enter__ method.
        pass  # pragma: no cover

  def testIRCClientTestMessageTimeout(self):
    channel = '#chromium'
    nick = 'findittest'
    message = 'Foo bar baz\n\n'
    other_nick = 'someone'
    with self.assertRaises(IOError):
      with IRCClient('irc.freenode.net', channel, nick, 'CulpritFinder') as i:
        # The connection must have been successful, message sending should not.
        self.mock_socket_obj.sendall.side_effect = IOError('misc error')
        i.SendMessage(message, other_nick, retry_delay=0)

  def testIRCClientTestLongIntro(self):
    channel = '#chromium'
    nick = 'findittest'
    message = 'Foo bar baz\n\n'
    # Force socket.recv to be called multiple times.
    self.mock_socket_obj.recv = mock.Mock(
        side_effect=['\n', '\n', SERVER_RESPONSE])
    with IRCClient('irc.freenode.net', channel, nick, 'CulpritFinder') as i:
      i.SendMessage(message)
    self.assertEqual(self.mock_socket_obj.sendall.call_args_list, [
        mock.call('USER %s %s %s : CulpritFinder\r\n' % (nick, nick, nick)),
        mock.call('NICK %s\r\n' % nick),
        mock.call('JOIN %s\r\n' % channel),
        mock.call('PRIVMSG %s :%s\r\n' % (channel, message)),
        mock.call('PART %s\r\n' % channel),
        mock.call('QUIT\r\n')
    ])

  def testIRCClientTestTruncatedJoinMessage(self):
    channel = '#chromium'
    nick = 'findittest'
    message = 'Foo bar baz\n\n'
    # Force socket.recv to be called multiple times.
    self.mock_socket_obj.recv = mock.Mock(side_effect=[
        'Preamble', 'MOTD message\r\n', 'Foo\r\n:verne.freenode.net 353 findit',
        'test @ #chromium :findittest @someone\r\nBar\r\n'
    ])
    with IRCClient('irc.freenode.net', channel, nick, 'CulpritFinder') as i:
      i.SendMessage(message)
    self.assertEqual(self.mock_socket_obj.sendall.call_args_list, [
        mock.call('USER %s %s %s : CulpritFinder\r\n' % (nick, nick, nick)),
        mock.call('NICK %s\r\n' % nick),
        mock.call('JOIN %s\r\n' % channel),
        mock.call('PRIVMSG %s :%s\r\n' % (channel, message)),
        mock.call('PART %s\r\n' % channel),
        mock.call('QUIT\r\n')
    ])
