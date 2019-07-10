// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package skylab

import (
	"github.com/google/uuid"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/config"

	"infra/libs/skylab/worker"
)

// env implements the worker.Environment interface.
type env struct {
	luciProject string
	logdogHost  string
}

// LUCIProject implements worker.Environment interface.
func (e *env) LUCIProject() string {
	return e.luciProject
}

// LogDogHost implements worker.Environment interface.
func (e *env) LogDogHost() string {
	return e.logdogHost
}

// GenerateLogPrefix implements worker.Environment interface.
func (e *env) GenerateLogPrefix() string {
	return "skylab/" + uuid.New().String()
}

func wrap(c *config.Config_SkylabWorker) worker.Environment {
	return &env{
		logdogHost:  c.LogDogHost,
		luciProject: c.LuciProject,
	}
}
