# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import json
import urllib

from google.appengine.api.app_identity import app_identity


TEMPLATE_URL = ('https://chromium-swarm.appspot.com/swarming/api/v1/client/'+
    'tasks?tag=master:{master}&tag=buildername:{buildername}&'+
    'tag=buildnumber:{buildnumber}')


def UpdateSwarmingTaskIdForFailedSteps(
    master_name, builder_name, build_number, failed_steps, http_client):
  """Checks failed step_names in swarming log for the build.

  Searches each failed step_name to identify swarming/non-swarming tests
  and keeps track of task ids for each failed swarming steps.
  """
  data = {
    'items':[]
  }
  step_name_prefix = 'stepname:'
  base_url = TEMPLATE_URL.format(
      master=master_name, buildername=builder_name, buildnumber=build_number)
  cursor = None

  while True:
    if not cursor:
      url = base_url
    else:
      url = base_url + '?cursor=%s' % urllib.quote(cursor)

    auth_token, _ = app_identity.get_access_token(
        'https://www.googleapis.com/auth/userinfo.email')
    status_code, new_data = http_client.Get(
        url, headers={'Authorization': 'Bearer <' + auth_token + '>'})
    if status_code != 200:
      return False

    new_data_json = json.loads(new_data)
    data['items'].extend(new_data_json['items'])
    if new_data_json.get('cursor'):
      cursor = new_data_json['cursor']
    else:
      break

  task_ids = defaultdict(list)
  for item in data['items']:
    if item['failure'] and not item['internal_failure']:
      # Only retrieves test results from tasks which have failures and
      # the failure should not be internal infrastructure failure.
      for tag in item['tags']:  # pragma: no cover
        if tag.startswith(step_name_prefix):
          swarming_step_name = tag[len(step_name_prefix):]
          break
      if swarming_step_name in failed_steps:
        task_ids[swarming_step_name].append(item['id'])

  for step_name in task_ids:
    failed_steps[step_name]['swarming_task_ids'] = task_ids[step_name]

  return True
