#!/usr/bin/env python
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib2

import util


SOURCE_BUCKET = 'gs://chrome-python-wheelhouse/sources'
WHEELS_BUCKET = 'gs://chrome-python-wheelhouse/wheels'


# Python versions + ABIs + Platforms we recognize => deps.py platform tag.
PLATFORMS = {
  ('cp27', 'cp27m', 'macosx_10_9_intel'): 'macosx_x86_64',
  ('cp27', 'cp27mu', 'manylinux1_i686'): 'linux_i686',
  ('cp27', 'cp27mu', 'manylinux1_x86_64'): 'linux_x86_64',
  ('cp27', 'none', 'win32'): 'windows_i686',
  ('cp27', 'none', 'win_amd64'): 'windows_x86_64',
  ('py2', 'none', 'any'): 'any',
  ('py2.py3', 'none', 'any'): 'any',
}


def query_pypi(package, version):
  response = urllib2.urlopen(
      'https://pypi.python.org/pypi/%s/%s/json' % (package, version))
  return json.loads(response.read())


def download_release(release, dest_dir):
  assert os.sep not in release['filename']
  dest = os.path.join(dest_dir, release['filename'])
  print 'Downloading %s...' % release['url']
  blob = urllib2.urlopen(release['url']).read()
  if hashlib.md5(blob).hexdigest() != release['md5_digest']:
    raise ValueError('MD5 digest mismatch')
  with open(dest,'wb') as output:
    output.write(blob)
  return dest


def upload_to_gs(local_path, gs_path):
  print 'Uploading %s...' % gs_path
  subprocess.check_call(['gsutil', 'cp', local_path, gs_path])
  print


def get_file_sha1(path):
  with open(path, 'rb') as f:
    return hashlib.sha1(f.read()).hexdigest()


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('package', help='Name of the PyPI package to ingest')
  parser.add_argument('version', help='Version to ingest')
  o = parser.parse_args()
  pkg = o.package
  version = o.version

  # '-' is used in wheel file names as a separator. Some scripts are getting
  # confused if '-' is used in package names. Use '_' instead. PyPI understand
  # this: "a-b-c" and "a_b_c" point to the exact same package.
  pkg = pkg.replace('-', '_')

  info = query_pypi(pkg, version)
  releases = sorted(info['releases'][version])

  # We first find source *.zip (or *.tar.gz) and use its SHA1 as build
  # identifier (assuming all wheels were build with that exact source).
  zips = [
    r for r in releases
    if r['packagetype'] == 'sdist' and r['filename'].endswith('.zip')
  ]
  tars = [
    r for r in releases
    if r['packagetype'] == 'sdist' and r['filename'].endswith('.tar.gz')
  ]
  sources = zips or tars
  if not sources:
    print 'Could not find a source distribution (*.zip or *.tar.gz)'
    return 1
  if len(sources) != 1:
    print 'More than 1 source distribution, don\'t know what to pick:'
    print '  \n'.join(sources)
    return 1
  source = sources[0]

  print 'Referring to the following source release:'
  print json.dumps(source, sort_keys=True, indent=2)
  print

  # Now find wheels for all platforms we care about.
  wheels = []
  only_on = set()
  for r in releases:
    if r['packagetype'] != 'bdist_wheel':
      continue
    fn = r['filename']
    if not fn.endswith('.whl'):
      print 'Not a wheel: %s' % fn
      continue
    # See https://www.python.org/dev/peps/pep-0491/#file-name-convention
    chunks = fn[:-len('.whl')].split('-')
    if chunks[0] != pkg or chunks[1] != version:
      print 'Unexpected filename: %s' % fn
      continue
    # See also https://www.python.org/dev/peps/pep-0425/
    py_tag, abi_tag, platform_tag = chunks[-3:]
    for (known_py, known_abi, known_plat), deps_tag in PLATFORMS.iteritems():
      if (py_tag == known_py and
          abi_tag == known_abi and
          known_plat in platform_tag):
        only_on.add(deps_tag)
        break
    else:
      continue
    wheels.append(r)

  print 'Going to ingest the following source distribution:'
  print '  * %s (%d downloads)' % (source['filename'], source['downloads'])
  print

  if wheels:
    print 'Going to ingest the following wheels:'
    for r in wheels:
      print '  * %s (%d downloads)' % (r['filename'], r['downloads'])
    print

    if 'any' in only_on:
      only_on = []
      print 'This will make the package available on all platforms.'
    else:
      only_on = sorted(only_on)
      print 'This will make the package available on:'
      for p in only_on:
        print '  * %s' % p
    print

  if raw_input('Continue? [Y] ') not in ('', 'y', 'Y'):
    return 2

  with util.tempdir() as tmp:
    # Upload the source code. We checked above it is .zip or .tar.gz.
    src = download_release(source, tmp)
    build_id = get_file_sha1(src)
    src_gs_file = build_id + ('.zip' if src.endswith('.zip') else '.tar.gz')
    upload_to_gs(src, '%s/%s' % (SOURCE_BUCKET, src_gs_file))
    # Upload all binary wheels.
    for release in wheels:
      chunks = release['filename'].split('-')
      new_name = '%s-%s-0_%s-%s' % (
          chunks[0], # package name
          chunks[1], # package version
          build_id,  # our fake build identifier
          '-'.join(chunks[-3:]), # all original tags and '.whl' extension
      )
      wheel = download_release(release, tmp)
      upload_to_gs(wheel, '%s/%s' % (WHEELS_BUCKET, new_name))

  print 'Done!'
  print

  entry = {
    'version': version,
    'build': '0',
    'gs': src_gs_file,
  }
  if only_on:
    entry['only_on'] = only_on

  print 'deps.pyl entry:'
  print json.dumps({pkg: entry}, sort_keys=True, indent=2)

  if not wheels:
    print
    print 'This is a source-only release. Once you update deps.pyl you\'ll need'
    print 'to run the following command to build and upload the cross-platform'
    print 'wheel made of the source code:'
    print
    print './build_deps.py --upload %s' % pkg


if __name__ == '__main__':
  sys.exit(main())
