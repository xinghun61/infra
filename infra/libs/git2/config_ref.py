# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging

from infra.libs import git2
from infra.libs.decorators import cached_property

LOGGER = logging.getLogger(__name__)

class ConfigRef(object):
  # {key: lambda self, val: convert(val)}
  CONVERT = {}

  # {key: default_val}
  DEFAULTS = {}

  REF = None

  FILENAME = 'config.json'

  def __init__(self, repo):
    assert self.REF is not None
    self._ref = repo[self.REF]
    self._repo = repo

  # pylint: disable=W0212
  ref = property(lambda self: self._ref)
  repo = property(lambda self: self._repo)

  def __getitem__(self, key):
    return self.current[key]

  @cached_property
  def current(self):
    cur = self.ref.commit

    while cur is not None and cur is not git2.INVALID:
      LOGGER.debug('Evaluating config at %s:%s', cur.hsh, self.FILENAME)
      try:
        data = self.repo.run('cat-file', 'blob',
                             '%s:%s' % (cur.hsh, self.FILENAME))
        data = json.loads(data)
        if not isinstance(data, dict):
          LOGGER.error('Non-dict config: %r', data)
          continue

        ret = {}
        for k, def_v in self.DEFAULTS.iteritems():
          ret[k] = self.CONVERT[k](self, data.get(k, def_v))

        LOGGER.debug('Using configuration at %s: %r', cur.hsh, ret)
        return ret
      except Exception:
        LOGGER.exception('Caught exception while processing')
      finally:
        cur = cur.parent
    LOGGER.warn('Using default config: %r', self.DEFAULTS)
    return dict(self.DEFAULTS)

  def evaluate(self):
    del self.current
    return self.current
