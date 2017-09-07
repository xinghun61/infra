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
