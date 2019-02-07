package handler

import (
	"encoding/json"
	"infra/appengine/sheriff-o-matic/som/client"
	"infra/monorail"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"testing"

	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestBugQueue(t *testing.T) {
	Convey("/bugqueue", t, func() {
		c := gaetesting.TestingContext()
		c = authtest.MockAuthConfig(c)
		c = gologger.StdConfig.Use(c)

		cl := testclock.New(testclock.TestRecentTimeUTC)
		c = clock.Set(c, cl)

		w := httptest.NewRecorder()

		monorailMux := http.NewServeMux()
		monorailResponse := func(w http.ResponseWriter, r *http.Request) {
			logging.Errorf(c, "got monorailMux request")
			res := &monorail.IssuesListResponse{
				Items:        []*monorail.Issue{},
				TotalResults: 0,
			}
			bytes, err := json.Marshal(res)
			if err != nil {
				logging.Errorf(c, "error marshaling response: %v", err)
			}
			w.Write(bytes)
		}
		monorailMux.HandleFunc("/", monorailResponse)

		monorailServer := httptest.NewServer(monorailMux)
		defer monorailServer.Close()
		monorail := client.NewMonorail(c, monorailServer.URL)

		bqh := &BugQueueHandler{
			Monorail: monorail,
		}

		Convey("mock getBugsFromMonorail", func() {
			Convey("get bug queue handler", func() {
				bqh.GetBugQueueHandler(&router.Context{
					Context: c,
					Writer:  w,
					Request: makeGetRequest(),
				})

				b, err := ioutil.ReadAll(w.Body)
				So(err, ShouldBeNil)
				So(w.Code, ShouldEqual, 200)
				So(string(b), ShouldEqual, "{}")
			})

			Convey("refresh bug queue handler", func() {
				bqh.RefreshBugQueueHandler(&router.Context{
					Context: c,
					Writer:  w,
					Request: makeGetRequest(),
				})

				b, err := ioutil.ReadAll(w.Body)
				So(err, ShouldBeNil)
				So(w.Code, ShouldEqual, 200)
				So(string(b), ShouldEqual, "{}")
			})

			Convey("refresh bug queue", func() {
				// HACK:
				oldOAClient := getOAuthClient
				getOAuthClient = func(c context.Context) (*http.Client, error) {
					return &http.Client{}, nil
				}

				_, err := bqh.refreshBugQueue(c, "label")
				So(err, ShouldBeNil)
				getOAuthClient = oldOAClient
			})

			Convey("get uncached bugs", func() {
				bqh.GetUncachedBugsHandler(&router.Context{
					Context: c,
					Writer:  w,
					Request: makeGetRequest(),
					Params:  makeParams("label", "infra-troopers"),
				})

				b, err := ioutil.ReadAll(w.Body)
				So(err, ShouldBeNil)
				So(w.Code, ShouldEqual, 200)
				So(string(b), ShouldEqual, "{}")
			})

			Convey("get alternate email", func() {
				e := getAlternateEmail("test@chromium.org")
				So(e, ShouldEqual, "test@google.com")

				e = getAlternateEmail("test@google.com")
				So(e, ShouldEqual, "test@chromium.org")
			})
		})
	})
}
