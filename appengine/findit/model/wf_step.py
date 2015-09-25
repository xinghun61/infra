# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.base_build_model import BaseBuildModel


class WfStep(BaseBuildModel):
  """Represents a step in a build cycle of a builder in a Chromium waterfall.

  'Wf' is short for waterfall.
  """
  log_data = ndb.BlobProperty(indexed=False, compressed=True)
  isolated = ndb.BooleanProperty(default=False)

  @staticmethod
  def _CreateKey(
      master_name, builder_name, build_number, step_name):  # pragma: no cover
    build_id = BaseBuildModel.CreateBuildId(
        master_name, builder_name, build_number)
    return ndb.Key('WfBuild', build_id, 'WfStep', step_name)

  @classmethod
  def Create(
      cls, master_name, builder_name, build_number,
      step_name):  # pragma: no cover
    return cls(key=cls._CreateKey(
                          master_name, builder_name, build_number, step_name))

  @classmethod
  def Get(
      cls, master_name, builder_name, build_number,
      step_name):  # pragma: no cover
    return cls._CreateKey(
        master_name, builder_name, build_number, step_name).get()
