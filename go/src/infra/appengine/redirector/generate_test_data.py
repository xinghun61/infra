# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''Quick and dirty script to generate the test data in redirect_test.go'''

import requests

CRBUG_HOSTS = [
  "crbug.com",
  "www.crbug.com",
  "new.crbug.com",
]

CRBUG_PATHS = [
  "/",
  "/new",
  "/new/",
  "/new/blah",
  "/new/blah/",
  "/new-detailed",
  "/new-detailed/",
  "/new-detailed/blah",
  "/new-detailed/blah/",
  "/wizard",
  "/wizard/",
  "/wizard/blah",
  "/wizard/blah/",
  "/1234",
  "/1234/",
  "/1234/blah",
  "/1234/blah/",
  "/foo",
  "/foo/",
  "/foo/new",
  "/foo/new/",
  "/foo/blah",
  "/foo/blah/",
  "/foo/1234",
  "/foo/1234/",
  "/foo/1234/blah",
  "/foo/1234/blah/",
  "/_foo",
  "/foo_",
  "/~bar",
  "/~bar/",
  "/foo/~bar",
  "/foo/~bar/",
]

for host in CRBUG_HOSTS:
  for path in CRBUG_PATHS:
    url = "https://%s%s" % (host, path)
    r = requests.get(url, allow_redirects=False)
    print '{"%s", "%s", %d},' % (
        url, r.headers.get("Location", ""), r.status_code)
  print ''
