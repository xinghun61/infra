#!/bin/bash
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -ex

gzip -k icon.png
gsutil -h "Content-Encoding:gzip" \
       -h "Content-Type:image/png" \
       -h "Cache-Control:public, max-age=3600" \
       cp icon.png.gz gs://crdx-feedback.appspot.com/icon.png
rm icon.png.gz
gsutil acl ch -u AllUsers:R gs://crdx-feedback.appspot.com/icon.png

gzip -k feedback.js
gsutil -h "Content-Encoding:gzip" \
       -h "Content-Type:application/javascript; charset=utf-8" \
       -h "Cache-Control:public, max-age=3600" \
       cp feedback.js.gz gs://crdx-feedback.appspot.com/feedback.js
rm feedback.js.gz
gsutil acl ch -u AllUsers:R gs://crdx-feedback.appspot.com/feedback.js
