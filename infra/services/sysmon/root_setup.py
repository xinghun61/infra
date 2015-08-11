# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from infra.services.service_manager import root_setup as service_manager_setup

def root_setup():
  service_manager_setup.write_service(
      name='sysmon',
      root_directory='/opt/infra-python',
      tool='infra.services.sysmon',
      args=['--interval', '60'])
  return 0
