// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"testing"

	"github.com/luci/gae/impl/memory"
	"golang.org/x/net/context"
)

func TestHandler(t *testing.T) {
	t.Parallel()
	c := memory.Use(context.Background())

	// First visitor.
	count, err := registerVisitor(c)
	if err != nil {
		t.Fatal(err)
	}
	if count != 1 {
		t.Fatalf("Expecting 1, got %d", count)
	}

	// Second one.
	count, err = registerVisitor(c)
	if err != nil {
		t.Fatal(err)
	}
	if count != 2 {
		t.Fatalf("Expecting 2, got %d", count)
	}
}
