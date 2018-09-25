package handlers

import (
	"infra/appengine/rotang"
	"infra/appengine/rotang/pkg/algo"
	"infra/appengine/rotang/pkg/calendar"
	"infra/appengine/rotang/pkg/datastore"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
)

const (
	weekDuration = 7 * fullDay
	fullDay      = 24 * time.Hour
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

	// Sort out the generators.
	gs := algo.New()
	gs.Register(algo.NewLegacy())
	gs.Register(algo.NewFair())
	gs.Register(algo.NewRandomGen())

	opts := Options{
		URL:         "http://localhost:8080",
		Generators:  gs,
		Calendar:    &calendar.Calendar{},
		MailSender:  &testableMail{},
		MailAddress: "admin@example.com",
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
	tests := []struct {
		name       string
		fail       bool
		cfg        *rotang.Configuration
		time       time.Time
		memberPool []rotang.Member
		shifts     []rotang.ShiftEntry
		want       []rotang.ShiftEntry
	}{{
		name: "Config not enabled",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:       "Test Rota",
				Enabled:    false,
				Expiration: 4,
			},
		},
	}, {
		name: "Non existing generator",
		fail: true,
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
			},
		},
	}, {
		name: "Success schedule shifts",
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
			},
		},
	}, {
		name: "Split shifts",
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
			},
		},
	},
	}

	// Sort out the generators.
	gs := algo.New()
	gs.Register(algo.NewLegacy())
	gs.Register(algo.NewFair())
	gs.Register(algo.NewRandomGen())

	opts := Options{
		URL:         "http://localhost:8080",
		Generators:  gs,
		Calendar:    &calendar.Calendar{},
		MailSender:  &testableMail{},
		MailAddress: "admin@example.com",
	}
	setupStoreHandlers(&opts, datastore.New)
	h, err := New(&opts)
	if err != nil {
		t.Fatalf("New failed: %v", err)
	}

	ctx := newTestContext()

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

			err := h.scheduleShifts(ctx, tst.cfg, midnight)
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
