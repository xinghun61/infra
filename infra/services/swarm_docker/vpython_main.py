#!/usr/bin/env vpython
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file serves as an alternative entry-point for the swarm_docker package.

It replaces infra's VENV (invoked via the //run.py tool) with vpython. The
following vpython spec handles the needed non-std py libs, while the system
path manipulation below it handles the path setup.

This should allow the package to be invoked by either vpython or //run.py.

TODO(crbug.com/977627): Migrate all *_docker packages to vpython and tear out
VENV support if things work well.
"""

# [VPYTHON:BEGIN]
# wheel: <
#   name: "infra/python/wheels/docker-py2_py3"
#   version: "version:2.7.0"
# >
# wheel: <
#   name: "infra/python/wheels/docker-pycreds-py2_py3"
#   version: "version:0.2.1"
# >
# wheel: <
#   name: "infra/python/wheels/backports_ssl_match_hostname-py2_py3"
#   version: "version:3.5.0.1"
# >
# wheel: <
#   name: "infra/python/wheels/ipaddress-py2"
#   version: "version:1.0.18"
# >
# wheel: <
#   name: "infra/python/wheels/six-py2_py3"
#   version: "version:1.10.0"
# >
# wheel: <
#   name: "infra/python/wheels/requests-py2_py3"
#   version: "version:2.21.0"
# >
# wheel: <
#   name: "infra/python/wheels/websocket_client-py2_py3"
#   version: "version:0.40.0"
# >
# wheel: <
#   name: "infra/python/wheels/certifi-py2_py3"
#   version: "version:2018.11.29"
# >
# wheel: <
#   name: "infra/python/wheels/chardet-py2_py3"
#   version: "version:3.0.4"
# >
# wheel: <
#   name: "infra/python/wheels/idna-py2_py3"
#   version: "version:2.8"
# >
# wheel: <
#   name: "infra/python/wheels/urllib3-py2_py3"
#   version: "version:1.22"
# >
# [VPYTHON:END]

import os
import sys

ROOT_INFRA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, ROOT_INFRA_DIR)

from infra.services.swarm_docker import __main__ as swarm_docker_main
from infra.services.swarm_docker import main_helpers


if __name__ == '__main__':
  with main_helpers.main_wrapper():
    sys.exit(swarm_docker_main.main())
