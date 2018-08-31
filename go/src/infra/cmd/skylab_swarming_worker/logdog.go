// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/logdog/common/types"

	"infra/cmd/skylab_swarming_worker/internal/logdog"
)

// openLogDog creates a LogDog client.
func openLogDog(ctx context.Context, sa *types.StreamAddr) (*logdog.Client, error) {
	o := logdog.Options{
		AnnotationStream: sa,
		SourceInfo:       []string{"skylab", "worker"},
	}
	lc, err := logdog.New(ctx, &o)
	if err != nil {
		return nil, errors.Annotate(err, "error configuring LogDog").Err()
	}
	return lc, nil
}
