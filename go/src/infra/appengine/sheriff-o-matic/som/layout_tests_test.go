package som

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"golang.org/x/net/context"

	te "infra/libs/testexpectations"
	testhelper "infra/monitoring/client/test"

	"github.com/luci/gae/impl/dummy"
	"github.com/luci/gae/service/info"
	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/appengine/gaetesting"
	"github.com/luci/luci-go/server/router"

	. "github.com/smartystreets/goconvey/convey"
)

const (
	gitilesPrefix = "https://chromium.googlesource.com/chromium/src/+/master/"
)

func TestGetLayoutTestsHandler(t *testing.T) {
	Convey("get layout tests", t, func() {
		c := gaetesting.TestingContext()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", time.Now(), nil}
		})
		gt := &testhelper.MockGitilesTransport{Responses: map[string]string{}}
		c = urlfetch.Set(c, gt)
		w := httptest.NewRecorder()

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
		}

		Convey("load all, error", func() {
			getLayoutTestsHandler(ctx)

			So(w.Code, ShouldEqual, http.StatusInternalServerError)
		})

		Convey("load all, no error", func() {
			for _, path := range te.LayoutTestExpectations {
				gt.Responses[gitilesPrefix+path+"?format=TEXT"] = `unused`
			}
			getLayoutTestsHandler(ctx)

			So(w.Code, ShouldEqual, http.StatusOK)
		})
	})
}
