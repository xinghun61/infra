# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import re

from recipe_engine.recipe_api import Property

DEPS = [
  'recipe_engine/buildbucket',
  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/raw_io',
  'recipe_engine/step',
  'depot_tools/gclient',
  'depot_tools/git',
  'depot_tools/gitiles',
]

PROPERTIES = {
    'source_repo': Property(
        help='The URL of the repo to be mirrored with submodules'),
    'target_repo': Property(
        help='The URL of the mirror repo to be built/maintained'),
    'extra_submodules': Property(
        default=[],
        help='A list of <path>=<url> strings, indicating extra submodules to '
             'add to the mirror repo.'),
}

COMMIT_USERNAME = 'Submodules bot'
COMMIT_EMAIL_ADDRESS = \
    'infra-codesearch@chops-service-accounts.iam.gserviceaccount.com'

SHA1_RE = re.compile(r'[0-9a-fA-F]{40}')

def RunSteps(api, source_repo, target_repo, extra_submodules):
  _, source_project = api.gitiles.parse_repo_url(source_repo)

  # NOTE: This name must match the definition in cr-buildbucket.cfg. Do not
  # change without adjusting that config to match.
  checkout_dir = api.m.path['cache'].join('codesearch_update_submodules_mirror')
  api.m.file.ensure_directory('Create checkout parent dir', checkout_dir)

  # We assume here that we won't have a mirror for two repos with the same name.
  # If we do, the directories will have the same name. This shouldn't be an
  # issue, but if it is we should add an intermediate directory with an
  # unambiguous name.
  #
  # We want to keep the final component equal to the below, as gclient/DEPS can
  # be sensitive to the name of the directory a repo is checked out to.
  #
  # The slash on the end doesn't make a difference for source_checkout_dir. But
  # it's necessary for the other uses for source_checkout_name, below.
  source_checkout_name = source_project[source_project.rfind('/') + 1:] + '/'
  source_checkout_dir = checkout_dir.join(source_checkout_name)

  # TODO: less hacky way of checking if the dir exists?
  glob = api.m.file.glob_paths('Check for existing source checkout dir',
                               checkout_dir, source_checkout_name)
  if not glob:
    # We don't depend on any particular cwd, as source_checkout_dir is absolute.
    # But we must supply *some* valid path, or it will fail to spawn the
    # process.
    with api.context(cwd=checkout_dir):
      api.git('clone', source_repo, source_checkout_dir)

  # This is implicitly used as the cwd by all the git steps below.
  api.m.path['checkout'] = source_checkout_dir

  api.git('fetch')

  # Discard any commits from previous runs.
  api.git('reset', '--hard', 'origin/master')

  if not ShouldGenerateNewCommit(api, target_repo):
    return

  gclient_spec = ("solutions=[{"
                  "'managed':False,"
                  "'name':'%s',"
                  "'url':'%s',"
                  "'deps_file':'DEPS'}]"
                  % (source_checkout_name, source_repo))
  with api.context(cwd=checkout_dir):
    deps = json.loads(api.gclient('evaluate DEPS',
                                  ['revinfo', '--deps', 'all',
                                   '--ignore-dep-type=cipd',
                                   '--spec', gclient_spec, '--output-json=-'],
                                  stdout=api.raw_io.output_text()).stdout)

  for item in extra_submodules:
    path, url = item.split('=')
    deps[path] = {'url': url, 'rev': 'master'}

  gitmodules_entries = []
  update_index_entries = []
  for path, entry in deps.iteritems():
    url = entry['url']
    rev = entry['rev']
    if rev is None:
      rev = 'master'

    # Filter out any DEPS that point outside of the repo, as there's no way to
    # represent this with submodules.
    #
    # Note that source_checkout_name has a slash on the end, so this will
    # correctly filter out any path which has the checkout name as a prefix.
    # For example, src-internal in the src DEPS file.
    if not path.startswith(source_checkout_name):
      continue
    # Filter out the root repo itself, which shows up for some reason.
    if path == source_checkout_name:
      continue
    # Filter out deps that are nested within other deps. Submodules can't
    # represent this.
    if any(path != other_path and path.startswith(other_path + '/')
           for other_path in deps.iterkeys()):
      continue

    # json.loads returns unicode but the recipe framework can only handle str.
    path = str(path[len(source_checkout_name):])

    path = path.rstrip('/')

    if not SHA1_RE.match(rev):
      if rev.startswith('origin/'):
        rev = rev[len('origin/'):]
      rev = api.git(
          'ls-remote', url, rev,
          stdout=api.raw_io.output_text()).stdout.split()[0]

    update_index_entries.extend(['--cacheinfo', '160000,%s,%s' % (rev, path)])

    gitmodules_entries.append('[submodule "%s"]\n\tpath = %s\n\turl = %s'
                              % (path, path, str(url)))

  # This adds submodule entries to the index without cloning the underlying
  # repository.
  api.git('update-index', '--add', *update_index_entries, name='Add gitlinks')

  api.file.write_text('Write .gitmodules file',
                      source_checkout_dir.join('.gitmodules'),
                      '\n'.join(gitmodules_entries))
  api.git('add', '.gitmodules')

  api.git('-c', 'user.name=%s' % COMMIT_USERNAME,
          '-c', 'user.email=%s' % COMMIT_EMAIL_ADDRESS,
          'commit', '-m', 'Synthetic commit for submodules',
          name='git commit')

  # This branch is used by the log cache job to ensure that the cache point
  # remains reachable even after this recipe runs again - if we put the cache
  # point at HEAD it wouldn't be.
  api.git('branch', '-f', 'master-original', 'HEAD~')

  api.git('push',
          # skip-validation is necessary as without it we cannot push >=10k
          # commits at once.
          '--push-option=skip-validation',
          # We've effectively deleted the commit that was at HEAD before. This
          # means that we've diverged from the remote repo, and hence must do a
          # force push.
          '--force',
          '--all',
          target_repo,
          name='git push --all')
  # You can't use --all and --tags at the same time for some reason.
  # --mirror pushes both, but it also pushes remotes, which we don't want.
  api.git('push', '--tags', target_repo, name='git push --tags')

def ShouldGenerateNewCommit(api, target_repo):
  """
   See if we can avoid running the rest of the recipe, if there's no new
   commits to incorporate into the mirror. We should be conservative in the
   direction of "True" - the worst case is we update the mirror without any new
   commits, which will generate a new synthetic commit (with a different hash
   due to a different timestamp) at the same underlying commit. Unnecessary,
   but harmless.
  """
  with api.step.nest('Check for new commits') as step:
    try:
      commits, _ = api.gitiles.log(
          target_repo,
          'master',
          limit=2,
          step_name='Find latest commit to target repo')
    except api.step.StepFailure:
      # gitiles gives a 404 when making a log request for an empty repo. In
      # this case, we do need to generate a new commit. Of course there are
      # other reasons why this step may fail, but we would rather proceed in
      # those cases than fail in the empty repo case.
      return True

    if commits and commits[0]['author']['name'] == COMMIT_USERNAME:
      latest_real_commit_in_target = commits[1]['commit']
      latest_commit_in_source = api.git(
          'rev-parse', 'master',
          stdout=api.raw_io.output(),
          name='Get latest commit hash in source repo').stdout.strip()
      if latest_real_commit_in_target == latest_commit_in_source:
        step.presentation.step_text = 'no new commits, exiting'
        return False

      # If we get here we'll need to generate a new commit. We don't care
      # whether DEPS has changed, since we always want to include the latest
      # commit in the target repo.
    else:
      # HEAD in the target repo isn't authored by the submodules bot. This means
      # we definitely need to generate a new commit. Either we've never run on
      # this repo or we somehow ended up in an invalid state.
      pass
  return True


fake_src_deps = """
{
  "src/v8": {
    "url": "https://chromium.googlesource.com/v8/v8.git",
    "rev": "4ad2459561d76217c9b7aff412c5c086b491078a"
  },
  "src/buildtools": {
    "url": "https://chromium.googlesource.com/chromium/buildtools.git",
    "rev": "13a00f110ef910a25763346d6538b60f12845656"
  },
  "src-internal": {
    "url": "https://chromi-internal.googlesource.com/chrome/src-internal.git",
    "rev": "34b7d6a218430e7ff716b81854743a30cfbd3967"
  },
  "src/": {
    "url": "https://chromium.googlesource.com/chromium/src.git",
    "rev": null
  }
}
"""

fake_deps_with_symbolic_ref = """
{
  "src/v8": {
    "url": "https://chromium.googlesource.com/v8/v8.git",
    "rev": "origin/master"
  }
}
"""

fake_deps_with_nested_dep = """
{
  "src/third_party/gsutil": {
    "url": "https://chromium.googlesource.com/external/gsutil/src.git",
    "rev": "5cba434b828da428a906c8197a23c9ae120d2636"
  },
  "src/third_party/gsutil/boto": {
    "url": "https://chromium.googlesource.com/external/boto.git",
    "rev": "98fc59a5896f4ea990a4d527548204fed8f06c64"
  }
}
"""

fake_deps_with_trailing_slash = """
{
  "src/v8/": {
    "url": "https://chromium.googlesource.com/v8/v8.git",
    "rev": "4ad2459561d76217c9b7aff412c5c086b491078a"
  }
}
"""

def GenTests(api):
  yield (
      api.test('first_time_running') +
      api.properties(
          source_repo='https://chromium.googlesource.com/chromium/src',
          target_repo='https://chromium.googlesource.com/codesearch/src_mirror'
      ) +
      api.step_data('Check for existing source checkout dir',
                    # Checkout doesn't exist.
                    api.raw_io.stream_output('', stream='stdout')) +
      api.step_data('Check for new commits.Find latest commit to target repo',
                    # No commits in the target repo.
                    api.json.output({'log': []})) +
      api.step_data('gclient evaluate DEPS',
                    api.raw_io.stream_output(fake_src_deps, stream='stdout'))
  )

  yield (
      api.test('existing_checkout_no_new_commits') +
      api.properties(
          source_repo='https://chromium.googlesource.com/chromium/src',
          target_repo='https://chromium.googlesource.com/codesearch/src_mirror'
      ) +
      api.step_data('Check for existing source checkout dir',
                    api.raw_io.stream_output('src', stream='stdout')) +
      api.step_data('Check for new commits.Find latest commit to target repo',
                    api.json.output({'log': [
                        {
                            'commit': 'b' * 40,
                            'author': {'name': COMMIT_USERNAME},
                        },
                        {
                            'commit': 'a' * 40,
                            'author': {'name': 'Someone else'},
                        },
                    ]})) +
      api.step_data(
          'Check for new commits.Get latest commit hash in source repo',
          api.raw_io.stream_output('a' * 40))
  )

  yield (
      api.test('existing_checkout_new_commits') +
      api.properties(
          source_repo='https://chromium.googlesource.com/chromium/src',
          target_repo='https://chromium.googlesource.com/codesearch/src_mirror'
      ) +
      api.step_data('Check for existing source checkout dir',
                    api.raw_io.stream_output('src', stream='stdout')) +
      api.step_data('Check for new commits.Find latest commit to target repo',
                    api.json.output({'log': [
                        {
                            'commit': 'b' * 40,
                            'author': {'name': COMMIT_USERNAME},
                        },
                        {
                            'commit': 'a' * 40,
                            'author': {'name': 'Someone else'},
                        },
                    ]})) +
      api.step_data(
          'Check for new commits.Get latest commit hash in source repo',
          api.raw_io.stream_output('c' * 40)) +
      api.step_data('gclient evaluate DEPS',
                    api.raw_io.stream_output(fake_src_deps, stream='stdout'))
  )

  yield (
      api.test('existing_checkout_latest_commit_not_by_bot') +
      api.properties(
          source_repo='https://chromium.googlesource.com/chromium/src',
          target_repo='https://chromium.googlesource.com/codesearch/src_mirror'
      ) +
      api.step_data('Check for existing source checkout dir',
                    api.raw_io.stream_output('src', stream='stdout')) +
      api.step_data('Check for new commits.Find latest commit to target repo',
                    api.json.output({'log': [
                        {
                            'commit': 'a' * 40,
                            'author': {'name': 'Someone else'},
                        },
                    ]})) +
      api.step_data('gclient evaluate DEPS',
                    api.raw_io.stream_output(fake_src_deps, stream='stdout'))
  )

  yield (
      api.test('existing_checkout_404_from_gitiles_log') +
      api.properties(
          source_repo='https://chromium.googlesource.com/chromium/src',
          target_repo='https://chromium.googlesource.com/codesearch/src_mirror'
      ) +
      api.step_data('Check for existing source checkout dir',
                    api.raw_io.stream_output('src', stream='stdout')) +
      api.step_data('Check for new commits.Find latest commit to target repo',
                    retcode=1) +
      api.step_data('gclient evaluate DEPS',
                    api.raw_io.stream_output(fake_src_deps, stream='stdout'))
  )

  yield (
      api.test('ref_that_needs_resolving') +
      api.properties(
          source_repo='https://chromium.googlesource.com/chromium/src',
          target_repo='https://chromium.googlesource.com/codesearch/src_mirror'
      ) +
      api.step_data('Check for existing source checkout dir',
                    api.raw_io.stream_output('src', stream='stdout')) +
      api.step_data('Check for new commits.Find latest commit to target repo',
                    api.json.output({'log': [
                        {
                            'commit': 'a' * 40,
                            'author': {'name': 'Someone else'},
                        },
                    ]})) +
      api.step_data('gclient evaluate DEPS',
                    api.raw_io.stream_output(fake_deps_with_symbolic_ref,
                                             stream='stdout')) +
      api.step_data('git ls-remote',
                    api.raw_io.stream_output(
                        '91c13923c1d136dc688527fa39583ef61a3277f7\t' +
                        'refs/heads/master',
                        stream='stdout'))
  )

  yield (
      api.test('nested_deps') +
      api.properties(
          source_repo='https://chromium.googlesource.com/chromium/src',
          target_repo='https://chromium.googlesource.com/codesearch/src_mirror'
      ) +
      api.step_data('Check for existing source checkout dir',
                    api.raw_io.stream_output('src', stream='stdout')) +
      api.step_data('Check for new commits.Find latest commit to target repo',
                    api.json.output({'log': [
                        {
                            'commit': 'a' * 40,
                            'author': {'name': 'Someone else'},
                        },
                    ]})) +
      api.step_data('gclient evaluate DEPS',
                    api.raw_io.stream_output(fake_deps_with_nested_dep,
                                             stream='stdout'))
  )

  yield (
      api.test('trailing_slash') +
      api.properties(
          source_repo='https://chromium.googlesource.com/chromium/src',
          target_repo='https://chromium.googlesource.com/codesearch/src_mirror'
      ) +
      api.step_data('Check for existing source checkout dir',
                    api.raw_io.stream_output('src', stream='stdout')) +
      api.step_data('Check for new commits.Find latest commit to target repo',
                    api.json.output({'log': [
                        {
                            'commit': 'a' * 40,
                            'author': {'name': 'Someone else'},
                        },
                    ]})) +
      api.step_data('gclient evaluate DEPS',
                    api.raw_io.stream_output(fake_deps_with_trailing_slash,
                                             stream='stdout'))
  )

  yield (
      api.test('extra_submodule') +
      api.properties(
          source_repo='https://chromium.googlesource.com/chromium/src',
          target_repo='https://chromium.googlesource.com/codesearch/src_mirror',
          extra_submodules=['src/extra=https://extra.googlesource.com/extra']
      ) +
      api.step_data('Check for existing source checkout dir',
                    api.raw_io.stream_output('src', stream='stdout')) +
      api.step_data('Check for new commits.Find latest commit to target repo',
                    api.json.output({'log': [
                        {
                            'commit': 'a' * 40,
                            'author': {'name': 'Someone else'},
                        },
                    ]})) +
      api.step_data('gclient evaluate DEPS',
                    api.raw_io.stream_output(fake_src_deps, stream='stdout')) +
      api.step_data('git ls-remote',
                    api.raw_io.stream_output(
                        'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\t' +
                        'refs/heads/master',
                        stream='stdout'))
  )
