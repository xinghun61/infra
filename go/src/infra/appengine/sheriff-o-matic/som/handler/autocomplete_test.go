package handler

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/server/router"

	. "github.com/smartystreets/goconvey/convey"
)

func TestGetUserAutocompleteHandler(t *testing.T) {
	Convey("basic", t, func() {
		c := gaetesting.TestingContext()
		r := makeGetRequest()
		w := httptest.NewRecorder()

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: r,
			Params:  makeParams("query", "def"),
		}

		GetUserAutocompleteHandler(ctx)
		So(w.Code, ShouldEqual, http.StatusOK)
	})
}

func TestAutocompleter(t *testing.T) {
	Convey("basic", t, func() {
		testStrs := []string{"abc", "bcd", "abcd", "def", "fghij"}

		ac := newAutocompleter(testStrs)
		Convey("single char", func() {
			res := ac.query("a")

			So(res, ShouldNotBeEmpty)
			So(res, ShouldResemble, []string{"abc", "abcd"})
		})

		Convey("multi-char prefix", func() {
			res := ac.query("ab")

			So(res, ShouldNotBeEmpty)
			So(res, ShouldResemble, []string{"abc", "abcd"})
		})

		Convey("multi-char suffix", func() {
			res := ac.query("cd")

			So(res, ShouldNotBeEmpty)
			So(res, ShouldResemble, []string{"bcd", "abcd"})
		})

		Convey("mid-string match", func() {
			res := ac.query("bc")

			So(res, ShouldNotBeEmpty)
			So(res, ShouldResemble, []string{"abc", "bcd", "abcd"})

			res = ac.query("ghi")

			So(res, ShouldNotBeEmpty)
			So(res, ShouldResemble, []string{"fghij"})
		})

		Convey("no match", func() {
			res := ac.query("x")
			So(res, ShouldBeEmpty)
		})
	})
}
