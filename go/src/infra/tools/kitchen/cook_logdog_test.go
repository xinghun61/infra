// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/memlogger"
	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/logdog/common/types"

	"golang.org/x/net/context"
	"google.golang.org/grpc/grpclog"

	. "github.com/luci/luci-go/common/testing/assertions"
	. "github.com/smartystreets/goconvey/convey"
)

func TestCookLogDogPrefix(t *testing.T) {
	t.Parallel()

	Convey(`With a fake environment`, t, func() {
		var (
			p cookLogDogParams

			env = environ.New([]string{
				"SWARMING_TASK_ID=1234567890abcdef",
			})
		)

		Convey(`Can resolve non-templated LogDog URLs.`, func() {
			p.annotationURL = "logdog://example.com/testproject/foo/bar/+/annotations"
			So(p.setupAndValidate(env), ShouldBeNil)

			So(p.annotationAddr, ShouldResemble, &types.StreamAddr{
				Host:    "example.com",
				Project: "testproject",
				Path:    "foo/bar/+/annotations",
			})
		})

		Convey(`Can resolve templated LogDog URLs`, func() {
			p.annotationURL = "logdog://example.com/testproject/foo/bar/${swarming_run_id}/+/annotations"

			Convey(`Can generate a LogDog address`, func() {
				So(p.setupAndValidate(env), ShouldBeNil)

				So(p.annotationAddr, ShouldResemble, &types.StreamAddr{
					Host:    "example.com",
					Project: "testproject",
					Path:    "foo/bar/1234567890abcdef/+/annotations",
				})
			})

			Convey(`If Swarming task ID is missing from the environment, will fail.`, func() {
				env.Set("SWARMING_TASK_ID", "")

				So(p.setupAndValidate(env), ShouldErrLike, `no substitution for "swarming_run_id"`)
			})
		})
	})
}

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
