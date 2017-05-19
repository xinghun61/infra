// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/memlogger"

	"golang.org/x/net/context"
	"google.golang.org/grpc/grpclog"

	. "github.com/smartystreets/goconvey/convey"
)

func TestDisableGRPCLogging(t *testing.T) {
	Convey(`LogDog executions suppress gRPC print-level logging`, t, func() {
		var (
			ctx = context.Background()
			ml  memlogger.MemLogger
		)

		// Install our memory logger.
		ctx = logging.SetFactory(ctx, func(context.Context) logging.Logger { return &ml })

		// Call "runWithLogdogButler". This should panic, but, more importantly for
		// this test, should also install our gRPC log suppression. Note that this
		// is GLOBAL, so we cannot run this in parallel.
		Convey(`When log level is Info, does not log Prints.`, func() {
			ctx = logging.SetLevel(ctx, logging.Info)
			disableGRPCLogging(ctx)

			grpclog.Println("TEST!")
			So(ml.Messages(), ShouldHaveLength, 0)
		})

		Convey(`When log level is Debug, does log Prints.`, func() {
			ctx = logging.SetLevel(ctx, logging.Debug)
			disableGRPCLogging(ctx)

			grpclog.Println("TEST!")
			So(ml.Messages(), ShouldHaveLength, 1)
		})
	})
}
