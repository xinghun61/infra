# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.base_build_model import BaseBuildModel


class Step(BaseBuildModel):
  """Represents a step in a build cycle of a builder in a waterfall."""

  @staticmethod
  def CreateKey(
      master_name, builder_name, build_number, step_name):  # pragma: no cover
    build_id = BaseBuildModel.CreateBuildId(
        master_name, builder_name, build_number)
    return ndb.Key('Build', build_id, 'Step', step_name)

  @staticmethod
  def CreateStep(
      master_name, builder_name, build_number, step_name):  # pragma: no cover
    return Step(
        key=Step.CreateKey(master_name, builder_name, build_number, step_name))

  @staticmethod
  def GetStep(
      master_name, builder_name, build_number, step_name):  # pragma: no cover
    return Step.CreateKey(
        master_name, builder_name, build_number, step_name).get()

  log_data = ndb.BlobProperty(indexed=False, compressed=True)
