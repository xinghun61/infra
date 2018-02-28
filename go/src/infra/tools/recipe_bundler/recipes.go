// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"os"
	"path/filepath"

	"go.chromium.org/luci/common/errors"
	"golang.org/x/net/context"
)

type recipes string

func newRecipes(repoRoot string) (recipes, error) {
	f, err := os.Open(filepath.Join(repoRoot, "infra", "config", "recipes.cfg"))
	if err != nil {
		return "", errors.Annotate(err, "opening recipes.cfg").Err()
	}
	cfg := &struct {
		RecipesPath string `json:"recipes_path"`
	}{}
	if err := json.NewDecoder(f).Decode(cfg); err != nil {
		return "", errors.Annotate(err, "reading recipes.cfg").Err()
	}

	return recipes(filepath.Join(repoRoot, cfg.RecipesPath)), nil
}

func (r recipes) run(ctx context.Context, args ...string) error {
	args = append([]string{"recipes.py", "--verbose"}, args...)
	run := newRunner(ctx, "recipes.run", "python", args)
	run.cwd = string(r)
	return run.do()
}
