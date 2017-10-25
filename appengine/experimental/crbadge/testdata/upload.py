#!/usr/bin/python

import os, sys
import argparse
import json, urllib


def upload(filenames, url):
  for filename in filenames:
    with open(filename) as f:
      # Load and validate JSON
      o = json.load(f)
    s = json.dumps(o)
    urllib.urlopen(url, data=urllib.urlencode({'data': s}))


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-u', '--url')
  parser.add_argument('filenames', nargs='+')
  args = parser.parse_args()
  upload(args.filenames, args.url)


if __name__ == '__main__':
  main()

