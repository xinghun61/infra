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
	"golang.org/x/net/context"

	cipd_common "go.chromium.org/luci/cipd/client/cipd/common"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag/stringmapflag"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
)

func bundleCmd() *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "bundle [options]",
		ShortDesc: "Bundles recipe repos",

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdBundle{}
			ret.logCfg.Level = logging.Info
			ret.logCfg.AddFlags(&ret.Flags)

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

func (f fetchSpec) isPinned() bool {
	return f.revision != "FETCH_HEAD"
}

type cmdBundle struct {
	subcommands.CommandRunBase

	logCfg logging.Config

	reposInput        stringmapflag.Value
	localDest         string
	workdir           string
	packageNamePrefix string

	env subcommands.Env

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

func (c *cmdBundle) parseFlags() (err error) {
	if len(c.reposInput) == 0 {
		return errors.New("no repos specified")
	}

	c.repos, err = parseRepoInput(c.reposInput)
	if err != nil {
		return errors.Annotate(err, "parsing repos").Err()
	}

	if c.localDest != "" {
		c.localDest, err = filepath.Abs(c.localDest)
		if err != nil {
			return errors.Annotate(err, "getting abspath of -local").Err()
		}
		if err = os.MkdirAll(c.localDest, 0777); err != nil {
			return errors.Annotate(err, "ensuring -local directory").Err()
		}
	}

	if err = cipd_common.ValidatePackageName(c.packageNamePrefix); err != nil {
		return errors.Annotate(err, "validating -package-name-prefix").Err()
	}

	if c.workdir, err = filepath.Abs(c.workdir); err != nil {
		return errors.Annotate(err, "resolving workdir").Err()
	}

	return nil
}

func (c *cmdBundle) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))
	c.env = env

	if err := c.parseFlags(); err != nil {
		logging.WithError(err).Errorf(ctx, "parsing flags")
		return 1
	}

	if err := c.run(ctx); err != nil {
		logging.WithError(err).Errorf(ctx, "failed")
		return 1
	}
	return 0
}

var pathSquisher = strings.NewReplacer(
	"/", "_",
	"\\", "_",
)

func (c *cmdBundle) mkRepoDirs(repoName string) (repo gitRepo, bundledir string, err error) {
	base := filepath.Join(c.workdir, pathSquisher.Replace(repoName))
	repo = gitRepo(filepath.Join(base, "repo"))
	bundledir = filepath.Join(base, "bndl")

	if err = os.MkdirAll(string(repo), 0777); err != nil {
		return
	}

	err = os.MkdirAll(bundledir, 0777)
	return
}

type gitRepo string

func (g gitRepo) git(ctx context.Context, args ...string) error {
	logging.Debugf(ctx, "running: %q", args)
	return nil
}

func (g gitRepo) hasCommit(ctx context.Context, commit string) bool {
	return g.git(ctx, "cat-file", "-e", commit+"^{commit}") == nil
}

func (g gitRepo) currentRevision(ctx context.Context) (string, error) {
	return "", nil
}

func (c *cmdBundle) run(ctx context.Context) error {
	return parallel.FanOutIn(func(ch chan<- func() error) {
		for repoName, fetch := range c.repos {
			repoName, fetch := repoName, fetch
			ch <- func() error {
				repo, bundleDir, err := c.mkRepoDirs(repoName)
				if err != nil {
					return errors.Annotate(err, "making repo dirs").Err()
				}
				ctx := logging.SetFields(ctx, logging.Fields{
					"repo":    repoName,
					"workdir": filepath.Dir(bundleDir),
				})

				logging.Infof(ctx, "fetching: %v", fetch)
				if err = repo.git(ctx, "init"); err != nil {
					return err
				}
				if !fetch.isPinned() || !repo.hasCommit(ctx, fetch.revision) {
					if err = repo.git(ctx, "fetch", "https://"+repoName, fetch.ref); err != nil {
						return err
					}
				}
				if err = repo.git(ctx, "checkout", fetch.revision); err != nil {
					return err
				}
				if fetch.revision, err = repo.currentRevision(ctx); err != nil {
					return err
				}
				logging.Infof(ctx, "got revision: %q", fetch.revision)

				// TODO
				// if ! local check cipd to see if this is done already
				// recipe fetch
				// recipe bundle
				// build cipd package
				// [upload cipd package]
				return nil
			}
		}
	})
}
