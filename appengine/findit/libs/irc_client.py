# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import socket
import time

# This is the maximum size of an IRC message.
BUFFER_SIZE = 512

# Some hosts take several seconds to send MOTD and joining the channel.
TIMEOUT = 30

# Try to connect this many times before giving up.
RETRIES = 3


class IRCClient(object):
  """A numb IRC client to connect and send a message to a IRC channel."""

  def __init__(self,
               server_hostname,
               channel_name,
               nick_name,
               description,
               port=6667):
    self._server_hostname = server_hostname
    self._channel_name = channel_name
    self._nick_name = nick_name
    self._description = description
    self._port = port
    self._joined = False
    self._irc = None
    self._timeout = 0
    self._retries_left = RETRIES

  def Connect(self):
    """Opens a connection to the irc server and joins a channel."""
    assert self._irc is None, 'Already connected'
    self._irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self._irc.connect((self._server_hostname, self._port))
    self._irc.settimeout(TIMEOUT)
    self._irc.sendall('USER {name} {name} {name} : {description}\r\n'.format(
        name=self._nick_name, description=self._description))
    self._irc.sendall('NICK %s\r\n' % self._nick_name)
    self._irc.sendall('JOIN %s\r\n' % self._channel_name)
    self._WaitForJoin()
    self._joined = True
    logging.info('Joined %s on %s', self._channel_name, self._server_hostname)

  def _WaitForJoin(self):
    """Waits for confirmation that we joined the channel.

    If we send a message before the sender confirms we joined the channel, the
    message may be dropped.
    """
    join_message_regex = re.compile(r'[^ ]+ [^ ]+ %s @ %s.*' %
                                    (self._nick_name, self._channel_name))
    # Keep the last line in this var in case it is truncated.
    partial_line = ''
    while True:
      messages = partial_line + self._irc.recv(BUFFER_SIZE)
      # Loop through the messages until we find confirmation of joining the
      # channel.
      for message in messages.splitlines(True):  # Keep '\n' or '\r' suffix.
        if message[-1] not in '\n\r':
          partial_line = message
        else:
          partial_line = ''
        if join_message_regex.match(message.strip()):
          return

  def SendMessage(self, message, receiver=None, retries=3, retry_delay=5):
    """Sends a message to the joined channel, or specific user.

    Args:
      message(str): A short message (suported length depends on host).
      receiver(str): Nick of receiver. None if the target is the channel.
      retries(int) (optional): How may times to retry sending the message if an
        unexpected socket exception or timeout happens. Default 3.
      retry_delay(float) (optional): How many seconds to sleep between the first
        and second attempts at sending the message. This will be doubled for
        each attempt. Default 5 sec.
    """
    assert self._joined, 'Not joined yet!'
    # Even with retries == 0, we still need to go into the loop once.
    tries_left = max(retries + 1, 1)  # Force a positive retry counter.
    while tries_left > 0:  # pragma: no branch.
      try:
        receiver = receiver or self._channel_name
        self._irc.sendall('PRIVMSG {receiver} :{message}\r\n'.format(
            receiver=receiver, message=message))
        logging.info('Message sent to %s: %s', receiver, message)
        return
      except (socket.timeout, IOError) as e:
        if tries_left:
          logging.warning('Failed to send messsage due to %s, '
                          'retrying after %s seconds', e, retry_delay)
          time.sleep(retry_delay)
          tries_left -= 1
          retry_delay *= 2
        else:
          logging.exception(
              'Exceeded %d retries sending irc message. Giving up', retries)
          raise

  def Disconnect(self):
    """Leaves the channel if needed, then closes connection to server."""
    if self._joined:
      self._irc.sendall('PART %s\r\n' % self._channel_name)
      self._irc.sendall('QUIT\r\n')
      logging.info('Leave %s, and quit', self._channel_name)
    # There's not much benefit in testing this branch.
    if self._irc:  # pragma: no branch
      self._irc.close()

  def __enter__(self):
    while True:
      try:
        self.Connect()
        return self
      except (socket.timeout, IOError):
        logging.debug(
            'Did not get irc join confirmation message, connecting again.')
        self._retries_left -= 1
        self.Disconnect()
        self._irc = None
        if self._retries_left < 1:
          raise

  def __exit__(self, _exc_type, _exc_val, _exc_tb):
    self.Disconnect()
