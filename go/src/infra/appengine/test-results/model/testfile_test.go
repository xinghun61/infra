package model

import (
	"io/ioutil"
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

		Convey("Should get an existing TestFile by ID", func() {
			tf := TestFile{ID: 1}
			So(ds.Get(&tf), ShouldBeNil)
			So(tf.ID, ShouldEqual, 1)
			So(tf.Name, ShouldEqual, "full_results.json")
			So(tf.Master, ShouldEqual, "Chromium")
		})

		Convey("Should fetch data from multiple DataEntries", func() {
			So(tf1.GetData(c), ShouldBeNil)
			b, err := ioutil.ReadAll(tf1.Data)
			So(err, ShouldBeNil)
			So(string(b), ShouldResemble, "hello, world")
		})
	})
}
