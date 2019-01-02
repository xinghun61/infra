// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import "testing"

func TestGetBotLabNumberOnNormalName(t *testing.T) {
	t.Parallel()
	got := getBotLabNumber("chromeos4-rack1-row-2-host3")
	want := "4"
	if got != want {
		t.Errorf(`getBotLabNumber("chromeos4-rack1-row-2-host3") = %s; want %s`, got, want)
	}
}

func TestGetBotLabNumberOnBadName(t *testing.T) {
	t.Parallel()
	got := getBotLabNumber("rack1-row-2-host3")
	want := ""
	if got != want {
		t.Errorf(`getBotLabNumber("chromeos4-rack1-row-2-host3") = %s; want %s`, got, want)
	}
}
