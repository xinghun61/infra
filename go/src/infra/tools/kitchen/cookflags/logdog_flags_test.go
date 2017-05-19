// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cookflags

import (
	"testing"

	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/logdog/common/types"

	. "github.com/luci/luci-go/common/testing/assertions"
	. "github.com/smartystreets/goconvey/convey"
)

func TestCookLogDogPrefix(t *testing.T) {
	t.Parallel()

	Convey(`With a fake environment`, t, func() {
		var (
			p LogDogFlags

			env = environ.New([]string{
				"SWARMING_BOT_ID=1234567890abcdef",
				"SWARMING_TASK_ID=1234567890abcdef",
			})
		)

		Convey(`When running in Swarming mode`, func() {
			mode := CookSwarming

			Convey(`Can resolve non-templated LogDog URLs.`, func() {
				p.AnnotationURL = "logdog://example.com/testproject/foo/bar/+/annotations"
				So(p.setupAndValidate(mode, env), ShouldBeNil)

				So(p.AnnotationAddr, ShouldResemble, &types.StreamAddr{
					Host:    "example.com",
					Project: "testproject",
					Path:    "foo/bar/+/annotations",
				})
			})

			Convey(`Can resolve templated LogDog URLs`, func() {
				p.AnnotationURL = "logdog://example.com/testproject/foo/bar/${swarming_run_id}/+/annotations"

				Convey(`Can generate a LogDog address`, func() {
					So(p.setupAndValidate(mode, env), ShouldBeNil)

					So(p.AnnotationAddr, ShouldResemble, &types.StreamAddr{
						Host:    "example.com",
						Project: "testproject",
						Path:    "foo/bar/1234567890abcdef/+/annotations",
					})
				})

				Convey(`If Swarming task ID is missing from the environment, will fail.`, func() {
					env.Set("SWARMING_TASK_ID", "")

					So(p.setupAndValidate(mode, env), ShouldErrLike, `no substitution for "swarming_run_id"`)
				})
			})
		})
	})
}
