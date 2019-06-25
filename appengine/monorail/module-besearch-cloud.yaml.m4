# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

define(`_VERSION', `syscmd(`echo $_VERSION')')

service: besearch
runtime: python27
api_version: 1
threadsafe: no

instance_class: F4

ifdef(`PROD', `
automatic_scaling:
  min_idle_instances: 40
  max_pending_latency: 0.2s
')

handlers:
- url: /_ah/warmup
  script: monorailapp.app
  login: admin

- url: /_backend/.*
  script: monorailapp.app

- url: /_ah/start
  script: monorailapp.app
  login: admin

- url: /_ah/stop
  script: monorailapp.app
  login: admin

ifdef(`PROD', `
inbound_services:
- warmup
')

libraries:
- name: endpoints
  version: 1.0
- name: MySQLdb
  version: "latest"
- name: django
  version: 1.4

env_variables:
  VERSION_ID: '_VERSION'

skip_files:
- ^(.*/)?#.*#$
- ^(.*/)?.*~$
- ^(.*/)?.*\.py[co]$
- ^(.*/)?.*/RCS/.*$
- ^(.*/)?\..*$
- node_modules/
