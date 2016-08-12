package buildextract

import (
	"io"
	"io/ioutil"
	"net/http"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestTestClient(t *testing.T) {
	t.Parallel()

	Convey("TestingClient", t, func() {
		readAll := func(data io.ReadCloser) []byte {
			defer data.Close()
			b, err := ioutil.ReadAll(data)
			So(err, ShouldBeNil)
			return b
		}

		Convey("exists", func() {
			tc := &TestingClient{
				M: map[string][]byte{
					"chromium.foo":   []byte(`{"bar":42}`),
					"chromium.hello": []byte(`{"baz":9000}`),
				},
				B: map[string]map[string][]byte{
					"chromium.foo": {
						"Ubuntu Linux": []byte(`{"canonical":"unity"}`),
					},
					"chromium.hello": {
						"Windows 10": []byte(`{"qux":"baaz"}`),
					},
				},
			}

			Convey("GetMasterJSON", func() {
				data, err := tc.GetMasterJSON("chromium.foo")
				So(err, ShouldBeNil)
				So(string(readAll(data)), ShouldEqual, `{"bar":42}`)

				data, err = tc.GetMasterJSON("chromium.hello")
				So(err, ShouldBeNil)
				So(string(readAll(data)), ShouldEqual, `{"baz":9000}`)
			})

			Convey("GetBuildsJSON", func() {
				data, err := tc.GetBuildsJSON("Ubuntu Linux", "chromium.foo", 10)
				So(err, ShouldBeNil)
				So(string(readAll(data)), ShouldEqual, `{"canonical":"unity"}`)

				data, err = tc.GetBuildsJSON("Windows 10", "chromium.hello", 10)
				So(err, ShouldBeNil)
				So(string(readAll(data)), ShouldEqual, `{"qux":"baaz"}`)
			})
		})

		Convey("nil", func() {
			tc := &TestingClient{}

			Convey("GetMasterJSON", func() {
				_, err := tc.GetMasterJSON("chromium.foo")
				So(err, ShouldHaveSameTypeAs, &StatusError{})
				So(err.(*StatusError).StatusCode, ShouldEqual, http.StatusNotFound)
			})

			Convey("GetBuildsJSON", func() {
				_, err := tc.GetBuildsJSON("bax", "bar", 10)
				So(err, ShouldHaveSameTypeAs, &StatusError{})
				So(err.(*StatusError).StatusCode, ShouldEqual, http.StatusNotFound)
			})
		})

		Convey("does not exist", func() {
			tc := &TestingClient{
				M: map[string][]byte{
					"chromium.foo": []byte(`{"bar":42}`),
				},
				B: map[string]map[string][]byte{
					"chromium.foo": {},
				},
			}

			Convey("GetMasterJSON", func() {
				_, err := tc.GetMasterJSON("chromium.hello")
				So(err, ShouldHaveSameTypeAs, &StatusError{})
				So(err.(*StatusError).StatusCode, ShouldEqual, http.StatusNotFound)
			})

			Convey("GetBuildsJSON", func() {
				_, err := tc.GetBuildsJSON("Ubuntu Linux", "chromium.foo", 10)
				So(err, ShouldHaveSameTypeAs, &StatusError{})
				So(err.(*StatusError).StatusCode, ShouldEqual, http.StatusNotFound)

				_, err = tc.GetBuildsJSON("Windows 10", "chromium.hello", 10)
				So(err, ShouldHaveSameTypeAs, &StatusError{})
				So(err.(*StatusError).StatusCode, ShouldEqual, http.StatusNotFound)
			})
		})
	})
}
