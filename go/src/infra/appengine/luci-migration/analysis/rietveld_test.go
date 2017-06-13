// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analysis

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestRietveld(t *testing.T) {
	t.Parallel()

	Convey("is404", t, func() {
		c := context.Background()

		status := http.StatusOK
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(status)
		}))
		defer server.Close()

		Convey("exists", func() {
			absent, err := is404(c, nil, server.URL)
			So(err, ShouldBeNil)
			So(absent, ShouldBeFalse)
		})

		Convey("absent", func() {
			status = http.StatusNotFound
			absent, err := is404(c, nil, server.URL)
			So(err, ShouldBeNil)
			So(absent, ShouldBeTrue)
		})
	})
}
