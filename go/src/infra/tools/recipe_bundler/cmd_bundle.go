// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"crypto/sha1"
	"encoding/hex"
	"net/url"
	"os"
	"path/filepath"
	"strings"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/cipd/client/cipd"
	cipd_common "go.chromium.org/luci/cipd/client/cipd/common"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag/stringmapflag"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/hardcoded/chromeinfra"
)

func bundleCmd(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "bundle [options]",
		ShortDesc: "Bundles recipe repos",

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdBundle{}
			ret.logCfg.Level = logging.Info
			ret.authFlags.Register(&ret.Flags, authOpts)

			ret.Flags.Var(&ret.reposInput, "r",
				`(repeatable) A `+"`"+`repospec`+"`"+` to bundle (e.g. 'host.name/to/repo').

	A git revision may be provided with an =, e.g. 'host.name/to/repo=deadbeef'.
	The revision must be either a full hexadecimal commit id, or it may be the literal
	'FETCH_HEAD' to indicate that the latest version should be used.

	If this revision lies on a ref other than 'HEAD', you may provide the
	ref to fetch after the revision by separating it with a comma, e.g.
	'host.name/to/repo=deadbeef,refs/other/thing'. Note that most repos configure
	'HEAD' to symlink to 'refs/heads/master'. See e.g.
	https://stackoverflow.com/a/8841024`)

			ret.Flags.StringVar(&ret.localDest, "local", "",
				`Set to a non-empty path, and this tool will produce CIPD packages in that local directory.
	Otherwise it will upload them to CIPD.`)

			ret.Flags.StringVar(&ret.workdir, "workdir", "./recipe_bundler",
				`Set where this tool should store its repo checkouts`)

			ret.Flags.StringVar(&ret.packageNamePrefix, "package-name-prefix", "infra/recipe_bundles",
				`Set to override the default CIPD package name prefix.`)

			return ret
		},
	}
}

type fetchSpec struct {
	revision string
	ref      string
}

type cmdBundle struct {
	subcommands.CommandRunBase

	logCfg    logging.Config
	authFlags authcli.Flags

	reposInput        stringmapflag.Value
	localDest         string
	workdir           string
	packageNamePrefix string

	repos map[string]fetchSpec
}

func parseRepoInput(input stringmapflag.Value) (ret map[string]fetchSpec, err error) {
	ret = make(map[string]fetchSpec, len(input))
	for repo, fetchInfo := range input {
		if repo == "" {
			err = errors.New("repo URL is blank")
			return
		}
		var u *url.URL
		if u, err = url.Parse("https://" + repo); err != nil {
			err = errors.Annotate(err, "parsing repo %q", repo).Err()
			return
		}
		if strings.Contains(u.Host, ":") {
			err = errors.Reason("parsing repo %q: must not include scheme", repo).Err()
			return
		}

		spec := fetchSpec{"FETCH_HEAD", "HEAD"}
		if fetchInfo != "" {
			switch toks := strings.SplitN(fetchInfo, ",", 2); {
			case len(toks) == 1:
				spec.revision = toks[0]
			case len(toks) == 2:
				spec.revision, spec.ref = toks[0], toks[1]
				if spec.ref != "HEAD" && !strings.HasPrefix(spec.ref, "refs/") {
					err = errors.Reason("parsing repo %q: ref must start with 'refs/', got %q", repo, spec.ref).Err()
					return
				}
			}
			if spec.revision != "FETCH_HEAD" {
				var decoded []byte
				if decoded, err = hex.DecodeString(spec.revision); err != nil {
					err = errors.Annotate(err, "parsing repo %q: bad revision", repo).Err()
					return
				}
				if len(decoded) != sha1.Size {
					err = errors.Reason("parsing repo %q: bad revision: wrong length", repo).Err()
					return
				}
			}
		}
		ret[repo] = spec
	}

	return
}

func (c *cmdBundle) parseFlags() (opts auth.Options, err error) {
	if len(c.reposInput) == 0 {
		err = errors.New("no repos specified")
		return
	}

	c.repos, err = parseRepoInput(c.reposInput)
	if err != nil {
		err = errors.Annotate(err, "parsing repos").Err()
		return
	}

	if c.localDest != "" {
		c.localDest, err = filepath.Abs(c.localDest)
		if err != nil {
			err = errors.Annotate(err, "getting abspath of -local").Err()
			return
		}
		if err = os.MkdirAll(c.localDest, 0777); err != nil {
			err = errors.Annotate(err, "ensuring -local directory").Err()
			return
		}
	}

	if err = cipd_common.ValidatePackageName(c.packageNamePrefix); err != nil {
		err = errors.Annotate(err, "validating -package-name-prefix").Err()
		return
	}

	return c.authFlags.Options()
}

func (c *cmdBundle) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))

	authOpts, err := c.parseFlags()
	if err != nil {
		logging.WithError(err).Errorf(ctx, "parsing flags")
		return 1
	}
	authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)
	authClient, err := authenticator.Client()
	if err != nil {
		logging.WithError(err).Errorf(ctx, "while getting authenticator")
		return 1
	}

	cipdOpts := cipd.ClientOptions{
		ServiceURL:          chromeinfra.CIPDServiceURL,
		AuthenticatedClient: authClient,
	}
	cipdOpts.LoadFromEnv(func(key string) string {
		logging.Warningf(ctx, "CHECK %s", key)
		return env[key].Value
	})
	client, err := cipd.NewClient(cipdOpts)
	if err != nil {
		logging.WithError(err).Errorf(ctx, "while generating cipd client")
		return 1
	}

	logging.Warningf(ctx, "I GOT: %s %v", c.repos, client)
	return 0
}
