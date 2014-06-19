# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging

from infra.services.gnumbd.support.util import cached_property
from infra.services.gnumbd.support.git import INVALID

LOGGER = logging.getLogger(__name__)

class ConfigRef(object):
  CONVERT = {
    'interval': lambda self, val: float(val),
    'pending_tag_prefix': lambda self, val: str(val),
    'pending_ref_prefix': lambda self, val: str(val),
    'enabled_refglobs': lambda self, val: map(str, list(val)),
  }
  DEFAULTS = {
    'interval': 5.0,
    'pending_tag_prefix': 'refs/pending-tags',
    'pending_ref_prefix': 'refs/pending',
    'enabled_refglobs': [],
  }

  def __init__(self, ref, filename='config.json'):
    self.ref = ref
    self.repo = ref.repo
    self.filename = filename

  def __getitem__(self, key):
    return self.current[key]

  @cached_property
  def current(self):
    cur = self.ref.commit

    while cur is not None and cur is not INVALID:
      LOGGER.debug('Evaluating config at %s:%s', cur.hsh, self.filename)
      try:
        data = self.repo.run('cat-file', 'blob',
                             '%s:%s' % (cur.hsh, self.filename))
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
