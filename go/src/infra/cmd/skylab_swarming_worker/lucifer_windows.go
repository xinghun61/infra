// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"io"

	"infra/cmd/skylab_swarming_worker/internal/lucifer"
	"infra/cmd/skylab_swarming_worker/internal/swarming"
)

type luciferResult struct {
	TestsFailed int
}

func runLuciferJob(b *swarming.Bot, w io.Writer, r lucifer.RunJobArgs) (*luciferResult, error) {
	panic("not supported on windows")
}

func runLuciferAdminTask(b *swarming.Bot, w io.Writer, r lucifer.AdminTaskArgs) (*luciferResult, error) {
	panic("not supported on windows")
}
