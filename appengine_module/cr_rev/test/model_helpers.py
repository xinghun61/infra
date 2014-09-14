# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file includes common model manipulation functions for tests."""

import json

from datetime import datetime

from appengine_module.cr_rev import models
from protorpc import protojson


def create_project():  # pragma: no cover
  my_project = models.Project()
  my_project.name = 'cool'
  my_project.last_scanned = datetime(1970, 01, 01)
  return my_project


def create_repo():  # pragma: no cover
  my_repo = models.Repo()
  my_repo.repo = 'cool_src'
  my_repo.project = 'cool'
  my_repo.first_commit = 'deadbeef' * 5
  my_repo.latest_commit = 'b0b1beef' * 5
  my_repo.last_scanned = datetime(1970, 01, 01)
  my_repo.active = True
  my_repo.real = True
  my_repo.excluded = True
  return my_repo


def create_commit():  # pragma: no cover
  my_commit = models.RevisionMap()
  my_commit.git_sha = 'b0b1beef' * 5
  my_commit.redirect_url = 'https://crrev.com/%s' % my_commit.git_sha
  my_commit.project = 'cool'
  my_commit.repo = 'cool_src'
  my_commit.number = 100
  my_commit.numberings = [
      models.NumberingMap(
        numbering_type=models.NumberingType.SVN,
        numbering_identifier='svn://svn.cool.org/cool_src',
        number=100
      ),
      models.NumberingMap(
        numbering_type=models.NumberingType.COMMIT_POSITION,
        numbering_identifier='refs/heads/master',
        number=100,
        project='cool',
        repo='cool_src'
      ),
  ]

  return my_commit


def create_numberings():  # pragma: no cover
  git_sha = 'b0b1beef' * 5
  redirect_url = 'https://crrev.com/%s' % git_sha
  numberings = [
      models.NumberingMap(
        numbering_type=models.NumberingType.SVN,
        numbering_identifier='svn://svn.cool.org/cool_src',
        number=100,
        project='cool',
        repo='cool_src',
        git_sha=git_sha,
        redirect_url=redirect_url,
      ),
      models.NumberingMap(
        numbering_type=models.NumberingType.COMMIT_POSITION,
        numbering_identifier='refs/heads/master',
        number=100,
        project='cool',
        repo='cool_src',
        git_sha=git_sha,
        redirect_url=redirect_url,
      ),
  ]

  return numberings


def convert_json_to_model_proto(model, js):  # pragma: no cover
  """Convert a dict returned by a JSON API into a protorpc message."""
  return protojson.decode_message(model.ProtoModel(), json.dumps(js))


def convert_items_to_protos(model, response_json):  # pragma: no cover
  """Convert the 'items' section of a JSON API into protorpc messages."""
  items = response_json['items']
  response_json['items']  = [convert_json_to_model_proto(model, item)
                             for item in items]
  return response_json
