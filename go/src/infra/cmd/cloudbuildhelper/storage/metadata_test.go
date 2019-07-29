// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package storage

import (
	"encoding/json"
	"testing"
	"time"

	"go.chromium.org/luci/common/clock/testclock"

	. "github.com/smartystreets/goconvey/convey"
)

func TestMetadata(t *testing.T) {
	t.Parallel()

	raw := func() map[string]string {
		return map[string]string{
			"raw1":    "v1",
			"raw2":    "v2",
			"a@2":     "v3",
			"b@2":     "v4",
			"a@4":     "v5",
			"b@4":     "v6",
			"c@0003":  "v7", // edge case, non essential when using real timestamps
			"d@0":     "v8", // edge case, non essential when using real timestamps
			"bad@?":   "v9",
			"bad@":    "v10",
			"bad@1@2": "v11",
		}
	}

	parsed := &Metadata{
		d: map[string][]Metadatum{
			"bad@": {
				{Key: "bad@", Timestamp: 0, Value: "v10"},
			},
			"bad@1@2": {
				{Key: "bad@1@2", Timestamp: 0, Value: "v11"},
			},
			"bad@?": {
				{Key: "bad@?", Timestamp: 0, Value: "v9"},
			},
			"d": {
				{Key: "d", Timestamp: 0, Value: "v8"},
			},
			"raw1": {
				{Key: "raw1", Timestamp: 0, Value: "v1"},
			},
			"raw2": {
				{Key: "raw2", Timestamp: 0, Value: "v2"},
			},
			"a": {
				{Key: "a", Timestamp: 4, Value: "v5"},
				{Key: "a", Timestamp: 2, Value: "v3"},
			},
			"b": {
				{Key: "b", Timestamp: 4, Value: "v6"},
				{Key: "b", Timestamp: 2, Value: "v4"},
			},
			"c": {
				{Key: "c", Timestamp: 3, Value: "v7"},
			},
		},
	}

	Convey("ParseMetadata", t, func() {
		So(ParseMetadata(raw()), ShouldResemble, parsed)
	})

	Convey("Assemble", t, func() {
		raw := raw()
		md := ParseMetadata(raw).Assemble()
		So(md, ShouldHaveLength, len(raw))

		// Known edge cases we don't care about.
		So(md["c@3"], ShouldEqual, "v7")
		So(md["d"], ShouldEqual, "v8")
		delete(md, "c@3")
		delete(raw, "c@0003")
		delete(md, "d")
		delete(raw, "d@0")

		So(md, ShouldResemble, raw)
	})

	Convey("Keys", t, func() {
		So(ParseMetadata(raw()).Keys(), ShouldResemble, []string{
			"a", "b", "bad@", "bad@1@2", "bad@?", "c", "d", "raw1", "raw2",
		})
	})

	Convey("Equal", t, func() {
		e := func(k string, ts int64) Metadatum {
			return Metadatum{Key: k, Timestamp: ts}
		}

		md := func(e ...Metadatum) *Metadata {
			out := &Metadata{}
			for _, x := range e {
				out.Add(x)
			}
			return out
		}

		So(md().Equal(md()), ShouldBeTrue)
		So(md(e("1", 1)).Equal(md(e("1", 1))), ShouldBeTrue)
		So(md(e("1", 1)).Equal(md(e("1", 2))), ShouldBeFalse)
		So(md(e("1", 1), e("1", 2)).Equal(md(e("1", 1))), ShouldBeFalse)
		So(md(e("1", 1), e("2", 2)).Equal(md(e("1", 1), e("1", 2))), ShouldBeFalse)
	})

	Convey("Clone", t, func() {
		md := ParseMetadata(raw())
		So(md.Clone().Equal(md), ShouldBeTrue)
	})

	Convey("Add", t, func() {
		md := ParseMetadata(raw())

		md.Add(Metadatum{Key: "new", Timestamp: 5})
		md.Add(Metadatum{Key: "new", Timestamp: 3})
		md.Add(Metadatum{Key: "new", Timestamp: 4})
		md.Add(Metadatum{Key: "new", Timestamp: 6})
		md.Add(Metadatum{Key: "new", Timestamp: 4, Value: "z"})

		So(md.Values("new"), ShouldResemble, []Metadatum{
			{Key: "new", Timestamp: 6},
			{Key: "new", Timestamp: 5},
			{Key: "new", Timestamp: 4, Value: "z"},
			{Key: "new", Timestamp: 3},
		})
	})

	Convey("Trim", t, func() {
		md := Metadata{}

		md.Add(Metadatum{Key: "k1", Timestamp: 1})
		md.Add(Metadatum{Key: "k1", Timestamp: 2})
		md.Add(Metadatum{Key: "k1", Timestamp: 3})
		md.Add(Metadatum{Key: "k2", Timestamp: 1})

		md.Trim(1)
		So(md.Assemble(), ShouldResemble, map[string]string{
			"k1@3": "", "k2@1": "",
		})
	})

	Convey("ToPretty", t, func() {
		ts := testclock.TestRecentTimeUTC
		md := Metadata{}

		add := func(key string, age time.Duration, val interface{}) {
			blob, err := json.Marshal(val)
			if err != nil {
				panic(err)
			}
			md.Add(Metadatum{
				Key:       key,
				Timestamp: ts.Add(-age).UnixNano() / 1000.0,
				Value:     string(blob),
			})
		}

		add("k1", 5*time.Second, "small1")
		add("k1", 10*time.Second, map[string]string{
			"long1": "loooooooooooooooooooooooong",
			"long2": "loooooooooooooooooooooooong",
		})
		add("k1", 15*time.Second, "small2")
		add("k2", 5*time.Second, "small1")
		add("k2", 10*time.Second, "small2")

		So("\n"+md.ToPretty(ts, 10), ShouldEqual, `
k1 (5 seconds ago): "small1"
k1 (10 seconds ago):
  {
    "long1": "loooooooooooooooooooooooong",
    "long2": "loooooooooooooooooooooooong"
  }
k1 (15 seconds ago): "small2"
k2 (5 seconds ago): "small1"
k2 (10 seconds ago): "small2"
`)
	})
}
