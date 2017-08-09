# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'build/perf_dashboard',
  'depot_tools/bot_update',
  'depot_tools/depot_tools',
  'depot_tools/gclient',
  'depot_tools/git',
  'depot_tools/gsutil',
  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
  'recipe_engine/time',
]


PROPERTIES = {}

# If changing, check https://chromeperf.appspot.com to avoid unintentionally
# overwriting existing data.
PERF_DASHBOARD_KEY = 'infra/luci/isolate/isolate-client-upload'


def RunSteps(api):
  api.gclient.set_config('infra')
  api.bot_update.ensure_checkout()
  api.gclient.runhooks()

  isolate = build_isolate(api)
  # Upload this isolate now in case we need to debug later.
  upload_isolate(api, isolate)

  # Download test data.
  test_dir, test_isolate = download_test_data(api)

  # Get information about commit now in case we need to debug.
  # Note that *commit* timestamps are used by perf dashboard.
  tstamp_unix, tstamp_iso_str, revision = api.git(
      'show', 'HEAD', '--format=%ct %cI %H', '-s',
      name='get commit info',
      stdout=api.raw_io.output(),
      step_test_data=lambda: api.raw_io.test_api.stream_output(
        '1476374537 2016-10-13T18:02:17+02:00 '
        '0123456789abcdeffedcba987654321012345678')
  ).stdout.strip().split()

  start = api.time.time()
  with api.context(cwd=test_dir):
    step_result = api.step('isolate perf',
        [isolate, 'archive', '--verbose',
         # Fake server is listening on localhost in the same process and keeps
         # archieved data in RAM, so don't increase test data size to avoid
         # thrashing.
         '-isolate-server', 'fake',
         '-isolate', test_isolate,
         # TODO(tandrii): maybe read this file and validate resulting hash?
         '-isolated', test_dir.join('result.isolated')
        ],
    )
  taken_seconds = api.time.time() - start
  step_result.presentation.step_text += (
      'Took %6.1f seconds on rev %s committed at %s' %
      (taken_seconds, revision, tstamp_iso_str))
  post_to_perf_dashboard(api, taken_seconds, revision, tstamp_iso_str,
                         tstamp_unix)


def build_isolate(api):
  go_env = api.path['checkout'].join('go', 'env.py')
  go_bin = api.path['checkout'].join('go', 'bin')
  # Make sure we actually build go binary, as opposed to accidentally re-using
  # old data.
  api.file.rmtree('clean go bin', go_bin)
  api.python('go third parties', go_env, ['go', 'version'])
  api.python('build luci-go', go_env,
             ['go', 'install', 'go.chromium.org/luci/client/cmd/...'])
  return api.path.join(go_bin, 'isolate')


def upload_isolate(api, isolate):
  with api.context(env={
      'DEPOT_TOOLS_GSUTIL_BIN_DIR': api.path['cache'].join('gsutil')}):
    api.python(
        'upload go bin',
        api.depot_tools.upload_to_google_storage_path,
        ['-b', 'chromium-luci', isolate])
  sha1 = api.file.read_text(
    'isolate sha1', str(isolate) + '.sha1',
    test_data='0123456789abcdeffedcba987654321012345678')
  api.step.active_result.presentation.step_text = sha1


def download_test_data(api):
  go_perf_data = api.path['checkout'].join('go', 'perf_data')
  test_isolate = go_perf_data.join('test.isolate')
  # test_isolate references huge file.
  huge_file = go_perf_data.join('blink_heap_unittests')

  api.gsutil.download_url('gs://chrome-dumpfiles/ykffaza5vm', test_isolate,
                          name='download test.isolate')
  if 1047258184 != get_file_size(api, 'get huge file size', huge_file):
    api.gsutil.download_url('gs://chrome-dumpfiles/yirqavzhxm', huge_file,
                            name='download huge test file')
  return go_perf_data, test_isolate


def post_to_perf_dashboard(api, taken_seconds, revision, tstamp_iso_str,
                           tstamp_unix):
  point = api.perf_dashboard.get_skeleton_point(
      test=PERF_DASHBOARD_KEY,
      # Chrome has commit position integer which is ever increasing,
      # normal git repos don't, so commit timestamp is used as a rough proxy.
      revision=tstamp_unix,
      value=round(taken_seconds))
  # TODO(tandrii): maybe run several times and compute some kinda errors?
  point['units'] = 's'
  point['supplemental_columns'] = {
    'tstamp': tstamp_iso_str,
    'a_default_rev': 'r_infra_infra_git',
    'r_infra_infra_git': revision,
    # TODO(tandrii): add link with doc about this perf with
    # 'a_infra_uri': '[Overview](link/to/foo.html)'.
  }
  api.perf_dashboard.set_default_config()
  api.perf_dashboard.add_point([point])
  api.perf_dashboard.add_dashboard_link(
      api.step.active_result.presentation,
      PERF_DASHBOARD_KEY,
      tstamp_unix)


def get_file_size(api, name, path):
  """Returns file size if file exists, else None"""
  step = api.python.inline(
      name,
      """
      import os, sys
      print os.stat(sys.argv[1]).st_size if os.path.exists(sys.argv[1]) else -1
      """,
      args=[path],
      stdout=api.raw_io.output(),
      step_test_data=lambda: api.raw_io.test_api.stream_output('-1'),
  )
  size = int(step.stdout.strip())
  if size == -1:
    step.presentation.step_text += 'file %s does not exist' % path
    return None
  step.presentation.step_text += 'file %s has size of %i bytes' % (path, size)
  return int(size)


def GenTests(api):
  yield (
    api.test('infra_win') +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='infra-perf-win',
        buildnumber=123,
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/infra/infra',
    ) +
    api.platform.name('win')
  )
  yield (
    api.test('infra_linux') +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='infra-perf-linux',
        buildnumber=123,
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/infra/infra',
    ) +
    api.platform.name('linux') +
    api.override_step_data('get huge file size',
                           api.raw_io.stream_output('1047258184'))
  )
