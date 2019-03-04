// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/system/environ"
)

// recipeEngine can invoke the recipe engine configured with some single recipe.
type recipeEngine struct {
	// put these args at the beginning of the Cmd. Must include the python
	// interpreter if necessary.
	cmdPrefix []string

	recipeName           string                 // name of the recipe
	properties           map[string]interface{} // input properties
	workDir              string                 // a directory where to run the recipe
	outputResultJSONFile string                 // path to the result file
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

	// Build our command (arguments first).
	args := []string{}
	args = append(args, eng.cmdPrefix...)
	args = append(args,
		"run",
		"--properties-file", propertiesPath,
		// TODO(iannucci): Remove `--workdir` entirely and make the recipe engine
		// operate in $CWD.
		"--workdir", eng.workDir,
	)
	if eng.outputResultJSONFile != "" {
		args = append(args, "--output-result-json", eng.outputResultJSONFile)
	}
	args = append(args, eng.recipeName)

	// Build the final exec.Cmd.
	recipeCmd := exec.CommandContext(ctx, args[0], args[1:]...)
	recipeCmd.Dir = eng.workDir
	recipeCmd.Env = env.Sorted()
	return recipeCmd, nil
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
