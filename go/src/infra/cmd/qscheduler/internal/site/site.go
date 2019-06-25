// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package site contains site local constants for the qscheduler tool.
package site

import (
	"os"
	"path/filepath"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/grpc/prpc"
)

// Environment contains environment specific values.
type Environment struct {
	QSchedulerHost string
}

// Prod is the environment for prod.
var Prod = Environment{
	QSchedulerHost: "qscheduler-prod.chromium.org",
}

// Dev is the environment for dev.
var Dev = Environment{
	QSchedulerHost: "qscheduler-dev.chromium.org",
}

// DefaultAuthOptions is an auth.Options struct prefilled with chrome-infra
// defaults.
//
// TODO(ayatane/akeshet): This is copied from the Go swarming client.  We
// should probably get our own OAuth client credentials at some point.
var DefaultAuthOptions = auth.Options{
	// Note that ClientSecret is not really a secret since it's hardcoded into
	// the source code (and binaries). It's totally fine, as long as it's callback
	// URI is configured to be 'localhost'. If someone decides to reuse such
	// ClientSecret they have to run something on user's local machine anyway
	// to get the refresh_token.
	ClientID:     "446450136466-2hr92jrq8e6i4tnsa56b52vacp7t3936.apps.googleusercontent.com",
	ClientSecret: "uBfbay2KCy9t4QveJ-dOqHtp",
	SecretsDir:   SecretsDir(),
	Scopes:       []string{auth.OAuthScopeEmail},
}

// DefaultPRPCOptions is used for PRPC clients.  If it is nil, the
// default value is used.  See prpc.Options for details.
//
// This is provided so it can be overridden for testing.
var DefaultPRPCOptions *prpc.Options

// SecretsDir returns an absolute path to a directory (in $HOME) to keep secret
// files in (e.g. OAuth refresh tokens) or an empty string if $HOME can't be
// determined (happens in some degenerate cases, it just disables auth token
// cache).
func SecretsDir() string {
	configDir := os.Getenv("XDG_CACHE_HOME")
	if configDir == "" {
		configDir = filepath.Join(os.Getenv("HOME"), ".cache")
	}
	return filepath.Join(configDir, "qscheduler", "auth")
}
