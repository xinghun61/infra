package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"infra/appengine/rotang"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/julienschmidt/httprouter"
	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

func TestHandleOncall(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name  string
		email string
		fail  bool
		ctx   *router.Context
	}{{
		name: "Canceled context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
			Params: httprouter.Params{
				{
					Key:   "name",
					Value: "Test Rota",
				},
			},
		},
	}, {
		name: "Not logged in",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Params: httprouter.Params{
				{
					Key:   "name",
					Value: "Test Rota",
				},
			},
		},
	}, {
		name: "Single rota",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Params: httprouter.Params{
				{
					Key:   "name",
					Value: "Test Rota",
				},
			},
		},
		email: "test@user.com",
	}, {
		name: "All rotas",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		email: "test@user.com",
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		if tst.email != "" {
			tst.ctx.Context = auth.WithState(tst.ctx.Context, &authtest.FakeState{
				Identity: identity.Identity("user:" + tst.email),
			})
		}

		h.HandleOncall(tst.ctx)

		recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
		if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
			t.Errorf("%s: HandleOncall(ctx) = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
		}
	}
}

func TestHandleOncallJSON(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name string
		fail bool
		ctx  *router.Context
	}{{
		name: "Canceled context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Not POST",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/oncalljson", nil),
		},
	}, {
		name: "Empty BODY",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("POST", "/oncalljson", nil),
		},
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		h.HandleOncallJSON(tst.ctx)

		recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
		if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
			t.Errorf("%s: HandleOncallJSON(ctx) = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			continue
		}
		if recorder.Code != http.StatusOK {
			continue
		}
	}
}

func buildBody(t *testing.T, req interface{}) *bytes.Buffer {
	t.Helper()

	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	if err := enc.Encode(req); err != nil {
		t.Fatalf("Encode(req) failed: %v", err)
	}
	return &buf
}

func TestGenAllRotas(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name       string
		fail       bool
		ctx        *router.Context
		rota       string
		at         time.Time
		email      string
		cfgs       []rotang.Configuration
		memberPool []rotang.Member
		shifts     []rotang.ShiftEntry
		want       templates.Args
	}{{
		name: "Success",
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/oncalljson", buildBody(t, []OnCallerRequest{
				{
					Name: "Test Rota",
					At:   midnight,
				},
			})),
			Writer: httptest.NewRecorder(),
		},
		rota:  "Test Rota",
		email: "test@member.com",
		at:    midnight,
		cfgs: []rotang.Configuration{
			{
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
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "test@member.com",
			},
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
		want: templates.Args{"Rotas": "[\"Test Rota\"]\n", "User": "test@member.com"},
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
				if err := h.configStore(ctx).CreateRotaConfig(ctx, &cfg); err != nil {
					t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, cfg.Config.Name)
			}
			if len(tst.cfgs) > 0 {
				if err := h.shiftStore(ctx).AddShifts(ctx, tst.rota, tst.shifts); err != nil {
					t.Fatalf("%s: AddShifts(ctx, _) failed: %v", tst.name, err)
				}
				defer h.shiftStore(ctx).DeleteAllShifts(ctx, tst.rota)
			}

			ts, err := h.genAllRotas(tst.ctx, tst.email, tst.at)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: genAllRotas(ctx, %q,  %v) = %t want: %t, err: %v", tst.name, tst.email, tst.at, got, want, err)
			}
			if err != nil {
				return
			}

			if diff := pretty.Compare(tst.want, ts); diff != "" {
				t.Fatalf("%s: allOncallJSON(ctx, %v) differ -want +got, \n%s", tst.name, tst.at, diff)
			}
		})
	}
}

func TestGenSingleRota(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name       string
		fail       bool
		ctx        *router.Context
		rota       string
		at         time.Time
		email      string
		cfgs       []rotang.Configuration
		memberPool []rotang.Member
		shifts     []rotang.ShiftEntry
		want       RotaShifts
	}{{
		name: "Success",
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/oncalljson", buildBody(t, []OnCallerRequest{
				{
					Name: "Test Rota",
					At:   midnight,
				},
			})),
			Writer: httptest.NewRecorder(),
		},
		rota:  "Test Rota",
		email: "test@member.com",
		at:    midnight,
		cfgs: []rotang.Configuration{
			{
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
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "test@member.com",
			},
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
		want: RotaShifts{
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
				if err := h.configStore(ctx).CreateRotaConfig(ctx, &cfg); err != nil {
					t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, cfg.Config.Name)
			}
			if len(tst.cfgs) > 0 {
				if err := h.shiftStore(ctx).AddShifts(ctx, tst.rota, tst.shifts); err != nil {
					t.Fatalf("%s: AddShifts(ctx, _) failed: %v", tst.name, err)
				}
				defer h.shiftStore(ctx).DeleteAllShifts(ctx, tst.rota)
			}

			ts, err := h.genSingleRota(tst.ctx, tst.email, tst.rota, tst.at)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: genSingleRota(ctx, %q, %q, %v) = %t want: %t, err: %v", tst.name, tst.email, tst.rota, tst.at, got, want, err)
			}
			if err != nil {
				return
			}

			var rs RotaShifts
			if err := json.NewDecoder(bytes.NewBufferString(ts["Current"].(string))).Decode(&rs); err != nil {
				t.Fatalf("%s: Decode() failed: %v", tst.name, err)
			}

			if diff := pretty.Compare(tst.want, rs); diff != "" {
				t.Fatalf("%s: allOncallJSON(ctx, %v) differ -want +got, \n%s", tst.name, tst.at, diff)
			}
		})
	}
}

func TestOncallJSON(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name       string
		fail       bool
		ctx        *router.Context
		rota       string
		at         time.Time
		cfgs       []rotang.Configuration
		memberPool []rotang.Member
		shifts     []rotang.ShiftEntry
		want       []OnCallers
	}{{
		name: "Success",
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/oncalljson", buildBody(t, []OnCallerRequest{
				{
					Name: "Test Rota",
					At:   midnight,
				},
			})),
			Writer: httptest.NewRecorder(),
		},
		rota: "Test Rota",
		at:   midnight,
		cfgs: []rotang.Configuration{
			{
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
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "test@member.com",
			},
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
		want: []OnCallers{
			{
				Name: "Test Rota",
				Shift: rotang.ShiftEntry{
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
	}, {
		name: "JSON Encode fail",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/oncalljson", bytes.NewBufferString("not json")),
			Writer:  httptest.NewRecorder(),
		},
		rota: "Test Rota",
		at:   midnight,
	}, {
		name: "Nobody oncall",
		ctx: &router.Context{
			Context: ctx,
			Request: httptest.NewRequest("POST", "/oncalljson", buildBody(t, []OnCallerRequest{
				{
					Name: "Test Rota",
					At:   midnight,
				},
			})),
			Writer: httptest.NewRecorder(),
		},
		rota: "Test Rota",
		at:   midnight,
		cfgs: []rotang.Configuration{
			{
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
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "test@member.com",
			},
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
				StartTime: midnight.Add(fullDay),
				EndTime:   midnight.Add(2 * fullDay),
			},
		},
		want: []OnCallers{
			{
				Name: "Test Rota",
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
				if err := h.configStore(ctx).CreateRotaConfig(ctx, &cfg); err != nil {
					t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, cfg.Config.Name)
			}
			if len(tst.cfgs) > 0 {
				if err := h.shiftStore(ctx).AddShifts(ctx, tst.rota, tst.shifts); err != nil {
					t.Fatalf("%s: AddShifts(ctx, _) failed: %v", tst.name, err)
				}
				defer h.shiftStore(ctx).DeleteAllShifts(ctx, tst.rota)
			}

			oncallers, err := h.oncallJSON(tst.ctx)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: allOncallJSON(ctx, %v) = %t want: %t, err: %v", tst.name, tst.at, got, want, err)
			}
			if err != nil {
				return
			}

			var got []OnCallers
			if len(oncallers) > 0 {
				if err := json.NewDecoder(bytes.NewBufferString(oncallers)).Decode(&got); err != nil {
					t.Fatalf("%s: Decode() failed: %v", tst.name, err)
				}
			}

			if diff := pretty.Compare(tst.want, got); diff != "" {
				t.Fatalf("%s: allOncallJSON(ctx, %v) differ -want +got, \n%s", tst.name, tst.at, diff)
			}
		})
	}
}

func TestAllOncallJSON(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name       string
		fail       bool
		ctx        *router.Context
		rota       string
		at         time.Time
		cfgs       []rotang.Configuration
		memberPool []rotang.Member
		shifts     []rotang.ShiftEntry
		want       []OnCallers
	}{{
		name: "Success",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/oncalljson", nil),
		},
		rota: "Test Rota",
		at:   midnight,
		cfgs: []rotang.Configuration{
			{
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
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "test@member.com",
			},
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
		want: []OnCallers{
			{
				Name: "Test Rota",
				Shift: rotang.ShiftEntry{
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
	}, {
		name: "No rotas",
		fail: false,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/oncalljson", nil),
		},
		rota: "Test Rota",
		at:   midnight,
	}, {
		name: "Nobdy OnCall",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: httptest.NewRequest("GET", "/oncalljson", nil),
		},
		rota: "Test Rota",
		at:   midnight,
		cfgs: []rotang.Configuration{
			{
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
		},
		memberPool: []rotang.Member{
			{
				Name:  "Test Testson",
				Email: "test@member.com",
			},
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
				StartTime: midnight.Add(fullDay),
				EndTime:   midnight.Add(2 * fullDay),
			},
		},
		want: []OnCallers{
			{
				Name: "Test Rota",
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
				if err := h.configStore(ctx).CreateRotaConfig(ctx, &cfg); err != nil {
					t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, cfg.Config.Name)
			}
			if len(tst.cfgs) > 0 {
				if err := h.shiftStore(ctx).AddShifts(ctx, tst.rota, tst.shifts); err != nil {
					t.Fatalf("%s: AddShifts(ctx, _) failed: %v", tst.name, err)
				}
				defer h.shiftStore(ctx).DeleteAllShifts(ctx, tst.rota)
			}

			oncallers, err := h.allOncallJSON(tst.ctx, tst.at)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: allOncallJSON(ctx, %v) = %t want: %t, err: %v", tst.name, tst.at, got, want, err)
			}
			if err != nil {
				return
			}

			var got []OnCallers
			if len(oncallers) > 0 {
				if err := json.NewDecoder(bytes.NewBufferString(oncallers)).Decode(&got); err != nil {
					t.Fatalf("%s: Decode() failed: %v", tst.name, err)
				}
			}

			if diff := pretty.Compare(tst.want, got); diff != "" {
				t.Fatalf("%s: allOncallJSON(ctx, %v) differ -want +got, \n%s", tst.name, tst.at, diff)
			}
		})
	}
}
