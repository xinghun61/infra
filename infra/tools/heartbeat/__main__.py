#!/usr/bin/python
# Copyright 2014 Google Inc. All Rights Reserved.
# pylint: disable=F0401

"""Sign and send a heartbeat message to a remote service."""


import argparse
import sys

from infra.tools.heartbeat import heartbeat


def parse_options():
  # Gather user options.
  parser = argparse.ArgumentParser()
  parser.add_argument('-u', '--urls', help='URLs to send heartbeat.',
      action='append', default=[
          'https://chrome-heartbeats.appspot.com/heartbeat'])
  parser.add_argument('-n', '--name', help='Override the hostname detector.')
  parser.add_argument('-i', '--ident', help='Override the machine ID.')
  parser.add_argument('-s', '--secret',
                    default='~/.heartbeat.key',
                    help='Key file for authentication')
  args = parser.parse_args()

  secret = heartbeat.get_secret(args.secret)
  return secret, args.name, args.ident, args.urls


def main():
  # Step 1: Get options and secret.
  secret, name, ident, urls = parse_options()

  # Step 2: Create and populate the heartbeat object.
  data = heartbeat.get_heartbeat_data(name, ident)

  # Step 3: Sign heartbeat with key.
  signed_message = heartbeat.get_hashed_message(data, secret)

  # Step 4: Send heartbeat
  result = heartbeat.send(signed_message, urls)
  if result == 402:
    # Unknown user -> need to send key along with request.
    print 'Server does not recognize the hostname. Resending with key.'
    signed_message['key'] = secret
    result = heartbeat.send(signed_message, urls)
  return result


if __name__ == '__main__':
  sys.exit(main())
