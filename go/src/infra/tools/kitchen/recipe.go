// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"

	"golang.org/x/net/context"

	"infra/tools/kitchen/third_party/recipe_engine"

	"go.chromium.org/luci/common/errors"
	log "go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/system/environ"
	"go.chromium.org/luci/common/system/exitcode"
)

// recipeEngine can invoke the recipe engine configured with some single recipe.
type recipeEngine struct {
	// put these args at the beginning of the Cmd. Must include the python
	// interpreter if necessary.
	cmdPrefix []string

	recipeName           string                  // name of the recipe
	properties           map[string]interface{}  // input properties
	opArgs               recipe_engine.Arguments // operational arguments for the recipe engine
	workDir              string                  // a directory where to run the recipe
	outputResultJSONFile string                  // path to the result file
}

// commandRun prepares a command that runs a recipe.
func (eng *recipeEngine) commandRun(ctx context.Context, tdir string, env environ.Env) (*exec.Cmd, error) {
	if len(eng.cmdPrefix) == 0 {
		return nil, errors.New("empty command prefix")
	}
	if err := ensureDir(tdir); err != nil {
		return nil, err
	}

	// Pass properties in a file.
	propertiesPath := filepath.Join(tdir, "properties.json")
	if err := encodeJSONToPath(propertiesPath, eng.properties); err != nil {
		return nil, errors.Annotate(err, "could not write properties file at %q", propertiesPath).Err()
	}

	// Write our operational arguments.
	log.Debugf(ctx, "Using operational args: %s", eng.opArgs.String())
	opArgsPath := filepath.Join(tdir, "op_args.json")
	if err := encodeJSONToPath(opArgsPath, &eng.opArgs); err != nil {
		return nil, errors.Annotate(err, "could not write arguments file at %q", opArgsPath).Err()
	}

	// Build our command (arguments first).
	args := []string{}
	args = append(args, eng.cmdPrefix...)
	args = append(args,
		"--operational-args-path", opArgsPath,
		"run",
		"--properties-file", propertiesPath,
		"--workdir", eng.workDir,
	)
	if eng.outputResultJSONFile != "" {
		args = append(args, "--output-result-json", eng.outputResultJSONFile)
	}
	args = append(args, eng.recipeName)

	// Build the final exec.Cmd.
	recipeCmd := exec.CommandContext(ctx, args[0], args[1:]...)
	recipeCmd.Env = env.Sorted()
	return recipeCmd, nil
}

// commandFetch prepares a command that fetches recipe dependences.
func (eng *recipeEngine) commandFetch(ctx context.Context, env environ.Env) (*exec.Cmd, error) {
	if len(eng.cmdPrefix) == 0 {
		return nil, errors.New("empty command prefix")
	}

	args := []string{}
	args = append(args, eng.cmdPrefix...)
	args = append(args, "-v", "fetch")

	recipeCmd := exec.CommandContext(ctx, args[0], args[1:]...)
	recipeCmd.Env = env.Sorted()
	return recipeCmd, nil
}

// fetchRecipeDeps fetches recipe dependencies via 'recipes.py fetch'.
func (eng *recipeEngine) fetchRecipeDeps(ctx context.Context, env environ.Env) error {
	cmd, err := eng.commandFetch(ctx, env)
	if err != nil {
		return err
	}
	printCommand(ctx, cmd)

	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	err = cmd.Run()
	switch rv, hasRV := exitcode.Get(err); {
	case !hasRV:
		return errors.Annotate(err, "failed to run recipe fetch").Err()
	case rv != 0:
		return errors.New(fmt.Sprintf("recipes fetch failed with exit code %d", rv))
	}
	return nil
}

func getRecipesPath(repoDir string) (string, error) {
	recipesCfg := filepath.Join(repoDir, "infra", "config", "recipes.cfg")
	fileContents, err := ioutil.ReadFile(recipesCfg)
	if err != nil {
		return "", errors.Annotate(err, "could not read recipes.cfg at %q", recipesCfg).Err()
	}

	var cfg struct {
		RecipesPath string `json:"recipes_path"`
	}
	if err := json.Unmarshal(fileContents, &cfg); err != nil {
		return "", errors.Annotate(err, "could not parse recipes.cfg at %q", recipesCfg).Err()
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
		return "", errors.Annotate(err, "could not make %q absolute", workdir).Err()
	}
	workdir = abs

	switch hasFiles, err := dirHasFiles(workdir); {
	case os.IsNotExist(err):
		return workdir, ensureDir(workdir)

	case err != nil:
		return "", errors.Annotate(err, "could not read dir %q", workdir).Err()

	case hasFiles:
		return "", errors.Annotate(err, "workdir %q is not empty", workdir).Err()

	default:
		return workdir, nil
	}
}
