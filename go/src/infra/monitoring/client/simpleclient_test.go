package client

import (
	"fmt"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestRetry(t *testing.T) {
	Convey("test retry logic", t, func() {
		Convey("success, no retry", func() {
			i := 0
			var err error
			err = retry(func() (bool, error) {
				i++
				return false, nil
			}, 3)
			So(err, ShouldBeNil)
			So(i, ShouldEqual, 1)
		})

		Convey("success, retry", func() {
			i := 0
			var err error
			err = retry(func() (bool, error) {
				i++
				if i < 3 {
					return true, fmt.Errorf("fail")
				}
				return false, nil
			}, 3)
			So(err, ShouldBeNil)
			So(i, ShouldEqual, 3)
		})

		Convey("fail, no retry", func() {
			i := 0
			var err error
			err = retry(func() (bool, error) {
				i++
				return false, fmt.Errorf("fail")
			}, 3)
			So(err, ShouldNotBeNil)
			So(i, ShouldEqual, 1)
		})

		Convey("fail, retry", func() {
			i := 0
			var err error
			err = retry(func() (bool, error) {
				i++
				return true, fmt.Errorf("fail")
			}, 3)
			So(err, ShouldNotBeNil)
			So(i, ShouldEqual, 3)
		})
	})
}
