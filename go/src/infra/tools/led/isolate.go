// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"crypto"
	"encoding/json"
	"net/http"
	"os"

	"golang.org/x/net/context"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/client/archiver"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/isolated"
	"go.chromium.org/luci/common/isolatedclient"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/retry"
)

func combineIsolates(ctx context.Context, arc *archiver.Archiver, h crypto.Hash, isoHashes ...isolated.HexDigest) (isolated.HexDigest, error) {
	if len(isoHashes) == 1 {
		return isoHashes[0], nil
	}
	if len(isoHashes) == 0 {
		return "", nil
	}

	iso := isolated.New(h)
	iso.Includes = isoHashes
	isolated, err := json.Marshal(iso)
	if err != nil {
		return "", errors.Annotate(err, "encoding ISOLATED.json").Err()
	}
	promise := arc.Push("ISOLATED.json", isolatedclient.NewBytesSource(isolated), 0)
	promise.WaitForHashed()
	return promise.Digest(), arc.Close()
}

func mkArchiver(ctx context.Context, isoClient *isolatedclient.Client) *archiver.Archiver {
	// The archiver is pretty noisy at Info level, so we skip giving it
	// a logging-enabled context unless the user actually requseted verbose.
	arcCtx := context.Background()
	if logging.GetLevel(ctx) < logging.Info {
		arcCtx = ctx
	}
	// os.Stderr will cause the archiver to print a one-liner progress status.
	return archiver.New(arcCtx, isoClient, os.Stderr)
}

func isolateDirectory(ctx context.Context, isoClient *isolatedclient.Client, dir string) (isolated.HexDigest, error) {
	checker := archiver.NewChecker(ctx, isoClient, 32)
	uploader := archiver.NewUploader(ctx, isoClient, 8)
	arc := archiver.NewTarringArchiver(checker, uploader)

	summary, err := arc.Archive([]string{dir}, dir, isolated.New(isoClient.Hash()), nil, "")
	if err != nil {
		return "", errors.Annotate(err, "isolating directory").Err()
	}

	if err := checker.Close(); err != nil {
		return "", errors.Annotate(err, "closing checker").Err()
	}

	if err := uploader.Close(); err != nil {
		return "", errors.Annotate(err, "closing uploader").Err()
	}

	return summary.Digest, nil
}

func mkAuthClient(ctx context.Context, authOpts auth.Options) (*http.Client, error) {
	authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)
	return authenticator.Client()
}

func newIsolatedClient(ctx context.Context, isolatedFlags isolatedclient.Flags, authClient *http.Client) (*isolatedclient.Client, error) {
	return isolatedclient.New(
		nil, authClient,
		isolatedFlags.ServerURL, isolatedFlags.Namespace,
		retry.Default,
		nil,
	), nil
}
