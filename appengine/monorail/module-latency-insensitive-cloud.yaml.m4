# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

define(`_VERSION', `syscmd(`echo $_VERSION')')

service: latency-insensitive
runtime: python27
api_version: 1
threadsafe: no

default_expiration: "3600d"

instance_class: F4

ifdef(`PROD', `
automatic_scaling:
  min_idle_instances: 5
  max_pending_latency: 0.2s
')

handlers:
- url: /_ah/warmup
  script: monorailapp.app
  login: admin

- url: /_ah/api/.*
  script: monorailapp.endpoints

- url: /_task/.*
  script: monorailapp.app
  login: admin

- url: /_cron/.*
  script: monorailapp.app
  login: admin

- url: /_ah/mail/.*
  script: monorailapp.app
  login: admin

inbound_services:
- mail
- mail_bounce
ifdef(`PROD', `
- warmup
')

libraries:
- name: endpoints
  version: 1.0
- name: MySQLdb
  version: "latest"
- name: pycrypto
  version: "2.6"
- name: django
  version: 1.9

includes:
- gae_ts_mon

env_variables:
  VERSION_ID: '_VERSION'

skip_files:
- ^(.*/)?#.*#$
- ^(.*/)?.*~$
- ^(.*/)?.*\.py[co]$
- ^(.*/)?.*/RCS/.*$
- ^(.*/)?\..*$
- node_modules/
