// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"fmt"
	"io"
	"log"
	"os"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/logdog/common/types"

	"infra/cmd/skylab_swarming_worker/internal/logdog"
)

// openLogDogWriter returns a writeCloser for LogDog output and
// annotations.  If the URL given is the empty string, a stdout writer
// is returned as a default fallback.
func openLogDogWriter(ctx context.Context, annotationURL string) (writeCloser, error) {
	if annotationURL == "" {
		log.Printf("Using stdout for LogDog stream")
		return writeCloser{w: os.Stdout}, nil
	}
	log.Printf("Setting up LogDog stream")
	sa, err := types.ParseURL(annotationURL)
	if err != nil {
		return writeCloser{}, errors.Annotate(err, "open LogDog writer for %s", annotationURL).Err()
	}
	o := logdog.Options{
		AnnotationStream: sa,
		SourceInfo:       []string{"skylab", "worker"},
	}
	lc, err := logdog.New(ctx, &o)
	if err != nil {
		return writeCloser{}, errors.Annotate(err, "open LogDog writer for %s", annotationURL).Err()
	}
	w := lc.Stdout()
	fmt.Fprintf(w, `NOTE: This is the root LogDog stream.
This is used primarily for LogDog annotations.
You most likely want to ignore everything in this log,
and check the other logs instead.
`)
	return writeCloser{c: lc, w: w}, nil
}

type writeCloser struct {
	c io.Closer
	w io.Writer
}

func (wc writeCloser) Write(p []byte) (int, error) {
	return wc.w.Write(p)
}

func (wc writeCloser) Close() error {
	if wc.c == nil {
		return nil
	}
	return wc.c.Close()
}
