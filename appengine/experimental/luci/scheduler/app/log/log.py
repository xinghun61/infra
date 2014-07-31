# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from app.response import success, failure
from app.framework import Application
from app.log.model import log, get_logs

app = Application(debug = True)

@app.route('/log/<category:.+(/.+)?>/', methods = ['POST'])
def put(request, category):
  lines = request.get_all('line')
  if len(lines):
    log(category, lines)
  return success()

@app.route('/log/<category:.+(/.+)?>/', methods = ['GET'])
def get(request, category):
  return success({'logs': get_logs(category)})

@app.route('/log/<category:.+(/.+)?>', methods = ['GET', 'POST'])
def no_slash(request, category):
  if request.method == 'GET':
    return get(request, category)
  else:
    return put(request, category)
