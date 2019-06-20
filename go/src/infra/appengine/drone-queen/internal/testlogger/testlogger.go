// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package testlogger implements a logging.Logger for use in tests.
package testlogger

import (
	"context"
	"testing"

	"go.chromium.org/luci/common/logging"
)

// Use adds a logging.Logger implementation to the context which logs for a test.
func Use(ctx context.Context, t *testing.T) context.Context {
	return logging.SetFactory(ctx, func(ctx context.Context) logging.Logger {
		return loggerImpl{ctx: ctx, t: t}
	})
}

type loggerImpl struct {
	ctx context.Context
	t   *testing.T
}

func (gl loggerImpl) Debugf(format string, args ...interface{}) {
	gl.LogCall(logging.Debug, 1, format, args)
}
func (gl loggerImpl) Infof(format string, args ...interface{}) {
	gl.LogCall(logging.Info, 1, format, args)
}
func (gl loggerImpl) Warningf(format string, args ...interface{}) {
	gl.LogCall(logging.Warning, 1, format, args)
}
func (gl loggerImpl) Errorf(format string, args ...interface{}) {
	gl.LogCall(logging.Error, 1, format, args)
}

func (gl loggerImpl) LogCall(l logging.Level, calldepth int, format string, args []interface{}) {
	if !logging.IsLogging(gl.ctx, l) {
		return
	}
	gl.t.Logf(format, args...)
}
