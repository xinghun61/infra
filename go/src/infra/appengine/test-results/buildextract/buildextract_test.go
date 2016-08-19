// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package buildextract

import (
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestClient(t *testing.T) {
	t.Parallel()

	// Data is not representative of actual data from live API.
	masterData := map[string][]byte{
		"chromium.mac": []byte(`{ "life": 42 }`),
	}
	buildsData := map[string]map[string][]byte{
		"chromium.mac": {
			"ios.simulator": []byte(`{ "hello": "world" }`),
		},
	}

	getChromiumMacMaster := func(w http.ResponseWriter, req *http.Request) {
		w.Write(masterData["chromium.mac"])
	}
	getBuilds := func(w http.ResponseWriter, req *http.Request) {
		m, b := req.FormValue("master"), req.FormValue("builder")
		data, ok := buildsData[m][b]
		if !ok {
			http.Error(w, "not found", http.StatusNotFound)
			return
		}
		w.Write(data)
	}

	mux := http.NewServeMux()
	mux.Handle("/get_master/chromium.mac", http.HandlerFunc(getChromiumMacMaster))
	mux.Handle("/get_builds", http.HandlerFunc(getBuilds))
	srv := httptest.NewServer(mux)

	Convey("Client", t, func() {
		c := Client{
			HTTPClient: &http.Client{},
			BaseURL:    srv.URL,
		}

		Convey("exists", func() {
			Convey("GetMasterJSON", func() {
				data, err := c.GetMasterJSON("chromium.mac")
				So(err, ShouldBeNil)
				defer data.Close()
				b, err := ioutil.ReadAll(data)
				So(err, ShouldBeNil)
				So(b, ShouldResemble, []byte(`{ "life": 42 }`))
			})
			Convey("GetBuildsJSON", func() {
				data, err := c.GetBuildsJSON("ios.simulator", "chromium.mac", 1)
				So(err, ShouldBeNil)
				defer data.Close()
				b, err := ioutil.ReadAll(data)
				So(err, ShouldBeNil)
				So(b, ShouldResemble, []byte(`{ "hello": "world" }`))
			})

		})
		Convey("does not exist", func() {
			Convey("GetMasterJSON", func() {
				_, err := c.GetMasterJSON("non-existent")
				So(err, ShouldHaveSameTypeAs, &StatusError{})
				So(err.(*StatusError).StatusCode, ShouldEqual, http.StatusNotFound)

			})
			Convey("GetBuildsJSON", func() {
				_, err := c.GetBuildsJSON("non-existent", "chromium.mac", 1)
				So(err, ShouldHaveSameTypeAs, &StatusError{})
				So(err.(*StatusError).StatusCode, ShouldEqual, http.StatusNotFound)
			})
		})

	})
}
