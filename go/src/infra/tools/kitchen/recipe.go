// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"

	"golang.org/x/net/context"

	"infra/tools/kitchen/third_party/recipe_engine"

	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/system/environ"
)

// localRecipeRun can run a local recipe.
type recipeRun struct {
	// put these args at the beginning of the Cmd. Must include the python
	// interpreter if necessary.
	cmdPrefix []string

	recipeName           string                  // name of the recipe
	properties           map[string]interface{}  // input properties
	opArgs               recipe_engine.Arguments // operational arguments for the recipe engine
	workDir              string                  // a directory where to run the recipe
	outputResultJSONFile string                  // path to the result file
}

// command prepares a command that runs a recipe.
func (rr *recipeRun) command(ctx context.Context, tdir string, env environ.Env) (*exec.Cmd, error) {
	if len(rr.cmdPrefix) == 0 {
		return nil, errors.New("empty command prefix")
	}
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
	args := append(rr.cmdPrefix,
		"--operational-args-path", opArgsPath,
		"run",
		"--properties-file", propertiesPath,
		"--workdir", rr.workDir,
	)

	recipeCmd := exec.CommandContext(ctx, args[0], args[1:]...)
	if rr.outputResultJSONFile != "" {
		recipeCmd.Args = append(recipeCmd.Args,
			"--output-result-json", rr.outputResultJSONFile)
	}
	recipeCmd.Args = append(recipeCmd.Args, rr.recipeName)

	// Apply our environment.
	if env.Len() > 0 {
		recipeCmd.Env = env.Sorted()
	}

	return recipeCmd, nil
}

func getRecipesPath(repoDir string) (string, error) {
	recipesCfg := filepath.Join(repoDir, "infra", "config", "recipes.cfg")
	fileContents, err := ioutil.ReadFile(recipesCfg)
	if err != nil {
		return "", errors.Annotate(err).Reason("could not read recipes.cfg at %(path)q").
			D("path", recipesCfg).
			Err()
	}

	var cfg struct {
		RecipesPath string `json:"recipes_path"`
	}
	if err := json.Unmarshal(fileContents, &cfg); err != nil {
		return "", errors.Annotate(err).Reason("could not parse recipes.cfg at %(path)q").
			D("path", recipesCfg).
			Err()
	}
	return cfg.RecipesPath, nil
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
