package testexpectations

import (
	"strings"
	"testing"
	"time"

	"golang.org/x/net/context"

	testhelper "infra/appengine/sheriff-o-matic/som/client/test"

	"go.chromium.org/gae/impl/dummy"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/gae/service/urlfetch"
	"go.chromium.org/luci/appengine/gaetesting"

	. "github.com/smartystreets/goconvey/convey"
)

func TestUpdateExpectations(t *testing.T) {
	Convey("Update with empty expectation returns error", t, func() {
		fs := &FileSet{
			Files: []*File{
				{
					Path:         "/some/path",
					Expectations: []*ExpectationStatement{},
				},
			},
		}

		err := fs.UpdateExpectation(&ExpectationStatement{})
		So(err, ShouldNotBeNil)
	})

	Convey("Update basic, single file, existing test", t, func() {
		fs := &FileSet{
			Files: []*File{
				{
					Path: "/some/path",
					Expectations: []*ExpectationStatement{
						{
							TestName:     "/third_party/test_name",
							Expectations: []string{"PASS"},
							Dirty:        true,
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

	Convey("Update basic, single file, new test", t, func() {
		fs := &FileSet{
			Files: []*File{
				{
					Path: defaultExpectationsFile,
					Expectations: []*ExpectationStatement{
						{
							TestName:     "/third_party/test_name",
							Expectations: []string{"PASS"},
							Original:     "/third_party/test_name [ PASS ]",
						},
					},
				},
			},
		}

		cl := fs.ToCL()
		So(cl, ShouldNotBeNil)
		So(len(cl), ShouldEqual, 0)

		err := fs.UpdateExpectation(&ExpectationStatement{
			TestName:     "/third_party/new_test_name",
			Expectations: []string{"PASS", "FAIL"},
			Dirty:        true,
		})
		So(err, ShouldBeNil)

		cl = fs.ToCL()
		So(cl, ShouldNotBeNil)
		So(len(cl), ShouldEqual, 1)
		So(cl[defaultExpectationsFile], ShouldEqual, "/third_party/test_name [ PASS ]\n/third_party/new_test_name [ PASS FAIL ]")
	})

	Convey("Update basic, multiple files, new test", t, func() {
		fs := &FileSet{
			Files: []*File{
				{
					Path: "/some/path",
					Expectations: []*ExpectationStatement{
						{
							TestName:     "/third_party/test_name",
							Expectations: []string{"PASS"},
							Original:     "/third_party/test_name [ PASS ]",
						},
					},
				},
				{
					Path:         defaultExpectationsFile,
					Expectations: []*ExpectationStatement{},
				},
			},
		}

		cl := fs.ToCL()
		So(cl, ShouldNotBeNil)
		So(len(cl), ShouldEqual, 0)

		err := fs.UpdateExpectation(&ExpectationStatement{
			TestName:     "/third_party/new_test_name",
			Expectations: []string{"PASS", "FAIL"},
			Dirty:        true,
		})
		So(err, ShouldBeNil)

		cl = fs.ToCL()
		So(cl, ShouldNotBeNil)
		So(len(cl), ShouldEqual, 1)

		So(cl[defaultExpectationsFile], ShouldEqual, "/third_party/new_test_name [ PASS FAIL ]")
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

func TestExpectationStatement(t *testing.T) {
	Convey("modifiers", t, func() {
		Convey("expanded match", func() {
			es := &ExpectationStatement{
				Original:     "[ Mac ] /third_party/test_dir/foo_bar/baz.html [ FAIL ]",
				TestName:     "/third_party/test_dir/foo_bar/baz.html",
				Expectations: []string{"FAIL"},
				Modifiers:    []string{"Mac"},
			}

			So(es.ExpandModifiers(), ShouldResemble, []string{"Mac", "retina", "mac10.9", "mac10.11", "mac10.12"})
			So(es.ModifierMatch("Mac10.9"), ShouldEqual, true)
		})

		Convey("applies", func() {
			Convey("narrow specifiers", func() {
				es := &ExpectationStatement{
					Original:     "[ Mac ] /third_party/test_dir/foo_bar/baz.html [ FAIL ]",
					TestName:     "/third_party/test_dir/foo_bar/baz.html",
					Expectations: []string{"FAIL"},
					Modifiers:    []string{"Mac"},
				}

				So(es.Applies("/third_party/test_dir/foo_bar/baz.html", "Mac"), ShouldEqual, true)
			})
		})
	})
}

func TestForTest(t *testing.T) {
	Convey("basic", t, func() {
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
				{
					Path: "/some/path3",
					Expectations: []*ExpectationStatement{
						{
							Original:     "/third_party/test_dir/foo_bar [ PASS ]",
							TestName:     "/third_party/test_dir/foo_bar",
							Expectations: []string{"PASS"},
						},
					},
				},
				{
					Path: "/some/path3",
					Expectations: []*ExpectationStatement{
						{
							Original:     "[ Mac ] /third_party/test_dir/foo_bar/baz.html [ FAIL ]",
							TestName:     "/third_party/test_dir/foo_bar/baz.html",
							Expectations: []string{"FAIL"},
							Modifiers:    []string{"Mac"},
						},
					},
				},
				{
					Path: "/some/path3",
					Expectations: []*ExpectationStatement{
						{
							Original:     "[ Mac10.12 ] /third_party/test_dir/zippy.html [ FAIL ]",
							TestName:     "/third_party/test_dir/zippy.html",
							Expectations: []string{"FAIL"},
							Modifiers:    []string{"Mac10.12"},
						},
					},
				},
			},
		}

		Convey("no matches", func() {
			matches := fs.ForTest("foo", &BuilderConfig{})
			So(len(matches), ShouldEqual, 0)
		})

		Convey("one match", func() {
			matches := fs.ForTest("/third_party/test_name2", &BuilderConfig{})
			So(len(matches), ShouldEqual, 1)
		})

		Convey("multiple matches", func() {
			matches := fs.ForTest("/third_party/test_dir/foo_bar/zippy.html", &BuilderConfig{})
			So(len(matches), ShouldEqual, 1)
			So(matches[0].Original, ShouldEqual, "/third_party/test_dir/foo_bar [ PASS ]")
		})

		Convey("modifier expansion", func() {
			matches := fs.ForTest("/third_party/test_dir/foo_bar/baz.html", &BuilderConfig{Specifiers: []string{"Mac10.11"}})
			Printf("matches: %v", matches)
			So(len(matches), ShouldEqual, 2)
			// Eventually should only return 1 result. For now, most specific first.
			So(matches[0].Original, ShouldEqual, "[ Mac ] /third_party/test_dir/foo_bar/baz.html [ FAIL ]")
			So(matches[1].Original, ShouldEqual, "/third_party/test_dir/foo_bar [ PASS ]")

			// The first (and eventually, only) ExpectationStatement should override the rest.
			So(matches[0].Overrides(matches[1]), ShouldBeTrue)
		})

		Convey("rule has similar modifier, but doesn't apply", func() {
			matches := fs.ForTest("/third_party/test_dir/zippy.html", &BuilderConfig{Specifiers: []string{"Mac10.11", "Release"}})
			So(len(matches), ShouldEqual, 0)
			matches = fs.ForTest("/third_party/test_dir/zippy.html", &BuilderConfig{Specifiers: []string{"Mac10.12"}})
			So(len(matches), ShouldEqual, 1)
		})
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
