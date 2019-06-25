// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package execution provides implementations for test execution runners.
package execution

import (
	"context"

	build_api "go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"

	"infra/cmd/cros_test_platform/internal/execution/internal/skylab"
	"infra/cmd/cros_test_platform/internal/execution/swarming"
)

// Runner defines the interface implemented by Skylab or Autotest execution
// runners.
type Runner interface {
	LaunchAndWait(context.Context, swarming.Client) error
	Response(swarming.Client) *steps.ExecuteResponse
}

// NewSkylabRunner returns a Runner that will execute the given tests in
// the skylab environment.
func NewSkylabRunner(tests []*build_api.AutotestTest, params *test_platform.Request_Params) Runner {
	return skylab.NewTaskSet(tests, params)
}
