#!/usr/bin/env python
#
# Copyright 2012 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime

# This is a list of (start, duration) datetime pairs.  Whenever time.time() is
# between a start and the corresponding end, the wizard will simply
# redirect the user to the "classic" issue entry page, which presumably
# would inform the user that the site is read-only.
# Times are in UTC.

READ_ONLY_WINDOWS = [
    (datetime.datetime(2012, 10, 23, 13, 00, 00),
      datetime.timedelta(hours=2)),
    ]
