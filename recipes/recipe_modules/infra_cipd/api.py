# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import collections

from recipe_engine import recipe_api


class InfraCIPDApi(recipe_api.RecipeApi):
  """API for building packages defined in infra's public and intenral repos.

  Essentially a shim around scripts in
  https://chromium.googlesource.com/infra/infra.git/+/master/build/
  and its internal counterpart.
  """

  def __init__(self, mastername, buildername, buildnumber, **kwargs):
    super(InfraCIPDApi, self).__init__(**kwargs)
    self._mastername = mastername
    self._buildername = buildername
    self._buildnumber = buildnumber
    self._cur_ctx = None  # (path_to_repo, is_cross_compile)

  @contextlib.contextmanager
  def context(self, path_to_repo, goos=None, goarch=None):
    """Sets context building CIPD packages.

    Arguments:
      path_to_repo (path): path infra or infra_internal repo root dir.
        Expects to find `build/build.py` inside provided dir.
      goos, goarch (str): allows for setting GOOS and GOARCH
        for cross-compiling Go code.

    Doesn't support nesting.
    """
    if self._cur_ctx is not None:  # pragma: no cover
      raise ValueError('Nesting contexts not allowed')
    if bool(goos) != bool(goarch):  # pragma: no cover
      raise ValueError('GOOS and GOARCH must be either both set or both unset')

    env, name_prefix = None, None
    if goos and goarch:
      env = {'GOOS': goos, 'GOARCH': goarch}
      name_prefix ='[GOOS:%s GOARCH:%s]' % (goos, goarch)
    self._cur_ctx = (path_to_repo, (goos and goarch))
    try:
      with self.m.context(env=env, name_prefix=name_prefix):
        yield
    finally:
      self._cur_ctx = None

  @property
  def _ctx_path_to_repo(self):
    if self._cur_ctx is None:  # pragma: no cover
      raise Exception('must be run under infra_cipd.context')
    return self._cur_ctx[0]

  @property
  def _ctx_is_cross_compile(self):
    if self._cur_ctx is None:  # pragma: no cover
      raise Exception('must be run under infra_cipd.context')
    return self._cur_ctx[1]

  def build(self):
    """Builds packages."""
    return self.m.python(
        'cipd - build packages',
        self._ctx_path_to_repo.join('build', 'build.py'),
        ['--builder', self._buildername])

  def test(self, skip_if_cross_compiling=False):
    """Tests previously built packages integrity."""
    if self._ctx_is_cross_compile and skip_if_cross_compiling:
      return None
    return self.m.python(
        'cipd - test packages integrity',
        self._ctx_path_to_repo.join('build', 'test_packages.py'))

  def upload(self, tags, step_test_data=None):
    """Uploads previously built packages."""
    args = []
    if not self.m.runtime.is_luci:
      # TODO(tandrii): get rid of these creds once we are on LUCI.
      args = [
          '--service-account-json',
          self.m.cipd.default_bot_service_account_credentials,
      ]
    args.extend([
      '--no-rebuild',
      '--upload',
      '--json-output', self.m.json.output(),
      '--builder', self._buildername,
      '--tags',
    ])
    args.extend(tags)
    try:
      return self.m.python(
          'cipd - upload packages',
          self._ctx_path_to_repo.join('build', 'build.py'),
          args,
          step_test_data=step_test_data or self.test_api.example_upload,
      )
    finally:
      step_result = self.m.step.active_result
      output = step_result.json.output or {}
      p = step_result.presentation
      for pkg in output.get('succeeded', []):
        info = pkg['info']
        title = '%s %s' % (info['package'], info['instance_id'])
        p.links[title] = info.get(
            'url', 'http://example.com/not-implemented-yet')

  def tags(self, git_repo_url, revision):
    """Returns tags to be attached to uploaded CIPD packages."""
    if self._buildnumber == -1:
      raise ValueError('buildnumbers must be enabled')  # pragma: no cover
    if self.m.runtime.is_luci:
      build_tag_key = 'luci_build'
      bucket = self.m.buildbucket.properties['build']['bucket']
    else:
      # TODO(tandrii): get rid of this once migrated to LUCI.
      build_tag_key = 'buildbot_build'
      assert self._mastername
      bucket = self._mastername
    return [
      '%s:%s/%s/%s' % (
        build_tag_key, bucket, self._buildername, self._buildnumber),
      'git_repository:%s' % git_repo_url,
      'git_revision:%s' % revision,
    ]

