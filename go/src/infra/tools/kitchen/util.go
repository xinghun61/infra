// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"encoding/json"
	"io/ioutil"
	"os"

	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"

	"golang.org/x/net/context"
)

func withTempDir(ctx context.Context, fn func(context.Context, string) error) error {
	tdir, err := ioutil.TempDir("", "kitchen")
	if err != nil {
		return errors.Annotate(err).Reason("failed to create temporary directory").Err()
	}
	defer func() {
		if rmErr := os.RemoveAll(tdir); rmErr != nil {
			log.Warningf(ctx, "Failed to clean up temporary directory at [%s]: %s", tdir, rmErr)
		}
	}()
	return fn(ctx, tdir)
}

func encodeJSONToPath(path string, obj interface{}) (err error) {
	fd, err := os.Create(path)
	if err != nil {
		return errors.Annotate(err).Reason("failed to create output file").Err()
	}
	defer func() {
		closeErr := fd.Close()
		if closeErr != nil && err == nil {
			err = errors.Annotate(closeErr).Reason("failed to close output file").Err()
		}
	}()
	if err = json.NewEncoder(fd).Encode(obj); err != nil {
		return errors.Annotate(err).Reason("failed to write encoded object").Err()
	}
	return nil
}
