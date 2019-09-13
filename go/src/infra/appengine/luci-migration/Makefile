# Copyright 2018 The LUCI Authors. All rights reserved.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
projdir := $(patsubst %/,%,$(dir $(mkfile_path)))

up:
	gae.py upload -A luci-migration --app-dir $(projdir)/app

switch:
	gae.py switch -A luci-migration --app-dir $(projdir)/app

up-dev:
	gae.py upload -A luci-migration-dev --app-dir $(projdir)/app

switch-dev:
	gae.py switch -A luci-migration-dev --app-dir $(projdir)/app
