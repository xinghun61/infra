# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


################################################################################
# Base Class
################################################################################

class Alterable(object):
  def to_dict(self):  # pragma: no cover
    """The shallow dictionary representation of this object (i.e. the dictionary
    may contain Alterable instances as values)."""
    raise NotImplementedError()

  def alter(self, **kwargs):  # pragma: no cover
    """Returns a copy of self, except with the fields listed in kwargs replaced
    with new values."""
    raise NotImplementedError()

  @classmethod
  def from_raw(cls, data):  # pragma: no cover
    """Construct an instance of this class from a string."""
    raise NotImplementedError()
