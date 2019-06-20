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

package config

import (
	"context"
	"flag"
	"io/ioutil"
	"net/http"
	"sync/atomic"
	"time"

	"github.com/golang/protobuf/proto"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
)

// Loader periodically rereads qscheduler config file from disk and injects
// it into the request context.
//
// Intended for GKE environment where the config is distributed as k8s ConfigMap
// object.
type Loader struct {
	ConfigPath string // path to the config file, set via -qscheduler-config

	lastGood atomic.Value
}

// RegisterFlags registers CLI flags.
func (l *Loader) RegisterFlags(fs *flag.FlagSet) {
	fs.StringVar(&l.ConfigPath, "qscheduler-config", "", "Path to qscheduler config file")
}

// Load parses and validates the config file.
//
// On success remembers it as a "last good config", to be used when serving
// requests.
func (l *Loader) Load() (*Config, error) {
	if l.ConfigPath == "" {
		return nil, errors.Reason("-qscheduler-config is required").Err()
	}

	blob, err := ioutil.ReadFile(l.ConfigPath)
	if err != nil {
		return nil, errors.Annotate(err, "failed to open the config file").Err()
	}

	cfg := &Config{}
	if err := proto.UnmarshalText(string(blob), cfg); err != nil {
		return nil, errors.Annotate(err, "not a valid Config proto message").Err()
	}

	l.lastGood.Store(cfg)
	return cfg, nil
}

// Config returns last good config or nil.
func (l *Loader) Config() *Config {
	cfg, _ := l.lastGood.Load().(*Config)
	return cfg
}

// ReloadLoop periodically reloads the config file until the context is
// canceled.
func (l *Loader) ReloadLoop(c context.Context) {
	for {
		if r := <-clock.After(c, time.Minute); r.Err != nil {
			return // the context is canceled, the server is closing
		}
		prevCfg := l.Config()
		newCfg, err := l.Load()
		if err != nil {
			logging.WithError(err).Errorf(c, "Failed to reload the config, using the cached one")
		} else if prevCfg != nil && !proto.Equal(prevCfg, newCfg) {
			logging.Infof(c, "Reloaded the config")
		}
	}
}

// Install returns a middleware that injects the latest good config into
// the request context.
//
// Fails requests with internal error if there's no config available.
func (l *Loader) Install() router.Middleware {
	return func(c *router.Context, next router.Handler) {
		if cfg := l.Config(); cfg != nil {
			c.Context = Use(c.Context, cfg)
			next(c)
		} else {
			logging.Errorf(c.Context, "Application config not loaded yet")
			http.Error(c.Writer, "Internal server error", http.StatusInternalServerError)
		}
	}
}
