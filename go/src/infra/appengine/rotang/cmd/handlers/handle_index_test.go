package handlers

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

func TestHandleIndex(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name string
		fail bool
		ctx  *router.Context
	}{{
		name: "Failed context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/"),
		},
	},
		{
			name: "Index Success",
			ctx: &router.Context{
				Context: ctx,
				Writer:  httptest.NewRecorder(),
				Request: getRequest("/"),
			},
		},
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			tst.ctx.Context = templates.Use(tst.ctx.Context, &templates.Bundle{
				Loader: templates.FileSystemLoader(templatesLocation),
			}, nil)

			HandleIndex(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: HandleIndex() = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
		})
	}
}
