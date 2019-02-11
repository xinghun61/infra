# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cryptography
import requests

SITE = 'https://www.google.com'

print 'Using requests version:', requests.__version__
print 'Using cryptography version:', cryptography.__version__
print 'Testing requests from:', SITE
r = requests.get(SITE)
print 'Status Code:', r.status_code
if len(r.text) == 0:
  print 'Content length is zero!'
else:
  print 'Content length is non-zero.'
