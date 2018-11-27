package handlers

import (
	"infra/appengine/rotang"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"

	"context"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

func TestHandleGenerate(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		user       string
		rota       string
		ctx        *router.Context
		cfg        *rotang.Configuration
		values     url.Values
		memberPool []rotang.Member
		shifts     []rotang.ShiftEntry
	}{{
		name: "Canceled context",
		fail: true,
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
			},
		},
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("POST", "/generate", nil),
		},
	}, {
		name: "Success",
		user: "test@testing.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("POST", "/generate", nil),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@testing.com"},
				Shifts: rotang.ShiftConfig{
					StartTime: midnight,
					Length:    1,
					Generator: "Fair",
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All Day",
							Duration: fullDay,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					ShiftName: "MTV All Day",
					Email:     "mtv1@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv2@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv3@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv4@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
			},
			{
				Email: "mtv2@oncall.com",
			},
			{
				Email: "mtv3@oncall.com",
			},
			{
				Email: "mtv4@oncall.com",
			},
		},
		values: url.Values{
			"rota":      {"Test Rota"},
			"nrShifts":  {"2"},
			"generator": {"Fair"},
			"startTime": {"2018-10-03"},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "mtv1@oncall.com",
					},
				},
			}, {
				Name:      "MTV All Day",
				StartTime: midnight.Add(fullDay),
				EndTime:   midnight.Add(2 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "mtv2@oncall.com",
					},
				},
			},
		},
	}, {
		name: "Rota not set",
		fail: true,
		user: "test@testing.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("POST", "/generate", nil),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@testing.com"},
				Shifts: rotang.ShiftConfig{
					StartTime: midnight,
					Length:    1,
					Generator: "Fair",
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All Day",
							Duration: fullDay,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					ShiftName: "MTV All Day",
					Email:     "mtv1@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv2@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv3@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv4@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
			},
			{
				Email: "mtv2@oncall.com",
			},
			{
				Email: "mtv3@oncall.com",
			},
			{
				Email: "mtv4@oncall.com",
			},
		},
		values: url.Values{
			"nrShifts":  {"2"},
			"generator": {"Fair"},
			"startTime": {"2018-10-03"},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "mtv1@oncall.com",
					},
				},
			}, {
				Name:      "MTV All Day",
				StartTime: midnight.Add(fullDay),
				EndTime:   midnight.Add(2 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "mtv2@oncall.com",
					},
				},
			},
		},
	}, {
		name: "Rota wrong",
		fail: true,
		user: "test@testing.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("POST", "/generate", nil),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@testing.com"},
				Shifts: rotang.ShiftConfig{
					StartTime: midnight,
					Length:    1,
					Generator: "Fair",
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All Day",
							Duration: fullDay,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					ShiftName: "MTV All Day",
					Email:     "mtv1@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv2@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv3@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv4@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
			},
			{
				Email: "mtv2@oncall.com",
			},
			{
				Email: "mtv3@oncall.com",
			},
			{
				Email: "mtv4@oncall.com",
			},
		},
		values: url.Values{
			"rota":      {"wrong"},
			"nrShifts":  {"2"},
			"generator": {"Fair"},
			"startTime": {"2018-10-03"},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "mtv1@oncall.com",
					},
				},
			}, {
				Name:      "MTV All Day",
				StartTime: midnight.Add(fullDay),
				EndTime:   midnight.Add(2 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "mtv2@oncall.com",
					},
				},
			},
		},
	}, {
		name: "Not owner",
		fail: true,
		user: "not-test@testing.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("POST", "/generate", nil),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@testing.com"},
				Shifts: rotang.ShiftConfig{
					StartTime: midnight,
					Length:    1,
					Generator: "Fair",
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All Day",
							Duration: fullDay,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					ShiftName: "MTV All Day",
					Email:     "mtv1@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv2@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv3@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv4@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
			},
			{
				Email: "mtv2@oncall.com",
			},
			{
				Email: "mtv3@oncall.com",
			},
			{
				Email: "mtv4@oncall.com",
			},
		},
		values: url.Values{
			"rota":      {"Test Rota"},
			"nrShifts":  {"2"},
			"generator": {"Fair"},
			"startTime": {"2018-10-03"},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "mtv1@oncall.com",
					},
				},
			}, {
				Name:      "MTV All Day",
				StartTime: midnight.Add(fullDay),
				EndTime:   midnight.Add(2 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "mtv2@oncall.com",
					},
				},
			},
		},
	}, {
		name: "No start time",
		user: "test@testing.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("POST", "/generate", nil),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@testing.com"},
				Shifts: rotang.ShiftConfig{
					StartTime: midnight,
					Length:    1,
					Generator: "Fair",
					Shifts: []rotang.Shift{
						{
							Name:     "MTV All Day",
							Duration: fullDay,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					ShiftName: "MTV All Day",
					Email:     "mtv1@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv2@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv3@oncall.com",
				},
				{
					ShiftName: "MTV All Day",
					Email:     "mtv4@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "mtv1@oncall.com",
			},
			{
				Email: "mtv2@oncall.com",
			},
			{
				Email: "mtv3@oncall.com",
			},
			{
				Email: "mtv4@oncall.com",
			},
		},
		values: url.Values{
			"rota":      {"Test Rota"},
			"nrShifts":  {"2"},
			"generator": {"Fair"},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "mtv1@oncall.com",
					},
				},
			}, {
				Name:      "MTV All Day",
				StartTime: midnight.Add(fullDay),
				EndTime:   midnight.Add(2 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "mtv2@oncall.com",
					},
				},
			},
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
			if err := h.shiftStore(ctx).AddShifts(ctx, tst.cfg.Config.Name, tst.shifts); err != nil {
				t.Fatalf("%s: AddShifts(ctx, %q, _) failed: %v", tst.name, tst.cfg.Config.Name, err)
			}
			defer h.shiftStore(ctx).DeleteAllShifts(ctx, tst.cfg.Config.Name)

			tst.ctx.Context = templates.Use(tst.ctx.Context, &templates.Bundle{
				Loader: templates.FileSystemLoader(templatesLocation),
			}, nil)
			if tst.user != "" {
				tst.ctx.Context = auth.WithState(tst.ctx.Context, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.user),
				})
			}

			tst.ctx.Request.Form = tst.values

			h.HandleGenerate(tst.ctx)
			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: HandleGenerate(ctx) = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
		})
	}
}
