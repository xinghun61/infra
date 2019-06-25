// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package proxy_test

import (
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"infra/libs/skylab/autotest/proxy"
)

func TestRunSuite(t *testing.T) {
	Convey("When creating a request for a set of RunSuite arguments", t, func() {
		args := proxy.RunSuiteArgs{
			Board:     "foo-board",
			Build:     "foo-build",
			Model:     "foo-model",
			Pool:      "foo-pool",
			SuiteName: "foo-suite",
		}
		req := proxy.NewRunSuite(args)
		So(req, ShouldNotBeNil)
		So(req.TaskSlices, ShouldHaveLength, 1)
		Convey("the correct commandline args are present.", func() {
			slice := req.TaskSlices[0]
			flatCmd := strings.Join(slice.Properties.Command, " ")
			So(flatCmd, ShouldContainSubstring, "--board foo-board")
			So(flatCmd, ShouldContainSubstring, "--build foo-build")
			So(flatCmd, ShouldContainSubstring, "--model foo-model")
			So(flatCmd, ShouldContainSubstring, "--pool foo-pool")
			So(flatCmd, ShouldContainSubstring, "--suite_name foo-suite")
		})
	})
}
