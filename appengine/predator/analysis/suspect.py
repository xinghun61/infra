# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple

from libs.gitiles.commit_util import DistanceBetweenLineRanges


# TODO(wrengr): maybe break this into separate unanalyzed suspect,
# and analyzed suspect; so we can distinguish the input to
# ``ChangelistClassifier`` from the output of it (which will amend each
# suspect with extra metadata like the confidence and reasons).
class Suspect(object):
  """A suspected changelog to be classified as a possible ``Culprit``.

  That is, for each ``CrashReport`` the ``Predator.FindCulprit`` method
  receives, it will generate a bunch of these suspects and then inspect
  them to determine the ``Culprit`` it returns.
  """

  def __init__(self, changelog, dep_path,
               confidence=None, reasons=None, changed_files=None):
    if not isinstance(confidence, (int, float, type(None))): # pragma: no cover
      raise TypeError(
          'In the ``confidence`` argument to the Suspect constructor, '
          'expected a number or None, but got a %s object instead.'
          % confidence.__class__.__name__)
    self.changelog = changelog
    self.dep_path = dep_path
    self.confidence = None if confidence is None else float(confidence)
    self.reasons = reasons
    self.changed_files = changed_files

  def ToDict(self):
    return {
        'url': self.changelog.commit_url,
        'review_url': self.changelog.code_review_url,
        'revision': self.changelog.revision,
        'project_path': self.dep_path,
        'author': self.changelog.author.email,
        'time': str(self.changelog.author.time),
        'reasons': self.reasons,
        'changed_files': self.changed_files,
        'confidence': self.confidence,
    }

  def ToString(self):
    return str(self.ToDict())

  def __str__(self):
    return self.ToString()
