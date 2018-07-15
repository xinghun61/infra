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


class SyncSubmodulesApi(recipe_api.RecipeApi):
  def __call__(self, source, dest, source_ref='refs/heads/master',
               dest_ref='refs/heads/master', extra_submodules=None,
               deps_path_prefix=None,
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
      disable_path_prefix: disable filtering out DEPS by path prefix.
    """

    if extra_submodules is None:  # pragma: nocover
      extra_submodules = []

    solution_name = Humanish(source)
    if deps_path_prefix is None:
      deps_path_prefix = '%s/' % solution_name

    sanitized_buildername = ''.join(
        c if c.isalnum() else '_' for c in self.m.properties['buildername'])
    checkout_dir = self.m.path['cache'].join(sanitized_buildername)
    self.m.file.ensure_directory('makedirs checkout', checkout_dir)
    self.m.path['checkout'] = checkout_dir

    # Populate the git cache, get the path to the mirror.
    git_cache = self.m.infra_paths.default_git_cache_dir

    with self.m.context(cwd=checkout_dir):
      # Retrieve/refresh the source solution.
      self.m.gclient.use_mirror = True
      src_cfg = self.m.gclient.make_config(CACHE_DIR=git_cache)
      # Target every OS. This enables us to check out most of the conditional
      # dependencies in the DEPS file so they can be shown in Code Search.
      # TODO(crbug.com/860379): Remove this once we can tell gclient to evaluate
      # all dependencies regardless of conditions.
      src_cfg.target_os = [
          'android', 'chromeos', 'fuchsia', 'ios', 'unix', 'mac', 'win']
      soln = src_cfg.solutions.add()
      soln.name = solution_name
      soln.url = source
      self.m.gclient.c = src_cfg
      self.m.bot_update.ensure_checkout()

      revinfo_params = ['revinfo', '--output-json', self.m.json.output(),
                        '--ignore-dep-type=cipd']
      revinfo_step = self.m.gclient('get revinfo', revinfo_params)

    # Checkout the gitlink overlay repository.
    overlay_repo_dir = self.m.path['start_dir'].join('overlay')
    self.m.git.checkout(
        dest, ref='master', dir_path=overlay_repo_dir, submodules=False)

    # Create submodule references.
    deps2submodules_cmd = [
        'python',
        self.resource('deps2submodules.py'),
        '--path-prefix', deps_path_prefix,
        self.m.json.input(revinfo_step.json.output),
    ]
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
          # TODO(hinoka): Delete after luci migration
          if self.m.runtime.is_experimental:
            self.m.git('push', 'origin', '--dry-run', 'HEAD:%s' % dest_ref)
          else:
            self.m.git('push', 'origin', 'HEAD:%s' % dest_ref)
        else:
          raise
