package handlers

import (
	"infra/appengine/rotang"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"

	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"golang.org/x/net/context"
)

func TestHandleEnableDisable(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name string
		fail bool
		ctx  *router.Context
		rota string
		user string
		cfg  *rotang.Configuration
		want bool
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Request: httptest.NewRequest("POST", "/enabledisable", nil),
			Writer:  httptest.NewRecorder(),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
			},
		},
	}, {
		name: "Enable rotation",
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/enabledisable", nil),
			Writer:  httptest.NewRecorder(),
		},
		rota: "Test Rota",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@user.com"},
			},
		},
		user: "test@user.com",
		want: true,
	}, {
		name: "Disable rotation",
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/enabledisable", nil),
			Writer:  httptest.NewRecorder(),
		},
		rota: "Test Rota",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:    "Test Rota",
				Owners:  []string{"test@user.com"},
				Enabled: true,
			},
		},
		user: "test@user.com",
		want: false,
	}, {
		name: "Not POST",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("UPDATE", "/enabledisable", nil),
			Writer:  httptest.NewRecorder(),
		},
		rota: "Test Rota",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@user.com"},
			},
		},
		user: "test@user.com",
		want: true,
	}, {
		name: "No name",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/enabledisable", nil),
			Writer:  httptest.NewRecorder(),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@user.com"},
			},
		},
		user: "test@user.com",
		want: true,
	}, {
		name: "Rota not matching",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/enabledisable", nil),
			Writer:  httptest.NewRecorder(),
		},
		rota: "Test Rota",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Not Test Rota",
				Owners: []string{"test@user.com"},
			},
		},
		user: "test@user.com",
		want: true,
	}, {
		name: "Not owner",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/enabledisable", nil),
			Writer:  httptest.NewRecorder(),
		},
		rota: "Test Rota",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@user.com"},
			},
		},
		user: "not_test@user.com",
		want: true,
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			if err := h.configStore(ctx).CreateRotaConfig(ctx, tst.cfg); err != nil {
				t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
			}
			defer h.configStore(ctx).DeleteRotaConfig(ctx, tst.cfg.Config.Name)

			tst.ctx.Context = templates.Use(tst.ctx.Context, &templates.Bundle{
				Loader: templates.FileSystemLoader(templatesLocation),
			}, nil)

			if tst.user != "" {
				tst.ctx.Context = auth.WithState(tst.ctx.Context, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.user),
				})
			}

			tst.ctx.Request.Form = url.Values{
				"name": {tst.rota},
			}

			h.HandleEnableDisable(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: HandleEnableDisable(ctx) = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
			if recorder.Code != http.StatusOK {
				return
			}

			state, err := h.configStore(ctx).RotaEnabled(ctx, tst.rota)
			if err != nil {
				t.Fatalf("%s: RotaEnabled(ctx) failed: %v", tst.name, err)
			}
			if got, want := state, tst.want; got != want {
				t.Fatalf("%s: HandleEnableDisable(ctx) = %t want: %t", tst.name, got, want)
			}
		})
	}
}
