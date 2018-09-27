# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'recipe_engine/cipd',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/step',
]


# Swarming servers to snapshot Machine Provider bots on.
SERVERS = [
    'chromium-swarm-dev',
]

# OSes where snapshotting is allowed.
OSES = set([
    'Ubuntu',
])

# Test data resembling JSON output from "swarming bots" call.
BOTS_TEST_DATA = [
    {
        'bot_id': 'snapshot-me',
        'dimensions': [{'key': 'os', 'value': ['Ubuntu', 'Ubuntu-14.04']}],
        'machine_type': 'mt',
    },
    {
        'bot_id': 'dont-snapshot-me',
        'dimensions': [{'key': 'os', 'value': ['Windows', 'Windows-10']}],
        'machine_type': 'mt',
    },
]


def get_value(pairs, key):
  """Returns a the value for the given key in the given pairs.

  Args:
    pairs: A list of {"key": key, "value": value} dicts.
    key: A key whose value to get. If the key appears more than once, only
      the first value is returned.

  Returns:
    The value for the given key.

  Raises:
    ValueError: If the key doesn't exist.
  """
  for p in pairs:
    if p['key'] == key:
      return p['value']
  raise ValueError # pragma: no cover


def RunSteps(api):
  packages_dir = api.path['start_dir'].join('packages')
  ensure_file = api.cipd.EnsureFile()
  ensure_file.add_package('infra/tools/luci/swarming/${platform}', 'latest')
  api.cipd.ensure(packages_dir, ensure_file)

  swarming = packages_dir.join('swarming')
  for server in SERVERS:
    with api.step.nest(server):
      # Maps machine_type -> bot_id of bots to snapshot.
      bots = {}
      res = api.step('bots', [
          swarming,
          'bots',
          '-field', 'items/dimensions',
          '-field', 'items/bot_id',
          '-field', 'items/machine_type',
          '-json', api.json.output(),
          '-mp',
          '-server', '%s.appspot.com' % server,
      ], step_test_data=lambda: api.json.test_api.output(BOTS_TEST_DATA))
      # For each machine_type, pick a bot to snapshot.
      # TODO(smut): Consider exposing machine_type as a dimension.
      # In that case, a specific bot wouldn't need to be chosen.
      for bot in res.json.output:
        # Only consider this bot if it's running supported OS.
        if set(get_value(bot['dimensions'], 'os')).intersection(OSES):
          bots[bot['machine_type']] = bot['bot_id']

      for mt, bot in bots.iteritems():
        api.step('machine type: %s' % mt, ['echo', bot])


def GenTests(api):
  yield (
    api.test('snapshot') +
    api.platform('linux', 64) +
    api.properties.git_scheduled(
        buildername='snapshot',
    )
  )
