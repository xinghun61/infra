// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package annotations provides an API for writing annotation lines that
// annotee can parse and turn into LogDog annotations.
//
// See https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/master/chromium_step.py
// and https://chromium.googlesource.com/infra/luci/luci-go/+/master/logdog/client/annotee/annotation/annotation.go
package annotations

import (
	"fmt"
	"io"
)

// BuildStep prints a BUILD_STEP annotation.
func BuildStep(w io.Writer, name string) (int, error) {
	return fmt.Fprintf(w, "@@@BUILD_STEP %s@@@\n", name)
}

// SeedStep prints a SEED_STEP annotation.
func SeedStep(w io.Writer, name string) (int, error) {
	return fmt.Fprintf(w, "@@@SEED_STEP %s@@@\n", name)
}

// StepCursor prints a STEP_CURSOR annotation.
func StepCursor(w io.Writer, name string) (int, error) {
	return fmt.Fprintf(w, "@@@STEP_CURSOR %s@@@\n", name)
}

// StepLink prints a STEP_LINK annotation.
func StepLink(w io.Writer, label, url string) (int, error) {
	return fmt.Fprintf(w, "@@@STEP_LINK@%s@%s@@@\n", label, url)
}

// StepStarted prints a STEP_STARTED annotation.
func StepStarted(w io.Writer) (int, error) {
	return fmt.Fprintf(w, "@@@STEP_STARTED@@@\n")
}

// StepException prints a STEP_EXCEPTION annotation.
func StepException(w io.Writer) (int, error) {
	return fmt.Fprintf(w, "@@@STEP_EXCEPTION@@@\n")
}

// StepClosed prints a STEP_CLOSED annotation.
func StepClosed(w io.Writer) (int, error) {
	return fmt.Fprintf(w, "@@@STEP_CLOSED@@@\n")
}
