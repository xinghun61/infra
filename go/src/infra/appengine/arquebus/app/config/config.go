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
	"net/mail"
	"regexp"
	"time"

	"github.com/golang/protobuf/proto"
	"github.com/golang/protobuf/ptypes"
	"go.chromium.org/luci/common/data/stringset"
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
	// The regex rule that all assigner IDs must conform to.
	assignerIDRegex = `^([a-z0-9]+-?)*[a-z0-9]$`
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

	c.Context = setConfig(c.Context, &cfg)
	c.Context = setConfigMeta(c.Context, &meta)
	next(c)
}

// setConfig installs cfg into c.
func setConfig(c context.Context, cfg *Config) context.Context {
	return context.WithValue(c, ctxKeyConfig, cfg)
}

// setConfigMeta installs the Config.Meta into c.
func setConfigMeta(c context.Context, meta *config.Meta) context.Context {
	return context.WithValue(c, ctxKeyConfigMeta, meta)
}

// GetConfigRevision returns the revision of the current config.
func GetConfigRevision(c context.Context) string {
	meta := c.Value(ctxKeyConfigMeta).(*config.Meta)
	return meta.Revision
}

// SetupValidation adds validation rules for configuration data pushed via
// luci-config.
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
	// check duplicate IDs.
	seen := stringset.New(len(cfg.Assigners))
	for i, a := range cfg.Assigners {
		c.Enter("assigner #%d:%s", i+1, a.Id)
		if !seen.Add(a.Id) {
			c.Errorf("duplicate id")
		}
		validateAssigner(c, a)
		c.Exit()
	}
	return nil
}

func validateAssigner(c *validation.Context, a *Assigner) {
	// to make URLs short and simple when they are made with assigner ids.
	re := regexp.MustCompile(assignerIDRegex)
	if !re.MatchString(a.Id) {
		c.Errorf(
			"invalid id; only lowercase alphabet letters and " +
				"numbers are allowed. A hyphen may be placed " +
				"between letters and numbers",
		)
	}

	// owners should be all valid email addresses.
	for _, owner := range a.Owners {
		c.Enter("owner %q", owner)
		if _, err := mail.ParseAddress(owner); err != nil {
			c.Errorf("invalid email address: %s", err)
		}
		c.Exit()
	}

	if a.Interval == nil {
		c.Errorf("missing interval")
	} else {
		d, err := ptypes.Duration(a.Interval)
		if err != nil {
			c.Errorf("invalid interval: %s", err)
		} else if d < time.Minute {
			c.Errorf("interval should be at least one minute")
		}
	}

	if a.IssueQuery == nil {
		c.Errorf("missing issue_query")
	} else {
		c.Enter("issue_query")
		if a.IssueQuery.Q == "" {
			c.Errorf("missing q")
		}
		if len(a.IssueQuery.ProjectNames) == 0 {
			c.Errorf("missing project_names")
		}
		c.Exit()
	}

	if len(a.Rotations) == 0 {
		c.Errorf("missing rotations")
	}
}

// IsEqual returns whether the IssueQuery objects are equal.
func (lhs *IssueQuery) IsEqual(rhs *IssueQuery) bool {
	// IssueQuery is a proto-generated struct.
	return (lhs.Q == rhs.Q &&
		util.EqualSortedLists(lhs.ProjectNames, rhs.ProjectNames))
}
