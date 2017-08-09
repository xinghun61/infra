// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"net/http"
	"net/http/httptest"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/server/router"
)

func TestCommitPositionToHash(t *testing.T) {
	t.Parallel()

	data := map[string][]byte{
		"1300": []byte(`{
 "git_sha": "0dfc81bbe403cd98f4cd2d58e7817cdc8a881a5f",
"repo": "chromium/src",
"redirect_url": "https://chromium.googlesource.com/chromium/src/+/0dfc81bbe403cd98f4cd2d58e7817cdc8a881a5f",
"project": "chromium",
"redirect_type": "GIT_FROM_NUMBER",
"repo_url": "https://chromium.googlesource.com/chromium/src/",
"kind": "crrev#redirectItem",
"etag": "\"kuKkspxlsT40mYsjSiqyueMe20E/qt8_sNqlQbK8xP9pkpc9EOsNyrE\""
}`),
	}
	handler := func(c *router.Context) {
		b, ok := data[c.Params.ByName("pos")]
		if !ok {
			http.Error(c.Writer, "not found", http.StatusNotFound)
			return
		}
		c.Writer.Write(b)
	}
	r := router.New()
	r.GET("/:pos", router.MiddlewareChain{}, handler)

	srv := httptest.NewServer(r)

	client := crRevClient{
		HTTPClient: &http.Client{},
		BaseURL:    srv.URL,
	}

	Convey("commitPositionToHash", t, func() {
		Convey("existing position", func() {
			hash, err := client.commitHash("1300")
			So(err, ShouldBeNil)
			So(hash, ShouldEqual, "0dfc81bbe403cd98f4cd2d58e7817cdc8a881a5f")
		})

		Convey("non-existent position", func() {
			_, err := client.commitHash("0")
			So(err, ShouldNotBeNil)
		})
	})
}
