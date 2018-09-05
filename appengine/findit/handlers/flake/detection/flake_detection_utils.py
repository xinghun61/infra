# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Util functions for flake detection handlers."""

from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)


def GetFlakeInformation(flake, max_occurrence_count, with_occurrences=True):
  """Gets information for a detected flakes.
  Gets occurrences of the flake and the attached monorail issue.

  Args:
    flake(Flake): Flake object for a flaky test.
    max_occurrence_count(int): Maximum number of occurrences to fetch.
    with_occurrences(bool): If the flake must be with occurrences or not.
      For flakes reported by Flake detection, there should always be
      occurrences, but it's not always true for flakes reported by
      Flake Analyzer, ignore those flakes for now.

  Returns:
    flake_dict(dict): A dict of information for the test. Including data from
    its Flake entity, its flake issue information and information of all its
    flake occurrences.
  """
  flake_dict = flake.to_dict()

  occurrences = CQFalseRejectionFlakeOccurrence.query(ancestor=flake.key).order(
      -CQFalseRejectionFlakeOccurrence.time_happened).fetch(
          max_occurrence_count)

  if not occurrences and with_occurrences:
    # Flake must be with occurrences, but there is no occurrence, bail out.
    return None

  flake_dict['occurrences'] = [
      occurrence.to_dict() for occurrence in occurrences
  ]

  # JavaScript numbers are always stored as double precision floating point
  # numbers, where the number (the fraction) is stored in bits 0 to 51, the
  # exponent in bits 52 to 62, and the sign in bit 63. So integers are
  # accurate up to 15 digits. To keep the precision of build ids (int 64),
  # convert them to string before rendering HTML pages.
  for occurrence in flake_dict['occurrences']:
    occurrence['build_id'] = str(occurrence['build_id'])
    occurrence['reference_succeeded_build_id'] = str(
        occurrence['reference_succeeded_build_id'])

  if flake.flake_issue_key:
    flake_issue = flake.flake_issue_key.get()
    flake_dict['flake_issue'] = flake_issue.to_dict()
    flake_dict['flake_issue']['issue_link'] = FlakeIssue.GetLinkForIssue(
        flake_issue.monorail_project, flake_issue.issue_id)

  return flake_dict
