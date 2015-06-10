// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package jsutil

import (
	"bytes"
	"encoding/json"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestGet(t *testing.T) {
	t.Parallel()

	const testDoc = `
	[
		{
			"some": [1337, {"mixed": "values"}],
			"wat": "thing"
		},
		{}
	]
	`

	var data interface{}
	dec := json.NewDecoder(bytes.NewBufferString(testDoc))
	dec.UseNumber()
	if err := dec.Decode(&data); err != nil {
		panic(err)
	}

	Convey("Test Get and GetError", t, func() {
		Convey("can extract values", func() {
			So(len(Get(data, 0).(map[string]interface{})), ShouldEqual, 2)
			val, err := Get(data, 0, "some", 0).(json.Number).Int64()
			So(err, ShouldBeNil)
			So(val, ShouldEqual, 1337)
		})

		Convey("getting a value that's not there panics", func() {
			So(func() {
				Get(data, "nope")
			}, ShouldPanic)
		})

		Convey("errors are resonable", func() {
			_, err := GetError(data, 0, "some", 1, "mixed", 10)
			So(err.Error(), ShouldContainSubstring,
				"expected []interface{}, but got string")

			_, err = GetError(data, 0, "some", 1, "mixed", "nonex")
			So(err.Error(), ShouldContainSubstring,
				"expected map[string]interface{}, but got string")

			_, err = GetError(data, 0.1)
			So(err.Error(), ShouldContainSubstring,
				"expected string or int in pathElems, got float64 instead")
		})
	})
}
