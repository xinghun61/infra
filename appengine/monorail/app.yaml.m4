# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

application: monorail-staging
version: 2015-05-26
runtime: python27
api_version: 1
threadsafe: no

default_expiration: "3600d"

ifdef(`PROD', `
instance_class: F4
automatic_scaling:
  min_idle_instances: 25
  max_pending_latency: 0.2s
')

ifdef(`STAGING', `
instance_class: F4
automatic_scaling:
  min_idle_instances: 25
  max_pending_latency: 0.2s
')

ifdef(`DEMO', `
instance_class: F4
')

handlers:
- url: /_ah/api/.*
  script: monorailapp.endpoints

- url: /robots.txt
  static_files: static/robots.txt
  upload: static/robots.txt

- url: /database-maintenance
  static_files: static/database-maintenance.html
  upload: static/database-maintenance.html

- url: /bower_components
  static_dir: bower_components
  secure: always
  mime_type: application/javascript

- url: /node_modules
  static_dir: node_modules
  secure: always
  mime_type: application/javascript

- url: /deployed_node_modules
  static_dir: deployed_node_modules
  secure: always
  mime_type: application/javascript

- url: /elements
  static_dir: elements
  secure: always

- url: /static/jsm
  static_dir: static/jsm
  mime_type: application/javascript

- url: /static
  static_dir: static

- url: /_ah/mail/.+
  script: monorailapp.app
  login: admin

- url: /_ah/warmup
  script: monorailapp.app
  login: admin

- url: /.*
  script: monorailapp.app
  secure: always

inbound_services:
- mail
- mail_bounce
ifdef(`PROD', `
- warmup
')
ifdef(`STAGING', `
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

skip_files:
- ^(.*/)?#.*#$
- ^(.*/)?.*~$
- ^(.*/)?.*\.py[co]$
- ^(.*/)?.*/RCS/.*$
- ^(.*/)?\..*$
- node_modules/
