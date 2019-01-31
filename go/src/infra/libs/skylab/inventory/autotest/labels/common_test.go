// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package labels

import (
	"reflect"
	"testing"
)

func TestRemoveLabel(t *testing.T) {
	t.Parallel()
	got := []string{"ayanami", "laffey", "javelin"}
	got = removeLabel(got, 1)
	want := []string{"ayanami", "javelin"}
	if !reflect.DeepEqual(got, want) {
		input := []string{"ayanami", "laffey", "javelin"}
		t.Errorf("removeLabel(%#v, 1) = %#v; want %#v", input, got, want)
	}
}

func TestRemoveLabelOnLastItem(t *testing.T) {
	t.Parallel()
	got := []string{"ayanami", "laffey", "javelin"}
	got = removeLabel(got, 2)
	want := []string{"ayanami", "laffey"}
	if !reflect.DeepEqual(got, want) {
		input := []string{"ayanami", "laffey", "javelin"}
		t.Errorf("removeLabel(%#v, 2) = %#v; want %#v", input, got, want)
	}
}
