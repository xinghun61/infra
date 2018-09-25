package handlers

import (
	"infra/appengine/rotang"
	"infra/appengine/rotang/pkg/algo"
	"infra/appengine/rotang/pkg/calendar"
	"infra/appengine/rotang/pkg/datastore"
	"net/http"
	"net/http/httptest"
	"testing"

	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"golang.org/x/net/context"
)

func TestHandleManageRota(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		ctx        *router.Context
		cfg        []rotang.Configuration
		memberPool []rotang.Member
		user       string
	}{{
		name: "Context canceled",
		fail: true,
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/", ""),
		},
	}, {
		name: "Rotation success",
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/", ""),
		},
		memberPool: []rotang.Member{
			{
				Email: "test@user.com",
			}, {
				Email: "another@user.com",
			},
		},
		cfg: []rotang.Configuration{
			{
				Config: rotang.Config{
					Name:   "Rota one",
					Owners: []string{"test@user.com"},
				},
			}, {
				Config: rotang.Config{
					Name:   "Rota Two",
					Owners: []string{"test@user.com"},
				},
			},
		},
	}, {
		name: "Not logged in",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/", ""),
		},
		memberPool: []rotang.Member{
			{
				Email: "test@user.com",
			}, {
				Email: "another@user.com",
			},
		},
		cfg: []rotang.Configuration{
			{
				Config: rotang.Config{
					Name:   "Rota one",
					Owners: []string{"test@user.com"},
				},
			}, {
				Config: rotang.Config{
					Name:   "Rota Two",
					Owners: []string{"test@user.com"},
				},
			},
		},
	}, {
		name: "No rotations",
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/", ""),
		},
		memberPool: []rotang.Member{
			{
				Email: "test@user.com",
			}, {
				Email: "another@user.com",
			},
		},
	},
	}

	opts := Options{
		URL:        "http://localhost:8080",
		Generators: &algo.Generators{},
		Calendar:   &calendar.Calendar{},
	}
	setupStoreHandlers(&opts, datastore.New)
	h, err := New(&opts)
	if err != nil {
		t.Fatalf("New failed: %v", err)
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: CreateMember(ctx, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			for _, c := range tst.cfg {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, &c); err != nil {
					t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, c.Config.Name)
			}
			tst.ctx.Context = templates.Use(tst.ctx.Context, &templates.Bundle{
				Loader: templates.FileSystemLoader(templatesLocation),
			}, nil)
			if tst.user != "" {
				tst.ctx.Context = auth.WithState(tst.ctx.Context, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.user),
				})
			}

			h.HandleManageRota(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: HandleManageRota(ctx) = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
		})
	}
}
