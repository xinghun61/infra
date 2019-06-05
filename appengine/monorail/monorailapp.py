# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Main program for Monorail.

Monorail is an issue tracking tool that is based on the code.google.com
issue tracker, but it has been ported to Google AppEngine and Google Cloud SQL.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import webapp2

from components import endpoints_webapp2

import gae_ts_mon

import registerpages
from framework import sorting
from services import api_svc_v1
from services import service_manager


services = service_manager.set_up_services()
sorting.InitializeArtValues(services)
registry = registerpages.ServletRegistry()
app_routes = registry.Register(services)
app = webapp2.WSGIApplication(
    app_routes, config={'services': services})
gae_ts_mon.initialize(app)

endpoints = endpoints_webapp2.api_server(
    [api_svc_v1.MonorailApi, api_svc_v1.ClientConfigApi])
