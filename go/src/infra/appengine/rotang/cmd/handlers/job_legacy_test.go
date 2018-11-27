package handlers

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"context"
	"go.chromium.org/luci/server/router"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type trooperFake struct {
	fail bool
	ret  string
}

func (f *trooperFake) troopers(ctx *router.Context, file string) (string, error) {
	if f.fail {
		return "", status.Errorf(codes.Internal, "test fail")
	}

	return f.ret, nil
}

func TestJobLegacy(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	var f trooperFake

	tests := []struct {
		name       string
		fail       bool
		fakeFail   bool
		fakeReturn string
		lm         map[string]func(*router.Context, string) (string, error)
		ctx        *router.Context
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Success",
		lm: map[string]func(*router.Context, string) (string, error){
			"trooper_file1": f.troopers,
			"trooper_file2": f.troopers,
			"trooper_file3": f.troopers,
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		fakeReturn: "primary, secondary1, secondary2",
	}, {
		name:     "Fake fail",
		fakeFail: true,
		lm: map[string]func(*router.Context, string) (string, error){
			"trooper_file1": f.troopers,
			"trooper_file2": f.troopers,
			"trooper_file3": f.troopers,
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		fakeReturn: "primary, secondary1, secondary2",
	}, {
		name: "Cache updated",
		lm: map[string]func(*router.Context, string) (string, error){
			"trooper_file1": f.troopers,
			"trooper_file2": f.troopers,
			"trooper_file3": f.troopers,
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		fakeReturn: "primary2, secondary3, secondary4",
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		f.fail = tst.fakeFail
		f.ret = tst.fakeReturn
		h.legacyMap = tst.lm
		h.JobLegacy(tst.ctx)

		recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
		if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
			t.Errorf("%s: JobLegacy(ctx) = %t want: %t, code: %v", tst.name, got, want, recorder.Code)
			continue
		}
	}
}
