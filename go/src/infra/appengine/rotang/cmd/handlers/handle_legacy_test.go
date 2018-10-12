package handlers

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/julienschmidt/httprouter"
	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
)

func TestHandleLegacy(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	var f trooperFake

	tests := []struct {
		name       string
		fail       bool
		ctx        *router.Context
		lm         map[string]func(*router.Context, string) (string, error)
		fakeFail   bool
		fakeReturn string
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Success",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Params: httprouter.Params{
				{
					Key:   "name",
					Value: "trooper.js",
				},
			},
		},
		lm: map[string]func(*router.Context, string) (string, error){
			"trooper.js": f.troopers,
		},
	}, {
		name: "Name not in the map",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Params: httprouter.Params{
				{
					Key:   "name",
					Value: "trooper.js",
				},
			},
		},
		lm: map[string]func(*router.Context, string) (string, error){
			"not_trooper.js": f.troopers,
		},
	}, {
		name:     "Func fail",
		fail:     true,
		fakeFail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Params: httprouter.Params{
				{
					Key:   "name",
					Value: "trooper.js",
				},
			},
		},
		lm: map[string]func(*router.Context, string) (string, error){
			"trooper.js": f.troopers,
		},
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		f.fail = tst.fakeFail
		f.ret = tst.fakeReturn
		h.legacyMap = tst.lm

		h.HandleLegacy(tst.ctx)

		recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
		if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
			t.Errorf("%s: HandleLegacy(ctx) = %t want: %t, code: %v", tst.name, got, want, recorder.Code)
			continue
		}
	}

}

func TestLegacyTroopers(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name       string
		fail       bool
		calFail    bool
		ctx        *router.Context
		file       string
		oncallers  []string
		updateTime time.Time
		want       string
	}{{
		name: "Success JS",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/legacy", nil),
		},
		file:       "trooper.js",
		oncallers:  []string{"primary1", "secondary1", "secondary2"},
		updateTime: midnight,
		want:       "document.Write('primary1, secondary: secondary1, secondary2');",
	}, {
		name: "Success JSON",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/legacy", nil),
		},
		file:       "current_trooper.json",
		oncallers:  []string{"primary1", "secondary1", "secondary2"},
		updateTime: midnight,
		want: `{"primary":"primary1","secondary":["secondary1","secondary2"],"updated_unix_timestamp":1143936000}
`,
	}, {
		name: "Success txt",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/legacy", nil),
		},
		file:       "current_trooper.txt",
		oncallers:  []string{"primary1", "secondary1", "secondary2"},
		updateTime: midnight,
		want:       "primary1,secondary1,secondary2",
	}, {
		name:    "Calendar fail",
		fail:    true,
		calFail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/legacy", nil),
		},
		file:       "current_trooper.txt",
		oncallers:  []string{"primary1", "secondary1", "secondary2"},
		updateTime: midnight,
	}, {
		name: "Unknown file",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/legacy", nil),
		},
		file:       "unknown_trooper.txt",
		oncallers:  []string{"primary1", "secondary1", "secondary2"},
		updateTime: midnight,
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		h.legacyCalendar.(*fakeCal).SetTroopers(tst.oncallers, tst.calFail)

		tst.ctx.Context = clock.Set(tst.ctx.Context, testclock.New(tst.updateTime))

		resStr, err := h.legacyTrooper(tst.ctx, tst.file)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: legacyTrooper(ctx) = %t want: %t, err: %v", tst.name, got, want, err)
			continue
		}
		if err != nil {
			continue
		}

		if diff := pretty.Compare(tst.want, resStr); diff != "" {
			t.Errorf("%s: legacyTrooper(ctx) differ -want +got,\n%s", tst.name, diff)
		}
	}

}
