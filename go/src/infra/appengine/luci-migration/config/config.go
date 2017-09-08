// Copyright 2017 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package config

import (
	"golang.org/x/net/context"

	"go.chromium.org/luci/luci_config/server/cfgclient"
	"go.chromium.org/luci/luci_config/server/cfgclient/textproto"
)

// Get returns currently imported config.
func Get(c context.Context) (*Config, error) {
	var cfg Config
	return &cfg, cfgclient.Get(
		c,
		cfgclient.AsService,
		cfgclient.CurrentServiceConfigSet(c),
		"config.cfg",
		textproto.Message(&cfg),
		nil,
	)
}
