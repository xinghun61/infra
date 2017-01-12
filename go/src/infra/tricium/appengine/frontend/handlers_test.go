// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"net/http"
	"net/url"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestFormRequests(t *testing.T) {
	Convey("Test Environment", t, func() {
		project := "test-project"
		gitref := "ref/test"
		paths := []string{
			"README.md",
			"README2.md",
		}

		Convey("Form request", func() {
			v := url.Values{}

			Convey("Is successfully parsed when complete", func() {
				v.Set("Project", project)
				v.Set("GitRef", gitref)
				v["Path[]"] = paths
				sr, err := parseRequestForm(&http.Request{Form: v})
				So(err, ShouldBeNil)
				So(sr.Project, ShouldEqual, project)
				So(sr.GitRef, ShouldEqual, gitref)
				So(len(sr.Paths), ShouldEqual, len(paths))
				for k, p := range paths {
					So(sr.Paths[k], ShouldEqual, p)
				}
			})

			Convey("Fails with missing project", func() {
				v.Set("GitRef", gitref)
				v["Path[]"] = paths
				_, err := parseRequestForm(&http.Request{Form: v})
				So(err, ShouldNotBeNil)
			})

			Convey("Fails with missing Git ref", func() {
				v.Set("Project", project)
				v["Path[]"] = paths
				_, err := parseRequestForm(&http.Request{Form: v})
				So(err, ShouldNotBeNil)
			})

			Convey("Fails with missing paths", func() {
				v.Set("Project", project)
				v.Set("GitRef", gitref)
				_, err := parseRequestForm(&http.Request{Form: v})
				So(err, ShouldNotBeNil)
			})
		})
	})
}
