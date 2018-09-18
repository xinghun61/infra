# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class BaseBuildModel(ndb.Model):  # pragma: no cover
  """A base class to provide computed properties from the key.

  The computed properties are master name, builder name, and build number.
  Subclasses should set its key as:
    build_key = BaseBuildModel.CreateBuildKey(
        master_name, builder_name, build_number)
    ndb.Key('KindName', build_key, 'Optional_KindName', optional_id, ...)
  """

  # The ID of the buildbucket build this base build represents.
  build_id = ndb.StringProperty(indexed=False)

  @staticmethod
  def CreateBuildKey(master_name, builder_name, build_number):
    return '%s/%s/%s' % (master_name, builder_name, build_number)

  @staticmethod
  def GetBuildInfoFromBuildKey(build_key):
    return build_key.split('/')

  @ndb.ComputedProperty
  def master_name(self):
    return self.key.pairs()[0][1].split('/')[0]

  @ndb.ComputedProperty
  def builder_name(self):
    return self.key.pairs()[0][1].split('/')[1]

  @ndb.ComputedProperty
  def build_number(self):
    return int(self.key.pairs()[0][1].split('/')[2])
