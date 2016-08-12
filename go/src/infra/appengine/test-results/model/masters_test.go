package model

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestMasters(t *testing.T) {
	t.Parallel()

	Convey("Masters", t, func() {
		Convey("Known Masters", func() {
			Convey("ByName", func() {
				Convey("existing", func() {
					So(MasterByName("TryServerChromiumMac"), ShouldResemble, &Master{
						Name:       "TryServerChromiumMac",
						Identifier: "tryserver.chromium.mac",
						Groups:     []string{"Unused"},
					})
				})

				Convey("not existing", func() {
					So(MasterByName("FooBar"), ShouldBeNil)
					So(MasterByName("tryserver.chromium.mac"), ShouldBeNil)
				})
			})

			Convey("ByIdentifier", func() {
				Convey("existing", func() {
					So(MasterByIdentifier("tryserver.chromium.linux"), ShouldResemble, &Master{
						Name:       "TryServerChromiumLinux",
						Identifier: "tryserver.chromium.linux",
						Groups:     []string{"Unused"},
					})
				})

				Convey("not existing", func() {
					So(MasterByIdentifier("foo.bar"), ShouldBeNil)
					So(MasterByIdentifier("TryServerChromiumLinux"), ShouldBeNil)
				})
			})
		})
	})
}
