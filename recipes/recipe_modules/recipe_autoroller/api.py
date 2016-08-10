# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import json
import re

from recipe_engine import recipe_api


def get_reviewers(commit_infos):
  """Get a set of authors and reviewers from 'recipes.py autoroll' commit infos.
  """
  reviewers = set()
  for commits in commit_infos.values():
    for commit in commits:
      reviewers.add(commit['author'])
  return reviewers


def get_bugs(commit_infos):
  """Return a set of bug IDs from 'recipes.py autoroll' commit infos.
  """
  bugs = set()
  for commits in commit_infos.values():
    for commit in commits:
      for m in re.findall('^BUG=(.*)', commit['message'], re.MULTILINE):
        for s in m.split(','):
          if s:
            bugs.add(s.strip())
  return bugs


def get_blame(commit_infos):
  blame = []
  for project, commits in commit_infos.iteritems():
    blame.append('%s:' % project)
    for commit in commits:
      message = commit['message'].splitlines()
      # TODO(phajdan.jr): truncate long messages.
      message = message[0] if message else 'n/a'
      blame.append('  https://crrev.com/%s %s (%s)' % (
          commit['revision'], message, commit['author']))
  return blame


COMMIT_MESSAGE_HEADER = (
"""
This is an automated CL created by the recipe roller. This CL rolls recipe
changes from upstream projects (e.g. depot_tools) into downstream projects
(e.g. tools/build).
""")


NON_TRIVIAL_MESSAGE = (
"""

Please review the expectation changes, and LGTM as normal. The recipe roller
will *NOT* CQ the change itself, so you must commit the change manually.
"""
)

COMMIT_MESSAGE_FOOTER = (
"""

More info is at https://goo.gl/zkKdpD. Use https://goo.gl/noib3a to file a bug
(or complain)

""")


TRIVIAL_ROLL_TBR_EMAILS = (
    'martiniss@chromium.org',
    'phajdan.jr@chromium.org',
)


# These are different results of a roll attempt:
#   - success means we have a working non-empty roll
#   - empty means the repo is using latest revision of its dependencies
#   - failure means there are roll candidates but none of them are suitable
#     for an automated roll
ROLL_SUCCESS, ROLL_EMPTY, ROLL_FAILURE = range(3)


def get_commit_message(roll_result):
  """Construct a roll commit message from 'recipes.py autoroll' result.
  """
  message = 'Roll recipe dependencies (%s).\n' % (
      'trivial' if roll_result['trivial'] else 'nontrivial')
  message += COMMIT_MESSAGE_HEADER
  if not roll_result['trivial']:
    message += NON_TRIVIAL_MESSAGE
  message += COMMIT_MESSAGE_FOOTER

  commit_infos = roll_result['picked_roll_details']['commit_infos']

  message += '%s\n' % '\n'.join(get_blame(commit_infos))
  message += '\n'
  message += 'R=%s\n' % ','.join(get_reviewers(commit_infos))
  message += 'BUG=%s\n' % ','.join(get_bugs(commit_infos))
  return message


class RecipeAutorollerApi(recipe_api.RecipeApi):
  def prepare_checkout(self): #pragma: no cover
    """Creates a default checkout for the recipe autoroller."""
    # Removed, but keep it here so roll succeeds
    # TODO(martiniss): Delete once safe
    pass


  def roll_projects(self, projects):
    """Attempts to roll each project from the provided list.

    If rolling any of the projects leads to failures, other
    projects are not affected.
    """
    project_data = self.m.luci_config.get_projects()

    self.m.cipd.install_client()
    with self.m.tempfile.temp_dir('recipes') as recipes_dir:
      self.m.cipd.ensure(recipes_dir, {
          'infra/recipes-py': 'latest',
      })

      results = []
      with recipe_api.defer_results():
        for project in projects:
          with self.m.step.nest(str(project)):
            results.append(self._roll_project(
                project_data[project], recipes_dir))

      # We need to unwrap |DeferredResult|s.
      results = [r.get_result() for r in results]

      # Failures to roll are OK as long as at least one of the repos is moving
      # forward. For example, with repos with following dependencies:
      #
      #   A    <- B
      #   A, B <- C
      #
      # New commit in A repo will need to get rolled into B first. However,
      # it'd also appear as a candidate for C roll, leading to a failure there.
      if ROLL_FAILURE in results and ROLL_SUCCESS not in results:
        self.m.python.failing_step(
            'roll result',
            'manual intervention needed: automated roll attempt failed')

  def _roll_project(self, project_data, recipes_dir):
    with self.m.tempfile.temp_dir('roll_%s' % project_data['id']) as workdir:
      self.m.git.checkout(
          project_data['repo_url'], dir_path=workdir, submodules=False,
          use_git_cache=True)

      # Introduce ourselves to git - also needed for git cl upload to work.
      self.m.git(
          'config', 'user.email', 'recipe-roller@chromium.org', cwd=workdir)
      self.m.git('config', 'user.name', 'recipe-roller', cwd=workdir)

      # git cl upload cannot work with detached HEAD, it requires a branch.
      self.m.git('checkout', '-t', '-b', 'roll', 'origin/master', cwd=workdir)

      recipes_cfg_path = workdir.join('infra', 'config', 'recipes.cfg')

      # Use the recipes bootstrap to checkout coverage.
      roll_step = self.m.step(
          'roll',
          [recipes_dir.join('recipes.py'), '--use-bootstrap', '--package',
           recipes_cfg_path, 'autoroll', '--output-json', self.m.json.output()])
      roll_result = roll_step.json.output

      if roll_result['success']:
        self._process_successful_roll(roll_step, roll_result, workdir)
        return ROLL_SUCCESS
      else:
        if (not roll_result['roll_details'] and
            not roll_result['rejected_candidates_details']):
          roll_step.presentation.step_text += ' (already at latest revisions)'
          return ROLL_EMPTY
        else:
          return ROLL_FAILURE

  def _process_successful_roll(self, roll_step, roll_result, workdir):
    roll_step.presentation.logs['blame'] = get_blame(
        roll_result['picked_roll_details']['commit_infos'])

    if roll_result['trivial']:
      roll_step.presentation.step_text += ' (trivial)'
    else:
      roll_step.presentation.status = self.m.step.FAILURE

    # We use recipes.cfg hashes to uniquely identify changes (which might be
    # rebased).
    cfg_contents = roll_result['picked_roll_details']['spec']
    cfg_digest = hashlib.md5(cfg_contents).hexdigest()

    # We use diff hashes to uniquely identify patchsets within a change.
    self.m.git('commit', '-a', '-m', 'roll recipes.cfg', cwd=workdir)
    diff_result = self.m.git(
        'show', '--format=%b',
        stdout=self.m.raw_io.output(),
        cwd=workdir,
        step_test_data=lambda: self.m.raw_io.test_api.stream_output(
            '-some line\n+some other line\n'))
    diff = diff_result.stdout
    diff_result.presentation.logs['output'] = diff.splitlines()
    diff_digest = hashlib.md5(diff).hexdigest()

    # Check if we have uploaded this before.
    need_to_upload = False
    rebase = False
    cat_result = self.m.gsutil.cat(
        'gs://recipe-roller-cl-uploads/%s' % cfg_digest,
        stdout=self.m.raw_io.output(),
        stderr=self.m.raw_io.output(),
        ok_ret=(0,1))

    if cat_result.retcode:
      cat_result.presentation.logs['stderr'] = [
          self.m.step.active_result.stderr]
      assert re.search('No URLs matched', cat_result.stderr), (
          'gsutil failed in an unexpected way; see stderr log')
      # We have never uploaded this change before.
      need_to_upload = True

    if not need_to_upload:
      # We have uploaded before, now let's check the diff hash to see if we
      # have uploaded this patchset before.
      change_data = json.loads(cat_result.stdout)
      cat_result.presentation.links['Issue %s' % change_data['issue']] = (
          change_data['issue_url'])
      # Pass --rietveld flag to match upload args below.
      self.m.git('cl', 'issue', change_data['issue'], '--rietveld', cwd=workdir)
      if change_data['diff_digest'] != diff_digest:
        need_to_upload = True
        rebase = True
      elif roll_result['trivial']:
        # We won't be uploading. Make sure trivial rolls don't get stuck
        # if previous CQ attempt failed because of flake.
        # Pass --rietveld flag to match upload args below.
        self.m.git('cl', 'set-commit', '--rietveld', cwd=workdir)

    if need_to_upload:
      commit_message = (
          'Rebase' if rebase else get_commit_message(roll_result))
      if roll_result['trivial']:
        # Land immediately.
        upload_args = ['--use-commit-queue']
        if not rebase:
          commit_message += '\nTBR=%s\n' % ','.join(TRIVIAL_ROLL_TBR_EMAILS)
      else:
        upload_args = ['--send-mail', '--cq-dry-run']
      upload_args.extend(['--bypass-hooks', '-f'])
      # git cl upload doesn't work yet with gerrit and git cache.
      upload_args.extend(['--rietveld'])
      upload_args.extend([
          '--auth-refresh-token-json=/creds/refresh_tokens/recipe-roller'])
      self.m.git_cl.upload(
          commit_message, upload_args, name='git cl upload', cwd=workdir)
      issue_result = self.m.git(
          'cl', 'issue',
          name='git cl issue', stdout=self.m.raw_io.output(),
          cwd=workdir,
          step_test_data=lambda: self.m.raw_io.test_api.stream_output(
              'Issue number: '
              '123456789 (https://codereview.chromium.org/123456789)'))

      m = re.match('Issue number: (\d+) \((\S*)\)', issue_result.stdout.strip())
      if not m:
        self.m.python.failing_step(
            'git cl upload failed', 'git cl issue output "%s" is not valid' %
                                    issue_result.stdout.strip())

      change_data = {
        'issue': m.group(1),
        'issue_url': m.group(2),
        'diff_digest': diff_digest,
      }
      issue_result.presentation.links['Issue %s' % change_data['issue']] = (
          change_data['issue_url'])
      self.m.gsutil.upload(
          self.m.json.input(change_data),
          'recipe-roller-cl-uploads',
          cfg_digest)
