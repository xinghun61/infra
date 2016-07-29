// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/logdog/common/types"

	. "github.com/luci/luci-go/common/testing/assertions"
	. "github.com/smartystreets/goconvey/convey"
)

func TestCookLogDogPrefix(t *testing.T) {
	Convey(`With a fake environment`, t, func() {
		var (
			p cookLogDogParams

			env = environ.New([]string{
				"SWARMING_SERVER=https://example.appspot.com",
				"SWARMING_TASK_ID=1234567890abcdef",
			})
		)

		Convey(`Will prefer command-line prefix`, func() {
			p.prefix = "foo/bar"

			pfx, err := p.getPrefix(env)
			So(err, ShouldBeNil)
			So(pfx, ShouldEqual, types.StreamName("foo/bar"))
		})

		Convey(`Can generate a LogDog prefix`, func() {
			pfx, err := p.getPrefix(env)
			So(err, ShouldBeNil)
			So(pfx, ShouldEqual, types.StreamName("swarm/example.appspot.com/1234567890abcdef"))
		})

		Convey(`Can generate a LogDog prefix from a host instead of a server URL`, func() {
			env.Set("SWARMING_SERVER", "example.appspot.com")

			pfx, err := p.getPrefix(env)
			So(err, ShouldBeNil)
			So(pfx, ShouldEqual, types.StreamName("swarm/example.appspot.com/1234567890abcdef"))
		})

		Convey(`If Swarming server is missing from the environment, will fail.`, func() {
			env.Set("SWARMING_SERVER", "")

			_, err := p.getPrefix(env)
			So(err, ShouldErrLike, "missing or empty SWARMING_SERVER")
		})

		Convey(`If Swarming task ID is missing from the environment, will fail.`, func() {
			env.Set("SWARMING_TASK_ID", "")

			_, err := p.getPrefix(env)
			So(err, ShouldErrLike, "missing or empty SWARMING_TASK_ID")
		})
	})
}
