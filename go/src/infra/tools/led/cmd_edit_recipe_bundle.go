// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"

	"golang.org/x/net/context"

	"github.com/maruel/subcommands"

	"go.chromium.org/luci/client/authcli"
	"go.chromium.org/luci/common/auth"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag/stringmapflag"
	"go.chromium.org/luci/common/logging"
)

func editRecipeBundleCmd(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "edit-recipe-bundle [-O project_id=/path/to/local/repo]*",
		ShortDesc: "isolates recipes and adds them to a JobDefinition",
		LongDesc: `Takes recipes from the current repo (based on cwd), along with
any supplied overrides, and pushes them to the isolate service. The isolated
hash for the recipes will be added to the JobDefinition.

Isolating recipes takes a bit of time, so you may want to save the result
of this command (stdout) to an intermediate file for quick edits.
`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdEditRecipeBundle{}
			ret.logCfg.Level = logging.Info

			ret.logCfg.AddFlags(&ret.Flags)
			ret.authFlags.Register(&ret.Flags, authOpts)

			ret.Flags.Var(&ret.overrides, "O",
				"(repeatable) override a repo dependency. Takes a parameter of `project_id=/path/to/local/repo`.")
			return ret
		},
	}
}

type cmdEditRecipeBundle struct {
	subcommands.CommandRunBase

	logCfg    logging.Config
	authFlags authcli.Flags

	overrides stringmapflag.Value
}

func (c *cmdEditRecipeBundle) validateFlags(ctx context.Context, args []string) (authOpts auth.Options, err error) {
	if len(args) > 0 {
		err = errors.Reason("unexpected positional arguments: %q", args).Err()
		return
	}

	for k, v := range c.overrides {
		if k == "" {
			err = errors.New("override has empty project_id")
			return
		}
		if v == "" {
			err = errors.Reason("override %q has empty repo path", k).Err()
			return
		}
		v, err = filepath.Abs(v)
		if err != nil {
			err = errors.Annotate(err, "override %q", k).Err()
			return
		}
		c.overrides[k] = v

		var fi os.FileInfo
		switch fi, err = os.Stat(v); {
		case err != nil:
			err = errors.Annotate(err, "override %q", k).Err()
			return
		case !fi.IsDir():
			err = errors.Reason("override %q: not a directory", k).Err()
			return
		}
	}

	return c.authFlags.Options()
}

func (c *cmdEditRecipeBundle) prepBundle(ctx context.Context, recipesPy, subdir string) (string, error) {
	retDir, err := ioutil.TempDir("", "luci-editor-bundle")
	if err != nil {
		return "", errors.Annotate(err, "generating bundle tempdir").Err()
	}

	args := []string{
		recipesPy,
	}
	if logging.GetLevel(ctx) < logging.Info {
		args = append(args, "-v")
	}
	for projID, path := range c.overrides {
		args = append(args, "-O", fmt.Sprintf("%s=%s", projID, path))
	}
	args = append(args, "bundle", "--destination", filepath.Join(retDir, subdir))
	cmd := logCmd(ctx, "python", args...)
	if logging.GetLevel(ctx) < logging.Info {
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
	}
	if err := cmdErr(cmd.Run(), "creating bundle"); err != nil {
		os.RemoveAll(retDir)
		return "", err
	}

	return retDir, nil
}

// findRecipesPy locates the current repo's `recipes.py`. It does this by:
//   * invoking git to find the repo root
//   * loading the recipes.cfg at infra/config/recipes.cfg
//   * stat'ing the recipes.py implied by the recipes_path in that cfg file.
//
// Failure will return an error.
//
// On success, the absolute path to recipes.py is returned.
func (c *cmdEditRecipeBundle) findRecipesPy(ctx context.Context) (string, error) {
	cmd := logCmd(ctx, "git", "rev-parse", "--show-toplevel")
	out, err := cmd.Output()
	if err = cmdErr(err, "finding git repo"); err != nil {
		return "", err
	}

	repoRoot := strings.TrimSpace(string(out))

	pth := filepath.Join(repoRoot, "infra", "config", "recipes.cfg")
	switch st, err := os.Stat(pth); {
	case err != nil:
		return "", errors.Annotate(err, "reading recipes.cfg").Err()

	case !st.Mode().IsRegular():
		return "", errors.Reason("%q is not a regular file", pth).Err()
	}

	type recipesJSON struct {
		RecipesPath string `json:"recipes_path"`
	}
	rj := &recipesJSON{}

	f, err := os.Open(pth)
	if err != nil {
		return "", errors.Reason("reading recipes.cfg: %q", pth).Err()
	}
	defer f.Close()

	if err := json.NewDecoder(f).Decode(rj); err != nil {
		return "", errors.Reason("parsing recipes.cfg: %q", pth).Err()
	}

	return filepath.Join(
		repoRoot, filepath.FromSlash(rj.RecipesPath), "recipes.py"), nil
}

func (c *cmdEditRecipeBundle) bundle(ctx context.Context) (string, error) {
	repoRecipesPy, err := c.findRecipesPy(ctx)
	if err != nil {
		return "", err
	}
	logging.Debugf(ctx, "using recipes.py: %q", repoRecipesPy)
	return c.prepBundle(ctx, repoRecipesPy, recipeCheckoutDir)
}

func (c *cmdEditRecipeBundle) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))
	authOpts, err := c.validateFlags(ctx, args)
	if err != nil {
		logging.Errorf(ctx, "bad arguments: %s\n\n", err)
		c.GetFlags().Usage()
		return 1
	}

	logging.Infof(ctx, "bundling recipes")
	bundlePath, err := c.bundle(ctx)
	if err != nil {
		logging.Errorf(ctx, "fatal error during bundle: %s", err)
		return 1
	}
	defer os.RemoveAll(bundlePath)
	logging.Infof(ctx, "bundling recipes: done")

	err = editMode(ctx, func(jd *JobDefinition) error {
		_, _, swarm, err := newSwarmClient(ctx, authOpts, jd.SwarmingHostname)
		if err != nil {
			return err
		}

		isoFlags, err := getIsolatedFlags(swarm)
		if err != nil {
			return err
		}

		logging.Infof(ctx, "isolating recipes")
		hash, err := isolate(ctx, bundlePath, isoFlags, authOpts)
		if err != nil {
			return err
		}
		logging.Infof(ctx, "isolating recipes: done")

		ejd := jd.Edit()
		ejd.RecipeSource(string(hash), "", "")
		return ejd.Finalize()
	})
	if err != nil {
		errors.Log(ctx, err)
		return 1
	}

	return 0
}
