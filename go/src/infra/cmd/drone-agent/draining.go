// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"os"
	"time"

	"infra/cmd/drone-agent/internal/draining"
)

const checkDrainingInterval = time.Minute

// notifyDraining returns a context that is marked as draining when a
// file exists at the given path.
func notifyDraining(ctx context.Context, path string) context.Context {
	ctx, drain := draining.WithDraining(ctx)
	go func() {
		for {
			_, err := os.Stat(path)
			if err == nil {
				drain()
				return
			}
			time.Sleep(checkDrainingInterval)
		}
	}()
	return ctx
}
