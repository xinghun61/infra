// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"io"

	"infra/cmd/skylab_swarming_worker/internal/lucifer"
	"infra/cmd/skylab_swarming_worker/internal/swarming/harness"
)

type luciferResult struct {
	TestsFailed int
}

func runLuciferJob(i *harness.Info, w io.Writer, r lucifer.TestArgs) (*luciferResult, error) {
	panic("not supported on windows")
}

func runLuciferAdminTask(i *harness.Info, w io.Writer, r lucifer.AdminTaskArgs) (*luciferResult, error) {
	panic("not supported on windows")
}
