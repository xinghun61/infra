# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

# App Engine source file imports must be relative to their app's root.
# Provide a way to mangle sys.path, but not leave it littered with junk.

# TODO(ojan): This is a stopgap. Come up with a more general solution.

# pylint: disable=W0702

class PathMangler:  # pragma: no cover
  def __init__(self, root):
    self.app_root = root

  def __enter__(self):
    sys.path.append(self.app_root)

    try:
      import model
      reload(model)
    except:
      pass

    try:
      import handlers
      reload(handlers)
    except:
      pass

  def __exit__(self, etype, value, etraceback):
    sys.path.remove(self.app_root)
