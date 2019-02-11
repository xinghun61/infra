package handlers

import (
	"infra/appengine/rotang"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"context"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/luci/server/router"
)

const (
	weekDuration = 7 * fullDay
)

func TestJobSchedule(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		ctx        *router.Context
		cfgs       []*rotang.Configuration
		time       time.Time
		memberPool []rotang.Member
	}{{
		name: "Canceled context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "No configurations",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Success",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		cfgs: []*rotang.Configuration{
			{
				Config: rotang.Config{
					Name:             "Test Rota",
					Enabled:          true,
					Expiration:       2,
					ShiftsToSchedule: 2,
					Shifts: rotang.ShiftConfig{
						StartTime:    midnight,
						Length:       5,
						Skip:         2,
						Generator:    "Fair",
						ShiftMembers: 1,
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
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller1@oncall.com",
			},
			{
				Email: "oncaller2@oncall.com",
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
			for _, cfg := range tst.cfgs {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, cfg); err != nil {
					t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, cfg.Config.Name)
			}

			h.JobSchedule(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: JobSchedule(ctx) = %d want: %d", tst.name, recorder.Code, http.StatusOK)
			}
		})
	}

}

func TestScheduleShifts(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name       string
		fail       bool
		changeID   bool
		ctx        *router.Context
		cfg        *rotang.Configuration
		time       time.Time
		memberPool []rotang.Member
		shifts     []rotang.ShiftEntry
		want       []rotang.ShiftEntry
	}{{
		name: "Config not enabled",
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:       "Test Rota",
				Enabled:    false,
				Expiration: 4,
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
			}, {
				Name:      "MTV All Day",
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(12 * fullDay),
			}, {
				Name:      "MTV All Day",
				StartTime: midnight.Add(14 * fullDay),
				EndTime:   midnight.Add(19 * fullDay),
			},
		},
	}, {
		name: "Non existing generator",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Enabled:          true,
				Expiration:       2,
				ShiftsToSchedule: 2,
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					Length:       5,
					Skip:         2,
					Generator:    "NotExist",
					ShiftMembers: 1,
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
					Email:     "oncaller1@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller2@oncall.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller1@oncall.com",
			},
			{
				Email: "oncaller2@oncall.com",
			},
		},
	}, {
		name: "No shifts in config",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Enabled:          true,
				Expiration:       2,
				ShiftsToSchedule: 2,
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					Length:       5,
					Skip:         2,
					Generator:    "Fair",
					ShiftMembers: 1,
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "oncaller1@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller2@oncall.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller1@oncall.com",
			},
			{
				Email: "oncaller2@oncall.com",
			},
		},
	}, {
		name: "Shifts not expired",
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Enabled:          true,
				Expiration:       2,
				ShiftsToSchedule: 2,
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					Length:       5,
					Skip:         2,
					Generator:    "Fair",
					ShiftMembers: 1,
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
					Email:     "oncaller1@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller2@oncall.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller1@oncall.com",
			},
			{
				Email: "oncaller2@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(12 * fullDay),
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(14 * fullDay),
				EndTime:   midnight.Add(19 * fullDay),
			},
		},
	}, {
		name: "Don't consider already ended shifts",
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Enabled:          true,
				Expiration:       1,
				ShiftsToSchedule: 2,
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					Length:       5,
					Skip:         2,
					Generator:    "Fair",
					ShiftMembers: 1,
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
					Email:     "oncaller1@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller2@oncall.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller1@oncall.com",
			},
			{
				Email: "oncaller2@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(-weekDuration),
				EndTime:   midnight.Add(-weekDuration + 5*fullDay),
				EvtID:     "before 1",
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
				EvtID:     "before 2",
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(12 * fullDay),
				EvtID:     "0",
				Comment:   genComment,
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(14 * fullDay),
				EndTime:   midnight.Add(19 * fullDay),
				EvtID:     "1",
				Comment:   genComment,
			},
		},
	}, {
		name: "Success schedule shifts",
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Enabled:          true,
				Expiration:       2,
				ShiftsToSchedule: 2,
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					Length:       5,
					Skip:         2,
					Generator:    "Fair",
					ShiftMembers: 1,
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
					Email:     "oncaller1@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller2@oncall.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller1@oncall.com",
			},
			{
				Email: "oncaller2@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(12 * fullDay),
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(14 * fullDay),
				EndTime:   midnight.Add(19 * fullDay),
				EvtID:     "0",
				Comment:   genComment,
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(21 * fullDay),
				EndTime:   midnight.Add(26 * fullDay),
				EvtID:     "1",
				Comment:   genComment,
			},
		},
	}, {
		name: "With Modifier",
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Enabled:          true,
				Expiration:       2,
				ShiftsToSchedule: 2,
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					Length:       5,
					Skip:         2,
					Generator:    "Fair",
					Modifiers:    []string{"WeekendSkip"},
					ShiftMembers: 1,
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
					Email:     "oncaller1@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller2@oncall.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller1@oncall.com",
			},
			{
				Email: "oncaller2@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(12 * fullDay),
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(16 * fullDay),
				EndTime:   midnight.Add(21 * fullDay),
				EvtID:     "0",
				Comment:   genComment,
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(23 * fullDay),
				EndTime:   midnight.Add(28 * fullDay),
				EvtID:     "1",
				Comment:   genComment,
			},
		},
	}, {
		name: "Unknown Modifier",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Enabled:          true,
				Expiration:       2,
				ShiftsToSchedule: 2,
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					Length:       5,
					Skip:         2,
					Generator:    "Fair",
					Modifiers:    []string{"Unknown"},
					ShiftMembers: 1,
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
					Email:     "oncaller1@oncall.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "oncaller2@oncall.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller1@oncall.com",
			},
			{
				Email: "oncaller2@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(5 * fullDay),
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(12 * fullDay),
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller1@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(14 * fullDay),
				EndTime:   midnight.Add(19 * fullDay),
				EvtID:     "0",
				Comment:   genComment,
			}, {
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller2@oncall.com",
						ShiftName: "MTV All Day",
					},
				},
				StartTime: midnight.Add(21 * fullDay),
				EndTime:   midnight.Add(26 * fullDay),
				EvtID:     "1",
				Comment:   genComment,
			},
		},
	}, {
		name: "Split shifts",
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Enabled:          true,
				Expiration:       2,
				ShiftsToSchedule: 2,
				Shifts: rotang.ShiftConfig{
					StartTime:    midnight,
					Length:       5,
					Skip:         2,
					Generator:    "Fair",
					ShiftMembers: 1,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV Shift",
							Duration: 8 * time.Hour,
						}, {
							Name:     "SYD Shift",
							Duration: 8 * time.Hour,
						}, {
							Name:     "EU Shift",
							Duration: 8 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "mtv1@oncall.com",
					ShiftName: "MTV Shift",
				}, {
					Email:     "mtv2@oncall.com",
					ShiftName: "MTV Shift",
				},
				{
					Email:     "syd1@oncall.com",
					ShiftName: "SYD Shift",
				}, {
					Email:     "syd2@oncall.com",
					ShiftName: "SYD Shift",
				},
				{
					Email:     "eu1@oncall.com",
					ShiftName: "EU Shift",
				}, {
					Email:     "eu2@oncall.com",
					ShiftName: "EU Shift",
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
				Email: "syd1@oncall.com",
			},
			{
				Email: "syd2@oncall.com",
			},
			{
				Email: "eu1@oncall.com",
			},
			{
				Email: "eu2@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(4*fullDay + 8*time.Hour),
			}, {
				Name: "SYD Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd1@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(4*fullDay + 16*time.Hour),
			}, {
				Name: "EU Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu1@oncall.com",
						ShiftName: "EU Shift",
					},
				},
				StartTime: midnight.Add(16 * time.Hour),
				EndTime:   midnight.Add(5 * fullDay),
			},
			{
				Name: "MTV Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
				StartTime: midnight.Add(7 * fullDay),
				EndTime:   midnight.Add(4*fullDay + 8*time.Hour + weekDuration),
			}, {
				Name: "SYD Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd2@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
				StartTime: midnight.Add(8*time.Hour + weekDuration),
				EndTime:   midnight.Add(4*fullDay + 16*time.Hour + weekDuration),
			}, {
				Name: "EU Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu2@oncall.com",
						ShiftName: "EU Shift",
					},
				},
				StartTime: midnight.Add(16*time.Hour + weekDuration),
				EndTime:   midnight.Add(5*fullDay + weekDuration),
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name: "MTV Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv1@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
				StartTime: midnight.Add(2 * weekDuration),
				EndTime:   midnight.Add(4*fullDay + 8*time.Hour + 2*weekDuration),
				EvtID:     "0",
				Comment:   genComment,
			}, {
				Name: "SYD Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd1@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
				StartTime: midnight.Add(8*time.Hour + 2*weekDuration),
				EndTime:   midnight.Add(4*fullDay + 16*time.Hour + 2*weekDuration),
				EvtID:     "1",
				Comment:   genComment,
			}, {
				Name: "EU Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu1@oncall.com",
						ShiftName: "EU Shift",
					},
				},
				StartTime: midnight.Add(16*time.Hour + 2*weekDuration),
				EndTime:   midnight.Add(5*fullDay + 2*weekDuration),
				EvtID:     "2",
				Comment:   genComment,
			},
			{
				Name: "MTV Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "mtv2@oncall.com",
						ShiftName: "MTV Shift",
					},
				},
				StartTime: midnight.Add(3 * weekDuration),
				EndTime:   midnight.Add(4*fullDay + 8*time.Hour + 3*weekDuration),
				EvtID:     "3",
				Comment:   genComment,
			}, {
				Name: "SYD Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "syd2@oncall.com",
						ShiftName: "SYD Shift",
					},
				},
				StartTime: midnight.Add(8*time.Hour + 3*weekDuration),
				EndTime:   midnight.Add(4*fullDay + 16*time.Hour + 3*weekDuration),
				EvtID:     "4",
				Comment:   genComment,
			}, {
				Name: "EU Shift",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "eu2@oncall.com",
						ShiftName: "EU Shift",
					},
				},
				StartTime: midnight.Add(16*time.Hour + 3*weekDuration),
				EndTime:   midnight.Add(5*fullDay + 3*weekDuration),
				EvtID:     "5",
				Comment:   genComment,
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
				t.Fatalf("%s: AddShifts(ctx, _) failed: %v", tst.name, err)
			}
			defer h.shiftStore(ctx).DeleteAllShifts(ctx, tst.cfg.Config.Name)

			h.calendar.(*fakeCal).Set(nil, false, false, 0)
			err := h.scheduleShifts(tst.ctx, tst.cfg, midnight)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: scheduleShifts(ctx, _, %v) = %t want: %t, err: %v", tst.name, midnight, got, want, err)
			}
			if err != nil {
				return
			}

			got, err := h.shiftStore(ctx).AllShifts(ctx, tst.cfg.Config.Name)
			if err != nil {
				t.Fatalf("%s: AllShifts(ctx, %q) failed: %v", tst.name, tst.cfg.Config.Name, err)
			}

			if diff := pretty.Compare(append(tst.shifts, tst.want...), got); diff != "" {
				t.Fatalf("%s: scheduleShifts(ctx, _, %v) differ -want +got, %s", tst.name, midnight, diff)
			}
		})
	}
}
