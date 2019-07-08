// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package draining

import (
	"context"
	"testing"
)

func TestIsDraining(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	ctx, drain := WithDraining(ctx)
	if v := IsDraining(ctx); v {
		t.Fatalf("before calling drain, IsDraining = %v; want false", v)
	}
	drain()
	if v := IsDraining(ctx); !v {
		t.Fatalf("after calling drain, IsDraining = %v; want true", v)
	}
}

func TestC(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	ctx, drain := WithDraining(ctx)
	select {
	case <-C(ctx):
		t.Fatalf("received from channel before calling drain")
	default:
	}
	drain()
	select {
	case <-C(ctx):
	default:
		t.Fatalf("didn't receive from channel after calling drain")
	}
}
