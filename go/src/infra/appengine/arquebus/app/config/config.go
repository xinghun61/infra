// Copyright 2019 The LUCI Authors.
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

// Package config implements interface for app-level configs for Arquebus.
package config

import (
	"net/http"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/config"
	"go.chromium.org/luci/config/server/cfgclient"
	"go.chromium.org/luci/config/server/cfgclient/textproto"
	"go.chromium.org/luci/config/validation"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"

	"infra/appengine/arquebus/app/util"
)

const (
	configFile = "config.cfg"
)

// unique type to prevent assignment.
type ctxKeyTypeConfig struct{}
type ctxKeyTypeConfigMeta struct{}

// unique key used to store and retrieve context.
var ctxKeyConfig = ctxKeyTypeConfig{}
var ctxKeyConfigMeta = ctxKeyTypeConfigMeta{}

// Get returns the config stored in the context.
func Get(c context.Context) *Config {
	return c.Value(ctxKeyConfig).(*Config)
}

// Middleware loads the service config and installs it into the context.
func Middleware(c *router.Context, next router.Handler) {
	var cfg Config
	var meta config.Meta
	err := cfgclient.Get(
		c.Context,
		cfgclient.AsService,
		cfgclient.CurrentServiceConfigSet(c.Context),
		configFile,
		textproto.Message(&cfg),
		&meta,
	)
	if err != nil {
		logging.WithError(err).Errorf(c.Context, "could not load application config")
		http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)
		return
	}

	c.Context = SetConfig(c.Context, &cfg)
	c.Context = SetConfigMeta(c.Context, &meta)
	next(c)
}

// SetConfig installs cfg into c.
func SetConfig(c context.Context, cfg *Config) context.Context {
	return context.WithValue(c, ctxKeyConfig, cfg)
}

// SetConfigMeta installs the Config.Meta into c.
func SetConfigMeta(c context.Context, meta *config.Meta) context.Context {
	return context.WithValue(c, ctxKeyConfigMeta, meta)
}

// GetConfigRevision returns the revision of the current config.
func GetConfigRevision(c context.Context) string {
	meta := c.Value(ctxKeyConfigMeta).(*config.Meta)
	return meta.Revision
}

// SetupValidation adds validation rules for configuration data pushed via
// luci-config.
func SetupValidation(rules *validation.RuleSet) {
	rules.Add("services/${appid}", configFile, validateConfig)
}

// IsEqual returns whether the IssueQuery objects are equal.
func (lhs *IssueQuery) IsEqual(rhs *IssueQuery) bool {
	// IssueQuery is a proto-generated struct.
	return (lhs.Q == rhs.Q &&
		util.EqualSortedLists(lhs.ProjectNames, rhs.ProjectNames))
}
