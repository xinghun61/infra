package handlers

import (
	"bytes"
	"encoding/json"
	"infra/appengine/rotang"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"golang.org/x/net/context"
)

func TestHandleShifts(t *testing.T) {
	type testStruct struct {
		History []SplitShifts
		Current []SplitShifts
	}
	tests := []struct {
		name    string
		time    time.Time
		cfg     *rotang.Configuration
		members []rotang.ShiftMember
		shifts  []rotang.ShiftEntry
		want    testStruct
	}{{
		name: "Some shifts",
		time: midnight,
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
				Shifts: rotang.ShiftConfig{
					Shifts: []rotang.Shift{
						{
							Name: "MTV Half Day",
						}, {
							Name: "SYD Half Day",
						},
					},
				},
			},
		},
		members: []rotang.ShiftMember{
			{
				ShiftName: "MTV Half Day",
				Email:     "mtv1@oncall.com",
			}, {
				ShiftName: "MTV Half Day",
				Email:     "mtv2@oncall.com",
			}, {
				ShiftName: "SYD Half Day",
				Email:     "syd1@oncall.com",
			}, {
				ShiftName: "SYD Half Day",
				Email:     "syd2@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV Half Day",
				StartTime: midnight.Add(-2 * fullDay),
				EndTime:   midnight.Add(-1 * fullDay),
			}, {
				Name:      "SYD Half Day",
				StartTime: midnight.Add(-2*fullDay + 12*time.Hour),
				EndTime:   midnight.Add(-1*fullDay + 12*time.Hour),
			},
			{
				Name:      "MTV Half Day",
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay),
			}, {
				Name:      "SYD Half Day",
				StartTime: midnight.Add(12 * time.Hour),
				EndTime:   midnight.Add(fullDay + 12*time.Hour),
			},
		},
		want: testStruct{
			History: []SplitShifts{
				{
					Name:    "MTV Half Day",
					Members: []string{"mtv1@oncall.com", "mtv2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "MTV Half Day",
							StartTime: midnight.Add(-2 * fullDay),
							EndTime:   midnight.Add(-1 * fullDay),
						},
					},
				}, {
					Name:    "SYD Half Day",
					Members: []string{"syd1@oncall.com", "syd2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "SYD Half Day",
							StartTime: midnight.Add(-2*fullDay + 12*time.Hour),
							EndTime:   midnight.Add(-1*fullDay + 12*time.Hour),
						},
					},
				},
			},
			Current: []SplitShifts{
				{
					Name:    "MTV Half Day",
					Members: []string{"mtv1@oncall.com", "mtv2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "MTV Half Day",
							StartTime: midnight,
							EndTime:   midnight.Add(fullDay),
						},
					},
				}, {
					Name:    "SYD Half Day",
					Members: []string{"syd1@oncall.com", "syd2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "SYD Half Day",
							StartTime: midnight.Add(12 * time.Hour),
							EndTime:   midnight.Add(fullDay + 12*time.Hour),
						},
					},
				},
			},
		},
	},
	}

	for _, tst := range tests {
		h, c := handleShifts(tst.shifts, tst.members, tst.time)
		arrangeShiftByStart(tst.cfg, h)
		arrangeShiftByStart(tst.cfg, c)
		if diff := pretty.Compare(tst.want, testStruct{h, c}); diff != "" {
			t.Errorf("%s: handleShifts(_, _, %v) differ -want +got, %s", tst.name, tst.time, diff)
		}
	}
}

func mustJSON(in *RotaShifts) string {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	if err := enc.Encode(in); err != nil {
		panic(err)
	}
	return buf.String()
}

func TestHandleGeneratedShifts(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name       string
		fail       bool
		cfg        *rotang.Configuration
		memberPool []rotang.Member
		rotaShifts *RotaShifts
		want       []rotang.ShiftEntry
	}{{
		name: "Success",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
			},
			Members: []rotang.ShiftMember{
				{
					ShiftName: "MTV Half Day",
					Email:     "mtv1@oncall.com",
				},
				{
					ShiftName: "MTV Half Day",
					Email:     "mtv2@oncall.com",
				},
				{
					ShiftName: "SYD Half Day",
					Email:     "syd1@oncall.com",
				},
				{
					ShiftName: "MTV Half Day",
					Email:     "syd2@oncall.com",
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
		},
		rotaShifts: &RotaShifts{
			Rota: "Test Rota",
			SplitShifts: []SplitShifts{
				{
					Name:    "MTV Half Day",
					Members: []string{"mtv1@oncall.com", "mtv2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "MTV Half Day",
							StartTime: midnight,
							EndTime:   midnight.Add(fullDay),
							OnCall: []rotang.ShiftMember{
								{
									ShiftName: "MTV Half Day",
									Email:     "mtv1@oncall.com",
								},
							},
						}, {
							Name:      "MTV Half Day",
							StartTime: midnight.Add(2 * fullDay),
							EndTime:   midnight.Add(3 * fullDay),
							OnCall: []rotang.ShiftMember{
								{
									ShiftName: "MTV Half Day",
									Email:     "mtv2@oncall.com",
								},
							},
							Comment: "After Update",
						},
					},
				}, {
					Name:    "SYD Half Day",
					Members: []string{"syd1@oncall.com", "syd2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "SYD Half Day",
							StartTime: midnight.Add(12 * time.Hour),
							EndTime:   midnight.Add(fullDay + 12*time.Hour),
							OnCall: []rotang.ShiftMember{
								{
									ShiftName: "SYD Half Day",
									Email:     "syd1@oncall.com",
								},
							},
						},
					},
				},
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name:      "MTV Half Day",
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV Half Day",
						Email:     "mtv1@oncall.com",
					},
				},
			}, {
				Name:      "SYD Half Day",
				StartTime: midnight.Add(12 * time.Hour),
				EndTime:   midnight.Add(fullDay + 12*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "SYD Half Day",
						Email:     "syd1@oncall.com",
					},
				},
			},
			{
				Name:      "MTV Half Day",
				StartTime: midnight.Add(2 * fullDay),
				EndTime:   midnight.Add(3 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV Half Day",
						Email:     "mtv2@oncall.com",
					},
				},
				Comment: "After Update",
			},
		},
	}}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: AddMember(ctx, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			if err := h.configStore(ctx).CreateRotaConfig(ctx, tst.cfg); err != nil {
				t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
			}
			defer h.configStore(ctx).DeleteRotaConfig(ctx, tst.cfg.Config.Name)

			err := h.handleGeneratedShifts(ctx, tst.cfg, tst.rotaShifts)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: handleGeneratedShifts(ctx, _, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
			if err != nil {
				return
			}

			shifts, err := h.shiftStore(ctx).AllShifts(ctx, tst.cfg.Config.Name)
			if err != nil {
				t.Fatalf("%s: AllShifts(ctx, %q) failed: %v", tst.name, tst.cfg.Config.Name, err)
			}

			if diff := pretty.Compare(tst.want, shifts); diff != "" {
				t.Fatalf("%s: handleGeneratedShifts(ctx, _) differ -want +got, %s", tst.name, diff)
			}
		})
	}
}

func TestHandleUpdatedShifts(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name       string
		fail       bool
		cfg        *rotang.Configuration
		memberPool []rotang.Member
		rotaShifts *RotaShifts
		shifts     []rotang.ShiftEntry
		want       []rotang.ShiftEntry
	}{{
		name: "Success",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
			},
			Members: []rotang.ShiftMember{
				{
					ShiftName: "MTV Half Day",
					Email:     "mtv1@oncall.com",
				},
				{
					ShiftName: "MTV Half Day",
					Email:     "mtv2@oncall.com",
				},
				{
					ShiftName: "SYD Half Day",
					Email:     "syd1@oncall.com",
				},
				{
					ShiftName: "MTV Half Day",
					Email:     "syd2@oncall.com",
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
		},
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV Half Day",
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV Half Day",
						Email:     "mtv1@oncall.com",
					}, {
						ShiftName: "MTV Half Day",
						Email:     "mtv2@oncall.com",
					},
				},
			}, {
				Name:      "SYD Half Day",
				StartTime: midnight.Add(12 * time.Hour),
				EndTime:   midnight.Add(fullDay + 12*time.Hour),
				Comment:   "Before Update",
			},
			{
				Name:      "MTV Half Day",
				StartTime: midnight.Add(2 * fullDay),
				EndTime:   midnight.Add(3 * fullDay),
			}, {
				Name:      "SYD Half Day",
				StartTime: midnight.Add(2*fullDay + 12*time.Hour),
				EndTime:   midnight.Add(3*fullDay + 12*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "SYD Half Day",
						Email:     "syd1@oncall.com",
					},
				},
			},
		},
		rotaShifts: &RotaShifts{
			Rota: "Test Rota",
			SplitShifts: []SplitShifts{
				{
					Name:    "MTV Half Day",
					Members: []string{"mtv1@oncall.com", "mtv2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "MTV Half Day",
							StartTime: midnight,
							EndTime:   midnight.Add(fullDay),
							OnCall: []rotang.ShiftMember{
								{
									ShiftName: "MTV Half Day",
									Email:     "mtv1@oncall.com",
								},
							},
						}, {
							Name:      "MTV Half Day",
							StartTime: midnight.Add(2 * fullDay),
							EndTime:   midnight.Add(3 * fullDay),
							OnCall: []rotang.ShiftMember{
								{
									ShiftName: "MTV Half Day",
									Email:     "mtv2@oncall.com",
								},
							},
							Comment: "After Update",
						},
					},
				}, {
					Name:    "SYD Half Day",
					Members: []string{"syd1@oncall.com", "syd2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "SYD Half Day",
							StartTime: midnight.Add(12 * time.Hour),
							EndTime:   midnight.Add(fullDay + 12*time.Hour),
							OnCall: []rotang.ShiftMember{
								{
									ShiftName: "SYD Half Day",
									Email:     "syd1@oncall.com",
								},
							},
						},
					},
				},
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name:      "MTV Half Day",
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV Half Day",
						Email:     "mtv1@oncall.com",
					},
				},
			}, {
				Name:      "SYD Half Day",
				StartTime: midnight.Add(12 * time.Hour),
				EndTime:   midnight.Add(fullDay + 12*time.Hour),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "SYD Half Day",
						Email:     "syd1@oncall.com",
					},
				},
			},
			{
				Name:      "MTV Half Day",
				StartTime: midnight.Add(2 * fullDay),
				EndTime:   midnight.Add(3 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV Half Day",
						Email:     "mtv2@oncall.com",
					},
				},
				Comment: "After Update",
			},
		},
	}}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: AddMember(ctx, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			if err := h.configStore(ctx).CreateRotaConfig(ctx, tst.cfg); err != nil {
				t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
			}
			defer h.configStore(ctx).DeleteRotaConfig(ctx, tst.cfg.Config.Name)
			if err := h.shiftStore(ctx).AddShifts(ctx, tst.cfg.Config.Name, tst.shifts); err != nil {
				t.Fatalf("%s: AddShifts(ctx, _, %q, _) failed: %v", tst.name, tst.cfg.Config.Name, err)
			}

			err := h.handleUpdatedShifts(ctx, tst.cfg, tst.rotaShifts)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: handleUpdatedShifts(ctx, _, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
			if err != nil {
				return
			}

			shifts, err := h.shiftStore(ctx).AllShifts(ctx, tst.cfg.Config.Name)
			if err != nil {
				t.Fatalf("%s: AllShifts(ctx, %q) failed: %v", tst.name, tst.cfg.Config.Name, err)
			}

			if diff := pretty.Compare(tst.want, shifts); diff != "" {
				t.Fatalf("%s: handleUpdatedShifts(ctx, _) differ -want +got, %s", tst.name, diff)
			}
		})
	}
}

func TestShiftSetup(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name string
		fail bool
		ctx  *router.Context
		json string
		cfg  *rotang.Configuration
		user string
		want *RotaShifts
	}{{
		name: "Context canceled",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
			},
		},
	}, {
		name: "Success",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		user: "test@user.com",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@user.com"},
			},
		},
		json: mustJSON(&RotaShifts{
			Rota: "Test Rota",
			SplitShifts: []SplitShifts{
				{
					Name:    "MTV Half Day",
					Members: []string{"mtv1@oncall.com", "mtv2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "MTV Half Day",
							StartTime: midnight,
							EndTime:   midnight.Add(fullDay),
						},
					},
				}, {
					Name:    "SYD Half Day",
					Members: []string{"syd1@oncall.com", "syd2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "SYD Half Day",
							StartTime: midnight.Add(12 * time.Hour),
							EndTime:   midnight.Add(fullDay + 12*time.Hour),
						},
					},
				},
			},
		}),
		want: &RotaShifts{
			Rota: "Test Rota",
			SplitShifts: []SplitShifts{
				{
					Name:    "MTV Half Day",
					Members: []string{"mtv1@oncall.com", "mtv2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "MTV Half Day",
							StartTime: midnight,
							EndTime:   midnight.Add(fullDay),
						},
					},
				}, {
					Name:    "SYD Half Day",
					Members: []string{"syd1@oncall.com", "syd2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "SYD Half Day",
							StartTime: midnight.Add(12 * time.Hour),
							EndTime:   midnight.Add(fullDay + 12*time.Hour),
						},
					},
				},
			},
		},
	}, {
		name: "Rota not found",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		user: "test@user.com",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@user.com"},
			},
		},
		json: mustJSON(&RotaShifts{
			Rota: "Non existing Test Rota",
			SplitShifts: []SplitShifts{
				{
					Name:    "MTV Half Day",
					Members: []string{"mtv1@oncall.com", "mtv2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "MTV Half Day",
							StartTime: midnight,
							EndTime:   midnight.Add(fullDay),
						},
					},
				}, {
					Name:    "SYD Half Day",
					Members: []string{"syd1@oncall.com", "syd2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "SYD Half Day",
							StartTime: midnight.Add(12 * time.Hour),
							EndTime:   midnight.Add(fullDay + 12*time.Hour),
						},
					},
				},
			},
		}),
	}, {
		name: "Not owner",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		user: "nottest@user.com",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@user.com"},
			},
		},
		json: mustJSON(&RotaShifts{
			Rota: "Test Rota",
			SplitShifts: []SplitShifts{
				{
					Name:    "MTV Half Day",
					Members: []string{"mtv1@oncall.com", "mtv2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "MTV Half Day",
							StartTime: midnight,
							EndTime:   midnight.Add(fullDay),
						},
					},
				}, {
					Name:    "SYD Half Day",
					Members: []string{"syd1@oncall.com", "syd2@oncall.com"},
					Shifts: []rotang.ShiftEntry{
						{
							Name:      "SYD Half Day",
							StartTime: midnight.Add(12 * time.Hour),
							EndTime:   midnight.Add(fullDay + 12*time.Hour),
						},
					},
				},
			},
		}),
	}, {
		name: "JSON Decode fail",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		user: "test@user.com",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@user.com"},
			},
		},
		json: "Not JSON",
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

			buf := bytes.NewBufferString(tst.json)

			tst.ctx.Request = httptest.NewRequest("POST", "/shiftsgenerate", buf)

			_, rs, err := h.shiftSetup(tst.ctx)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: shiftSetup(ctx) = %t want: %t, err: %v", tst.name, got, want, err)
			}
			if err != nil {
				return
			}

			if diff := pretty.Compare(tst.want, rs); diff != "" {
				t.Fatalf("%s; shiftSetup(ctx) differ -want +got, %s", tst.name, diff)
			}
		})
	}
}

func TestArrangeShiftByStart(t *testing.T) {
	tests := []struct {
		name string
		cfg  *rotang.Configuration
		in   []SplitShifts
		want []SplitShifts
	}{{
		name: "Success",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
				Shifts: rotang.ShiftConfig{
					Shifts: []rotang.Shift{
						{
							Name: "MTV 8 hours",
						}, {
							Name: "SYD 8 hours",
						}, {
							Name: "EU 8 hours",
						},
					},
				},
			},
		},
		in: []SplitShifts{
			{
				Name:    "EU 8 hours",
				Members: []string{"eu1@oncall.com", "eu2@oncall.com"},
			}, {
				Name:    "SYD 8 hours",
				Members: []string{"syd1@oncall.com", "syd2@oncall.com"},
			}, {
				Name:    "MTV 8 hours",
				Members: []string{"mtv1@oncall.com", "mtv2@oncall.com"},
			},
		},
		want: []SplitShifts{
			{
				Name:    "MTV 8 hours",
				Members: []string{"mtv1@oncall.com", "mtv2@oncall.com"},
			}, {
				Name:    "SYD 8 hours",
				Members: []string{"syd1@oncall.com", "syd2@oncall.com"},
			}, {
				Name:    "EU 8 hours",
				Members: []string{"eu1@oncall.com", "eu2@oncall.com"},
			},
		},
	},
	}

	for _, tst := range tests {
		arrangeShiftByStart(tst.cfg, tst.in)
		if diff := pretty.Compare(tst.want, tst.in); diff != "" {
			t.Errorf("%s: arrangeShiftByStart(_, _) differ -want +got, %s", tst.name, diff)
		}
	}
}

func TestHandleManageShifts(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name   string
		fail   bool
		ctx    *router.Context
		user   string
		rota   string
		values url.Values
		cfg    *rotang.Configuration
	}{{
		name: "Canceled context",
		fail: true,
		rota: "Test rota",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test rota",
			},
		},
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Name not set",
		fail: true,
		rota: "Test rota",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test rota",
			},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Success",
		rota: "Test rota",
		user: "test@user.com",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test rota",
				Owners: []string{"test@user.com"},
			},
		},
		values: url.Values{
			"name": {"Test rota"},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Rota not found",
		fail: true,
		rota: "Test rota",
		user: "test@user.com",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test rota",
				Owners: []string{"test@user.com"},
			},
		},
		values: url.Values{
			"name": {"Another Test rota"},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Not owner",
		fail: true,
		rota: "Test rota",
		user: "notowner@user.com",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test rota",
				Owners: []string{"test@user.com"},
			},
		},
		values: url.Values{
			"name": {"Test rota"},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
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

			tst.ctx.Context = templates.Use(tst.ctx.Context, &templates.Bundle{
				Loader: templates.FileSystemLoader(templatesLocation),
			}, nil)
			if tst.user != "" {
				tst.ctx.Context = auth.WithState(tst.ctx.Context, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.user),
				})
			}

			tst.ctx.Request = httptest.NewRequest("GET", "/manageshifts", nil)
			tst.ctx.Request.Form = tst.values

			h.HandleManageShifts(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: HandleManageShifts() = %t want: %t, res: %v", tst.name, got, want, recorder.Code)
			}
			if recorder.Code != http.StatusOK {
				return
			}

		})
	}
}
