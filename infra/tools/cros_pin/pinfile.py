# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import contextlib
import json
import os
import re

from infra.libs.gitiles import gitiles
from infra.tools.cros_pin.logger import LOGGER

class InvalidPinError(Exception):
  pass

class ReadOnlyError(Exception):
  pass


# Named Chromite pins to their checkout-relative paths.
Config = collections.namedtuple('Config',
    ('name', 'base', 'json_subpath', 'masters'))


EXTERNAL = Config(
    'external',
    ('build',),
    ('scripts', 'common', 'cros_chromite_pins.json'),
    ('chromiumos',))


INTERNAL = Config(
    'internal',
    ('build_internal',),
    ('scripts', 'common_internal', 'cros_chromite_internal_pins.json'),
    ('chromeos', 'chromeos_release'))


PinUpdate = collections.namedtuple('PinUpdate',
    ('name', 'fr', 'to'))


class Editor(object):

  # Regular expression to match a Git commit (SHA1)
  RE_COMMIT_SHA1 = re.compile(r'^[a-fA-F0-9]{40}$')

  def __init__(self, checkout_path, gitiles_repo, validate=True):
    self._checkout_path = checkout_path
    self._gitiles = None
    self._validate = validate
    self._gitiles = gitiles_repo

  def load(self, pin):
    return self.File(self, pin)

  def get_commit(self, branch):
    try:
      return self._gitiles.ref_info(branch)['commit']
    except gitiles.GitilesError:
      raise InvalidPinError("Pin ref [%s] does not exist." % (branch,))

  def validate_pin(self, ref):
    if not self.RE_COMMIT_SHA1.match(ref):
      raise InvalidPinError("Not a valid SHA1 hash")
    self.get_commit(ref)

  class File(object):
    def __init__(self, editor, pin):
      self._editor = editor
      self._pin = pin
      self._path = os.path.join(editor._checkout_path,
                                *(pin.base + pin.json_subpath))

    @contextlib.contextmanager
    def edit(self):
      d = self.load()
      orig = d.copy()
      try:
        yield d
      finally:
        if d != orig:
          self.save(**d)

    def load(self):
      with open(self._path, 'r') as fd:
        return json.load(fd)

    def save(self, **pins):
      for k, v in pins.iteritems():
        assert isinstance(k, basestring)
        assert isinstance(v, basestring)
      LOGGER.debug('Writing pin file [%s]: %s', self._path, pins)
      with open(self._path, 'w') as fd:
        json.dump(pins, fd, indent=2, sort_keys=True)


    def update(self, pin_name, create=False, version=None):
      """Updates a single pin value."""
      if not version:
        LOGGER.debug('Resolving version for pin [%s]', pin_name)
        version = self._editor.get_commit(pin_name)
      elif self._editor._validate:
        LOGGER.debug('Validating pin [%s]', pin_name)
        self._editor.validate_pin(version)

      with self.edit() as pins:
        current = pins.get(pin_name)
        if current == version:
          LOGGER.warning('Pin [%s.%s] is already at version [%s]',
                         self._pin.name, pin_name, current)
          return None

        LOGGER.info('Updating pin [%s.%s]: [%s] => [%s]',
                    self._pin.name, pin_name, current, version)
        if not (current or create):
          raise ReadOnlyError("Pin does not exist [%s]" % (pin_name,))
        pins[pin_name] = version
      return PinUpdate(pin_name, current, version)

    def remove(self, pin_name):
      """Removes a single pin from the pin list."""
      with self.edit() as pins:
        cur = pins.pop(pin_name, None)
        if cur is None:
          return None
      return PinUpdate(pin_name, cur, None)

    def iterpins(self):
      """Returns a list of pins."""
      return self.load().iteritems()
