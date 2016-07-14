package frontend

import (
	"net/url"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
)

func TestTestFileParams(t *testing.T) {
	Convey("TestFileParams", t, func() {
		values := url.Values{
			"master":   []string{"tryserver.chromium.win"},
			"builder":  []string{"win_chromium_rel_ng", "this_val_should_be_ignored"},
			"name":     []string{"results.json"},
			"numfiles": []string{"", "42"},
			"testtype": []string{"unit_tests (with patch)"},
			"callback": []string{"", ""},
			"before":   []string{"2007-12-30T00:24:05Z"},
		}
		p, err := NewURLParams(values)
		So(err, ShouldBeNil)

		Convey("Should have correct values for present keys", func() {
			So(p.Master, ShouldEqual, "tryserver.chromium.win")
			So(p.Builder, ShouldEqual, "win_chromium_rel_ng")
			So(p.Name, ShouldEqual, "results.json")
			So(p.NumFiles, ShouldBeZeroValue)
			So(p.TestType, ShouldEqual, "unit_tests (with patch)")
			So(p.Before.Equal(time.Date(2007, 12, 30, 00, 24, 05, 0, time.UTC)), ShouldBeTrue)
		})

		Convey("Should have zero values for absent keys", func() {
			So(p.BuildNumber, ShouldBeZeroValue)
			So(p.Key, ShouldBeZeroValue)
			So(p.TestListJSON, ShouldBeZeroValue)
			So(p.Callback, ShouldBeZeroValue)
		})
	})
}
