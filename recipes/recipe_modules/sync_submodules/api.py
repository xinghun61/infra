# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import config_types
from recipe_engine import recipe_api

COMMIT_MESSAGE = """Update submodule references.

This is an artificial commit to make dependencies specified in the DEPS file
visible to Codesearch.
This commit does not exist in the underlying repository."""


def Humanish(url):
  if url.endswith('.git'):  # pragma: nocover
    url = url[:-4]
  slash = url.rfind('/')
  if slash != -1:
    url = url[slash + 1:]
  return url


# Work around some assertions in config_types.Path.__init__.
class AbsolutePath(config_types.BasePath):
  def __init__(self, path):
    self._path = path

  def resolve(self, test_enabled):
    if test_enabled:
      return "[HACK]"
    return self._path  # pragma: no cover


class SyncSubmodulesApi(recipe_api.RecipeApi):
  def __call__(self, source, dest, source_ref='refs/heads/master',
               dest_ref='refs/heads/master', extra_submodules=None,
               deps_path_prefix=None, enable_recurse_deps=False,
               disable_path_prefix=False):
    """
    Args:
      source: URL of the git repository to mirror.
      dest: URL of the git repository to push to.
      source_ref: git ref in the source repository to checkout.
      dest_ref: git ref in the destination repository to push to.
      extra_submodules: a list of "path=URL" strings.  These are added as extra
          submodules.
      deps_path_prefix: path prefix used to filter out DEPS. DEPS with the
          prefix are included.
      enable_recurse_deps: enable collecting submodules for recurse deps repos
      disable_path_prefix: disable filtering out DEPS by path prefix.
    """

    if extra_submodules is None:  # pragma: nocover
      extra_submodules = []

    if deps_path_prefix is None:
      deps_path_prefix = '%s/' % Humanish(source)

    # remote_run creates a temporary directory for our pwd, but that means big
    # checkouts get thrown away every build, and take 15 minutes to re-fetch
    # even from the cache.
    # The chromium_tests module seems to hack around this by using a
    # 'builder_cache' path, but it's not clear where that's defined.  The
    # infra_paths module mentions it, but I can't figure out where it's
    # instantiated or how it's used.
    # For now, hardcode an absolute path of '/b/build/slave/cache_dir/'.
    sanitized_buildername = ''.join(
        c if c.isalnum() else '_' for c in self.m.properties['buildername'])
    checkout_dir = config_types.Path(AbsolutePath('/b/build/slave/cache_dir/'),
                                     sanitized_buildername)
    self.m.file.ensure_directory('makedirs checkout', checkout_dir)
    self.m.path['checkout'] = checkout_dir

    # Populate the git cache, get the path to the mirror.
    git_cache = self.m.infra_paths.default_git_cache_dir
    self.m.git(
        'cache', 'populate', '--cache-dir=%s' % git_cache, '--ignore-locks',
        source)
    mirror_dir = self.m.git(
        'cache', 'exists', '--cache-dir=%s' % git_cache, '--quiet', source,
        stdout=self.m.raw_io.output(),
        step_test_data=lambda:
            self.m.raw_io.test_api.stream_output('/foo')).stdout.strip()

    # Checkout the source repository.
    self.m.git.checkout(
        mirror_dir, ref=source_ref, dir_path=checkout_dir, submodules=False)

    # Checkout the gitlink overlay repository.
    overlay_repo_dir = self.m.path['start_dir'].join('overlay')
    self.m.git.checkout(
        dest, ref='master', dir_path=overlay_repo_dir, submodules=False)

    # Create submodule references.
    deps2submodules_cmd = [
        'python',
        self.resource('deps2submodules.py'),
        '--path-prefix', deps_path_prefix,
        self.m.path.join(checkout_dir, 'DEPS'),
    ]
    if enable_recurse_deps:
      deps2submodules_cmd.append('--enable-recurse-deps')
    if disable_path_prefix:
      deps2submodules_cmd.append('--disable-path-prefix')
    for extra_submodule in extra_submodules:
      deps2submodules_cmd.extend(['--extra-submodule', extra_submodule])
    with self.m.context(cwd=overlay_repo_dir):
      self.m.step('deps2submodules', deps2submodules_cmd)

      # Check whether deps2submodules changed anything.
      try:
        self.m.git('diff-index', '--quiet', '--cached', 'HEAD')
      except self.m.step.StepFailure as f:
        # An exit code of 1 means there were differences.
        if f.retcode == 1:
          # Commit and push to the destination ref.
          self.m.git('commit', '-m', COMMIT_MESSAGE)
          self.m.git('push', 'origin', 'HEAD:%s' % dest_ref)
        else:
          raise
