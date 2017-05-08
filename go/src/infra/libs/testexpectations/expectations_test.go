package testexpectations

import (
	"strings"
	"testing"
	"time"

	"golang.org/x/net/context"

	testhelper "infra/monitoring/client/test"

	"github.com/luci/gae/impl/dummy"
	"github.com/luci/gae/service/info"
	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/appengine/gaetesting"

	. "github.com/smartystreets/goconvey/convey"
)

func TestUpdateExpectations(t *testing.T) {
	Convey("Update empty", t, func() {
		fs := &FileSet{
			Files: []*File{
				{
					Path:         "/some/path",
					Expectations: []*ExpectationStatement{},
				},
			},
		}

		err := fs.UpdateExpectation(&ExpectationStatement{})
		So(err, ShouldBeNil)
	})

	Convey("Update basic, single file", t, func() {
		fs := &FileSet{
			Files: []*File{
				{
					Path: "/some/path",
					Expectations: []*ExpectationStatement{
						{
							TestName:     "/third_party/test_name",
							Expectations: []string{"PASS"},
						},
					},
				},
			},
		}

		cl := fs.ToCL()
		So(cl, ShouldNotBeNil)
		So(len(cl), ShouldEqual, 1)

		So(cl["/some/path"], ShouldEqual, "/third_party/test_name [ PASS ]")

		err := fs.UpdateExpectation(&ExpectationStatement{
			TestName:     "/third_party/test_name",
			Expectations: []string{"PASS", "FAIL"},
		})
		So(err, ShouldBeNil)

		cl = fs.ToCL()
		So(cl, ShouldNotBeNil)
		So(len(cl), ShouldEqual, 1)

		So(cl["/some/path"], ShouldEqual, "/third_party/test_name [ PASS FAIL ]")
	})

	Convey("Update basic, multiple files and tests", t, func() {
		fs := &FileSet{
			Files: []*File{
				{
					Path: "/some/path1",
					Expectations: []*ExpectationStatement{
						{
							Original:     "/third_party/test_name1 [ PASS ]",
							TestName:     "/third_party/test_name1",
							Expectations: []string{"PASS"},
						},
						{
							Original:     "/third_party/test_name1b [ FAIL ]",
							TestName:     "/third_party/test_name1b",
							Expectations: []string{"FAIL"},
						},
					},
				},
				{
					Path: "/some/path2",
					Expectations: []*ExpectationStatement{
						{
							Original:     "/third_party/test_name2 [ PASS ]",
							TestName:     "/third_party/test_name2",
							Expectations: []string{"PASS"},
						},
					},
				},
			},
		}

		cl := fs.ToCL()
		So(cl, ShouldNotBeNil)
		So(len(cl), ShouldEqual, 0)

		err := fs.UpdateExpectation(&ExpectationStatement{
			TestName:     "/third_party/test_name1",
			Expectations: []string{"PASS", "FAIL"},
		})
		So(err, ShouldBeNil)

		cl = fs.ToCL()
		So(cl, ShouldNotBeNil)
		So(len(cl), ShouldEqual, 1)

		So(cl["/some/path1"], ShouldEqual, strings.Join([]string{
			"/third_party/test_name1 [ PASS FAIL ]",
			"/third_party/test_name1b [ FAIL ]",
		}, "\n"))

		So(cl["/some/path2"], ShouldEqual, "")
	})

	Convey("Update basic, comments, multiple files and tests", t, func() {
		fs := &FileSet{
			Files: []*File{
				{
					Path: "/some/path1",
					Expectations: []*ExpectationStatement{
						{
							Original: "# a comment",
							Comment:  "# a comment",
						},
						{
							Original: "",
							Comment:  "",
						},
						{
							Original:     "/third_party/test_name1 [ PASS ]",
							TestName:     "/third_party/test_name1",
							Expectations: []string{"PASS"},
						},
						{
							Original:     "/third_party/test_name1b [ FAIL ]",
							TestName:     "/third_party/test_name1b",
							Expectations: []string{"FAIL"},
						},
					},
				},
				{
					Path: "/some/path2",
					Expectations: []*ExpectationStatement{
						{
							Original:     "/third_party/test_name2 [ PASS ]",
							TestName:     "/third_party/test_name2",
							Expectations: []string{"PASS"},
						},
					},
				},
			},
		}

		cl := fs.ToCL()
		So(cl, ShouldNotBeNil)
		So(len(cl), ShouldEqual, 0)

		err := fs.UpdateExpectation(&ExpectationStatement{
			TestName:     "/third_party/test_name1",
			Expectations: []string{"PASS", "FAIL"},
		})
		So(err, ShouldBeNil)

		cl = fs.ToCL()
		So(cl, ShouldNotBeNil)
		So(len(cl), ShouldEqual, 1)

		So(cl["/some/path1"], ShouldEqual, strings.Join([]string{
			"# a comment",
			"",
			"/third_party/test_name1 [ PASS FAIL ]",
			"/third_party/test_name1b [ FAIL ]",
		}, "\n"))

		So(cl["/some/path2"], ShouldEqual, "")
	})
}

type giMock struct {
	info.RawInterface
	token  string
	expiry time.Time
	err    error
}

func (gi giMock) AccessToken(scopes ...string) (token string, expiry time.Time, err error) {
	return gi.token, gi.expiry, gi.err
}

func TestLoadAll(t *testing.T) {
	c := gaetesting.TestingContext()
	c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
		return giMock{dummy.Info(), "", time.Now(), nil}
	})
	c = urlfetch.Set(c, &testhelper.MockGitilesTransport{
		Responses: map[string]string{
			"http://foo.bar": `unused`,
		},
	})

	Convey("load all, error", t, func() {
		all, err := LoadAll(c)
		So(all, ShouldBeNil)
		So(err, ShouldNotBeNil)
	})
}
