package handlers

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
)

func TestJobBackup(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name    string
		ctx     *router.Context
		fail    bool
		handler http.Handler
	}{{
		name: "Canceled context",
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
			Request: getRequest("/cron/backup"),
		},
		handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		}),
	}, {
		name: "Backup fail",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/cron/backup"),
		},
		handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			http.Error(w, "Test fail", http.StatusInternalServerError)
		}),
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		tstSrv := httptest.NewServer(tst.handler)
		defer tstSrv.Close()
		baseURL = tstSrv.URL

		h.JobBackup(tst.ctx)

		recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
		if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
			t.Errorf("%s: JobBackup() = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			continue
		}
	}
}
