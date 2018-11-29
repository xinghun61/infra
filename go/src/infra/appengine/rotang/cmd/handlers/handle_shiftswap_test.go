package handlers

import (
	"context"
	"infra/appengine/rotang"
	"net/http"
	"net/http/httptest"
	"testing"

	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
)

func TestHandleShiftSwap(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name       string
		fail       bool
		ctx        *router.Context
		email      string
		memberPool []rotang.Member
		cfg        *rotang.Configuration
		shifts     []rotang.ShiftEntry
	}{{
		name: "Setup fail",
		fail: true,
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
			},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("UPDATE", "/shiftswap", nil),
		},
	}, {
		name:  "Not a rotation member",
		fail:  true,
		email: "test@member.com",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
			},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("POST", "/shiftswap", buildBody(t, &RotaShifts{
				Rota: "Test Rota",
			})),
		},
	}, {
		name:  "Success",
		email: "test@member.com",
		memberPool: []rotang.Member{
			{
				Name:  "Test User",
				Email: "test@member.com",
			},
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
			},
			Members: []rotang.ShiftMember{
				{
					Email: "test@member.com",
				},
			},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("POST", "/shiftswap", buildBody(t, &RotaShifts{
				Rota: "Test Rota",
			})),
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
				t.Fatalf("%s: DeleteRotaConfig(ctx, _) failed: %v", tst.name, err)
			}
			defer h.shiftStore(ctx).DeleteAllShifts(ctx, tst.cfg.Config.Name)

			if tst.email != "" {
				tst.ctx.Context = auth.WithState(tst.ctx.Context, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.email),
				})
			}

			h.HandleShiftSwap(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: swapSetup(ctx) = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
			if recorder.Code != http.StatusOK {
				return
			}

		})
	}
}

func TestSwapSetup(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name string
		fail bool
		ctx  *router.Context
		cfg  *rotang.Configuration
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
			Request: httptest.NewRequest("POST", "/shiftswap", nil),
		},
	}, {
		name: "Unsupported method",
		fail: true,
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
			},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("UPDATE", "/shiftswap", nil),
		},
	}, {
		name: "Success",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
			},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("POST", "/shiftswap", buildBody(t, &RotaShifts{
				Rota: "Test Rota",
			})),
		},
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			if err := h.configStore(ctx).CreateRotaConfig(ctx, tst.cfg); err != nil {
				t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
			}
			defer h.configStore(ctx).DeleteRotaConfig(ctx, tst.cfg.Config.Name)

			_, _, err := h.swapSetup(tst.ctx)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: swapSetup(ctx) = %t want: %t, err: %v", tst.name, got, want, err)
			}
			if err != nil {
				return
			}

		})
	}
}

func TestShiftChanges(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name       string
		fail       bool
		cfg        *rotang.Configuration
		ss         *RotaShifts
		usr        *rotang.ShiftMember
		shifts     []rotang.ShiftEntry
		memberPool []rotang.Member
	}{{
		name: "Invalid Args",
		fail: true,
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
			},
		},
	}, {
		name: "No change",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
				Shifts: rotang.ShiftConfig{
					Shifts: []rotang.Shift{
						{
							Name:     "Test All Day",
							Duration: fullDay,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "test@member.com",
					ShiftName: "Test All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test User",
				Email: "test@member.com",
			},
		},
		ss: &RotaShifts{
			Rota: "Test Rota",
			SplitShifts: []SplitShifts{
				{
					Name:    "Test All Day",
					Members: []string{"test@member.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name: "Test All Day",
							OnCall: []rotang.ShiftMember{
								{
									Email:     "test@member.com",
									ShiftName: "Test All Day",
								},
							},
							StartTime: midnight,
							EndTime:   midnight.Add(fullDay),
						},
					},
				},
			},
		},
		usr: &rotang.ShiftMember{
			Email:     "test@member.com",
			ShiftName: "Test All Day",
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "Test All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "test@member.com",
						ShiftName: "Test All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay),
			},
		},
	}, {
		name: "Changed shift",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
				Shifts: rotang.ShiftConfig{
					Shifts: []rotang.Shift{
						{
							Name:     "Test All Day",
							Duration: fullDay,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "test@member.com",
					ShiftName: "Test All Day",
				}, {
					Email:     "test2@member.com",
					ShiftName: "Test All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test User",
				Email: "test@member.com",
			}, {
				Name:  "Second Test User",
				Email: "test2@member.com",
			},
		},
		ss: &RotaShifts{
			Rota: "Test Rota",
			SplitShifts: []SplitShifts{
				{
					Name:    "Test All Day",
					Members: []string{"test@member.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name: "Test All Day",
							OnCall: []rotang.ShiftMember{
								{
									Email:     "test@member.com",
									ShiftName: "Test All Day",
								},
							},
							StartTime: midnight,
							EndTime:   midnight.Add(fullDay),
							Comment:   "Yep yep",
						},
					},
				},
			},
		},
		usr: &rotang.ShiftMember{
			Email:     "test@member.com",
			ShiftName: "Test All Day",
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "Test All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "test2@member.com",
						ShiftName: "Test All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay),
			},
		},
	}, {
		name: "Missing comment",
		fail: true,
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
				Shifts: rotang.ShiftConfig{
					Shifts: []rotang.Shift{
						{
							Name:     "Test All Day",
							Duration: fullDay,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "test@member.com",
					ShiftName: "Test All Day",
				}, {
					Email:     "test2@member.com",
					ShiftName: "Test All Day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test User",
				Email: "test@member.com",
			}, {
				Name:  "Second Test User",
				Email: "test2@member.com",
			},
		},
		ss: &RotaShifts{
			Rota: "Test Rota",
			SplitShifts: []SplitShifts{
				{
					Name:    "Test All Day",
					Members: []string{"test@member.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name: "Test All Day",
							OnCall: []rotang.ShiftMember{
								{
									Email:     "test@member.com",
									ShiftName: "Test All Day",
								},
							},
							StartTime: midnight,
							EndTime:   midnight.Add(fullDay),
						},
					},
				},
			},
		},
		usr: &rotang.ShiftMember{
			Email:     "test@member.com",
			ShiftName: "Test All Day",
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "Test All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "test2@member.com",
						ShiftName: "Test All Day",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay),
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

			err := h.shiftChanges(&router.Context{
				Context: ctx,
				Request: httptest.NewRequest("GET", "/cron/email", nil),
			}, tst.cfg, tst.ss, tst.usr)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: shiftChanges(ctx, _, _, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
			if err != nil {
				return
			}
		})
	}
}

func TestShiftUserDiff(t *testing.T) {
	tests := []struct {
		name     string
		want     bool
		original *rotang.ShiftEntry
		update   *rotang.ShiftEntry
		user     rotang.ShiftMember
	}{{
		name: "Success update",
		want: true,
		original: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "toBeChanged@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		update: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			Comment:   "Swapping shifts",
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		user: rotang.ShiftMember{
			Email:     "test@test.com",
			ShiftName: "MTV All Day",
		},
	}, {
		name: "No change",
		want: false,
		original: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "toBeChanged@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		update: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "toBeChanged@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		user: rotang.ShiftMember{
			Email:     "test@test.com",
			ShiftName: "MTV All Day",
		},
	}, {
		name: "Member added",
		want: true,
		original: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		update: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		user: rotang.ShiftMember{
			Email:     "test@test.com",
			ShiftName: "MTV All Day",
		},
	}, {
		name: "Member deleted",
		want: true,
		original: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		update: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		user: rotang.ShiftMember{
			Email:     "test@test.com",
			ShiftName: "MTV All Day",
		},
	}, {
		name: "Member added twice",
		want: false,
		original: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		update: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		user: rotang.ShiftMember{
			Email:     "test@test.com",
			ShiftName: "MTV All Day",
		},
	}, {
		name: "Added member not matching",
		want: false,
		original: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		update: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test@test.com",
					ShiftName: "Shift not matching",
				},
			},
		},
		user: rotang.ShiftMember{
			Email:     "test@test.com",
			ShiftName: "MTV All Day",
		},
	}, {
		name: "Added member changed entry",
		want: false,
		original: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "willBeChanged@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		update: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "wasChanged@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		user: rotang.ShiftMember{
			Email:     "test@test.com",
			ShiftName: "MTV All Day",
		},
	}, {
		name: "Multiple entries deleted",
		want: false,
		original: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		update: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "test@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		user: rotang.ShiftMember{
			Email:     "test@test.com",
			ShiftName: "MTV All Day",
		},
	}, {
		name: "Multiple user entries",
		want: false,
		original: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		update: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			Comment:   "Swapping shifts",
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		user: rotang.ShiftMember{
			Email:     "test@test.com",
			ShiftName: "MTV All Day",
		},
	}, {
		name: "Order changed",
		want: false,
		original: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		update: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight,
			EndTime:   midnight.Add(5 * fullDay),
			Comment:   "Swapping shifts",
			OnCall: []rotang.ShiftMember{
				{
					Email:     "notChanged2@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "notChanged1@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		user: rotang.ShiftMember{
			Email:     "test@test.com",
			ShiftName: "MTV All Day",
		},
	},
	}

	for _, tst := range tests {
		if got, want := shiftUserDiff(tst.original, tst.update, tst.user), tst.want; got != want {
			t.Errorf("%s: shiftUserDiff(_, _, _, _) = %t want: %t, original: %v, update: %v", tst.name, got, want, tst.original, tst.update)
		}
	}
}
