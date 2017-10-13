// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"golang.org/x/net/context"

	"go.chromium.org/luci/common/auth"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/system/environ"
	"go.chromium.org/luci/lucictx"

	"infra/libs/infraenv"
)

// AuthContext represents some single service account to use for calls.
//
// Such context can be used by Kitchen itself or by subprocesses launched by
// Kitchen (if they are launched with environ populated via ExportIntoEnv).
//
// There are two such contexts: a system context and a recipe context.
//
// The system auth context is used for fetching recipes with git, running logdog
// and flushing metrics to BigQuery. On Swarming all these actions will use
// bot-associated account (specified in Swarming bot config), whose logical name
// (usually "system") is provided via "-luci-system-account" command-line flag.
//
// The recipe auth context is used for actually running the recipe. It is the
// context the kitchen starts with by default. On Swarming this will be the
// context associated with service account specified in the Swarming task
// definition.
//
// AuthContext is more than just a LUCI_CONTEXT with an appropriate account
// selected as default. It also implements necessary support for running third
// party tools (such as git and gsutil) with proper authentication.
type AuthContext struct {
	// Title is used only in logs, it is friendly name of this context.
	Title string

	// LocalAuth defines authentication related configuration that propagates to
	// the subprocesses through LUCI_CONTEXT.
	//
	// In particular it defines what logical account (e.g. "system" or "task") to
	// use by default in this context.
	//
	// May be nil, in which case the subprocesses won't use LUCI_CONTEXT auth
	// mechanism at all and instead will rely on existing cached refresh tokens or
	// other predeployed credentials. This happens in Buildbot mode.
	LocalAuth *lucictx.LocalAuth

	// ServiceAccountJSONPath is path to a service account private key to use.
	//
	// Exists for legacy Buildbot mode. When set, overrides LUCI_CONTEXT-based
	// authentication.
	//
	// Subprocesses do not inherit this authentication context: it affects only
	// Kitchen itself (e.g. logdog and bigquery auth, not git).
	//
	// TODO(vadimsh): It is possible to make subprocesses inherit this (by
	// launching local auth server in Kitchen and exposing it via LUCI_CONTEXT),
	// but it is not needed currently on Buildbot, so not implemented. This would
	// be needed for full "LUCI Emulation Mode" if it ever happens.
	ServiceAccountJSONPath string

	// EnableGitAuth enables authentication for git subprocesses.
	//
	// Assumes 'git' binary is actually gitwrapper and that 'git-credential-luci'
	// binary is in PATH.
	EnableGitAuth bool

	ctx      context.Context  // stores modified LUCI_CONTEXT
	exported lucictx.Exported // exported LUCI_CONTEXT on disk
}

// Launch launches this auth context. It must be called before any other method.
//
// Callers shouldn't modify AuthContext fields after Launch is called.
func (ac *AuthContext) Launch(ctx context.Context) error {
	ctx = lucictx.SetLocalAuth(ctx, ac.LocalAuth)
	exported, err := lucictx.Export(ctx)
	if err != nil {
		return errors.Annotate(err, "failed to export LUCI_CONTEXT for %s", ac.Title).Err()
	}

	if ac.EnableGitAuth {
		// TODO(vadimsh): Prepare new HOME with .gitconfig.
	}

	ac.ctx = ctx
	ac.exported = exported
	return nil
}

// Close stops this context, cleaning up after it.
//
// The context is not usable after this. Logs errors inside (there's nothing
// caller can do about them anyway).
func (ac *AuthContext) Close() {
	if ac.EnableGitAuth {
		// TODO(vadimsh): Kill git home.
	}

	if err := ac.exported.Close(); err != nil {
		logging.Errorf(ac.ctx, "Failed to delete exported LUCI_CONTEXT for %s - %s", ac.Title, err)
	}

	ac.ctx = nil
	ac.exported = nil
}

// Authenticator returns an authenticator that can be used by Kitchen itself.
func (ac *AuthContext) Authenticator(scopes []string) *auth.Authenticator {
	// Note: ServiceAccountJSONPath (if given) takes precedence over ambient
	// LUCI_CONTEXT authentication carried through ac.ctx.
	authOpts := infraenv.DefaultAuthOptions()
	authOpts.Scopes = scopes
	authOpts.ServiceAccountJSONPath = ac.ServiceAccountJSONPath
	return auth.NewAuthenticator(ac.ctx, auth.SilentLogin, authOpts)
}

// ExportIntoEnv exports details of this context into the environment, so it can
// be inherited by subprocesses that supports it.
//
// Returns a modified copy of 'env'.
func (ac *AuthContext) ExportIntoEnv(env environ.Env) environ.Env {
	env = env.Clone()
	ac.exported.SetInEnviron(env)
	if ac.EnableGitAuth {
		// TODO(vadimsh): Export git env vars.
	}
	return env
}

// ReportServiceAccount logs service account email used by this auth context.
func (ac *AuthContext) ReportServiceAccount() {
	email, err := ac.Authenticator([]string{auth.OAuthScopeEmail}).GetEmail()
	if err != nil {
		logging.Warningf(ac.ctx, "%s email is not known: %s", ac.Title, err)
	} else {
		logging.Infof(ac.ctx, "%s email is %s", ac.Title, email)
	}
}
