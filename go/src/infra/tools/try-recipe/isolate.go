// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
)

// findRecipesPy locates the current repo's `recipes.py`. It does this by:
//   * invoking git to find the repo root
//   * loading the recipes.cfg at infra/config/recipes.cfg
//   * stat'ing the recipes.py implied by the recipes_path in that cfg file.
//
// Failure will return an error.
//
// On success, the absolute path to recipes.py is returned.
func findRecipesPy(ctx context.Context) (string, error) {
	cmd := logCmd(ctx, "git", "rev-parse", "--show-toplevel")
	out, err := cmd.Output()
	if err = cmdErr(err, "finding git repo"); err != nil {
		return "", err
	}

	repoRoot := strings.TrimSpace(string(out))

	pth := filepath.Join(repoRoot, "infra", "config", "recipes.cfg")
	switch st, err := os.Stat(pth); {
	case err != nil:
		return "", errors.Annotate(err).Reason("reading recipes.cfg").Err()

	case !st.Mode().IsRegular():
		return "", errors.Reason("%(path)q is not a regular file").
			D("path", pth).Err()
	}

	type recipesJSON struct {
		RecipesPath string `json:"recipes_path"`
	}
	rj := &recipesJSON{}

	f, err := os.Open(pth)
	if err != nil {
		return "", errors.Reason("reading recipes.cfg: %(path)q").
			D("path", pth).Err()
	}
	defer f.Close()

	if err := json.NewDecoder(f).Decode(rj); err != nil {
		return "", errors.Reason("parsing recipes.cfg: %(path)q").
			D("path", pth).Err()
	}

	return filepath.Join(
		repoRoot, filepath.FromSlash(rj.RecipesPath), "recipes.py"), nil
}

func prepBundle(ctx context.Context, recipesPy string) (string, error) {
	retDir, err := ioutil.TempDir("", "try-recipe-bundle")
	if err != nil {
		return "", errors.Annotate(err).Reason("generating bundle tempdir").Err()
	}

	cmd := logCmd(ctx, "python", recipesPy, "-v", "bundle", "--destination", retDir)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmdErr(cmd.Run(), "creating bundle"); err != nil {
		os.RemoveAll(retDir)
		return "", err
	}

	return retDir, nil
}

func bundleAndIsolate(ctx context.Context) error {
	repoRecipesPy, err := findRecipesPy(ctx)
	if err != nil {
		return err
	}

	logging.Infof(ctx, "using recipes.py: %q", repoRecipesPy)

	bundlePath, err := prepBundle(ctx, repoRecipesPy)
	if err != nil {
		return err
	}
	//defer os.RemoveAll(bundlePath)

	logging.Infof(ctx, "bundle created at: %q", bundlePath)

	panic("not implemented")
}
