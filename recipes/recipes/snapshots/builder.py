# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'recipe_engine/buildbucket',
  'recipe_engine/cipd',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/step',
]


# Servers to snapshot Machine Provider bots on.
# Each element is a tuple of (Swarming server, Buildbucket server).
SERVERS = [
    ('chromium-swarm-dev', 'cr-buildbucket-dev'),
]

# OSes where snapshotting is allowed.
OSES = set([
    'Ubuntu',
])

# Test data resembling JSON output from "swarming bots" call.
BOTS_TEST_DATA = [
    {
        'bot_id': 'snapshot-me',
        'dimensions': [
            {'key': 'os', 'value': ['Ubuntu', 'Ubuntu-14.04']},
            {'key': 'pool', 'value': ['Chrome']},
        ],
        'machine_type': 'mt',
    },
    {
        'bot_id': 'dont-snapshot-me',
        'dimensions': [
            {'key': 'os', 'value': ['Windows', 'Windows-10']},
            {'key': 'pool', 'value': ['Chrome']},
        ],
        'machine_type': 'mt',
    },
    {
        'bot_id': 'missing-machine-type',
        'dimensions': [
            {'key': 'pool', 'value': ['Chrome']},
        ],
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
  """
  for p in pairs:
    if p['key'] == key:
      return p['value']
  return []


def RunSteps(api):
  packages_dir = api.path['start_dir'].join('packages')
  ensure_file = api.cipd.EnsureFile()
  ensure_file.add_package('infra/tools/luci/swarming/${platform}', 'latest')
  api.cipd.ensure(packages_dir, ensure_file)

  swarming = packages_dir.join('swarming')
  for sw_server, bb_server in SERVERS:
    with api.step.nest(sw_server):
      # Maps machine_type -> (bot_id, pool) of bots to snapshot.
      bots = {}
      res = api.step('bots', [
          swarming,
          'bots',
          '-field', 'items/dimensions',
          '-field', 'items/bot_id',
          '-field', 'items/machine_type',
          '-json', api.json.output(),
          '-mp',
          '-server', '%s.appspot.com' % sw_server,
      ], step_test_data=lambda: api.json.test_api.output(BOTS_TEST_DATA))
      # For each machine_type, pick a bot to snapshot.
      # TODO(smut): Consider exposing machine_type as a dimension.
      # In that case, a specific bot wouldn't need to be chosen.
      for bot in res.json.output:
        # Newly created Machine Provider bots may not have dimensions yet.
        if bot.get('dimensions'):
          # Only consider this bot if it's running a supported OS.
          if set(get_value(bot['dimensions'], 'os')).intersection(OSES):
            # Pool is required, but snapshotting is pool-independent.
            pool = get_value(bot['dimensions'], 'pool')[0]
            # TODO(crbug/723130): Revise for GCE Provider.
            # machine_type is no longer set for any bots.
            if bot.get('machine_type'):
              bots[bot['machine_type']] = (bot['bot_id'], pool)

      api.buildbucket.set_buildbucket_host('%s.appspot.com' % bb_server)
      builds = []
      for mt, (bot, pool) in bots.iteritems():
        builds.append({
            'bucket': 'luci.chromium.cron',
            'parameters': {
                'builder_name': 'Snapshots',
                'properties': {'machine_type': mt},
                'swarming': {
                    'override_builder_cfg': {
                        'dimensions': ['id:%s' % bot, 'pool:%s' % pool],
                    },
                },
            },
            'tags': {'machine_type': mt},
        })
      api.buildbucket.put(builds)


def GenTests(api):
  yield (
    api.test('snapshot') +
    api.platform('linux', 64) +
    api.properties.git_scheduled() +
    api.step_data(
        'chromium-swarm-dev.buildbucket.put',
        stdout=api.json.output({}),
    )
  )
