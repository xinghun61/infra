# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib

from google.appengine.ext import ndb


class ReportBase(ndb.Model):
  """Holds shared info for both postsubmit and presubmit reports."""

  bucket_name = ndb.StringProperty(indexed=False)

  gs_url = ndb.StringProperty(indexed=False)

  source_and_report_gs_path = ndb.StringProperty(indexed=False)

  build_id = ndb.IntegerProperty(indexed=False)


class PostsubmitReport(ReportBase):
  """Represents a postsubmit code coverage report."""

  server_host = ndb.StringProperty(indexed=True)

  project = ndb.StringProperty(indexed=True)

  revision = ndb.StringProperty(indexed=False)

  commit_position = ndb.IntegerProperty(indexed=True)

  commit_timestamp = ndb.DateTimeProperty(indexed=True)

  summary_metrics = ndb.JsonProperty(indexed=False)


class PresubmitReport(ReportBase):
  """Represents a presubmit code coverage report."""

  server_host = ndb.StringProperty(indexed=True)

  project = ndb.StringProperty(indexed=True)

  change = ndb.IntegerProperty(indexed=True)

  patchset = ndb.IntegerProperty(indexed=True)


class CoverageData(ndb.Model):
  """Represents the code coverage data of a single file or directory."""

  server_host = ndb.StringProperty(indexed=True)

  code_revision_index = ndb.StringProperty(indexed=False)

  data_type = ndb.StringProperty(indexed=True)

  path = ndb.StringProperty(indexed=True)

  data = ndb.JsonProperty(indexed=False, compressed=True)

  @staticmethod
  def _CreateKey(server_host, code_revision_index, data_type, path):
    return hashlib.sha1('%s$%s$%s$%s' % (server_host, code_revision_index,
                                         data_type, path)).hexdigest()

  @classmethod
  def Create(cls, server_host, code_revision_index, data_type, path, data):
    return cls(
        key=ndb.Key(
            cls,
            cls._CreateKey(server_host, code_revision_index, data_type, path)),
        server_host=server_host,
        code_revision_index=code_revision_index,
        path=path,
        data=data)

  @classmethod
  def Get(cls, server_host, code_revision_index, data_type, path):
    return ndb.Key(
        cls, cls._CreateKey(server_host, code_revision_index, data_type,
                            path)).get()
