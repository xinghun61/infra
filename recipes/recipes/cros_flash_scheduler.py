# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This recipe is used to keep Chrome's pools of CrOS DUTs up to date.

It does so by launching tasks into the DUT pools which flash the devices.
When ran, this recipe aims to get a portion of a given pool on the latest
CHROMEOS_LKGM version. It will never flash more than a third of the pool at a
single time. This is to ensure the remainder of the pool is online for tests.
Consequently, this recipe will need to be run multiple times to upgrade the
entire pool.

This recipe is intended to run several times during MTV's off-peak hours. Its
builder should be backed by a single thin Ubuntu VM, while the tasks it launches
run the cros_flash recipe and run on DUT swarming bots.
"""

from collections import defaultdict

import base64
import math
import re

from recipe_engine import post_process
from recipe_engine.config import Single
from recipe_engine.recipe_api import Property

DEPS = [
  'build/swarming_client',
  'depot_tools/gitiles',
  'depot_tools/gsutil',
  'recipe_engine/buildbucket',
  'recipe_engine/context',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
  'recipe_engine/tempfile',
]

# The gitiles url of the CHROMEOS_LKGM file. This file represents the latest
# version of ChromeOS compatible with Chromium's trunk. The contents of this
# file control what version of CrOS to flash the DUT pools to.
CHROMEOS_LKGM_REPO_URL = 'https://chromium.googlesource.com/chromium/src'
CHROMEOS_LKGM_FILE_PATH = 'chromeos/CHROMEOS_LKGM'

# Should match something that looks like "12345.0.0".
LKGM_RE = re.compile(r'\d+\.\d+\.\d+')

# GS bucket that stores test images for all CrOS boards.
CHROMEOS_IMAGE_BUCKET = 'chromeos-image-archive'

PROPERTIES = {
  'swarming_server': Property(
      kind=str,
      help='Swarming server of the DUT pool to flash.'),
  'swarming_pool': Property(
      kind=str,
      help='Swarming pool of the DUT pool to flash.'),
  'device_type': Property(
      kind=str,
      help='DUT type (ie: CrOS board) of the DUT pool to flash.'),
  'bb_host': Property(
      kind=str,
      help='Buildbucket host to use when triggering flashing jobs.',
      default=None),
  'random_seed': Property(
      kind=Single((int, float)),
      help='Random seed to set when selected a subset of bots to flash.',
      default=None),
  'flashing_builder': Property(
      kind=str,
      help='Name of the builder that does the flashing task',
      default='cros-dut-flash'),
  'flashing_builder_bucket': Property(
      kind=str,
      help='Bucket containing the flashing builder',
      default='luci.infra.cron'),
  'image_type': Property(
      kind=str,
      help='Type of image to be flashed [release, release-tryjob, full, etc.]',
      default='full'),
  'jobs_per_host': Property(
      kind=int,
      help='Maximum number of host jobs that a host can execute concurrently.',
      # Currently available hosts in the lab happen to be dell servers running
      # on Intel Xeon CPUs, which can flash 3 bots in parallel. This value was
      # determined experimentally and increasing it might lead to flaky flash
      # jobs.
      default=3),
}


def get_bots_in_pool(api, swarming_server, pool, device_type):
  """Returns the list of bots that belong to the given pool.

  This uses swarming.py's bot/list query, and returns the resulting bots.
  """
  # TODO(crbug.com/866062): Pass down a service account if a pool ever needs it.
  cmd = [
    'query',
    '-S', swarming_server,
    'bots/list?dimensions=device_type:%s&dimensions=pool:%s' % (
        device_type, pool)
  ]
  result = api.python('get all bots',
      api.swarming_client.path.join('swarming.py'),
      cmd, stdout=api.json.output())
  if not result.stdout or not result.stdout.get('items', []):
    result.presentation.status = api.step.WARNING
    return [], result
  all_bots = [
      DUTBot(swarming_server, bot_dict) for bot_dict in result.stdout['items']
  ]
  result.presentation.logs['found %d bots' % len(all_bots)] = (
      b.id for b in all_bots)
  return all_bots, result


class DUTBot(object):

  def __init__(self, swarming_url, swarming_dict):
    self.swarming_url = swarming_url
    self._parse_swarming_dict(swarming_dict)

  def _parse_swarming_dict(self, swarming_dict):
    self.id = swarming_dict['bot_id']
    self.is_unhealthy = swarming_dict['quarantined'] or swarming_dict['is_dead']
    self.os = 'unknown'
    # Swarming returns a bot's dimensions as a list of dicts like:
    # { 'key': 'dimension_name', 'value': ['dimension_value'] } ... 🤷
    for d in swarming_dict['dimensions']:
      if d['key'] == 'device_os':
        self.os = d['value'][0]
        break
    # The only available place where host is referenced is 'authenticated_as'
    # TODO: Add 'parent_name' field to bots dimensions (crbug.com/953107)
    self.parent = swarming_dict['authenticated_as']

  def update_status(self, api):
    cmd = [
      'query',
      '-S', self.swarming_url,
      'bot/%s/get' % self.id,
    ]
    result = api.python('get status of %s' % self.id,
        api.swarming_client.path.join('swarming.py'),
        cmd, stdout=api.json.output())
    self._parse_swarming_dict(result.stdout)


def get_closest_available_version(api, board, image_type, lkgm_base):
  """Returns the GS path of the latest image for the given board and lkgm.

  This finds the first LATEST-$lkgm file in GS closest to the current lkgm.
  It'll decrement the lkgm until it finds one, up to 100 attempts. This logic
  is taken from:
  https://codesearch.chromium.org/chromium/src/third_party/chromite/cli/cros/cros_chrome_sdk.py?rcl=63924982b3fdaf3c313e0052fe0c07dae5e4628a&l=350

  Once it finds a valid LATEST-$lkgm file, it returns its contents appended
  to the board's directory in the GS image bucket, which contains the images
  built for that board at that version.
  (eg: gs://chromeos-image-archive/kevin-full/R72-11244.0.0-rc2/)

  Returns tuple of:
    The 5-digit manifest for the latest image.
    GS path for the latest image.
  """
  board += '-' + image_type
  gs_path_prefix = 'gs://%s/%s/' % (CHROMEOS_IMAGE_BUCKET, board)
  with api.step.nest('find latest image at %s' % lkgm_base):
    # Occasionally an image won't be available for the board at the current
    # LKGM. So start decrementing the version until we find one that's
    # available.
    lkgm_base = int(lkgm_base)
    for candidate_version in xrange(lkgm_base, lkgm_base-100, -1):
      full_version_file_path = gs_path_prefix + 'LATEST-%d.0.0' % (
          candidate_version)
      try:
        # Only retry the gsutil calls for the first 5 attempts.
        should_retry = candidate_version > lkgm_base - 5
        result = api.gsutil.cat(
            full_version_file_path, name='cat LATEST-%d' % candidate_version,
            use_retry_wrapper=should_retry, stdout=api.raw_io.output(),
            infra_step=False)
        return str(candidate_version), gs_path_prefix + result.stdout.strip()
      except api.step.StepFailure:
        pass  # Gracefully skip 404s.
  return None, None


def trigger_flash(api, bot, gs_image_path, flashing_builder,
                  flashing_builder_bucket):
  build_req = {
    'bucket': flashing_builder_bucket,
    'parameters': {
      'builder_name': flashing_builder,
      'properties': {
        'gs_image_bucket': CHROMEOS_IMAGE_BUCKET,
        # gs_image_path expects everything to the right of the bucket name
        'gs_image_path': gs_image_path.split(CHROMEOS_IMAGE_BUCKET+'/')[1],
      },
      'swarming': {
        'override_builder_cfg': {
          'dimensions': [
            'id:%s' % bot.id,
            # Append the device's current OS to the request. This
            # ensures that if its OS changes unexpectedly, we don't
            # overwrite it.
            'device_os:%s' % bot.os,
          ],
        },
      },
    },
  }
  result = api.buildbucket.put([build_req], name=bot.id)
  build_id = result.stdout['results'][0]['build']['id']
  build_url = result.stdout['results'][0]['build']['url']
  result.presentation.links[build_id] = build_url
  return build_id


def RunSteps(api, swarming_server, swarming_pool, device_type, bb_host,
             random_seed, flashing_builder, flashing_builder_bucket,
             image_type, jobs_per_host):
  # Recipe-runtime import of random to avoid "Non-whitelisted" recipe errors.
  # TODO(crbug.com/913124): Remove this.
  import random

  api.swarming_client.checkout(revision='master')

  if bb_host:
    api.buildbucket.set_buildbucket_host(bb_host)

  if random_seed:
    random.seed(int(random_seed))

  # Curl the current CHROMEOS_LKGM pin. Don't bother with a full chromium
  # checkout since all we need is that one file.
  lkgm = api.gitiles.download_file(
      CHROMEOS_LKGM_REPO_URL, CHROMEOS_LKGM_FILE_PATH,
      step_name='fetch CHROMEOS_LKGM')
  if not LKGM_RE.match(lkgm):
    api.python.failing_step('unknown CHROMEOS_LKGM format',
        'The only supported format for the LKGM file is "12345.0.0". Its '
        'contents currently are "%s".' % lkgm)
  api.step.active_result.presentation.step_text = 'current LKGM: %s ' % lkgm
  lkgm_base = lkgm.split('.')[0]

  # Fetch the full path in GS for the board at the current lkgm.
  latest_version_base, latest_version_gs_path = get_closest_available_version(
      api, device_type, image_type, lkgm_base)
  if not latest_version_gs_path:
    api.python.failing_step('no available image at %s' % lkgm, '')
  gs_image_path = latest_version_gs_path + '/chromiumos_test_image.tar.xz'
  # Do a quick GS ls to ensure the image path exists.
  api.gsutil.list(gs_image_path, name='ls ' + gs_image_path)

  # Collect the number of bots in the pool that need to be flashed.
  all_bots, step_result = get_bots_in_pool(
      api, swarming_server, swarming_pool, device_type)
  if not all_bots:
    api.python.failing_step('no bots online', '')
  unhealthy_bots = []
  up_to_date_bots = []
  out_of_date_bots = []
  for bot in all_bots:
    if bot.is_unhealthy:
      unhealthy_bots.append(bot)
      continue
    if bot.os != latest_version_base:
      out_of_date_bots.append(bot)
    else:
      up_to_date_bots.append(bot)

  # Add logs entries that list all bots that belong to each category.
  if unhealthy_bots:
    step_result.presentation.logs['unhealthy bots'] = (
        b.id for b in unhealthy_bots)
  if up_to_date_bots:
    step_result.presentation.logs['up to date bots'] = (
        b.id for b in up_to_date_bots)
  if out_of_date_bots:
    step_result.presentation.logs['out of date bots'] = (
        b.id for b in out_of_date_bots)
  else:
    step_result.presentation.logs['all bots up to date!'] = [
        'No flashes are necessary since all bots are up to date.']
    return

  # Select a subset of bots to flash such that at least 67% of the pool stays
  # online for the tests to run. Bots are selected randomly with two
  # constraints
  #   1. No host can flash more than jobs_per_host number of devicecs at once.
  #   2. Cannot have more than 33% of bots being flashed at any given time.
  out_of_date_bots_per_host = defaultdict(list)
  bots_to_flash = list()
  for bot in out_of_date_bots:
    out_of_date_bots_per_host[bot.parent].append(bot)

  for host in out_of_date_bots_per_host:
    # If the host has greater than jobs_per_host to be flashed, randomly
    # sample the bots.
    if len(out_of_date_bots_per_host[host]) > jobs_per_host:
      subset = random.sample(out_of_date_bots_per_host[host], jobs_per_host)
      step_result.presentation.logs['dropped bots from {}'.format(host)] = (
          bot.id for bot in (set(out_of_date_bots_per_host[host]) -
                             set(subset)))
      out_of_date_bots_per_host[host] = subset

  num_available_bots = len(up_to_date_bots) + len(out_of_date_bots)
  # 33% of available bots or minimum of 1 bot
  max_num_to_flash = max(num_available_bots / 3, 1)
  for bot_list in out_of_date_bots_per_host.itervalues():
    bots_to_flash.extend(bot_list)

  # If the number of bots selected to flash is greater than 33% of available
  # bots then randomly sample the required number of bots
  if len(bots_to_flash) > max_num_to_flash:
    bots_to_flash = random.sample(bots_to_flash, max_num_to_flash)

  flashing_requests = set()
  with api.step.nest('flash bots'):
    for bot in bots_to_flash:
      flashing_requests.add(
          trigger_flash(api, bot, gs_image_path, flashing_builder,
                        flashing_builder_bucket))

  # Wait for all the flashing jobs. Nest it under a single step since there
  # will be several buildbucket.get_build() step calls.
  finished_builds = []
  with api.step.nest('wait for %d flashing jobs' % len(flashing_requests)):
    # Sleep indefinitely if the jobs never finish. Let swarming's task timeout
    # kill us if we won't exit.
    i = 0
    while flashing_requests:
      api.python.inline('1 min sleep #%d' % i, 'import time; time.sleep(60)')
      i += 1
      for build in flashing_requests.copy():
        result = api.buildbucket.get_build(build)
        if result.stdout['build']['status'] == 'COMPLETED':
          finished_builds.append(result.stdout['build'])
          flashing_requests.remove(build)

  # Add a no-op step that lists pass/fail results for each flashing job.
  failed_jobs = []
  step_result = api.step('collect flashing results', cmd=None)
  for build in finished_builds:
    if build['result'] == 'SUCCESS':
      step_result.presentation.links['%s (passed)' % build['id']] = build['url']
    else:
      step_result.presentation.links['%s (failed)' % build['id']] = build['url']
      failed_jobs.append(build)

  # Quit early if more than half of the flashing requests failed. Some may fail
  # transiently, so continue on in that case, and they'll be retried in
  # subsequent runs.
  max_allowed_failing = math.ceil(len(finished_builds) / 2.0)
  if len(failed_jobs) >= max_allowed_failing:
    api.python.failing_step('failed %d flashing jobs' % len(failed_jobs),
        'Max allowed failures of %d was exceeded. These failures are:\n%s' % (
            max_allowed_failing, '\n'.join(j['url'] for j in failed_jobs)))

  # Wait for all the bots that were flashed to come back up and report healthy.
  with api.step.nest('wait for bots to become available again'):
    # Wait at most 10 min.
    for i in xrange(10):
      for b in bots_to_flash:
        b.update_status(api)
      if any(b.is_unhealthy or b.os != latest_version_base
                 for b in bots_to_flash):
        api.python.inline('1 min sleep #%d' % i, 'import time; time.sleep(60)')
      else:
        break

  # Fail the recipe if any bot wasn't safely flashed.
  unhealthy_bots = [b.id for b in bots_to_flash if b.is_unhealthy]
  if unhealthy_bots:
    api.python.failing_step(
        '%d bots dropped offline after the flash' % len(unhealthy_bots),
        'The following bots were flashed but have not come back up: %s' % (
            unhealthy_bots))

  # We did it! Now trigger ourselves again with the same properties to finish
  # flashing the remaining bots. Use this chained triggering instead of a
  # single loop to make the guts of this recipe a bit simpler.
  build_req = {
    'bucket': api.buildbucket.bucket_v1,
    'parameters': {
      'builder_name': api.buildbucket.builder_name,
      'properties': {
        'swarming_server': swarming_server,
        'swarming_pool': swarming_pool,
        'device_type': device_type,
        'flashing_builder': flashing_builder,
        'flashing_builder_bucket': flashing_builder_bucket,
      },
    },
  }
  if bb_host:
    build_req['parameters']['properties']['bb_host'] = bb_host
  result = api.buildbucket.put([build_req], name='retrigger myself')
  build_id = result.stdout['results'][0]['build']['id']
  build_url = result.stdout['results'][0]['build']['url']
  result.presentation.links[build_id] = build_url


def GenTests(api):
  def bot_json(parent, bot_id, os, quarantined=False):
    return {
      'authenticated_as': 'bot:' + parent,
      'bot_id': bot_id,
      'quarantined': quarantined,
      'is_dead': False,
      'dimensions': [
        {
          'key': 'device_os',
          'value': [os],
        }
      ]
    }

  def bb_json_get(build_id, finished=True, result='SUCCESS'):
    build = {
      'build': {
        'id': build_id,
        'status': 'COMPLETED' if finished else 'RUNNING',
        'url': 'https://some.build.url',
      }
    }
    if finished:
      build['build']['result'] = result
    return build

  def bb_json_put(build_id):
    return {
      'results': [
        {
          'build': {
            'id': build_id,
            'url': 'https://some.build.url',
          }
        }
      ]
    }

  def test_props(name, include_lkgm_steps=True):
    test = (
      api.test(name) +
      api.platform('linux', 64) +
      api.properties(
        swarming_server='some-swarming-server',
        swarming_pool='some-swarming-pool',
        device_type='some-device-type',
        bb_host='some-buildbucket-server',
        random_seed=12345) +
      api.buildbucket.ci_build(
        project='infra',
        bucket='cron',
        builder='cros-scheduler'))
    if include_lkgm_steps:
      test += (
        api.override_step_data(
            'fetch CHROMEOS_LKGM',
            api.json.output({'value': base64.b64encode('12345.0.0')}))
      )
    return test

  yield (
    test_props('full_run') +
    api.step_data(
        'get all bots',
        stdout=api.json.output({
          'items': [
            bot_json('host_1', 'up_to_date_bot', '12345'),
            bot_json('host_2', 'out_of_date_bot_1', '11111'),
            bot_json('host_2', 'out_of_date_bot_2', '11111'),
            bot_json('host_2', 'out_of_date_bot_3', '11111'),
            bot_json('host_2', 'out_of_date_bot_4', '11111'),
            bot_json('host_1', 'unhealthy_bot', '12345', quarantined=True),
          ]
        })) +
    api.step_data(
        'flash bots.out_of_date_bot_2',
        stdout=api.json.output(bb_json_put('1234567890'))) +
    # Build finises after the third buildbucket query.
    api.step_data(
        'wait for 1 flashing jobs.buildbucket.get',
        stdout=api.json.output(bb_json_get('1234567890', finished=False))) +
    api.step_data(
        'wait for 1 flashing jobs.buildbucket.get (2)',
        stdout=api.json.output(bb_json_get('1234567890', finished=False))) +
    api.step_data(
        'wait for 1 flashing jobs.buildbucket.get (3)',
        stdout=api.json.output(bb_json_get('1234567890'))) +
    # First the bot's online but out of date.
    api.step_data(
        'wait for bots to become available again.get status of '
        'out_of_date_bot_2',
        stdout=api.json.output(
            bot_json('host_2', 'out_of_date_bot_2', '11111'))) +
    # Then the bot's quarantined.
    api.step_data(
        'wait for bots to become available again.'
            'get status of out_of_date_bot_2 (2)',
        stdout=api.json.output(
            bot_json('host_2', 'out_of_date_bot_2', '12345',
                     quarantined=True))) +
    # Finally it's healthy and up to date.
    api.step_data(
        'wait for bots to become available again.'
            'get status of out_of_date_bot_2 (3)',
        stdout=api.json.output(
            bot_json('host_2', 'out_of_date_bot_2', '12345'))) +
    api.step_data(
        'retrigger myself',
        stdout=api.json.output(bb_json_put('1234567890'))) +
    api.post_process(post_process.StatusSuccess)
  )

  yield (
    test_props('one_flash_that_failed') +
    api.step_data(
        'get all bots',
        stdout=api.json.output({
          'items': [bot_json('host', 'out_of_date_bot', '11111')]
        })) +
    api.step_data(
        'flash bots.out_of_date_bot',
        stdout=api.json.output(bb_json_put('1234567890'))) +
    api.step_data(
        'wait for 1 flashing jobs.buildbucket.get',
        stdout=api.json.output(bb_json_get('1234567890', result='FAILURE'))) +
    api.post_process(post_process.MustRun, 'failed 1 flashing jobs') +
    api.post_process(post_process.DropExpectation)
  )

  offline_after_flashing_test = (
    test_props('bot_offline_after_flashing') +
    api.step_data(
        'get all bots',
        stdout=api.json.output({'items': [bot_json('host', 'bot', '11111')]})) +
    api.step_data(
        'flash bots.bot',
        stdout=api.json.output(bb_json_put('1234567890'))) +
    api.step_data(
        'wait for 1 flashing jobs.buildbucket.get',
        stdout=api.json.output(bb_json_get('1234567890'))) +
    api.step_data(
        'wait for bots to become available again.get status of bot',
        stdout=api.json.output(bot_json('host', 'bot', '11111',
                                        quarantined=True))) +
    api.post_process(
        post_process.MustRun, '1 bots dropped offline after the flash') +
    api.post_process(post_process.DropExpectation)
  )
  # The bot still reports as offline after all 10 queries.
  for i in xrange(2, 11):
    offline_after_flashing_test += api.step_data(
        'wait for bots to become available again.get status of bot (%d)' % i,
        stdout=api.json.output(bot_json('host', 'bot', '11111',
                                        quarantined=True)))
  yield offline_after_flashing_test

  yield (
    test_props('wrong_lkgm_format', include_lkgm_steps=False) +
    api.override_step_data(
        'fetch CHROMEOS_LKGM',
        api.json.output({'value': base64.b64encode('this-is-wrong')})) +
    api.post_process(post_process.MustRun, 'unknown CHROMEOS_LKGM format') +
    api.post_process(post_process.StatusFailure) +
    api.post_process(post_process.DropExpectation)
  )

  retry_test = (
    test_props('exhaust_all_gs_retries', include_lkgm_steps=False) +
    api.override_step_data(
        'fetch CHROMEOS_LKGM',
        api.json.output({'value': base64.b64encode('99999.0.0')})) +
    api.post_process(post_process.MustRun, 'no available image at 99999.0.0') +
    api.post_process(post_process.StatusFailure) +
    api.post_process(post_process.DropExpectation)
  )
  # gsutil calls return non-zero for all 100 attempts.
  for i in xrange(100):
    next_ver = 99999 - i
    step_name = 'find latest image at 99999.gsutil cat LATEST-%d' % next_ver
    retry_test += api.step_data(step_name, retcode=1)
  yield retry_test

  yield (
    test_props('no_bots') +
    api.step_data(
        'get all bots',
        stdout=api.json.output({'items': []})) +
    api.post_process(post_process.MustRun, 'no bots online') +
    api.post_process(post_process.StatusFailure) +
    api.post_process(post_process.DropExpectation)
  )

  yield (
    test_props('no_flashing_needed') +
    api.step_data(
        'get all bots',
        stdout=api.json.output({
          'items': [
            bot_json('host', 'bot2', '12345'),
            bot_json('host', 'bot1', '12345'),
          ]
        })) +
    api.post_process(post_process.StatusSuccess) +
    api.post_process(post_process.DropExpectation)
  )
