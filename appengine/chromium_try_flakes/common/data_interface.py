# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import zlib

from google.appengine.ext import ndb

from model.flake import Cache, CacheAncestor


# Ignore FlakeTypes with less than MIN_NUMBER_OF_FLAKES occurrences.
MIN_NUMBER_OF_FLAKES = 3


def _split_list(row, position):
  return tuple(row[:position]), row[position]


def _get_cache_ancestor_key():
  ancestor_key = ndb.Key('CacheAncestor', 'singleton')
  if ancestor_key.get():
    return ancestor_key
  return CacheAncestor(key=ancestor_key).put()
