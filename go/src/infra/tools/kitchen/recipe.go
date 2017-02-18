// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"io/ioutil"
	"net/url"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"strings"

	"golang.org/x/net/context"

	"infra/tools/kitchen/proto"

	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/system/environ"
)

// recipeRemoteRun is a configurable recipe engine configuration.
type recipeRemoteRun struct {
	// recipeEnginePath is a path to a https://github.com/luci/recipes-py
	// checkout.
	recipeEnginePath string

	recipe               string
	timestamps           bool
	allowGitiles         bool
	repositoryURL        string
	revision             string
	checkoutDir          string
	workDir              string
	outputResultJSONFile string

	properties map[string]interface{}
	opArgs     recipe_engine.Arguments
}

func (rr *recipeRemoteRun) normalize() error {
	if rr.recipeEnginePath == "" {
		return errors.New("-recipe-engine-path is required")
	}

	// Validate Repository.
	if rr.repositoryURL == "" {
		return errors.New("-repository is required")
	}
	repoURL, err := url.Parse(rr.repositoryURL)
	if err != nil {
		return errors.Annotate(err).Reason("invalid repository %(repo)q").
			D("repo", repoURL).
			Err()
	}

	repoName := path.Base(repoURL.Path)
	if repoName == "" {
		return errors.Reason("invalid repository %(repo)q: no path").
			D("repo", repoURL).
			Err()
	}

	// Validate Recipe.
	if rr.recipe == "" {
		return errors.New("-recipe is required")
	}

	// Fix CheckoutDir.
	if rr.checkoutDir == "" {
		rr.checkoutDir = repoName
	}

	return nil
}

func (rr *recipeRemoteRun) command(ctx context.Context, tdir string, env environ.Env) (*exec.Cmd, error) {
	// Pass properties in a file.
	propertiesPath := filepath.Join(tdir, "properties.json")
	if err := encodeJSONToPath(propertiesPath, rr.properties); err != nil {
		return nil, errors.Annotate(err).Reason("could not write properties file at %(path)").
			D("path", propertiesPath).
			Err()
	}

	// Write our operational arguments.
	log.Debugf(ctx, "Using operational args: %s", rr.opArgs.String())
	opArgsPath := filepath.Join(tdir, "op_args.json")
	if err := encodeJSONToPath(opArgsPath, &rr.opArgs); err != nil {
		return nil, errors.Annotate(err).Reason("could not write arguments file at %(path)").
			D("path", opArgsPath).
			Err()
	}

	// Build our command (arguments first).
	recipeCmd := exec.CommandContext(
		ctx,
		"python",
		filepath.Join(rr.recipeEnginePath, "recipes.py"),
		"remote",
		"--repository", rr.repositoryURL,
		"--revision", rr.revision,
		"--workdir", rr.checkoutDir, // this is not a workdir for recipe run!
	)

	// remote subcommand does not sniff whether repository is gitiles or generic
	// git. Instead it accepts an explicit "--use-gitiles" flag.
	// We are not told whether the repo is gitiles or not, so sniff it here.
	if rr.allowGitiles && looksLikeGitiles(rr.repositoryURL) {
		recipeCmd.Args = append(recipeCmd.Args, "--use-gitiles")
	}

	// Now add the arguments for the recipes.py that will be fetched.
	recipeCmd.Args = append(recipeCmd.Args,
		"--",
		"--operational-args-path", opArgsPath,
		"run",
		"--properties-file", propertiesPath,
		"--workdir", rr.workDir,
	)
	if rr.outputResultJSONFile != "" {
		recipeCmd.Args = append(recipeCmd.Args,
			"--output-result-json", rr.outputResultJSONFile)
	}
	recipeCmd.Args = append(recipeCmd.Args, rr.recipe)

	// Apply our enviornment.
	if env.Len() > 0 {
		recipeCmd.Env = env.Sorted()
	}

	return recipeCmd, nil
}

func (rr *recipeRemoteRun) prepareWorkDir() error {
	// Setup our working directory.
	if rr.workDir == "" {
		rr.workDir = "kitchen-workdir"
	}

	abs, err := filepath.Abs(rr.workDir)
	if err != nil {
		return errors.Annotate(err).Reason("could not make %(workDir)q absolute").
			D("workDir", rr.workDir).
			Err()
	}
	rr.workDir = abs

	switch entries, err := ioutil.ReadDir(rr.workDir); {
	case os.IsNotExist(err):
		return os.Mkdir(rr.workDir, 0777)

	case err != nil:
		return errors.Annotate(err).Reason("could not read workdir %(workDir)q").
			D("workDir", rr.workDir).
			Err()

	case len(entries) > 0:
		return errors.Annotate(err).Reason("workdir %(workDir)q is not empty").
			D("workDir", rr.workDir).
			Err()

	default:
		return nil
	}
}

func looksLikeGitiles(rawurl string) bool {
	u, err := url.Parse(rawurl)
	return err == nil && strings.HasSuffix(u.Host, ".googlesource.com")
}
