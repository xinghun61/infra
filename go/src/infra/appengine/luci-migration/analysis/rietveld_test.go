// Copyright 2017 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

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
