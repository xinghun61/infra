package builderstate

import (
	"encoding/json"
	"testing"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/memcache"
	. "github.com/smartystreets/goconvey/convey"

	"infra/appengine/test-results/model"
)

func TestBuilderState(t *testing.T) {
	t.Parallel()

	Convey("builderstate", t, func() {
		masterName := "chromium.webkit"
		builder := "Webkit Linux"
		testType := "browser_tests"
		// Limit to microsecond precision, because of PythonISOTimeFormat
		// limited precision (6-digit microseconds).
		modTime := time.Now().UTC().Round(time.Microsecond)

		// memcache, datastore setup.

		c := memory.Use(context.Background())
		mem := memcache.Get(c)
		ds := datastore.Get(c)
		testFileIdx, err := datastore.FindAndParseIndexYAML("testdata")
		So(err, ShouldBeNil)
		ds.Testable().AddIndexes(testFileIdx...)
		ds.Testable().CatchupIndexes()

		buildbotDataJSON := []byte(`{
			"masters": [{
				"tests": {
					"browser_tests": {
						"builders": [ 
							"Webkit Linux",
							"Webkit Mac",
							"Webkit Win"
						]
					},
					"mini_installer_test": {
						"builders": [ 
							"Webkit Linux",
							"Webkit Mac",
							"Webkit Win"
						]
					},
					"webkit_tests": {
						"builders": [ 
							"Webkit Linux",
							"Webkit Win"
						]
					}
				},
				"name":       "ChromiumWebkit",
				"url_name":   "chromium.webkit",
				"groups":     ["@ToT Chromium", "@ToT Blink"]
			}]
		}`)

		builderStateData := BuilderState{
			Masters: []Master{
				{
					Tests: map[string]*Test{
						"browser_tests": {
							Builders: map[string]time.Time{
								"Webkit Linux": {},
								"Webkit Mac":   {},
								"Webkit Win":   {},
							},
						},
						"mini_installer_test": {
							Builders: map[string]time.Time{
								"Webkit Linux": {},
								"Webkit Mac":   {},
								"Webkit Win":   {},
							},
						},
						"webkit_tests": {
							Builders: map[string]time.Time{
								"Webkit Linux": {},
								"Webkit Win":   {},
							},
						},
					},
					Name:       "ChromiumWebkit",
					Identifier: "chromium.webkit",
					Groups:     []string{"@ToT Chromium", "@ToT Blink"},
				},
			},
		}
		builderStateDataJSON, err := json.Marshal(&builderStateData)
		So(err, ShouldBeNil)
		Convey("Update", func() {
			Convey("no existing state", func() {
				So(
					Update(c, masterName, builder, testType, modTime),
					ShouldEqual,
					memcache.ErrCacheMiss,
				)
			})

			Convey("with existing state", func() {
				item := mem.NewItem(MemcacheKey)
				item.SetValue(builderStateDataJSON)
				mem.Set(item)

				So(Update(c, masterName, builder, testType, modTime), ShouldBeNil)
				item, err := mem.Get(MemcacheKey)
				So(err, ShouldBeNil)

				var actual BuilderState
				So(json.Unmarshal(item.Value(), &actual), ShouldBeNil)

				expected := builderStateData
				expected.Masters[0].Tests[testType].Builders[builder] = modTime

				So(actual, ShouldResemble, expected)
			})

			Convey("updating unknown master should not change data", func() {
				item := mem.NewItem(MemcacheKey)
				item.SetValue(builderStateDataJSON)
				mem.Set(item)

				err := Update(c, "UnknownMaster", builder, testType, modTime)
				So(err, ShouldNotBeNil)
				So(err.Error(), ShouldContainSubstring, "master") // master not found.
				item, err = mem.Get(MemcacheKey)
				So(err, ShouldBeNil)

				var actual BuilderState
				So(json.Unmarshal(item.Value(), &actual), ShouldBeNil)

				So(actual, ShouldResemble, builderStateData)
			})

			Convey("updating unknown test type should not change data", func() {
				item := mem.NewItem(MemcacheKey)
				item.SetValue(builderStateDataJSON)
				mem.Set(item)

				err := Update(c, masterName, builder, "unknown-test", modTime)
				So(err, ShouldNotBeNil)
				So(err.Error(), ShouldContainSubstring, "testType") // testType not found.
				item, err = mem.Get(MemcacheKey)
				So(err, ShouldBeNil)

				var actual BuilderState
				So(json.Unmarshal(item.Value(), &actual), ShouldBeNil)

				So(actual, ShouldResemble, builderStateData)
			})

		})

		Convey("RefreshCache", func() {
			Convey("no builder data", func() {
				_, err := RefreshCache(c)
				So(err, ShouldEqual, memcache.ErrCacheMiss)
				_, err = mem.Get(MemcacheKey)
				So(err, ShouldEqual, memcache.ErrCacheMiss)
			})

			Convey("TestFile does not exist: no last updated change", func() {
				item := mem.NewItem("buildbot_data")
				item.SetValue(buildbotDataJSON)
				mem.Set(item)

				item, err := RefreshCache(c)
				So(err, ShouldBeNil)

				var actual BuilderState
				So(json.Unmarshal(item.Value(), &actual), ShouldBeNil)
				So(actual, ShouldResemble, builderStateData)
			})

			Convey("TestFile exists: set last updated", func() {
				tf1 := model.TestFile{
					Name:     "full_results.json",
					Master:   masterName,
					Builder:  builder,
					TestType: testType,
					LastMod:  modTime,
				}
				So(ds.Put(&tf1), ShouldBeNil)
				ds.Testable().CatchupIndexes()

				item := mem.NewItem("buildbot_data")
				item.SetValue(buildbotDataJSON)
				mem.Set(item)

				item, err := RefreshCache(c)
				So(err, ShouldBeNil)

				var actual BuilderState
				So(json.Unmarshal(item.Value(), &actual), ShouldBeNil)

				expected := builderStateData
				expected.Masters[0].Tests[testType].Builders[builder] = modTime
				So(actual, ShouldResemble, expected)
			})
		})

		Convey("lastUpdated", func() {
			Convey("TestFile does not exist", func() {
				_, err := lastUpdated(c, masterName, builder, testType)
				So(err, ShouldNotBeNil)
				So(err.Error(), ShouldContainSubstring, "no TestFile")
			})

			Convey("TestFile exists, picks correct TestFile", func() {
				// TODO: test other variations (different Builder,
				// TestType, Name, etc.)

				t1 := time.Now().UTC().Round(time.Microsecond)
				tf1 := model.TestFile{
					Name:     "full_results.json",
					Master:   masterName,
					Builder:  builder,
					TestType: testType,
					LastMod:  t1,
				}
				t2 := time.Now().UTC().Add(time.Second * 10).Round(time.Microsecond)
				tf2 := model.TestFile{
					Name:     "full_results.json",
					Master:   "foo",
					Builder:  builder,
					TestType: testType,
					LastMod:  t2,
				}
				So(ds.Put(&tf1, &tf2), ShouldBeNil)
				ds.Testable().CatchupIndexes()

				mod, err := lastUpdated(c, masterName, builder, testType)
				So(err, ShouldBeNil)
				So(mod, ShouldResemble, t1)
			})
		})
	})
}
