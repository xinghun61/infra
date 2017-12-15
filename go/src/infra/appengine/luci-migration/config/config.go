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
	"net/http"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/luci_config/server/cfgclient"
	"go.chromium.org/luci/luci_config/server/cfgclient/textproto"
	"go.chromium.org/luci/server/router"
)

var contextKey = "config"

// Get returns the config in c, or panics.
// See also Use and Middleware.
func Get(c context.Context) *Config {
	return c.Value(contextKey).(*Config)
}

// Use installs cfg into c.
func Use(c context.Context, cfg *Config) context.Context {
	return context.WithValue(c, contextKey, cfg)
}

// Middleware loads config and installs into context.
func Middleware(c *router.Context, next router.Handler) {
	var cfg Config
	err := cfgclient.Get(
		c.Context,
		cfgclient.AsService,
		cfgclient.CurrentServiceConfigSet(c.Context),
		"config.cfg",
		textproto.Message(&cfg),
		nil,
	)
	if err != nil {
		logging.WithError(err).Errorf(c.Context, "could not load application config")
		http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)
		return
	}

	c.Context = Use(c.Context, &cfg)
	next(c)
}

// FindMaster finds a master by name.
func (c *Config) FindMaster(master string) *Master {
	for _, m := range c.Masters {
		if m.Name == master {
			return m
		}
	}
	return nil
}
