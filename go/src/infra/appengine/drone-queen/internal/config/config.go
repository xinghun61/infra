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

// Package config contains the service configuration protos.
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

//go:generate cproto

// File is the path of the LUCI config file.
const File = "config.cfg"

type key struct{}

// Get gets the config in the context.  If the context does not have a
// config, return a nil config.
//
// See also Use and Middleware.
func Get(ctx context.Context) *Config {
	switch v := ctx.Value(key{}); v := v.(type) {
	case *Config:
		return v
	case nil:
		return nil
	default:
		panic(v)
	}
}

// Use installs the config into ctx.
func Use(ctx context.Context, c *Config) context.Context {
	return context.WithValue(ctx, key{}, c)
}

// Validate is a LUCI config validation function.
func Validate(ctx *validation.Context, configSet, path string, content []byte) error {
	var c Config
	if err := proto.UnmarshalText(string(content), &c); err != nil {
		ctx.Errorf("unmarshaling config proto: %s", err)
		return nil
	}
	return nil
}

// Middleware loads the service config and installs it into the context.
func Middleware(ctx *router.Context, next router.Handler) {
	var cfg Config
	err := cfgclient.Get(
		ctx.Context,
		cfgclient.AsService,
		cfgclient.CurrentServiceConfigSet(ctx.Context),
		File,
		textproto.Message(&cfg),
		nil,
	)
	if err != nil {
		logging.WithError(err).Errorf(ctx.Context, "could not load application config")
		http.Error(ctx.Writer, "Internal server error", http.StatusInternalServerError)
		return
	}

	ctx.Context = Use(ctx.Context, &cfg)
	next(ctx)
}

// Instance returns the configured instance of the service.
func Instance(ctx context.Context) string {
	n := Get(ctx).GetInstance()
	if n == "" {
		return "unknown"
	}
	return n
}
