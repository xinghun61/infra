#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import bz2
import gzip
import json
import logging
import logging.handlers
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import urlparse

import requests

from infra.libs import logs as infra_logs

# This logger is modified by setup_logging() below.
LOGGER = logging.getLogger(__name__)
LOGFILE = 'logs_uploader.log'

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
# Directory containing build/
ROOT_DIR = os.path.dirname(os.path.dirname(
  os.path.dirname(os.path.dirname(SCRIPT_DIR))))
assert os.path.isdir(os.path.join(ROOT_DIR, 'build')), \
       'Script may have moved in the hierarchy'

GSUTIL_BIN = os.path.join(ROOT_DIR, 'depot_tools', 'gsutil.py')
assert os.path.isfile(GSUTIL_BIN), 'gsutil may have moved in the hierarchy'

GET_MASTER_CONFIG_BIN = os.path.join(
  ROOT_DIR, 'build', 'scripts', 'tools', 'get_master_config.py')
assert os.path.isfile(GET_MASTER_CONFIG_BIN), \
       'get_master_config.py may have moved in the hierarchy'
RUNIT_BIN = os.path.join(
  ROOT_DIR, 'build', 'scripts', 'tools', 'runit.py')
assert os.path.isfile(RUNIT_BIN), \
       'runit.py may have moved in the hierarchy'



class GSutilError(RuntimeError):
  pass


def call_gsutil(args, dry_run=False, stdin=None):
  """Call gsutil with the specified arguments.

  This function raises OSError when gsutil is not found or not executable.
  No exception is raised when gsutil returns a non-zero code.

  Args:
  args (list or tuple): gsutil arguments
  dry_run (boolean): if True, only prints what would be executed.
  stding (str): string to pass as standard input to gsutil.

  Return:
  (stdout, stderr, returncode) respectively strings containing standard output
     and standard error, and code returned by the process after completion.
  """
  if not isinstance(stdin, (basestring, types.NoneType)):
    raise ValueError('Incorrect type for stdin: must be a string or None.')

  cmd = [GSUTIL_BIN , '--force-version', '4.7']
  cmd.extend(args)
  LOGGER.debug('Running: %s', ' '.join(cmd))
  if dry_run:
    return '', '', 0

  proc = subprocess.Popen(cmd,
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
  stdout, stderr = proc.communicate(stdin)
  return stdout, stderr, proc.returncode


def get_master_config(mastername, dry_run=False):
  """Return content of master_site_config.py for specified master.

  This turns the object present in master_site_config.py into a dict.

  Args:
  mastername (string): name of the master (ex: chromium.perf). It's the last
    part of the directory containing the master configuration.

  Returns:
    (dict) master_config: keys are 'project_name', 'slave_port', 'master_host',
         'master_port_alt', 'buildbot_url', 'master_port'
  """
  if not isinstance(mastername, basestring):
    raise ValueError('Incorrect type for stdin: must be a string.')

  cmd = [RUNIT_BIN, 'python', GET_MASTER_CONFIG_BIN]
  cmd.extend(('--master-name', mastername))
  LOGGER.debug('Running: %s', ' '.join(cmd))
  if dry_run:
    return {'master_port': 8080}

  proc = subprocess.Popen(cmd,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
  stdout, stderr = proc.communicate()

  if proc.returncode:
    msg = 'Execution failed: "%s"' % ' '.join(cmd)
    LOGGER.error(msg)
    LOGGER.error('stdout: %s', stdout)
    LOGGER.error('stderr: %s', stderr)
    raise RuntimeError(msg)

  return json.loads(stdout)


class MemStorage(object):
  """An in-memory storage, used for testing."""
  # TODO(pgervais) This class should be dropped while refactoring for better
  # testability.
  def __init__(self, master_name):
    self._master_name = master_name
    self._refs = set()

  def _get_ref(self, builder_name, build_num=None, log_file=''):
    return ('%s/%s/%.7d/%s' % (self._master_name,
                               builder_name,
                               build_num or -1,
                               log_file))

  def get_builds(self, _builder_name):  # pylint: disable=R0201
    return {55, 56}

  def has_build(self, builder_name, build_num):
    ref = self._get_ref(builder_name, build_num)
    return ref in self._refs

  def put(self, builder_name, build_num, log_file, source,
          source_type=None):

    allowed_types = ('filename', 'content')
    if not source_type in allowed_types:
      raise ValueError('source_type must be in %s' % str(allowed_types))

    ref = self._get_ref(builder_name, build_num, log_file)
    if source_type == 'filename':
      LOGGER.debug('putting %s as %s', source, ref)
    elif source_type == 'content':
      LOGGER.debug('putting content as %s', ref)
    self._refs.add(ref)

  def mark_upload_started(self, builder_name, build_number):
    ref = self._get_ref(builder_name, build_number)
    LOGGER.debug('Marking upload as started: %s', ref)

  def mark_upload_ended(self, builder_name, build_number):
    ref = self._get_ref(builder_name, build_number)
    LOGGER.debug('Marking upload as done: %s', ref)

  def get_partial_uploads(self, _builder_name):  # pylint: disable=R0201
    return {55}


class GCStorage(object):
  """Google Cloud Storage backend.

  This is specific to buildbot. As such, it understands the notion of
  master, builder, build num and log file name.

  What is called a reference in the following is the tuple
  (master_name, builder_name, build_num, log_file), with master_name being
  implicit, and log_file optional. So (builder_name, build_num) is also a
  reference.
  """
  CHUNK_SIZE = 1024 * 1024

  # first path component for flag and log files.
  FLAG_PREFIX = 'flags'
  LOG_PREFIX = 'logs'

  def __init__(self, master_name, bucket, chunk_size=None, dry_run=False):
    if not chunk_size:
      chunk_size = self.CHUNK_SIZE

    self._master_name = master_name
    self._bucket = bucket.rstrip('/')
    # chunk to use when uncompressing files.
    self._chunk_size = chunk_size
    self._dry_run = dry_run
    # Cache to know if a build has been uploaded yet
    # self._builders[builder_name] is a set of build numbers (possibly empty.)
    # Beware: build numbers are _str_, not int.
    self._builders = {}

  def _get_ref(self, builder_name, build_num=None, log_file=None,
               prefix=LOG_PREFIX):
    ref = [prefix, self._master_name, builder_name]

    if build_num is not None:  # can be zero
      ref.append('%.7d' % build_num)

    if log_file is not None:
      if log_file == '':
        raise ValueError('log_file name provided was empty.')
      ref.append(log_file)

    return '/'.join(ref)

  def _get_gs_url(self, builder_name, build_num=None, log_file=None):
    """Compute the gs:// url to get to a log file."""
    ref = self._get_ref(builder_name, build_num=build_num, log_file=log_file,
                        prefix=self.LOG_PREFIX)
    return 'gs://' + self._bucket + '/' + ref

  def _get_flag_gs_url(self, builder_name, build_num=None):
    """Compute the gs:// url to get to a build flag file."""
    ref = self._get_ref(builder_name, build_num=build_num,
                        prefix=self.FLAG_PREFIX)
    return 'gs://' + self._bucket + '/' + ref

  def get_http_url(self, builder_name, build_num, log_file=None):
    """Compute the http:// url associated with a ref.

    This function exists mainly for reference purposes.

    See also
    https://developers.google.com/storage/docs/reference-uris
    """
    ref = self._get_ref(builder_name, build_num=build_num, log_file=log_file)
    return ('https://storage.cloud.google.com/'
            + self._bucket + '/' + ref.lstrip('/'))

  def get_builds(self, builder_name):
    """Return set of already uploaded builds."""
    build_nums = self._builders.get(builder_name)
    if build_nums is not None:  # could be empty set
      return build_nums

    build_nums = set()
    stdout, stderr, returncode = call_gsutil(['ls',
                                              self._get_gs_url(builder_name)],
                                             dry_run=self._dry_run)
    if returncode != 0:
      # The object can be missing when the builder name hasn't been used yet.
      if not 'One or more URLs matched no objects' in stderr:
        LOGGER.error('Unable to list bucket content.')
        raise GSutilError('Unable to list bucket content. gsutil stderr: %s',
                          stderr)
    else:
      for line in stdout.splitlines():
        num = line.strip('/').split('/')[-1]
        if not num.isdigit():
          raise RuntimeError('Unexpected build number from "gsutil ls": %s'
                             % num)
        build_nums.add(int(num))

    self._builders[builder_name] = build_nums

    return build_nums

  def has_build(self, builder_name, build_num):
    return build_num in self.get_builds(builder_name)

  def _copy_source_to_tempfile(self, source, out_f):
    """Prepare a source file for upload by gsutil.

    source: input file name
    out_f: temporary file. file descriptor (int) of a file open for writing.
    """
    if source.endswith('.bz2'):
      LOGGER.debug('Uncompressing bz2 file...')
      openfunc = lambda: bz2.BZ2File(source, 'rb')
    elif source.endswith('.gz'):
      LOGGER.debug('Uncompressing gz file...')
      openfunc = lambda: gzip.GzipFile(source, 'rb')
    else:
      # TODO(pgervais) could use a symbolic link instead.
      # But beware of race conditions.
      LOGGER.debug('Copying log file')
      openfunc = lambda: open(source, 'rb')

    with openfunc() as in_f:
      if not self._dry_run:
        shutil.copyfileobj(in_f, out_f, self._chunk_size)

  def put(self, builder_name, build_num, log_file, source,
          source_type=None):
    """Upload the content of a file to GCS.

    Args:
      builder_name (str): name of builder as shown on the waterfall
      build_num (int): build number
      log_file (str): name of log file on GCS

      source(str): path toward the source file to upload or content as string.
      source_type(str): if 'filename', then the 'source' parameter is a file
        name. if 'content' then the 'source' parameter is the content itself.

    Returns:
      success (bool): whether the file has been successfully uploaded or not.
    See also: get_http_url()
    """
    allowed_types = ('filename', 'content')
    if not source_type in allowed_types:
      raise ValueError('source_type must be in %s' % str(allowed_types))

    ref = self._get_ref(builder_name, build_num=build_num, log_file=log_file)
    if source_type == 'filename':
      LOGGER.debug('putting %s as %s', source, ref)
    elif source_type == 'content':
      LOGGER.debug('putting content as %s', ref)

    # The .txt extension is *essential*, so that the mime-type is set to
    # text/plain and not application/octet-stream. There are no options to
    # force the mimetype with the gsutil command (sigh.) 05/07/2014
    with tempfile.NamedTemporaryFile(suffix='_upload_logs_to_storage.txt',
                                     delete=True) as out_f:
      if source_type == 'filename':
        self._copy_source_to_tempfile(source, out_f)
      elif source_type == 'content':
        out_f.write(source)
      else:
        # This is not supposed to be reachable, but leaving it just in case.
        raise ValueError('Invalid value for source_type: %s' % source_type)

      out_f.flush()
      LOGGER.debug('Done uncompressing/copying.')
      _, _, returncode = call_gsutil(
        ['cp', out_f.name, self._get_gs_url(builder_name,
                                            build_num=build_num,
                                            log_file=log_file)],
        dry_run=self._dry_run)

    if returncode:
      LOGGER.error('Failed uploading %s', ref)
      return False

    LOGGER.info('Successfully uploaded to %s',
                self.get_http_url(builder_name,
                                  build_num=build_num,
                                  log_file=log_file))
    return True

  def mark_upload_started(self, builder_name, build_number):
    """Create a flag file on GCS."""
    gs_url = self._get_flag_gs_url(builder_name, build_num=build_number)
    # TODO(pgervais) set IP/hostname, pid, timestamp as flag content

    # Let's be paranoid and prevent bad files from being created.
    num = gs_url.strip('/').split('/')[-1]
    if not num.isdigit():
      LOGGER.error('gs url must end with an integer: %s', gs_url)
      raise ValueError('gs url must end with an integer: %s', gs_url)

    content = 'mark'
    _, stderr, returncode = call_gsutil(['cp', '-', gs_url],
                                        stdin=content,
                                        dry_run=self._dry_run)
    if returncode != 0:
      LOGGER.error('Unable to mark upload as started.')
      LOGGER.error(stderr)
      raise GSutilError('Unable to mark upload as started.')
    else:
      LOGGER.debug('Marked upload as started: %s/%s',
                   builder_name, build_number)

  def mark_upload_ended(self, builder_name, build_number):
    """Remove the flag file on GCS."""
    gs_url = self._get_flag_gs_url(builder_name, build_number)

    # Let's be paranoid. We really don't want to erase a random file.
    assert '*' not in gs_url
    assert gs_url.startswith('gs://')
    file_parts = gs_url[5:].split('/')
    assert file_parts[1] == self.FLAG_PREFIX

    _, _, returncode = call_gsutil(['rm', gs_url], dry_run=self._dry_run)
    if returncode != 0:
      LOGGER.error('Unable to mark upload as done: %s/%s',
                   builder_name, build_number)
      raise GSutilError('Unable to mark upload as done.')
    else:
      LOGGER.debug('Marked upload as done: %s/%s', builder_name, build_number)

  def get_partial_uploads(self, builder_name):
    """Get set of all unfinished uploads."""
    partial_uploads = set()

    stdout, stderr, returncode = call_gsutil(['ls',
                                         self._get_flag_gs_url(builder_name)],
                                        dry_run=self._dry_run)
    if returncode != 0:
      if not 'One or more URLs matched no objects' in stderr:
        LOGGER.error("Unable to list bucket content.")
        raise GSutilError("Unable to list bucket content. gsutil stderr: %s" %
                          stderr)
    else:
      for line in stdout.splitlines():
        num = line.strip('/').split('/')[-1]
        if not num.isdigit():
          raise RuntimeError('Unexpected build number from "gsutil ls": %s'
                             % num)
        partial_uploads.add(int(num))

    return partial_uploads


def get_master_directory(master_name):
  """Given a master name, returns the full path to the corresponding directory.

  This function either returns a path to an existing directory, or None.
  """
  # Look for the master directory
  for build_name in ('build', 'build_internal'):
    master_path = os.path.join(ROOT_DIR,
                               build_name,
                               'masters',
                               'master.' + master_name)

    if os.path.isdir(master_path):
      return master_path
  return None


class Waterfall(object):
  def __init__(self, master_name, url=None):
    LOGGER.debug('Instantiating Waterfall object')

    self._master_name = master_name
    self._master_path = get_master_directory(self._master_name)

    if not self._master_path:
      LOGGER.error('Cannot find master directory for %s', self._master_name)
      raise ValueError('Cannot find master directory')

    LOGGER.info('Found master directory: %s', self._master_path)

    # Compute URL
    self._url = None
    if url:
      self._url = url.rstrip('/')
      parsed_url = urlparse.urlparse(self._url)
      if parsed_url.scheme not in ('http', 'https'):
        raise ValueError('url should use an http(s) protocol')
    else:  # url not provided, relying on master_site_config.py
      master_config = get_master_config(self._master_name)

      if 'master_port' not in master_config:
        LOGGER.error('Master port could not be determined. This may be caused '
                     'by get_master_config.py not running properly.')
        raise OSError('Master URL could not be determined')

      self._master_port = master_config['master_port']
      self._url = 'http://localhost:%d' % self._master_port

    LOGGER.info('Using URL: %s', self._url)


  def get_builder_properties(self):
    """Query information about builders

    Return a dict mapping builder name to builder properties, as returned
    by buildbot.
    """
    try:
      return requests.get(self._url + '/json/builders').json()
    except requests.ConnectionError:
      LOGGER.error('Unable to reach %s.', self._url)
      raise

  def get_build_properties(self, builder_name, build_number):
    """Query information about a specific build."""
    r = requests.get(self._url + '/json/builders/%s/builds/%d'
                     % (builder_name, build_number))
    return r.text, r.json()

  def get_log_filenames(self, build_properties, basedir):
    """Compute log file names.

    build_properties (dict): build properties as returned by buildbot.
        Second return value of get_build_properties().
    basedir (string): builder directory containing the log files.
    """
    build_number = build_properties['number']

    step_logs = [(s['name'], loginfo[0])
                 for s in build_properties['steps']
                 for loginfo in s['logs']]
    log_filenames = []

    for step_name, log_name in step_logs:
      # From buildbot, in  status/build.py:generateLogfileName
      basename = '%d-log-%s-%s' % (build_number, step_name, log_name)
      basename = re.sub(r'[^\w\.\-]', '_', basename)
      filename = os.path.join(self._master_path, basedir, basename)
      ref = (build_properties['builderName'],
             build_number, re.sub(r'/', '_', step_name) + '.' + log_name)

      for ext in ('', '.gz', '.bz2'):
        filename_ext = filename + ext
        if os.path.isfile(filename_ext):
          log_filenames.append((ref, filename_ext))
          LOGGER.debug('Found log file %s', filename_ext)
          break
      else:
        LOGGER.warning('Skipping non-existing log file %s', filename)
    return log_filenames


def setup_logging(logger, output_dir, log_level=logging.WARN):
  """Log messages on stdout and in LOGFILE, in the master directory."""
  logfile_handler = logging.handlers.RotatingFileHandler(
    os.path.join(output_dir, LOGFILE),
    maxBytes=1048576, backupCount=20)

  infra_logs.add_handler(logger, handler=logfile_handler, level=logging.INFO)
  infra_logs.add_handler(logger, level=log_level)


def main(options):
  if not os.path.exists(GSUTIL_BIN):
    print >> sys.stderr, ('gsutil not found in %s\n' % GSUTIL_BIN)
    return 2

  setup_logging(LOGGER,
                get_master_directory(options.master_name),
                log_level=options.log_level)

  w = Waterfall(options.master_name, url=options.waterfall_url)
  builders = w.get_builder_properties()

  if options.bucket:
    storage = GCStorage(options.master_name,
                        options.bucket,
                        dry_run=options.dry_run)
  else:
    storage = MemStorage(options.master_name)

  builder_names = builders.keys()
  if options.builder_name:
    if options.builder_name not in builder_names:
      LOGGER.error("Specified builder (%s) doesn't exist on master",
                   options.builder_name)
      return 1
    builder_names = [options.builder_name]

  for builder_name in builder_names:
    LOGGER.info('Starting processing builder %s', builder_name)

    # Builds known to buildbot.
    cached_builds = builders[builder_name].get('cachedBuilds', [])
    cached_builds.sort(reverse=True)

    # Builds whose upload is not finished (leftovers from a previous crash.)
    partial_uploads = storage.get_partial_uploads(builder_name)
    if len(partial_uploads) > 100:
      LOGGER.warning('More than 100 partial uploads found.')

    # Build already uploaded
    stored_builds = storage.get_builds(builder_name)

    missing_builds = [
      b for b in cached_builds
      if (b not in stored_builds or b in partial_uploads)
      and b not in builders[builder_name]['currentBuilds']
      ]

    # Sort builds in reverse order so as to make the most recent builds
    # available first.
    missing_builds.sort(reverse=True)
    missing_builds_num = len(missing_builds)
    if options.limit:
      missing_builds = missing_builds[:options.limit]
    LOGGER.info('Uploading %d out of %d missing builds',
                len(missing_builds), missing_builds_num)
    LOGGER.info('Builds to upload: %s', str(missing_builds))

    for build_number in missing_builds:
      LOGGER.info('Starting processing build %s/%d',
                  builder_name, build_number)
      bp_str, bp = w.get_build_properties(builder_name, build_number)
      log_filenames = w.get_log_filenames(bp, builders[builder_name]['basedir'])

      # Beginning of critical section
      storage.mark_upload_started(builder_name, build_number)
      success = True
      success = storage.put(builder_name, build_number,
                            'METADATA', bp_str, source_type='content')

      for ref, log_filename in log_filenames:
        assert ref[0] == builder_name
        assert ref[1] == build_number
        log_name = ref[2]
        result = storage.put(builder_name, build_number, log_name,
                             log_filename, source_type='filename')
        success = success and result
      # If not all files have been uploaded, do not mark upload as ended. We
      # want to try again on next invocation.
      if success:
        storage.mark_upload_ended(builder_name, build_number)
      # End of critical section
  return 0
