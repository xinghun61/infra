#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import sys
import time

from infra.ext import requests


def get_builders(json_base):
  return requests.get(
      'https://%s/json/builders?filter=False' % json_base).json().keys()


def get_builder(json_base, builder):
  return requests.get(
      'https://%s/json/builders/%s?filter=False' % (json_base, builder)).json()


def get_build(json_base, builder, build):
  return requests.get(
      'https://%s/json/builders/%s/builds/%d?filter=False' % (
          json_base, builder, build)).json()


def build_duration(times):
  if not times or not times[0]:
    return None
  return (times[1] or int(round(time.time()))) - times[0]


def cmd_current(args):
  builders = args.builders or get_builders(args.json_base)

  # TODO(phajdan.jr): Separate data fetching from presentation.
  if args.blame:
    blame = set()
    for builder in builders:
      for build in get_builder(args.json_base, builder)['currentBuilds']:
        build_data = get_build(args.json_base, builder, build)
        blame.update(build_data.get('blame', []))
    print '\n'.join(blame)
    return 0

  for builder in builders:
    current_builds = get_builder(args.json_base, builder)['currentBuilds']
    if not args.quiet and current_builds:
      print builder
    for build in current_builds:
      build_data = get_build(args.json_base, builder, build)
      if args.quiet:
        print build_data['slave']
      else:
        out = '%4d: slave=%10s' % (build_data['number'], build_data['slave'])
        out += '  duration=%5d' % (build_duration(build_data['times'] or 0))
        if build_data.get('eta'):
          out += '  eta=%5.0f' % build_data['eta']
        else:
          out += '           '
        if build_data.get('blame'):
          out += '  blame=' + ', '.join(build_data['blame'])
        print out
  return 0


def main(argv):
  parser = argparse.ArgumentParser('python -m %s' % __package__)
  parser.add_argument('-q', '--quiet', action='store_true')

  cmd_parser = parser.add_subparsers(title='subcommands')

  cmd_parser_current = cmd_parser.add_parser('current')
  cmd_parser_current.set_defaults(func=cmd_current)
  cmd_parser_current.add_argument('json_base')
  cmd_parser_current.add_argument(
    '-b', '--builder', dest='builders', action='append', default=[],
    help='Builders to filter on')
  cmd_parser_current.add_argument('--blame', action='store_true')

  args = parser.parse_args(argv)

  # Dispatch to the function set for target subparser using set_defaults.
  return args.func(args)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
