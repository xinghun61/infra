// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"fmt"
	"net"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/auth"
	"go.chromium.org/luci/common/auth/devshell"
	"go.chromium.org/luci/common/auth/gsutil"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/system/environ"
	"go.chromium.org/luci/lucictx"

	"infra/libs/infraenv"
)

// OAuthScopes defines OAuth scopes used by Kitchen itself.
//
// This is superset of all scopes we might need. It is more efficient to create
// a single token with all the scopes than make a bunch of smaller-scoped
// tokens. We trust Google APIs enough to send widely-scoped tokens to them.
//
// Note that kitchen subprocesses (git, recipes engine, etc) are still free to
// request whatever scopes they need (though LUCI_CONTEXT protocol). The scopes
// here are only for parts of Kitchen (LogDog client, BigQuery export, Devshell
// proxy, etc).
//
// See https://developers.google.com/identity/protocols/googlescopes for list of
// available scopes.
var OAuthScopes = []string{
	"https://www.googleapis.com/auth/cloud-platform",
	"https://www.googleapis.com/auth/userinfo.email",
}

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
	// ID is used in logs and file names, it is friendly name of this context.
	ID string

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

	// EnableDevShell enables DevShell server and gsutil auth shim.
	//
	// They are used to make gsutil and gcloud use LUCI authentication.
	//
	// On Windows only gsutil auth shim is enabled, since enabling DevShell there
	// triggers bugs in gsutil. See https://crbug.com/788058#c14.
	EnableDevShell bool

	// KnownGerritHosts is list of Gerrit hosts to force git authentication for.
	//
	// By default public hosts are accessed anonymously, and the anonymous access
	// has very low quota. Kitchen needs to know all such hostnames in advance to
	// be able to force authenticated access to them.
	KnownGerritHosts []string

	ctx           context.Context     // stores modified LUCI_CONTEXT
	exported      lucictx.Exported    // exported LUCI_CONTEXT on disk
	authenticator *auth.Authenticator // used by Kitchen itself
	anonymous     bool                // true if not associated with any account
	email         string              // an account email or "" for anonymous

	gsutilSrv   *gsutil.Server // gsutil auth shim server
	gsutilState string         // path to a kitchen-managed state directory
	gsutilBoto  string         // path to a generated .boto file

	devShellSrv  *devshell.Server // DevShell server instance
	devShellAddr *net.TCPAddr     // address local DevShell instance is listening on

	gitHome string // custom HOME for git or "" if not using git auth
}

// Launch launches this auth context. It must be called before any other method.
//
// Callers shouldn't modify AuthContext fields after Launch is called.
func (ac *AuthContext) Launch(ctx context.Context, tempDir string) (err error) {
	defer func() {
		if err != nil {
			ac.Close()
		}
	}()

	ac.ctx = lucictx.SetLocalAuth(ctx, ac.LocalAuth)
	if ac.exported, err = lucictx.Export(ac.ctx); err != nil {
		return errors.Annotate(err, "failed to export LUCI_CONTEXT for %q account", ac.ID).Err()
	}

	// Construct authentication with default set of scopes to be used through out
	// Kitchen. Note: ServiceAccountJSONPath (if given) takes precedence over
	// ambient LUCI_CONTEXT authentication carried through ac.ctx.
	authOpts := infraenv.DefaultAuthOptions()
	authOpts.Scopes = OAuthScopes
	authOpts.ServiceAccountJSONPath = ac.ServiceAccountJSONPath
	ac.authenticator = auth.NewAuthenticator(ac.ctx, auth.SilentLogin, authOpts)

	// Figure out what email is associated with this account (if any).
	ac.email, err = ac.authenticator.GetEmail()
	switch {
	case err == auth.ErrLoginRequired:
		// This context is not associated with any account. This happens when
		// running Swarming tasks without service account specified.
		ac.anonymous = true
	case err != nil:
		return errors.Annotate(err, "failed to get email of %q account", ac.ID).Err()
	}

	if ac.EnableGitAuth {
		// Create new HOME for git and populate it with .gitconfig.
		ac.gitHome = filepath.Join(tempDir, "git_home_"+ac.ID)
		if err := os.Mkdir(ac.gitHome, 0700); err != nil {
			return errors.Annotate(err, "failed to create git HOME for %q account at %s", ac.ID, ac.gitHome).Err()
		}
		if err := ac.writeGitConfig(); err != nil {
			return errors.Annotate(err, "failed to setup .gitconfig for %q account", ac.ID).Err()
		}
	}

	if ac.EnableDevShell && !ac.anonymous {
		source, err := ac.authenticator.TokenSource()
		if err != nil {
			return errors.Annotate(err, "failed to get token source for %q account", ac.ID).Err()
		}

		// The directory for .boto and gsutil credentials cache (including access
		// tokens).
		ac.gsutilState = filepath.Join(tempDir, "gsutil_"+ac.ID)
		if err := os.Mkdir(ac.gsutilState, 0700); err != nil {
			return errors.Annotate(err, "failed to create gsutil state dir for %q account at %s", ac.ID, ac.gsutilState).Err()
		}

		// Launch gsutil auth shim server. It will put a specially constructed .boto
		// into gsutilState dir (and return path to it).
		ac.gsutilSrv = &gsutil.Server{
			Source:   source,
			StateDir: ac.gsutilState,
		}
		if ac.gsutilBoto, err = ac.gsutilSrv.Start(ctx); err != nil {
			return errors.Annotate(err, "failed to start gsutil auth shim server for %q account", ac.ID).Err()
		}

		// Presence of DevShell env var breaks gsutil on Windows. Luckily, we rarely
		// need to use gcloud in Windows, and gsutil (which we do use on Windows
		// extensively) is covered by gsutil auth shim server setup above.
		if runtime.GOOS != "windows" {
			ac.devShellSrv = &devshell.Server{
				Source: source,
				Email:  ac.email,
			}
			if ac.devShellAddr, err = ac.devShellSrv.Start(ctx); err != nil {
				return errors.Annotate(err, "failed to start the DevShell server").Err()
			}
		} else {
			// See https://crbug.com/788058#c14.
			logging.Warningf(ac.ctx, "Disabling devshell auth on Windows")
		}
	}

	return nil
}

// Close stops this context, cleaning up after it.
//
// The context is not usable after this. Logs errors inside (there's nothing
// caller can do about them anyway).
func (ac *AuthContext) Close() {
	if ac.gitHome != "" {
		if err := os.RemoveAll(ac.gitHome); err != nil {
			logging.Errorf(ac.ctx, "Failed to clean up git HOME for %q account at [%s]: %s", ac.ID, ac.gitHome, err)
		}
	}

	if ac.gsutilSrv != nil {
		if err := ac.gsutilSrv.Stop(ac.ctx); err != nil {
			logging.Errorf(ac.ctx, "Failed to stop gsutil shim server for %q account: %s", ac.ID, err)
		}
	}

	if ac.gsutilState != "" {
		if err := os.RemoveAll(ac.gsutilState); err != nil {
			logging.Errorf(ac.ctx, "Failed to clean up gsutil state for %q account at [%s]: %s", ac.ID, ac.gsutilState, err)
		}
	}

	if ac.devShellSrv != nil {
		if err := ac.devShellSrv.Stop(ac.ctx); err != nil {
			logging.Errorf(ac.ctx, "Failed to stop DevShell server for %q account: %s", ac.ID, err)
		}
	}

	if ac.exported != nil {
		if err := ac.exported.Close(); err != nil {
			logging.Errorf(ac.ctx, "Failed to delete exported LUCI_CONTEXT for %q account - %s", ac.ID, err)
		}
	}

	ac.ctx = nil
	ac.exported = nil
	ac.authenticator = nil
	ac.anonymous = false
	ac.email = ""
	ac.gsutilSrv = nil
	ac.gsutilState = ""
	ac.gsutilBoto = ""
	ac.devShellSrv = nil
	ac.devShellAddr = nil
	ac.gitHome = ""
}

// Authenticator returns an authenticator that can be used by Kitchen itself.
//
// It uses the default set of scopes, see OAuthScopes.
func (ac *AuthContext) Authenticator() *auth.Authenticator {
	return ac.authenticator
}

// ExportIntoEnv exports details of this context into the environment, so it can
// be inherited by subprocesses that supports it.
//
// Returns a modified copy of 'env'.
func (ac *AuthContext) ExportIntoEnv(env environ.Env) environ.Env {
	env = env.Clone()
	ac.exported.SetInEnviron(env)

	if ac.EnableGitAuth {
		env.Set("GIT_TERMINAL_PROMPT", "0")           // no interactive prompts
		env.Set("GIT_CONFIG_NOSYSTEM", "1")           // no $(prefix)/etc/gitconfig
		env.Set("INFRA_GIT_WRAPPER_HOME", ac.gitHome) // tell gitwrapper about the new HOME
	}

	if ac.EnableDevShell {
		env.Remove("BOTO_PATH") // avoid picking up bot-local configs, if any
		if ac.anonymous {
			// Make sure gsutil is not picking up any stale .boto configs randomly
			// laying around on the bot. Setting BOTO_CONFIG to empty dir disables
			// default ~/.boto.
			env.Set("BOTO_CONFIG", "")
		} else {
			// Point gsutil to use our auth shim server.
			env.Set("BOTO_CONFIG", ac.gsutilBoto)
			if ac.devShellAddr != nil {
				env.Set(devshell.EnvKey, fmt.Sprintf("%d", ac.devShellAddr.Port)) // pass the DevShell port
			}
		}
	}

	return env
}

// ReportServiceAccount logs service account email used by this auth context.
func (ac *AuthContext) ReportServiceAccount() {
	if ac.anonymous {
		logging.Infof(ac.ctx, "%q account is anonymous", ac.ID)
	} else {
		logging.Infof(ac.ctx, "%q account email is %s", ac.ID, ac.email)
	}
}

////

func (ac *AuthContext) writeGitConfig() error {
	var cfg gitConfig
	if !ac.anonymous {
		cfg = gitConfig{
			IsWindows:           runtime.GOOS == "windows",
			UserEmail:           ac.email,
			UserName:            strings.Split(ac.email, "@")[0],
			UseCredentialHelper: true,
			KnownGerritHosts:    ac.KnownGerritHosts,
		}
	} else {
		cfg = gitConfig{
			IsWindows:           runtime.GOOS == "windows",
			UserEmail:           "anonymous@example.com", // otherwise git doesn't work
			UserName:            "anonymous",
			UseCredentialHelper: false, // fetch will be anonymous, push will fail
			KnownGerritHosts:    nil,   // don't force non-anonymous fetch for public hosts
		}
	}
	return cfg.Write(filepath.Join(ac.gitHome, ".gitconfig"))
}
