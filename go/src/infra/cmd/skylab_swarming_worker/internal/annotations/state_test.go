// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package annotations

import (
	"bytes"
	"testing"

	"github.com/kylelemons/godebug/pretty"
)

func TestCloseStateWithOpenStep(t *testing.T) {
	t.Parallel()
	var b bytes.Buffer
	s := NewState(&b)
	s.OpenStep("foo")
	s.Close()
	got := b.String()
	want := `@@@SEED_STEP foo@@@
@@@STEP_CURSOR foo@@@
@@@STEP_STARTED@@@
@@@STEP_CLOSED@@@
`
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("Output differs -want +got:\n %s", diff)
	}
}

func TestCloseStateWithoutOpenStep(t *testing.T) {
	t.Parallel()
	var b bytes.Buffer
	s := NewState(&b)
	s.Close()
	got := b.String()
	want := ""
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("Output differs -want +got:\n %s", diff)
	}
}

func TestState_AddLink(t *testing.T) {
	t.Parallel()
	var b bytes.Buffer
	s := NewState(&b)
	s.AddLink("foo", "http://example.com")
	s.Close()
	got := b.String()
	want := "@@@STEP_LINK@foo@http://example.com@@@\n"
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("Output differs -want +got:\n %s", diff)
	}
}
