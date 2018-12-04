package handlers

import (
	"infra/appengine/rotang"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"

	"context"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func TestHandleShiftImport(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		calFail    bool
		rotaName   string
		user       string
		values     url.Values
		ctx        *router.Context
		cfg        *rotang.Configuration
		memberPool []rotang.Member
		shifts     []rotang.ShiftEntry
		want       []rotang.ShiftEntry
	}{{
		name:     "Context canceled",
		fail:     true,
		rotaName: "Test Rota",
		user:     "test@test.com",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
			},
		},
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name:     "List Success",
		rotaName: "Test Rota",
		user:     "test@test.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		values: url.Values{
			"name": {"Test Rota"},
		},
		memberPool: []rotang.Member{
			{
				Email: "test@test.com",
			},
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@test.com"},
				Shifts: rotang.ShiftConfig{
					Shifts: []rotang.Shift{
						{
							Name: "MTV All Day",
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					ShiftName: "MTV All Day",
					Email:     "test@test.com",
				},
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "test@test.com",
					},
				},
			},
		},
	}, {
		name:     "Store Success",
		rotaName: "Test Rota",
		user:     "test@test.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		values: url.Values{
			"name":  {"Test Rota"},
			"store": {"true"},
		},
		memberPool: []rotang.Member{
			{
				Email: "test@test.com",
			},
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@test.com"},
				Shifts: rotang.ShiftConfig{
					Shifts: []rotang.Shift{
						{
							Name: "MTV All Day",
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					ShiftName: "MTV All Day",
					Email:     "test@test.com",
				},
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(2 * 24 * time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "test@test.com",
					},
				},
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(2 * 24 * time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "test@test.com",
					},
				},
			},
		},
	}, {
		name:     "No rota name",
		rotaName: "Test Rota",
		fail:     true,
		user:     "test@test.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		values: url.Values{
			"store": {"true"},
		},
		memberPool: []rotang.Member{
			{
				Email: "test@test.com",
			},
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@test.com"},
				Shifts: rotang.ShiftConfig{
					Shifts: []rotang.Shift{
						{
							Name: "MTV All Day",
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					ShiftName: "MTV All Day",
					Email:     "test@test.com",
				},
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(2 * 24 * time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "test@test.com",
					},
				},
			},
		},
	}, {
		name:     "User not logged in",
		rotaName: "Test Rota",
		fail:     true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		values: url.Values{
			"name":  {"Test Rota"},
			"store": {"true"},
		},
		memberPool: []rotang.Member{
			{
				Email: "test@test.com",
			},
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@test.com"},
				Shifts: rotang.ShiftConfig{
					Shifts: []rotang.Shift{
						{
							Name: "MTV All Day",
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					ShiftName: "MTV All Day",
					Email:     "test@test.com",
				},
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(2 * 24 * time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "test@test.com",
					},
				},
			},
		},
	}, {
		name:     "Not owner",
		rotaName: "Test Rota",
		user:     "notOwner@test.com",
		fail:     true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		values: url.Values{
			"name": {"Test Rota"},
		},
		memberPool: []rotang.Member{
			{
				Email: "test@test.com",
			},
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@test.com", "test2@test.com"},
				Shifts: rotang.ShiftConfig{
					Shifts: []rotang.Shift{
						{
							Name: "MTV All Day",
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					ShiftName: "MTV All Day",
					Email:     "test@test.com",
				},
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "test@test.com",
					},
				},
			},
		},
	}, {
		name:     "Cal Fail",
		rotaName: "Test Rota",
		user:     "test@test.com",
		fail:     true,
		calFail:  true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		values: url.Values{
			"name": {"Test Rota"},
		},
		memberPool: []rotang.Member{
			{
				Email: "test@test.com",
			},
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@test.com", "test2@test.com"},
				Shifts: rotang.ShiftConfig{
					Shifts: []rotang.Shift{
						{
							Name: "MTV All Day",
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					ShiftName: "MTV All Day",
					Email:     "test@test.com",
				},
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "test@test.com",
					},
				},
			},
		},
	}, {
		name:     "Filter member",
		rotaName: "Test Rota",
		user:     "test@test.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		values: url.Values{
			"name":  {"Test Rota"},
			"store": {"true"},
		},
		memberPool: []rotang.Member{
			{
				Email: "test@test.com",
			},
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@test.com"},
				Shifts: rotang.ShiftConfig{
					Shifts: []rotang.Shift{
						{
							Name: "MTV All Day",
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					ShiftName: "MTV All Day",
					Email:     "test@test.com",
				},
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(2 * 24 * time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "test@test.com",
					},
				},
			},
			{
				Name:      "MTV All Day",
				StartTime: midnight.Add(2 * 24 * time.Hour),
				EndTime:   midnight.Add(4 * 24 * time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "test2@test.com",
					},
				},
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(2 * 24 * time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "test@test.com",
					},
				},
			}, {
				Name:      "MTV All Day",
				StartTime: midnight.Add(2 * 24 * time.Hour),
				EndTime:   midnight.Add(4 * 24 * time.Hour),
				OnCall:    []rotang.ShiftMember{},
			},
		},
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: CreateMember(_, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			if err := h.configStore(ctx).CreateRotaConfig(ctx, tst.cfg); err != nil {
				t.Fatalf("%s: CreateRotaConfig(_) failed: %v", tst.name, err)
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

			tst.ctx.Request = httptest.NewRequest("GET", "/importshifts", nil)
			tst.ctx.Request.Form = tst.values

			h.calendar.(*fakeCal).Set(tst.shifts, tst.calFail, false, 0)

			h.HandleShiftImportJSON(tst.ctx)
			defer h.shiftStore(ctx).DeleteAllShifts(ctx, tst.rotaName)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: HandleShiftImport(ctx) = %t want: %t, code: %v", tst.name, got, want, recorder)
			}
			if recorder.Code != http.StatusOK {
				return
			}
			shifts, err := h.shiftStore(ctx).AllShifts(ctx, tst.rotaName)
			if err != nil && status.Code(err) != codes.NotFound {
				t.Fatalf("%s: AllShifts(ctx, %q) failed: %v", tst.name, tst.rotaName, err)
			}
			if diff := pretty.Compare(tst.want, shifts); diff != "" {
				t.Fatalf("%s: HandleShiftImport(ctx) differ -want +got, %s", tst.name, diff)
			}
		})
	}

}
