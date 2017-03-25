# Copyright 2008 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Rietveld-BuildBucket integration module."""

import binascii
import datetime
import hashlib
import json
import logging
import random
import time
import uuid

from google.appengine.api import users
from google.appengine.ext import ndb

from codereview import common
from codereview import models
from codereview import net

EPOCH = datetime.datetime.utcfromtimestamp(0)
BUILDBUCKET_APP_ID = (
    'cr-buildbucket-test' if common.IS_DEV else 'cr-buildbucket')
BUILDBUCKET_API_ROOT = (
    'https://%s.appspot.com/api/buildbucket/v1' % BUILDBUCKET_APP_ID)
# See the convention
# https://chromium.googlesource.com/infra/infra/+/master/appengine/cr-buildbucket/doc/index.md#buildset-tag
BUILDSET_TAG_FORMAT = 'patch/rietveld/{hostname}/{issue}/{patch}'


IMPERSONATION_TOKEN_MINT_URL = (
    'https://luci-token-server.appspot.com/prpc/tokenserver.minter.TokenMinter/'
    'MintDelegationToken')
IMPERSONATION_TOKEN_CACHE_KEY_FORMAT = 'impersonation_token/v3/%s'


class BuildBucketError(Exception):
  """Raised when a buildbucket operation failed."""
  pass


# TODO: make it a simple Python class. http://crbug.com/461900
class BuildbucketTryJobResult(models.TryJobResult):
  """A TryJobResult created from a BuildBucket build.

  Not stored, but only passed to pathset.html template.
  """

  build_id = ndb.StringProperty()

  @property
  def is_from_buildbucket(self):
    # Used in build_result.html template.
    return True

  @classmethod
  def convert_status_to_result(cls, build):
    """Converts build status to TryJobResult.result.

    See buildbucket docs here:
    https://chromium.googlesource.com/infra/infra/+/master/appengine/cr-buildbucket/doc/index.md#Build
    """
    status = build.get('status')
    if status == 'SCHEDULED':
      return cls.TRYPENDING

    if status == 'COMPLETED':
      if build.get('result') == 'SUCCESS':
        return cls.SUCCESS
      if build.get('result') == 'FAILURE':
        if build.get('failure_reason') == 'BUILD_FAILURE':
          return cls.FAILURE
      if build.get('result') == 'CANCELED':
        if build.get('cancelation_reason') == 'TIMEOUT':
          return cls.SKIPPED
      return cls.EXCEPTION

    if status == 'STARTED':
      return cls.STARTED

    logging.warning('Unexpected build %s status: %s', build.get('id'), status)
    return None

  @staticmethod
  def parse_tags(tag_list):
    """Parses a list of colon-delimited tags to a map."""
    return dict(tag.split(':', 1) for tag in tag_list)

  @classmethod
  def from_build(cls, build):
    """Converts a BuildBucket build to BuildBucketTryJobResult."""
    tags = cls.parse_tags(build.get('tags', []))
    result_details = load_json_dict_safe(build, 'result_details_json')
    parameters = load_json_dict_safe(build, 'parameters_json')
    properties = (
        result_details.get('properties') or parameters.get('properties'))
    if not isinstance(properties, dict):
      properties = {}

    def read_prop(name, expected_type):
      return dict_get_safe(properties, name, expected_type)

    requester = None
    requester_str = read_prop('requester', basestring)
    if requester_str:
      try:
        requester = users.User(requester_str)
      except users.UserNotFoundError:
        pass

    timestamp = timestamp_to_datetime(build.get('status_changed_ts'))
    if timestamp is None:
      logging.warning('Build %s has status_changed_ts=None', build['id'])

    return cls(
        id=build['id'],  # Required for to_dict() serialization.
        build_id=build['id'],
        url=dict_get_safe(build, 'url', basestring),
        result=cls.convert_status_to_result(build),
        master=tags.get('master'),
        builder=dict_get_safe(parameters, 'builder_name', basestring),
        slave=read_prop('slavename', basestring),
        buildnumber=read_prop('buildnumber', int),
        reason=read_prop('reason', basestring),
        revision=read_prop('revision', basestring),
        timestamp=timestamp,
        clobber=read_prop('clobber', bool),
        tests=read_prop('testfilter', list) or [],
        project=read_prop('patch_project', basestring),
        requester=requester,
        category=read_prop('category', basestring),
        build_properties=json.dumps(properties, sort_keys=True),
    )


################################################################################
## API.


@ndb.tasklet
def get_builds_for_patchset_async(project, issue_id, patchset_id):
  """Queries BuildBucket for builds associated with the patchset.

  Requests for max 500 builds and does not check "next_cursor". Currently if
  more than 100 builds are requested, only 100 are returned. Presumably there
  will be no patchsets with >100 builds.

  Returns:
    A list of buildbucket build dicts.
  """
  buildset_tag = get_buildset_for(project, issue_id, patchset_id)
  params = {
      'max_builds': 500,
      'tag': 'buildset:%s' % buildset_tag,
  }

  logging.info(
      'Fetching builds for patchset %s/%s. Buildset: %s',
      issue_id, patchset_id, buildset_tag)
  start = datetime.datetime.now()
  try:
    resp = yield rpc_async('GET', 'search', params=params)
  except net.NotFoundError as ex:
    logging.error(
        'Buildbucket returned 404 unexpectedly. Body: %s', ex.response)
    raise
  took = datetime.datetime.now() - start
  logging.info(
      'Fetching %d builds for patchset %s/%s took %.1fs',
      len(resp.get('builds', [])), issue_id, patchset_id,
      took.total_seconds())
  if 'error' in resp:
    bb_error = resp.get('error', {})
    raise BuildBucketError(
        'BuildBucket responded with error (reason %s): %s' % (
            bb_error.get('reason', 'no-reason'),
            bb_error.get('message', 'no-message')))
  raise ndb.Return(resp.get('builds') or [])


@ndb.tasklet
def get_try_job_results_for_patchset_async(project, issue_id, patchset_id):
  """Returns try job results stored on buildbucket."""
  builds = yield get_builds_for_patchset_async(project, issue_id, patchset_id)
  results = []
  for build in builds:
    try_job_result = BuildbucketTryJobResult.from_build(build)
    if not try_job_result.builder:
      logging.info(
          'Build %s does not have a builder' % try_job_result.build_id)
      continue
    results.append(try_job_result)
  raise ndb.Return(results)


def schedule(issue, patchset_id, builds):
  """Schedules builds on buildbucket.

  |builds| is a list of dicts with keys:
    bucket: required, target buildbucket bucket name. May have "master." prefix.
    builder: required.
    revision
    properties
  """
  account = models.Account.current_user_account
  assert account, 'User is not logged in; cannot schedule builds.'

  if not builds:
    return

  self_hostname = common.get_preferred_domain(issue.project)

  req = {'builds':[]}
  opid = uuid.uuid4()

  for i, build in enumerate(builds):
    assert 'bucket' in build, build
    assert 'builder' in build, build

    master_prefix = 'master.'
    master_name = None   # Buildbot master name without "master." prefix.
    if build['bucket'].startswith(master_prefix):
      master_name = build['bucket'][len(master_prefix):]

    # Build definitions are similar to what CQ produces:
    # https://chrome-internal.googlesource.com/infra/infra_internal/+/c3092da98975c7a3e083093f21f0f4130c66a51c/commit_queue/buildbucket_util.py#171
    change = {
      'author': {'email': issue.owner.email()},
      'url': 'https://%s/%s/%s/' % (
          self_hostname, issue.key.id(), patchset_id)
    }
    if build.get('revision'):
      change['revision'] = build.get('revision')

    properties = build.get('properties') or {}
    properties.update({
      'issue': issue.key.id(),
      'patch_project': issue.project,
      'patch_storage': 'rietveld',
      'patchset': patchset_id,
      'rietveld': 'https://%s' % self_hostname,
    })
    if master_name:
      properties['master'] = master_name

    if 'presubmit' in build['builder'].lower():
      properties['dry_run'] = 'true'
    tags = [
      'builder:%s' % build['builder'],
      'buildset:%s' % get_buildset_for(
          issue.project, issue.key.id(), patchset_id),
      'user_agent:rietveld',
    ]
    if master_name:
      tags.append('master:%s' % master_name)
    req['builds'].append({
        'bucket': build['bucket'],
        'parameters_json': json.dumps({
          'builder_name': build['builder'],
          'changes': [change],
          'properties': properties,
        }),
        'tags': tags,
        'client_operation_id': '%s:%s' % (opid, i),
    })

  logging.debug(
      'Scheduling %d builds on behalf of %s', len(req['builds']), account.email)
  res = rpc_async('PUT', 'builds/batch', payload=req).get_result()
  for r in res['results']:
    error = r.get('error')
    if error:
      logging.error('Build scheduling failed. Response: %r', res)
      raise BuildBucketError('Could not schedule build(s): %r' % error)

  actual_builds = [r['build'] for r in res['results']]
  logging.info(
      'Scheduled buildbucket builds: %r',
      ', '.join([str(b['id']) for b in actual_builds]))
  return actual_builds


def get_swarmbucket_builders():
  """Fetches a list of swarmbucket builders.

  Slow API, do not use on serving path.

  Does not impersonate current user, but uses rietveld service account.

  For more information about swarmbucket builders:
  https://chromium.googlesource.com/infra/infra/+/master/appengine/cr-buildbucket/doc/swarming.md

  Returns:
    Dict {bucket_name_str: {category_str: [builder_name_str]}}
  """
  url = (
      'https://%s.appspot.com/_ah/api/swarmbucket/v1/builders' %
      BUILDBUCKET_APP_ID)
  response = net.json_request(url, scopes=net.EMAIL_SCOPE)
  result = {}
  for bucket in response['buckets']:
    categories = {}
    for builder in bucket.get('builders', []):
      category = builder.get('category') or None
      categories.setdefault(category, []).append(builder['name'])
    result[bucket['name']] = categories
  return result


################################################################################
## Buildbucket RPC.


def _get_token_fingerprint(blob):
  """Given a blob with signed token returns first 16 bytes of its SHA256 as hex.

  It can be used to identify this particular token in logs.
  """
  assert isinstance(blob, basestring)
  if isinstance(blob, unicode):
    blob = blob.encode('ascii', 'ignore')
  return binascii.hexlify(hashlib.sha256(blob).digest()[:16])


@ndb.tasklet
def _mint_delegation_token_async():
  """Generates an access token to impersonate the current user, if any.

  Memcaches the token.
  """
  account = models.Account.current_user_account
  if account is None:
    raise ndb.Return(None)

  ctx = ndb.get_context()
  # Get from cache.
  cache_key = IMPERSONATION_TOKEN_CACHE_KEY_FORMAT % account.email
  token_envelope = yield ctx.memcache_get(cache_key)
  if token_envelope:
    # Randomize token expiration time to workaround the case when multiple
    # concurrent requests start to refresh the token at the same time.
    token, exp_ts, lifetime_sec = token_envelope
    if time.time() < exp_ts - lifetime_sec * 0.05 * random.random():
      logging.info(
          'Fetched cached delegation token: fingerprint=%s',
          _get_token_fingerprint(token))
      raise ndb.Return(token)

  # Request a new one.
  logging.debug('Minting a delegation token for %s', account.email)
  req = {
    'delegatedIdentity': 'user:%s' % account.email,
    'audience': ['REQUESTOR'],
    'services': ['service:%s' % BUILDBUCKET_APP_ID],
    'validityDuration': 5*3600,
  }
  resp = yield net.json_request_async(
      IMPERSONATION_TOKEN_MINT_URL,
      method='POST',
      payload=req,
      scopes=net.EMAIL_SCOPE,
      headers={'Accept': 'application/json; charset=utf-8'})

  signed_token = resp.get('token')
  if not signed_token:
    raise BuildBucketError(
        'Could not mint a delegation token. Response: %s' % resp)

  token_struct = resp.get('delegationSubtoken')
  if not token_struct or not isinstance(token_struct, dict):
    logging.error('Bad delegation token response: %s', resp)
    raise BuildBucketError('Could not mint a delegation token')

  logging.info(
      'Token server "%s" generated token (subtoken_id=%s, fingerprint=%s):\n%s',
      resp.get('serviceVersion'),
      token_struct.get('subtokenId'),
      _get_token_fingerprint(signed_token),
      json.dumps(
          token_struct,
          sort_keys=True, indent=2, separators=(',', ': ')))

  # Put to cache.
  validity_duration_sec = token_struct.get('validityDuration')
  assert isinstance(validity_duration_sec, (int, float))
  if validity_duration_sec >= 10:
    validity_duration_sec -= 10  # Refresh the token 10 sec in advance.
    exp_ts = int(time.time() + validity_duration_sec)
    yield ctx.memcache_set(
        key=cache_key,
        value=(signed_token, exp_ts, validity_duration_sec),
        time=exp_ts)

  raise ndb.Return(signed_token)


@ndb.tasklet
def rpc_async(method, path, **kwargs):
  """Makes an authenticated request to buildbucket.

  Impersonates the current user if he/she is logged in.
  Otherwise sends an anonymous request.
  """
  assert 'scopes' not in kwargs
  assert 'headers' not in kwargs
  url = '%s/%s' % (BUILDBUCKET_API_ROOT, path)
  delegation_token = yield _mint_delegation_token_async()
  headers = {}
  scopes = None
  if delegation_token:
    headers['X-Delegation-Token-V1'] = delegation_token
    scopes = net.EMAIL_SCOPE
  res = yield net.json_request_async(
      url, method=method,
      headers=headers,
      scopes=scopes,
      **kwargs)
  raise ndb.Return(res)


################################################################################
## Utility functions.


def load_json_dict_safe(container_dict, key_name):
  """Tries to parse a json-encoded dict, otherwise returns {}."""
  possibly_json = container_dict.get(key_name)
  if not possibly_json:
    return {}
  try:
    result = json.loads(possibly_json)
    if result is None:
      return {}
    if not isinstance(result, dict):
      logging.warning(
          '%s expected to be a dict. Got %s instead', key_name, result)
      result = {}
  except ValueError as ex:
    logging.warning(
        'Could not parse %s as json: %s.\nInput: %s',
        key_name, ex, possibly_json)
    result = {}
  return result


def dict_get_safe(container_dict, key_name, expected_type):
  """Returns value if it is an instance of |expected_type|, otherwise None."""
  value = container_dict.get(key_name)
  if value is not None and not isinstance(value, expected_type):
    logging.warning(
        'Unexpected type for %s. Expected type: %s. Value: %r.',
        key_name, expected_type.__name__, value,
    )
    return None
  return value


def timestamp_to_datetime(timestamp):
  if timestamp is None:
    return None
  if isinstance(timestamp, basestring):
    timestamp = int(timestamp)
  return EPOCH + datetime.timedelta(microseconds=timestamp)


def get_buildset_for(project, issue_id, patchset_id):
  # See the convention
  # https://chromium.googlesource.com/infra/infra/+/master/appengine/cr-buildbucket/doc/index.md#buildset-tag
  hostname = common.get_preferred_domain(project, default_to_appid=False)
  if not hostname:
    logging.error(
        'Preferred domain name for this app is not set. '
        'See PREFERRED_DOMAIN_NAMES in settings.py: %r', hostname)
    raise ndb.Return([])

  return BUILDSET_TAG_FORMAT.format(
      hostname=hostname,
      issue=issue_id,
      patch=patchset_id,
  )
