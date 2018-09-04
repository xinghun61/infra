# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Sources for from where a flake analysis was triggered."""

# An analysis was triggered directly through Findit's UI.
FINDIT_UI = 1

# An analysis was triggered using Findit's API.
FINDIT_API = 2

# An analysis was triggered using Findit's normal analysis pipeline.
FINDIT_PIPELINE = 3

SOURCES_TO_DESCRIPTIONS = {
    FINDIT_UI: 'Findit UI',
    FINDIT_API: 'Findit API',
    FINDIT_PIPELINE: 'Findit pipeline'
}


def GetDescriptionForTriggeringSource(triggering_source, manually_triggered):
  """Returns a human-readable description for where a request came from."""
  template = 'The analysis was triggered %s through %s'

  def _GetTriggeringSourceDescription(triggering_source):
    return SOURCES_TO_DESCRIPTIONS.get(triggering_source,
                                       'other/unknown source')

  def _GetTriggeringUserDescription(manually_triggered):
    return 'manually' if manually_triggered else 'automatically'

  return template % (_GetTriggeringUserDescription(manually_triggered),
                     _GetTriggeringSourceDescription(triggering_source))
