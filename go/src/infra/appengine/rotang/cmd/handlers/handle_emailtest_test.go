package handlers

import (
	"context"
	"encoding/json"
	"infra/appengine/rotang"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"

	"github.com/kylelemons/godebug/pretty"

	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
)

func TestHandleEmailTestJSON(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		ctx        *router.Context
		rota       string
		cfg        *rotang.Configuration
		user       string
		memberPool []rotang.Member
		shifts     []rotang.ShiftEntry
		want       testEmail
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/testemail", nil),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test rotation",
			},
		},
	}, {
		name: "Dummy filled in",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/testemail", nil),
		},
		rota: "Test rotation",
		user: "test@user.com",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test rotation",
				Owners: []string{"test@user.com"},
				Email: rotang.Email{
					Subject: "Sheriff for {{.RotaName}} shift: {{.ShiftEntry.Name}}",
					Body:    "Hi {{.Member.Name}} friendly reminder; you're oncall for {{.RotaName}}",
				},
			},
		},
		want: testEmail{
			Subject: "Sheriff for Test rotation shift: Shift Dummy Entry",
			Body:    "Hi Dummy Member friendly reminder; you're oncall for Test rotation",
		},
	}, {
		name: "Success",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/testemail", nil),
		},
		rota: "Test rotation",
		user: "test@user.com",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test rotation",
				Owners: []string{"test@user.com"},
				Email: rotang.Email{
					Subject: "Sheriff for {{.RotaName}} shift: {{.ShiftEntry.Name}}",
					Body:    "Hi {{.Member.Name}} friendly reminder; you're oncall for {{.RotaName}} at {{.ShiftEntry.StartTime.In .Member.TZ}}",
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "test@user.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "test@user.com",
				TZ:    *mtvTime,
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "test@user.com",
					},
				},
			},
		},
		want: testEmail{
			Subject: "Sheriff for Test rotation shift: MTV All Day",
			Body:    "Hi Test Testson friendly reminder; you're oncall for Test rotation at 2006-04-01 16:00:00 -0800 PST",
		},
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: CreateMember(ctx, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			if err := h.configStore(ctx).CreateRotaConfig(ctx, tst.cfg); err != nil {
				t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
			}
			defer h.configStore(ctx).DeleteRotaConfig(ctx, tst.cfg.Config.Name)

			if tst.shifts != nil {
				if err := h.shiftStore(ctx).AddShifts(ctx, tst.cfg.Config.Name, tst.shifts); err != nil {
					t.Fatalf("%s: AddShifts(ctx, _) failed: %v", tst.name, err)
				}
			}

			if tst.user != "" {
				tst.ctx.Context = auth.WithState(tst.ctx.Context, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.user),
				})
			}

			tst.ctx.Request.Form = url.Values{
				"name": {tst.rota},
			}

			tst.ctx.Context = clock.Set(tst.ctx.Context, testclock.New(midnight))

			h.HandleEmailTestJSON(tst.ctx)
			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: HandleEnableDisable(ctx) = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
			if recorder.Code != http.StatusOK {
				return
			}

			var resEmail testEmail
			if err := json.NewDecoder(recorder.Body).Decode(&resEmail); err != nil {
				t.Fatalf("%s: Decode(_) failed: %v", tst.name, err)
			}

			if diff := pretty.Compare(tst.want, resEmail); diff != "" {
				t.Fatalf("%s: HandleEmailTestJSON differ -want +got,\n%s", tst.name, diff)
			}

		})
	}
}
