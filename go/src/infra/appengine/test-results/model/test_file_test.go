// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

import (
	"io"
	"io/ioutil"
	"path/filepath"
	"testing"

	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestTestFile(t *testing.T) {
	t.Parallel()

	Convey("TestFile", t, func() {
		c := memory.Use(context.Background())
		testFileIdx, err := datastore.FindAndParseIndexYAML("testdata")
		So(err, ShouldBeNil)
		datastore.GetTestable(c).AddIndexes(testFileIdx...)

		Convey("Get", func() {
			dataEntries := []DataEntry{
				{Data: []byte("hello, "), ID: 142},
				{Data: []byte("world"), ID: 199},
			}

			for _, de := range dataEntries {
				So(datastore.Put(c, &de), ShouldBeNil)
			}

			dataKeys := make([]*datastore.Key, len(dataEntries))
			for i, de := range dataEntries {
				dataKeys[i] = datastore.KeyForObj(c, &de)
			}

			tf1 := TestFile{
				ID:       1,
				Name:     "full_results.json",
				Master:   "Chromium",
				DataKeys: dataKeys,
			}

			So(datastore.Put(c, &tf1), ShouldBeNil)
			datastore.GetTestable(c).CatchupIndexes()

			Convey("get an existing TestFile by ID", func() {
				tf := TestFile{ID: 1}
				So(datastore.Get(c, &tf), ShouldBeNil)
				So(tf.ID, ShouldEqual, 1)
				So(tf.Name, ShouldEqual, "full_results.json")
				So(tf.Master, ShouldEqual, "Chromium")
			})

			Convey("fetch data from multiple DataEntrys", func() {
				reader, err := tf1.DataReader(c)
				So(err, ShouldBeNil)
				b, err := ioutil.ReadAll(reader)
				So(err, ShouldBeNil)
				So(string(b), ShouldResemble, "hello, world")
			})
		})

		Convey("Put", func() {
			Convey("puts and retrieves DataEntry", func() {
				data, err := ioutil.ReadFile(filepath.Join("testdata", "results.json"))
				So(err, ShouldBeNil)
				tf := TestFile{
					ID: 1,
				}
				So(tf.PutData(c, func(w io.Writer) error {
					_, err := w.Write(data)
					return err
				}), ShouldBeNil)
				So(datastore.Put(c, &tf), ShouldBeNil)

				datastore.GetTestable(c).CatchupIndexes()

				tf = TestFile{ID: 1}
				So(datastore.Get(c, &tf), ShouldBeNil)
				So(tf.ID, ShouldEqual, 1)

				reader, err := tf.DataReader(c)
				So(err, ShouldBeNil)
				b, err := ioutil.ReadAll(reader)
				So(err, ShouldBeNil)
				So(b, ShouldResemble, data)
			})

			Convey("puts and retrieves DataEntry with smaller datastore buff", func() {
				datastoreBlobLimitBackup := datastoreBlobLimit
				defer func() {
					datastoreBlobLimit = datastoreBlobLimitBackup
				}()
				// Set smaller limit so that parallelized datastore puts happen.
				datastoreBlobLimit = 1 << 15

				data, err := ioutil.ReadFile(filepath.Join("testdata", "results.json"))
				So(len(data), ShouldBeGreaterThan, datastoreBlobLimit)
				So(err, ShouldBeNil)
				tf := TestFile{
					ID: 1,
				}
				So(tf.PutData(c, func(w io.Writer) error {
					_, err := w.Write(data)
					return err
				}), ShouldBeNil)
				So(datastore.Put(c, &tf), ShouldBeNil)

				datastore.GetTestable(c).CatchupIndexes()

				tf = TestFile{ID: 1}
				So(datastore.Get(c, &tf), ShouldBeNil)
				So(tf.ID, ShouldEqual, 1)

				reader, err := tf.DataReader(c)
				So(err, ShouldBeNil)
				b, err := ioutil.ReadAll(reader)
				So(err, ShouldBeNil)
				So(b, ShouldResemble, data)
			})

			Convey("PutData updates DataKeys and OldDataKeys", func() {
				tf := TestFile{
					ID: 1,
				}
				So(tf.PutData(c, func(w io.Writer) error {
					_, err := w.Write([]byte(`{"hello":"world"}`))
					return err
				}), ShouldBeNil)
				So(tf.DataKeys, ShouldNotBeNil)
				So(datastore.Put(c, &tf), ShouldBeNil)

				k := make([]*datastore.Key, len(tf.DataKeys))
				copy(k, tf.DataKeys)

				So(tf.PutData(c, func(w io.Writer) error {
					_, err := w.Write([]byte(`{"new":"data"}`))
					return err
				}), ShouldBeNil)
				So(tf.OldDataKeys, ShouldResemble, k)
				So(datastore.Put(c, &tf), ShouldBeNil)

				Convey("OldDataKeys referenced DataEntry still exists", func() {
					datastore.GetTestable(c).CatchupIndexes()

					tmp := TestFile{DataKeys: k}
					reader, err := tmp.DataReader(c)
					So(err, ShouldBeNil)
					b, err := ioutil.ReadAll(reader)
					So(err, ShouldBeNil)
					So(b, ShouldResemble, []byte(`{"hello":"world"}`))
				})
			})
		})
	})
}
