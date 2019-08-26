// Copyright 2018 The LUCI Authors.
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

	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/config/server/cfgclient"
	"go.chromium.org/luci/config/server/cfgclient/textproto"
	"go.chromium.org/luci/config/validation"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
)

const configFile = "config.cfg"

// unique key used to store and retrieve context.
var contextKey = "qscheduler-swarming luci-config key"

// Provider returns the current non-nil config when called.
type Provider func() *Config

// Get returns the config in c if it exists, or nil.
// See also Use and MiddlewareForGAE.
func Get(c context.Context) *Config {
	if p, _ := c.Value(&contextKey).(Provider); p != nil {
		return p()
	}
	return nil
}

// MiddlewareForGAE loads the service config and installs it into the context.
//
// Works only on GAE currently, since 'cfgclient' library is not yet supported
// on GKE.
func MiddlewareForGAE(c *router.Context, next router.Handler) {
	var cfg Config
	err := cfgclient.Get(
		c.Context,
		cfgclient.AsService,
		cfgclient.CurrentServiceConfigSet(c.Context),
		configFile,
		textproto.Message(&cfg),
		nil,
	)
	if err != nil {
		logging.WithError(err).Errorf(c.Context, "could not load application config")
		http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)
		return
	}

	c.Context = Use(c.Context, func() *Config { return &cfg })
	next(c)
}

// Use installs a config provider into c.
func Use(c context.Context, p Provider) context.Context {
	return context.WithValue(c, &contextKey, p)
}

// SetupValidation adds validation rules for configuration data pushed via luci-config.
func SetupValidation() {
	rules := &validation.Rules
	rules.Add("services/${appid}", configFile, validateConfig)
}

func validateConfig(c *validation.Context, configSet, path string, content []byte) error {
	cfg := &Config{}
	if err := proto.UnmarshalText(string(content), cfg); err != nil {
		c.Errorf("not a valid Config proto message: %s", err)
		return nil
	}
	return nil
}
