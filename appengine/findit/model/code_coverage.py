# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib

from google.appengine.ext import ndb


class DependencyRepository(ndb.Model):
  # The source absolute path of the checkout into the root repository.
  # Example: "//third_party/pdfium/" for pdfium in a chromium/src checkout.
  path = ndb.StringProperty(indexed=False)

  # The Gitiles hostname, e.g. "pdfium.googlesource.com".
  server_host = ndb.StringProperty(indexed=False)

  # The Gitiles project name, e.g. "pdfium.git".
  project = ndb.StringProperty(indexed=False)

  # The commit hash of the revision.
  revision = ndb.StringProperty(indexed=False)

  @property
  def project_url(self):
    return 'https://%s/%s' % (self.server_host, self.project)


class PostsubmitReport(ndb.Model):
  """Represents a postsubmit code coverage report."""

  server_host = ndb.StringProperty(indexed=True)

  project = ndb.StringProperty(indexed=True)

  revision = ndb.StringProperty(indexed=False)

  commit_position = ndb.IntegerProperty(indexed=True)

  commit_timestamp = ndb.DateTimeProperty(indexed=True)

  # Manifest of all the code checkouts when the coverage report is generated.
  # In descending order by the length of the relative path in the root checkout.
  manifest = ndb.LocalStructuredProperty(
      DependencyRepository, repeated=True, indexed=False)

  summary_metrics = ndb.JsonProperty(indexed=False)

  build_id = ndb.IntegerProperty(indexed=False)

  # Used to control is a report is visible to the users, and the main use cause
  # is to quanrantine a 'bad' report. All the reports are visible to admins.
  visible = ndb.BooleanProperty(indexed=True, default=False)


class PresubmitReport(ndb.Model):
  """Represents a presubmit code coverage report."""

  server_host = ndb.StringProperty(indexed=True)

  project = ndb.StringProperty(indexed=True)

  change = ndb.IntegerProperty(indexed=True)

  patchset = ndb.IntegerProperty(indexed=True)

  build_id = ndb.IntegerProperty(indexed=False)


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
