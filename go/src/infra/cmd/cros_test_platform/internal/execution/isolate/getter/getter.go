// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package getter provides a client to fetch a named file from an isolate.
package getter

import (
	"context"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"

	"go.chromium.org/luci/client/downloader"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/isolated"
	"go.chromium.org/luci/common/isolatedclient"
)

// Client is a high level client for fetching an individual named file from isolate.
type Client struct {
	c *isolatedclient.Client
}

// New returns a Client interface for downloading files from isolate.
func New(c *isolatedclient.Client) *Client {
	return &Client{c}
}

// GetFile returns the contents of the named file from the given isolate.
func (c *Client) GetFile(ctx context.Context, digest isolated.HexDigest, filePath string) ([]byte, error) {
	dir, err := ioutil.TempDir("", "isolate-getter")
	if err != nil {
		return nil, errors.Annotate(err, "get isolate %s file %s", digest, filePath).Err()
	}

	defer func() {
		// TODO(akeshet): return it.
		if err = os.RemoveAll(dir); err != nil {
			log.Fatalf("unexpected failure to remove %s", dir)
		}
	}()

	// TODO(akeshet): Add a downloader option to limit to downloading to only
	// a whitelist a file paths, then use that option here.
	dl := downloader.New(ctx, c.c, digest, dir, &downloader.Options{})
	dl.Start()

	// Wait in a separate goroutine.
	e := make(chan error, 1)
	go func() { e <- dl.Wait() }()

	select {
	case err = <-e:
		if err != nil {
			return nil, errors.Annotate(err, "get isolate %s file %s", digest, filePath).Err()
		}
	case <-ctx.Done():
		return nil, errors.Annotate(ctx.Err(), "get isolate %s file %s", digest, filePath).Err()
	}

	path := filepath.Join(dir, filePath)
	bytes, err := ioutil.ReadFile(path)
	if err != nil {
		return nil, errors.Annotate(err, "get isolate %s file %s", digest, filePath).Err()
	}
	return bytes, nil
}
