package som

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	"infra/monitoring/client"
	testhelper "infra/monitoring/client/test"
	"infra/monitoring/messages"

	"github.com/luci/gae/impl/dummy"
	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/appengine/gaetesting"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/server/router"

	. "github.com/smartystreets/goconvey/convey"
)

func TestLogDiffHandler(t *testing.T) {
	Convey("ok request", t, func() {
		c := gaetesting.TestingContext()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", clock.Now(c), nil}
		})
		c = client.WithReader(c, testhelper.MockReader{
			BuildExtracts: map[string]*messages.BuildExtract{
				"chromium": {},
			},
		})
		w := httptest.NewRecorder()
		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
			Params:  makeParams("tree", "chromium"),
		}
		LogDiffHandler(ctx)
		So(w.Code, ShouldEqual, http.StatusOK)
	})
}
