// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"

	"golang.org/x/net/context"

	"infra/tools/kitchen/proto"

	"github.com/golang/protobuf/proto"
	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/system/environ"
)

// localRecipeRun can run a local recipe.
type recipeRun struct {
	recipesPyPath        string                  // path to the recipes.py
	recipeName           string                  // name of the recipe
	properties           map[string]interface{}  // input properties
	opArgs               recipe_engine.Arguments // operational arguments for the recipe engine
	workDir              string                  // a directory where to run the recipe
	timestamps           bool                    // whether to print timestamps
	outputResultJSONFile string                  // path to the result file
}

// command prepares a command that runs a recipe.
func (rr *recipeRun) command(ctx context.Context, tdir string, env environ.Env) (*exec.Cmd, error) {
	if err := ensureDir(tdir); err != nil {
		return nil, err
	}
	// Pass properties in a file.
	propertiesPath := filepath.Join(tdir, "properties.json")
	if err := encodeJSONToPath(propertiesPath, rr.properties); err != nil {
		return nil, errors.Annotate(err).Reason("could not write properties file at %(path)q").
			D("path", propertiesPath).
			Err()
	}

	// Write our operational arguments.
	log.Debugf(ctx, "Using operational args: %s", rr.opArgs.String())
	opArgsPath := filepath.Join(tdir, "op_args.json")
	if err := encodeJSONToPath(opArgsPath, &rr.opArgs); err != nil {
		return nil, errors.Annotate(err).Reason("could not write arguments file at %(path)q").
			D("path", opArgsPath).
			Err()
	}

	// Build our command (arguments first).
	recipeCmd := exec.CommandContext(
		ctx,
		"python",
		rr.recipesPyPath,
		"--operational-args-path", opArgsPath,
		"run",
		"--properties-file", propertiesPath,
		"--workdir", rr.workDir,
	)
	if rr.outputResultJSONFile != "" {
		recipeCmd.Args = append(recipeCmd.Args,
			"--output-result-json", rr.outputResultJSONFile)
	}
	recipeCmd.Args = append(recipeCmd.Args, rr.recipeName)

	// Apply our enviornment.
	if env.Len() > 0 {
		recipeCmd.Env = env.Sorted()
	}

	return recipeCmd, nil
}

func loadRecipesCfg(repoDir string) (*recipe_engine.Package, error) {
	recipesCfg := filepath.Join(repoDir, "infra", "config", "recipes.cfg")
	fileContents, err := ioutil.ReadFile(recipesCfg)
	if err != nil {
		return nil, errors.Annotate(err).Reason("could not read recipes.cfg at %(path)q").
			D("path", recipesCfg).
			Err()
	}

	pkg := &recipe_engine.Package{}
	if err := proto.UnmarshalText(string(fileContents), pkg); err != nil {
		return nil, errors.Annotate(err).Reason("could not parse recipes.cfg at %(path)q").
			D("path", recipesCfg).
			Err()
	}

	return pkg, nil
}

// prepareWorkDir verifies and normalizes a workdir is suitable for a recipe
// run.
func prepareRecipeRunWorkDir(workdir string) (string, error) {
	if workdir == "" {
		return "", errors.New("workdir is empty")
	}

	abs, err := filepath.Abs(workdir)
	if err != nil {
		return "", errors.Annotate(err).Reason("could not make %(workDir)q absolute").
			D("workDir", workdir).
			Err()
	}
	workdir = abs

	switch hasFiles, err := dirHasFiles(workdir); {
	case os.IsNotExist(err):
		return workdir, ensureDir(workdir)

	case err != nil:
		return "", errors.Annotate(err).Reason("could not read dir %(dir)q").
			D("dir", workdir).
			Err()

	case hasFiles:
		return "", errors.Annotate(err).Reason("workdir %(workDir)q is not empty").
			D("workDir", workdir).
			Err()

	default:
		return workdir, nil
	}
}
