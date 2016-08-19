// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

import (
	"bytes"
	"io/ioutil"
	"path/filepath"
	"testing"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/gae/service/datastore"
	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestTestFile(t *testing.T) {
	t.Parallel()

	Convey("TestFile", t, func() {
		c := memory.Use(context.Background())
		ds := datastore.Get(c)
		testFileIdx, err := datastore.FindAndParseIndexYAML("testdata")
		So(err, ShouldBeNil)
		ds.Testable().AddIndexes(testFileIdx...)

		Convey("Get", func() {
			dataEntries := []DataEntry{
				{Data: []byte("hello, "), ID: 142},
				{Data: []byte("world"), ID: 199},
			}

			for _, de := range dataEntries {
				So(ds.Put(&de), ShouldBeNil)
			}

			dataKeys := make([]*datastore.Key, len(dataEntries))
			for i, de := range dataEntries {
				dataKeys[i] = ds.KeyForObj(&de)
			}

			tf1 := TestFile{
				ID:       1,
				Name:     "full_results.json",
				Master:   "Chromium",
				DataKeys: dataKeys,
			}

			So(ds.Put(&tf1), ShouldBeNil)
			ds.Testable().CatchupIndexes()

			Convey("get an existing TestFile by ID", func() {
				tf := TestFile{ID: 1}
				So(ds.Get(&tf), ShouldBeNil)
				So(tf.ID, ShouldEqual, 1)
				So(tf.Name, ShouldEqual, "full_results.json")
				So(tf.Master, ShouldEqual, "Chromium")
			})

			Convey("fetch data from multiple DataEntrys", func() {
				So(tf1.GetData(c), ShouldBeNil)
				b, err := ioutil.ReadAll(tf1.Data)
				So(err, ShouldBeNil)
				So(string(b), ShouldResemble, "hello, world")
			})
		})

		Convey("Put", func() {
			Convey("puts and retrieves DataEntry", func() {
				data, err := ioutil.ReadFile(filepath.Join("testdata", "results.json"))
				So(err, ShouldBeNil)
				tf := TestFile{
					ID:   1,
					Data: bytes.NewReader(data),
				}
				So(tf.PutData(c), ShouldBeNil)
				So(ds.Put(&tf), ShouldBeNil)

				ds.Testable().CatchupIndexes()

				tf = TestFile{ID: 1}
				So(ds.Get(&tf), ShouldBeNil)
				So(tf.ID, ShouldEqual, 1)
				So(tf.GetData(c), ShouldBeNil)
				b, err := ioutil.ReadAll(tf.Data)
				So(err, ShouldBeNil)
				So(b, ShouldResemble, data)
			})

			Convey("PutData updates DataKeys and OldDataKeys", func() {
				tf := TestFile{
					ID:   1,
					Data: bytes.NewReader([]byte(`{"hello":"world"}`)),
				}
				So(tf.PutData(c), ShouldBeNil)
				So(tf.DataKeys, ShouldNotBeNil)
				So(ds.Put(&tf), ShouldBeNil)

				k := make([]*datastore.Key, len(tf.DataKeys))
				copy(k, tf.DataKeys)
				tf.Data = bytes.NewReader([]byte(`{"new":"data"}`))
				So(tf.PutData(c), ShouldBeNil)
				So(tf.OldDataKeys, ShouldResemble, k)
				So(ds.Put(&tf), ShouldBeNil)

				Convey("OldDataKeys referenced DataEntry still exists", func() {
					ds.Testable().CatchupIndexes()

					tmp := TestFile{DataKeys: k}
					So(tmp.GetData(c), ShouldBeNil)
					b, err := ioutil.ReadAll(tmp.Data)
					So(err, ShouldBeNil)
					So(b, ShouldResemble, []byte(`{"hello":"world"}`))
				})
			})
		})
	})
}
