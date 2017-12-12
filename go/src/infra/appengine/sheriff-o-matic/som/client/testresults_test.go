package client

import (
	"testing"

	"infra/monitoring/messages"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestTestResults(t *testing.T) {
	Convey("test test results", t, func() {
		trc := &testResults{}
		ctx := context.WithValue(context.Background(), testResultsKey, trc)
		Convey("cache tests", func() {
			trc.knownResults = knownResults{}
			trc.knownResults["test.master"] = map[string][]string{
				"test": {"builderA"},
			}

			res, err := trc.TestResults(ctx, &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/other.master", t)}, "builderB", "test", 0)
			So(err, ShouldBeNil)
			So(res, ShouldBeNil)

			res, err = trc.TestResults(ctx, &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/test.master", t)}, "builderB", "test", 0)
			So(err, ShouldBeNil)
			So(res, ShouldBeNil)

			res, err = trc.TestResults(ctx, &messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/test.master", t)}, "builderB", "foo", 0)
			So(err, ShouldBeNil)
			So(res, ShouldBeNil)
		})

	})
}

func TestBuilderTestHistory(t *testing.T) {
	Convey("IndexForBuildNum", t, func() {
		Convey("empty", func() {
			bth := &BuilderTestHistory{}
			_, err := bth.IndexForBuildNum(123)

			So(err, ShouldNotBeNil)
		})

		Convey("not empty", func() {
			bth := &BuilderTestHistory{
				BuildNumbers: []int64{10, 9, 8, 7, 6, 5, 4, 3},
			}
			_, err := bth.IndexForBuildNum(11)
			So(err, ShouldNotBeNil)

			idx, err := bth.IndexForBuildNum(7)
			So(err, ShouldBeNil)
			So(idx, ShouldEqual, 3)
		})
	})
	Convey("ResultsForBuildRange", t, func() {
		Convey("empty", func() {
			bth := &BuilderTestHistory{}
			_, err := bth.ResultsForBuildRange("foo_test", 123, 234)
			So(err, ShouldNotBeNil)
		})

		Convey("not empty", func() {
			bth := &BuilderTestHistory{
				BuildNumbers:   []int64{10, 9, 8, 7, 6, 5, 4, 3},
				ChromeRevision: []string{"10", "9", "8", "7", "6", "5", "4", "3"},
				Tests: map[string]*TestResultHistory{
					"foo_test": &TestResultHistory{
						Results: [][]interface{}{
							{float64(1), "A"},
							{float64(2), "B"},
							{float64(3), "CCB"},
							{float64(2), "A"},
							{float64(2), "CAB"},
						},
						Times: [][]int{},
					},
				},
				FailureMap: map[string]string{
					"A": "FAIL",
					"B": "PASS",
					"C": "CRASH",
				},
			}

			Convey("test exists, builds out of range", func() {
				_, err := bth.ResultsForBuildRange("foo_test", 11, 1)
				So(err, ShouldNotBeNil)
			})

			Convey("test exists, builds in range", func() {
				start, err := bth.IndexForBuildNum(10)
				So(err, ShouldBeNil)
				So(start, ShouldEqual, 0)

				end, err := bth.IndexForBuildNum(5)
				So(err, ShouldBeNil)
				So(end, ShouldEqual, 5)

				res, err := bth.ResultsForBuildRange("foo_test", 10, 3)
				So(err, ShouldBeNil)
				So(len(res), ShouldEqual, 8)
				So(res, ShouldResemble, []*BuildTestResults{
					&BuildTestResults{
						ChromeRevision: "10",
						BuildNumber:    10,
						Results:        []string{"FAIL"},
					},
					&BuildTestResults{
						ChromeRevision: "9",
						BuildNumber:    9,
						Results:        []string{"PASS"},
					},
					&BuildTestResults{
						ChromeRevision: "8",
						BuildNumber:    8,
						Results:        []string{"PASS"},
					},
					&BuildTestResults{
						ChromeRevision: "7",
						BuildNumber:    7,
						Results:        []string{"CRASH", "CRASH", "PASS"},
					},
					&BuildTestResults{
						ChromeRevision: "6",
						BuildNumber:    6,
						Results:        []string{"CRASH", "CRASH", "PASS"},
					},
					&BuildTestResults{
						ChromeRevision: "5",
						BuildNumber:    5,
						Results:        []string{"CRASH", "CRASH", "PASS"},
					},
					&BuildTestResults{
						ChromeRevision: "4",
						BuildNumber:    4,
						Results:        []string{"FAIL"},
					},
					&BuildTestResults{
						ChromeRevision: "3",
						BuildNumber:    3,
						Results:        []string{"FAIL"},
					},
				})
			})
		})
	})
}

func TestTestResultHistory(t *testing.T) {
	Convey("RLE basics", t, func() {
		Convey("empty", func() {
			trh := &TestResultHistory{}

			res, err := trh.ResultAt(0)
			So(err, ShouldNotBeNil)
			So(res, ShouldEqual, "")
		})

		Convey("1, 2, 3", func() {
			trh := &TestResultHistory{
				Results: [][]interface{}{
					{float64(1), "A"},
					{float64(2), "B"},
					{float64(3), "C"},
				},
			}

			res, err := trh.ResultAt(0)
			So(err, ShouldBeNil)
			So(res, ShouldEqual, "A")
			res, err = trh.ResultAt(1)
			So(err, ShouldBeNil)
			So(res, ShouldEqual, "B")
			res, err = trh.ResultAt(2)
			So(err, ShouldBeNil)
			So(res, ShouldEqual, "B")
			res, err = trh.ResultAt(3)
			So(err, ShouldBeNil)
			So(res, ShouldEqual, "C")
			res, err = trh.ResultAt(4)
			So(err, ShouldBeNil)
			So(res, ShouldEqual, "C")
			res, err = trh.ResultAt(5)
			So(err, ShouldBeNil)
			So(res, ShouldEqual, "C")
			res, err = trh.ResultAt(6)
			So(err, ShouldNotBeNil)
			So(res, ShouldEqual, "")
		})

	})
}
