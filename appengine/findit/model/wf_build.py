# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.base_build_model import BaseBuildModel


class WfBuild(BaseBuildModel):
  """Represents a build cycle of a builder in a Chromium waterfall.

  'Wf' is short for waterfall.
  """

  @staticmethod
  def _CreateKey(master_name, builder_name, build_number):  # pragma: no cover
    return ndb.Key('WfBuild',
                   BaseBuildModel.CreateBuildId(
                       master_name, builder_name, build_number))

  @staticmethod
  def Create(master_name, builder_name, build_number):  # pragma: no cover
    return WfBuild(
        key=WfBuild._CreateKey(master_name, builder_name, build_number))

  @staticmethod
  def Get(master_name, builder_name, build_number):  # pragma: no cover
    return WfBuild._CreateKey(master_name, builder_name, build_number).get()

  data = ndb.JsonProperty(indexed=False, compressed=True)
  last_crawled_time = ndb.DateTimeProperty(indexed=False)

  start_time = ndb.DateTimeProperty(indexed=False)
  completed = ndb.BooleanProperty(default=False, indexed=False)
  result = ndb.IntegerProperty(indexed=False)
