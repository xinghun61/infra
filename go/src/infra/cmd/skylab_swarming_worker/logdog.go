// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"io"
	"io/ioutil"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/logdog/common/types"

	"infra/cmd/skylab_swarming_worker/internal/log"
	"infra/cmd/skylab_swarming_worker/internal/logdog"
)

// copyToLogDog creates a LogDog client and synchronously copies the
// output from the Reader to LogDog.
func copyToLogDog(ctx context.Context, sa *types.StreamAddr, r io.Reader) (err error) {
	defer func() {
		// Empty out the pipe so it doesn't fill up and block
		// the writer.
		if err != nil {
			log.Printf("Purging LogDog stream")
			io.Copy(ioutil.Discard, r)
		}
	}()
	o := logdog.Options{
		AnnotationStream: sa,
		SourceInfo:       []string{"skylab", "worker"},
	}
	log.Printf("Setting up LogDog stream")
	lc, err := logdog.New(ctx, &o)
	if err != nil {
		return errors.Annotate(err, "error configuring LogDog").Err()
	}
	defer lc.Close()
	log.Printf("Copying LogDog stream")
	if _, err = io.Copy(lc.Stdout(), r); err != nil {
		return errors.Annotate(err, "copying LogDog buffer").Err()
	}
	return nil
}
