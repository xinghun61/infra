// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/client/archiver"
	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/isolated"
	"github.com/luci/luci-go/common/isolatedclient"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/retry"
)

func combineIsolates(ctx context.Context, arc *archiver.Archiver, isoHashes ...isolated.HexDigest) (isolated.HexDigest, error) {
	if len(isoHashes) == 1 {
		return isoHashes[0], nil
	}
	if len(isoHashes) == 0 {
		return "", nil
	}

	iso := isolated.New()
	iso.Includes = isoHashes
	isolated, err := json.Marshal(iso)
	if err != nil {
		return "", errors.Annotate(err, "encoding ISOLATED.json").Err()
	}
	promise := arc.Push("ISOLATED.json", isolatedclient.NewBytesSource(isolated), 0)
	promise.WaitForHashed()
	return promise.Digest(), arc.Close()
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

		relPath, err := filepath.Rel(dir, fullPath)
		if err != nil {
			return errors.Annotate(err, "relpath of %q", fullPath).Err()
		}

		if fi.Mode().IsRegular() {
			isoData = append(isoData, datum{
				relPath, arc.PushFile(relPath, fullPath, i)})
			i++
			iso.Files[relPath] = isolated.BasicFile("", int(fi.Mode()), fi.Size())
			return nil
		}
		if (fi.Mode() & os.ModeSymlink) != 0 {
			val, err := os.Readlink(fullPath)
			if err != nil {
				return errors.Annotate(err, "reading link of %q", fullPath).Err()
			}
			iso.Files[relPath] = isolated.SymLink(val)
			return nil
		}

		return errors.Reason("don't know how to process: %s", fi).Err()
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
		return "", errors.Annotate(err, "encoding ISOLATED.json").Err()
	}

	promise := arc.Push("ISOLATED.json", isolatedclient.NewBytesSource(isolated), 0)
	promise.WaitForHashed()

	return promise.Digest(), arc.Close()
}

func mkAuthClient(ctx context.Context, authOpts auth.Options) (*http.Client, error) {
	authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)
	return authenticator.Client()
}

func mkArchiver(ctx context.Context, isolatedFlags isolatedclient.Flags, authClient *http.Client) *archiver.Archiver {
	logging.Debugf(ctx, "making archiver for %s : %s", isolatedFlags.ServerURL, isolatedFlags.Namespace)
	isoClient := isolatedclient.New(
		nil, authClient,
		isolatedFlags.ServerURL, isolatedFlags.Namespace,
		retry.Default,
		nil,
	)

	// The archiver is pretty noisy at Info level, so we skip giving it
	// a logging-enabled context unless the user actually requseted verbose.
	arcCtx := context.Background()
	if logging.GetLevel(ctx) < logging.Info {
		arcCtx = ctx
	}
	// os.Stderr will cause the archiver to print a one-liner progress status.
	return archiver.New(arcCtx, isoClient, os.Stderr)
}

func isolate(ctx context.Context, bundlePath string, isolatedFlags isolatedclient.Flags, authOpts auth.Options) (isolated.HexDigest, error) {
	authClient, err := mkAuthClient(ctx, authOpts)
	if err != nil {
		return "", err
	}
	return isolateDirectory(ctx, mkArchiver(ctx, isolatedFlags, authClient),
		bundlePath)
}
