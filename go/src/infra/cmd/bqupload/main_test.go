// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"encoding/json"
	"fmt"
	"strings"
	"testing"

	"cloud.google.com/go/bigquery"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

type savedValue struct {
	insertID string
	row      map[string]bigquery.Value
}

func value(insertID, jsonVal string) savedValue {
	v := savedValue{insertID: insertID}
	So(json.Unmarshal([]byte(jsonVal), &v.row), ShouldBeNil)
	return v
}

func doReadInput(data string) ([]savedValue, error) {
	savers, err := readInput(strings.NewReader(data), "seed")
	if err != nil {
		return nil, err
	}
	out := make([]savedValue, len(savers))
	for i, saver := range savers {
		if out[i].row, out[i].insertID, err = saver.Save(); err != nil {
			return nil, err
		}
	}
	return out, nil
}

func TestReadInput(t *testing.T) {
	t.Parallel()

	Convey("Empty", t, func() {
		vals, err := doReadInput("")
		So(err, ShouldBeNil)
		So(vals, ShouldHaveLength, 0)
	})

	Convey("Whitespace only", t, func() {
		vals, err := doReadInput("\n  \n\n  \n  ")
		So(err, ShouldBeNil)
		So(vals, ShouldHaveLength, 0)
	})

	Convey("One line", t, func() {
		vals, err := doReadInput(`{"k": "v"}`)
		So(err, ShouldBeNil)
		So(vals, ShouldResemble, []savedValue{
			value("seed:0", `{"k": "v"}`),
		})
	})

	Convey("A bunch of lines (with spaces)", t, func() {
		vals, err := doReadInput(`
			{"k": "v1"}

			{"k": "v2"}
			{"k": "v3"}

		`)
		So(err, ShouldBeNil)
		So(vals, ShouldResemble, []savedValue{
			value("seed:0", `{"k": "v1"}`),
			value("seed:1", `{"k": "v2"}`),
			value("seed:2", `{"k": "v3"}`),
		})
	})

	Convey("Broken line", t, func() {
		_, err := doReadInput(`
			{"k": "v1"}

			{"k": "v2
			{"k": "v2"}
		`)
		So(err, ShouldErrLike, `bad input line 4: bad JSON - unexpected end of JSON input`)
	})

	Convey("Huge line", t, func() {
		// Note: this breaks bufio.Scanner with "token too long" error.
		huge := fmt.Sprintf(`{"k": %q}`, strings.Repeat("x", 100000))
		vals, err := doReadInput(huge)
		So(err, ShouldBeNil)
		So(vals, ShouldResemble, []savedValue{
			value("seed:0", huge),
		})
	})
}
