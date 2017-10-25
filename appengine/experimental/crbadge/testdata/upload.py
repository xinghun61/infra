#!/usr/bin/python

import os, sys
import optparse
import json, urllib
import httplib2
import urlparse


def upload(filenames, url, password):
  parsed = urlparse.urlparse(url)
  http = httplib2.Http()
  for filename in filenames:
    with open(filename) as f:
      # Load and validate JSON
      o = json.load(f)
    s = json.dumps(o)
    resp, cont = http.request(url, method='POST', body=urllib.urlencode(
        {'data': s, 'password': password}))
    print 'sent data to %s' % url
    print 'response (%s): %s: %s' % (resp['status'], resp, cont)


def main():
  parser = optparse.OptionParser()
  parser.add_option('-u', '--url')
  parser.add_option('-p', '--password')
  options, args = parser.parse_args()
  upload(args, options.url, options.password)


if __name__ == '__main__':
  main()

