package masters

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
					So(ByName("TryServerChromiumMac"), ShouldResemble, &Master{
						Name:       "TryServerChromiumMac",
						Identifier: "tryserver.chromium.mac",
						Groups:     []string{"Unused"},
					})
				})

				Convey("not existing", func() {
					So(ByName("FooBar"), ShouldBeNil)
					So(ByName("tryserver.chromium.mac"), ShouldBeNil)
				})
			})

			Convey("ByIdentifier", func() {
				Convey("existing", func() {
					So(ByIdentifier("tryserver.chromium.linux"), ShouldResemble, &Master{
						Name:       "TryServerChromiumLinux",
						Identifier: "tryserver.chromium.linux",
						Groups:     []string{"Unused"},
					})
				})

				Convey("not existing", func() {
					So(ByIdentifier("foo.bar"), ShouldBeNil)
					So(ByIdentifier("TryServerChromiumLinux"), ShouldBeNil)
				})
			})
		})
	})
}
