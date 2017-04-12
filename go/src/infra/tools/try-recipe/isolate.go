// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"io"
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/client/archiver"
	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/isolated"
	"github.com/luci/luci-go/common/isolatedclient"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/retry"
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

	args := []string{
		recipesPy,
	}
	if logging.GetLevel(ctx) < logging.Info {
		args = append(args, "-v")
	}
	args = append(args, "bundle", "--destination", retDir)
	cmd := logCmd(ctx, "python", args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmdErr(cmd.Run(), "creating bundle"); err != nil {
		os.RemoveAll(retDir)
		return "", err
	}

	return retDir, nil
}

func isolateDirectory(ctx context.Context, arc *archiver.Archiver, dir string) (isolated.HexDigest, error) {
	// TODO(iannucci): Replace this entire function with exparchvive library when
	// it's available.

	iso := isolated.New()
	type datum struct {
		path    string
		promise *archiver.Item
	}
	isoData := []datum{}
	i := int64(0)
	err := filepath.Walk(dir, func(fullPath string, fi os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if fi.IsDir() {
			return nil
		}

		if fi.Mode().IsRegular() {
			relPath, err := filepath.Rel(dir, fullPath)
			if err != nil {
				return errors.Annotate(err).Reason("relpath of %(full)q").D("full", fullPath).Err()
			}
			isoData = append(isoData, datum{
				relPath, arc.PushFile(relPath, fullPath, i)})
			iso.Files[relPath] = isolated.BasicFile("", int(fi.Mode()), fi.Size())
			i++
			return nil
		}

		return errors.Reason("don't know how to process: %(fi)v").D("fi", fi).Err()
	})
	if err != nil {
		return "", err
	}

	for _, d := range isoData {
		itm := iso.Files[d.path]
		d.promise.WaitForHashed()
		itm.Digest = d.promise.Digest()
		iso.Files[d.path] = itm
	}

	isolated, err := json.Marshal(iso)
	if err != nil {
		return "", errors.Annotate(err).Reason("encoding ISOLATED.json").Err()
	}

	promise := arc.Push("ISOLATED.json", isolatedclient.NewBytesSource(isolated), 0)
	promise.WaitForHashed()

	return promise.Digest(), arc.Close()
}

func bundleAndIsolate(ctx context.Context, isolatedFlags isolatedclient.Flags, authOpts auth.Options) error {
	repoRecipesPy, err := findRecipesPy(ctx)
	if err != nil {
		return err
	}

	logging.Infof(ctx, "using recipes.py: %q", repoRecipesPy)

	bundlePath, err := prepBundle(ctx, repoRecipesPy)
	if err != nil {
		return err
	}
	defer os.RemoveAll(bundlePath)

	logging.Debugf(ctx, "bundle created at: %q", bundlePath)
	logging.Infof(ctx, "isolating")

	authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)
	authClient, err := authenticator.Client()
	if err != nil {
		return err
	}
	isoClient := isolatedclient.New(
		nil, authClient,
		isolatedFlags.ServerURL, isolatedFlags.Namespace,
		retry.Default,
		nil,
	)

	var w io.Writer
	if logging.GetLevel(ctx) < logging.Info {
		w = os.Stdout
	}
	arc := archiver.New(isoClient, w)
	hash, err := isolateDirectory(ctx, arc, bundlePath)
	if err != nil {
		return err
	}

	logging.Infof(ctx, "isolated: %q", hash)
	logging.Infof(ctx, "URL: %s/browse?namespace=%s&hash=%s",
		isolatedFlags.ServerURL, isolatedFlags.Namespace, hash)

	return nil
}
