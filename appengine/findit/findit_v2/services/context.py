# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs.structured_object import StructuredObject


class Context(StructuredObject):
  """This class defines the context within which an analysis is run.

  Currently, its main goal is to scope the analysis/data for a specific project
  so that Findit can be more general to support multiple projects.
  """

  # The Luci project name as defined by Buildbucket, e.g. "chromium".
  luci_project_name = basestring

  # The hostname of the gitiles server that hosts the source code,
  # e.g. chromium.googlesource.com
  gitiles_host = basestring

  # The project name in the gitiles server for the code base, e.g.
  # "chromum/src".
  gitiles_project = basestring

  # The ref in the gitiles project/server for the code, e.g. "ref/heads/master".
  gitiles_ref = basestring

  # The sha of a gitiles commit.
  gitiles_id = basestring
