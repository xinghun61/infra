# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import datetime
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
will *NOT* CQ the change itself, so you must CQ the change manually.
"""
)

COMMIT_MESSAGE_INFO = (
"""

More info is at https://goo.gl/zkKdpD. Use https://goo.gl/noib3a to file a bug
(or complain)

""")

COMMIT_MESSAGE_FOOTER = (
"""
Recipe-Tryjob-Bypass-Reason: Autoroller
Bugdroid-Send-Email: False
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


_AUTH_REFRESH_TOKEN_FLAG = (
    '--auth-refresh-token-json=/creds/refresh_tokens/recipe-roller')


_TIME_FORMAT = '%Y-%m-%dT%H:%M:%S'


_ROLL_STALE_THRESHOLD = datetime.timedelta(hours=2)


def get_commit_message(roll_result, tbrs=()):
  """Construct a roll commit message from 'recipes.py autoroll' result.
  """
  trivial = roll_result['trivial']
  message = 'Roll recipe dependencies (%s).\n' % (
      'trivial' if trivial else 'nontrivial')
  message += COMMIT_MESSAGE_HEADER
  if not trivial:
    message += NON_TRIVIAL_MESSAGE
  message += COMMIT_MESSAGE_INFO

  commit_infos = roll_result['picked_roll_details']['commit_infos']

  message += '%s\n' % '\n'.join(get_blame(commit_infos))
  message += '\n'
  if not trivial:
    message += 'R=%s\n' % ','.join(get_reviewers(commit_infos))
  if tbrs:
    message += 'TBR=%s\n' % ','.join(tbrs)
  message += COMMIT_MESSAGE_FOOTER
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
    # Keep persistent checkout. Speeds up the roller for large repos
    # like chromium/src.
    workdir = self.m.path['cache'].join(
        'recipe_autoroller', project_data['id'])

    self.m.git.checkout(
        project_data['repo_url'], dir_path=workdir, submodules=False,
        use_git_cache=True)

    # Introduce ourselves to git - also needed for git cl upload to work.
    self.m.git(
        'config', 'user.email', 'recipe-roller@chromium.org', cwd=workdir)
    self.m.git('config', 'user.name', 'recipe-roller', cwd=workdir)

    # Clean up possibly left over roll branch. Ignore errors.
    self.m.git('branch', '-D', 'roll', ok_ret='any', cwd=workdir)

    # git cl upload cannot work with detached HEAD, it requires a branch.
    self.m.git('checkout', '-t', '-b', 'roll', 'origin/master', cwd=workdir)

    # Check status of last known CL for this repo. Ensure there's always
    # at most one roll CL in flight.
    repo_data, cl_status = self._get_pending_cl_status(
        project_data['repo_url'], workdir)
    if repo_data:
      last_roll_elapsed = None
      timestamp_str = repo_data.get('last_roll', {}).get('utc_timestamp')
      if timestamp_str:
        last_roll_timestamp = datetime.datetime.strptime(
            timestamp_str, _TIME_FORMAT)
        last_roll_elapsed = self.m.time.utcnow() - last_roll_timestamp

      # Allow trivial rolls in CQ to finish.
      if repo_data['trivial'] and cl_status == 'commit':
        if (last_roll_elapsed and
            last_roll_elapsed > _ROLL_STALE_THRESHOLD):
          self.m.python.failing_step(
              'stale roll',
              'manual intervention needed: automated roll attempt is stale')

        return ROLL_SUCCESS

      # Allow non-trivial rolls to wait for review comments.
      if not repo_data['trivial'] and cl_status != 'closed':
        if (last_roll_elapsed and
            last_roll_elapsed > _ROLL_STALE_THRESHOLD):
          self.m.python.failing_step(
              'stale roll',
              'manual intervention needed: automated roll attempt is stale')

        return ROLL_SUCCESS

      # TODO(phajdan.jr): detect staleness by creating CLs in a loop.
      # It's possible that the roller keeps creating new CLs (especially
      # trivial rolls), but they e.g. fail to land, causing staleness.

      # We're about to upload a new CL, so close the old one.
      # Pass --rietveld flag to match upload args below.
      self.m.git('cl', 'set-close',
                 '--issue', repo_data['issue'],
                 '--rietveld',
                 _AUTH_REFRESH_TOKEN_FLAG, cwd=workdir)

    recipes_cfg_path = workdir.join('infra', 'config', 'recipes.cfg')

    # Use the recipes bootstrap to checkout coverage.
    roll_step = self.m.step(
        'roll',
        [recipes_dir.join('recipes.py'), '--use-bootstrap', '--package',
         recipes_cfg_path, 'autoroll', '--output-json', self.m.json.output()])
    roll_result = roll_step.json.output

    if roll_result['success']:
      self._process_successful_roll(
          project_data['repo_url'], repo_data, roll_step, roll_result, workdir)
      return ROLL_SUCCESS
    else:
      if (not roll_result['roll_details'] and
          not roll_result['rejected_candidates_details']):
        roll_step.presentation.step_text += ' (already at latest revisions)'
        return ROLL_EMPTY
      else:
        candidate_number = 0
        for roll_candidate in roll_result['roll_details']:
          candidate_number += 1

          logs = []
          if 'recipes_simulation_test' in roll_candidate:
            logs.append('recipes_simulation_test (rc=%d):' %
                roll_candidate['recipes_simulation_test']['rc'])
            output = roll_candidate['recipes_simulation_test']['output']
            logs.extend(['  %s' % line for line in output.splitlines()])
          if 'recipes_simulation_test_train' in roll_candidate:
            logs.append('recipes_simulation_test_train (rc=%d):' %
                roll_candidate['recipes_simulation_test_train']['rc'])
            output = roll_candidate['recipes_simulation_test_train']['output']
            logs.extend(['  %s' % line for line in output.splitlines()])

          logs.append('blame:')
          logs.extend(['  %s' % line for line in
                      get_blame(roll_candidate['commit_infos'])])
          roll_step.presentation.logs['candidate #%d' % candidate_number] = logs
        return ROLL_FAILURE

  def _process_successful_roll(
      self, repo_url, original_repo_data, roll_step, roll_result, workdir):
    original_repo_data = original_repo_data or {}

    roll_step.presentation.logs['blame'] = get_blame(
        roll_result['picked_roll_details']['commit_infos'])

    if roll_result['trivial']:
      roll_step.presentation.step_text += ' (trivial)'
    else:
      roll_step.presentation.status = self.m.step.FAILURE

    self.m.git('commit', '-a', '-m', 'roll recipes.cfg', cwd=workdir)

    tbrs = []
    if roll_result['trivial']:
      # Land immediately.
      upload_args = ['--use-commit-queue']
      tbrs = TRIVIAL_ROLL_TBR_EMAILS
    else:
      upload_args = ['--send-mail', '--cq-dry-run']
    upload_args.extend(['--bypass-hooks', '-f'])
    # git cl upload doesn't work yet with gerrit and git cache.
    upload_args.extend(['--rietveld'])
    upload_args.extend([_AUTH_REFRESH_TOKEN_FLAG])
    commit_message = get_commit_message(roll_result, tbrs=tbrs)
    self.m.git_cl.upload(
        commit_message, upload_args, name='git cl upload', cwd=workdir)
    issue_step = self.m.git(
        'cl', 'issue', '--json', self.m.json.output(),
        name='git cl issue',
        cwd=workdir,
        step_test_data=lambda: self.m.json.test_api.output({
            'issue': 123456789,
            'issue_url': 'https://codereview.chromium.org/123456789'}))
    issue_result = issue_step.json.output

    if not issue_result['issue'] or not issue_result['issue_url']:
      self.m.python.failing_step(
          'git cl upload failed', 'no issue metadata returned')

    roll_data = {
      'spec': roll_result['picked_roll_details']['spec'],
      'trivial': roll_result['trivial'],
      'issue': str(issue_result['issue']),
      'issue_url': issue_result['issue_url'],
      'utc_timestamp': self.m.time.utcnow().strftime(_TIME_FORMAT),
    }

    repo_data = {
      'issue': str(issue_result['issue']),
      'issue_url': issue_result['issue_url'],
      'trivial': roll_result['trivial'],
      'last_roll': roll_data,
      'last_trivial': roll_data if roll_result['trivial']
                      else original_repo_data.get('last_trivial'),
      'last_nontrivial': roll_data if not roll_result['trivial']
                         else original_repo_data.get('last_nontrivial'),
    }

    issue_step.presentation.links['Issue %s' % repo_data['issue']] = (
        repo_data['issue_url'])

    self.m.gsutil.upload(
        self.m.json.input(repo_data),
        'recipe-roller-cl-uploads',
        'repo_metadata/%s' % base64.urlsafe_b64encode(repo_url))

  def _get_pending_cl_status(self, repo_url, workdir):
    """Returns (current_repo_data, git_cl_status_string) of the last known
    roll CL for given repo.

    If no such CL has been recorded, returns (None, None).
    """
    cat_result = self.m.gsutil.cat(
        'gs://recipe-roller-cl-uploads/repo_metadata/%s' % (
            base64.urlsafe_b64encode(repo_url)),
        stdout=self.m.raw_io.output(),
        stderr=self.m.raw_io.output(),
        ok_ret=(0,1),
        name='repo_state',
        step_test_data=lambda: self.m.raw_io.test_api.stream_output(
            'No URLs matched', stream='stderr', retcode=1))

    if cat_result.retcode:
      cat_result.presentation.logs['stderr'] = [
          self.m.step.active_result.stderr]
      if not re.search('No URLs matched', cat_result.stderr): # pragma: no cover
        raise Exception('gsutil failed in an unexpected way; see stderr log')
      return None, None

    repo_data = json.loads(cat_result.stdout)
    # TODO(phajdan.jr): remove when all repos have this key.
    if 'issue_url' in repo_data:
      cat_result.presentation.links['Issue %s' % repo_data['issue']] = (
          repo_data['issue_url'])
    if repo_data['trivial']:
      cat_result.presentation.step_text += ' (trivial)'

    status_result = self.m.git(
        'cl', 'status',
        '--issue', repo_data['issue'],
        '--rietveld',
        '--field', 'status',
        _AUTH_REFRESH_TOKEN_FLAG,
        name='git cl status', stdout=self.m.raw_io.output(),
        cwd=workdir,
        step_test_data=lambda: self.m.raw_io.test_api.stream_output(
            'foo')
    ).stdout.strip()

    return repo_data, status_result
