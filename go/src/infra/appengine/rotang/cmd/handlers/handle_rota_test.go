package handlers

import (
	"bytes"
	"encoding/json"
	"infra/appengine/rotang"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"

	"context"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

func TestHandleRotaCreateGET(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name string
		fail bool
		ctx  *router.Context
	}{
		{
			name: "Success",
			ctx: &router.Context{
				Context: ctx,
				Writer:  httptest.NewRecorder(),
				Request: httptest.NewRequest("GET", "/createrota", nil),
			},
		},
	}

	h := testSetup(t)

	for _, tst := range tests {
		tst.ctx.Context = templates.Use(tst.ctx.Context, &templates.Bundle{
			Loader: templates.FileSystemLoader(templatesLocation),
		}, nil)

		h.HandleRotaCreate(tst.ctx)

		recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
		if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
			t.Errorf("%s: HandleRotaCreate(ctx) = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			continue
		}
		if recorder.Code != http.StatusOK {
			continue
		}
	}
}

func TestHandleRotaModifyGET(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name string
		fail bool
		ctx  *router.Context
		rota string
		user string
		cfg  *rotang.Configuration
	}{
		{
			name: "Rota not found",
			fail: true,
			ctx: &router.Context{
				Context: ctx,
				Writer:  httptest.NewRecorder(),
				Request: httptest.NewRequest("GET", "/createrota", nil),
			},
			rota: "Test Rota",
		}, {
			name: "Not in owners",
			fail: true,
			ctx: &router.Context{
				Context: ctx,
				Writer:  httptest.NewRecorder(),
				Request: httptest.NewRequest("GET", "/createrota", nil),
			},
			cfg: &rotang.Configuration{
				Config: rotang.Config{
					Name:   "Test Rota",
					Owners: []string{"someone@else.se"},
				},
			},
			rota: "Test Rota",
		}, {
			name: "Success",
			ctx: &router.Context{
				Context: ctx,
				Writer:  httptest.NewRecorder(),
				Request: httptest.NewRequest("GET", "/createrota", nil),
			},
			user: "test@user.com",
			cfg: &rotang.Configuration{
				Config: rotang.Config{
					Name:   "Test Rota",
					Owners: []string{"test@user.com"},
				},
			},
			rota: "Test Rota",
		},
	}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			if tst.cfg != nil {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, tst.cfg); err != nil {
					t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, tst.cfg.Config.Name)
			}
			tst.ctx.Context = templates.Use(tst.ctx.Context, &templates.Bundle{
				Loader: templates.FileSystemLoader(templatesLocation),
			}, nil)
			if tst.user != "" {
				tst.ctx.Context = auth.WithState(tst.ctx.Context, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.user),
				})
			}

			tst.ctx.Request.Form = url.Values{"name": []string{tst.rota}}

			h.HandleRotaModify(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: HandleRotaModify(ctx) = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
			if recorder.Code != http.StatusOK {
				return
			}
		})
	}
}

func TestHandleRotaCreatePOST(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name         string
		fail         bool
		user         string
		ctx          *router.Context
		memberPool   []rotang.Member
		existingRota *rotang.Configuration
		rota         jsonRota
		want         rotang.Configuration
	}{{
		name: "Canceled context",
		fail: true,
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Success",
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		rota: jsonRota{
			Cfg: rotang.Configuration{
				Config: rotang.Config{
					Name:        "Test Rotation",
					Owners:      []string{"test@user.com"},
					Description: "Describe the rotation",
					Calendar:    "cal@cal",
					Email: rotang.Email{
						Subject: "You're on call!",
						Body:    "Darn",
					},
					Shifts: rotang.ShiftConfig{
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
						Email:     "test1@test.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "test2@test.com",
						ShiftName: "MTV All Day",
					},
				},
			},
			Members: []jsonMember{
				{
					Name:  "First Test",
					Email: "test1@test.com",
					TZ:    "America/Los_Angeles",
				}, {
					Name:  "Second Test",
					Email: "test2@test.com",
					TZ:    "America/Los_Angeles",
				},
			},
		},
		want: rotang.Configuration{
			Config: rotang.Config{
				Name:        "Test Rotation",
				Owners:      []string{"test@user.com"},
				Description: "Describe the rotation",
				Calendar:    "cal@cal",
				Email: rotang.Email{
					Subject: "You're on call!",
					Body:    "Darn",
				},
				Shifts: rotang.ShiftConfig{
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
					Email:     "test1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
	}, {
		name: "Rota already exist",
		fail: true,
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		existingRota: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rotation",
			},
		},
		rota: jsonRota{
			Cfg: rotang.Configuration{
				Config: rotang.Config{
					Name:        "Test Rotation",
					Owners:      []string{"test@user.com"},
					Description: "Describe the rotation",
					Calendar:    "cal@cal",
					Email: rotang.Email{
						Subject: "You're on call!",
						Body:    "Darn",
					},
					Shifts: rotang.ShiftConfig{
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
						Email:     "test1@test.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "test2@test.com",
						ShiftName: "MTV All Day",
					},
				},
			},
			Members: []jsonMember{
				{
					Name:  "First Test",
					Email: "test1@test.com",
					TZ:    "America/Los_Angeles",
				}, {
					Name:  "Second Test",
					Email: "test2@test.com",
					TZ:    "America/Los_Angeles",
				},
			},
		},
	}, {
		name: "Not owner",
		fail: true,
		user: "not-test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		rota: jsonRota{
			Cfg: rotang.Configuration{
				Config: rotang.Config{
					Name:        "Test Rotation",
					Owners:      []string{"test@user.com"},
					Description: "Describe the rotation",
					Calendar:    "cal@cal",
					Email: rotang.Email{
						Subject: "You're on call!",
						Body:    "Darn",
					},
					Shifts: rotang.ShiftConfig{
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
						Email:     "test1@test.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "test2@test.com",
						ShiftName: "MTV All Day",
					},
				},
			},
			Members: []jsonMember{
				{
					Name:  "First Test",
					Email: "test1@test.com",
					TZ:    "America/Los_Angeles",
				}, {
					Name:  "Second Test",
					Email: "test2@test.com",
					TZ:    "America/Los_Angeles",
				},
			},
		},
	}, {
		name: "Shifts does not add up to 24h",
		fail: true,
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		rota: jsonRota{
			Cfg: rotang.Configuration{
				Config: rotang.Config{
					Name:        "Test Rotation",
					Owners:      []string{"test@user.com"},
					Description: "Describe the rotation",
					Calendar:    "cal@cal",
					Email: rotang.Email{
						Subject: "You're on call!",
						Body:    "Darn",
					},
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name:     "MTV All Day",
								Duration: fullDay,
							}, {
								Name:     "Syd Half Day",
								Duration: fullDay / 2,
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "test1@test.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "test2@test.com",
						ShiftName: "MTV All Day",
					},
				},
			},
			Members: []jsonMember{
				{
					Name:  "First Test",
					Email: "test1@test.com",
					TZ:    "America/Los_Angeles",
				}, {
					Name:  "Second Test",
					Email: "test2@test.com",
					TZ:    "America/Los_Angeles",
				},
			},
		},
	}, {
		name: "Invalid Timezone",
		fail: true,
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		rota: jsonRota{
			Cfg: rotang.Configuration{
				Config: rotang.Config{
					Name:        "Test Rotation",
					Owners:      []string{"test@user.com"},
					Description: "Describe the rotation",
					Calendar:    "cal@cal",
					Email: rotang.Email{
						Subject: "You're on call!",
						Body:    "Darn",
					},
					Shifts: rotang.ShiftConfig{
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
						Email:     "test1@test.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "test2@test.com",
						ShiftName: "MTV All Day",
					},
				},
			},
			Members: []jsonMember{
				{
					Name:  "First Test",
					Email: "test1@test.com",
					TZ:    "America/Los_Angeles",
				}, {
					Name:  "Second Test",
					Email: "test2@test.com",
					TZ:    "America/Invalid",
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
					t.Fatalf("%s: s.CreateMember(_, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			if tst.existingRota != nil {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, tst.existingRota); err != nil {
					t.Fatalf("%s: s.CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, tst.existingRota.Config.Name)
			}

			tst.ctx.Context = templates.Use(tst.ctx.Context, &templates.Bundle{
				Loader: templates.FileSystemLoader(templatesLocation),
			}, nil)
			if tst.user != "" {
				tst.ctx.Context = auth.WithState(tst.ctx.Context, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.user),
				})
			}

			var jsonRota bytes.Buffer
			if err := json.NewEncoder(&jsonRota).Encode(tst.rota); err != nil {
				t.Fatalf("%s: json.Encode failed: %v", tst.name, err)
			}
			tst.ctx.Request = httptest.NewRequest("POST", "/createrota", &jsonRota)

			h.HandleRotaCreate(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: HandleRotaCreate(ctx) = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
			if recorder.Code != http.StatusOK {
				return
			}

			defer h.configStore(ctx).DeleteRotaConfig(ctx, tst.rota.Cfg.Config.Name)

			rota, err := h.configStore(ctx).RotaConfig(ctx, tst.rota.Cfg.Config.Name)
			if err != nil {
				t.Fatalf("%s: RotaConfig(ctx, %q) failed: %v", tst.name, tst.rota.Cfg.Config.Name, err)
			}

			if diff := pretty.Compare(tst.want, rota[0]); diff != "" {
				t.Fatalf("%s: HandleUpdateRota(ctx) differ -want +got,\n %s", tst.name, diff)
			}

		})
	}
}

func TestHandleRotaModify(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name         string
		fail         bool
		user         string
		ctx          *router.Context
		memberPool   []rotang.Member
		existingRota *rotang.Configuration
		rota         jsonRota
		want         rotang.Configuration
	}{{
		name: "Canceled context",
		fail: true,
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Success",
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		rota: jsonRota{
			Cfg: rotang.Configuration{
				Config: rotang.Config{
					Name:        "Test Rotation",
					Owners:      []string{"test@user.com"},
					Description: "Describe the rotation",
					Calendar:    "cal@cal",
					Email: rotang.Email{
						Subject: "You're on call!",
						Body:    "Darn",
					},
					Shifts: rotang.ShiftConfig{
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
						Email:     "test1@test.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "test2@test.com",
						ShiftName: "MTV All Day",
					},
				},
			},
			Members: []jsonMember{
				{
					Name:  "First Test",
					Email: "test1@test.com",
					TZ:    "America/Los_Angeles",
				}, {
					Name:  "Second Test",
					Email: "test2@test.com",
					TZ:    "America/Los_Angeles",
				},
			},
		},
		want: rotang.Configuration{
			Config: rotang.Config{
				Name:        "Test Rotation",
				Owners:      []string{"test@user.com"},
				Description: "Describe the rotation",
				Calendar:    "cal@cal",
				Email: rotang.Email{
					Subject: "You're on call!",
					Body:    "Darn",
				},
				Shifts: rotang.ShiftConfig{
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
					Email:     "test1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
	}, {
		name: "Rota already exist",
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		existingRota: &rotang.Configuration{
			Config: rotang.Config{
				Name:        "Test Rotation",
				Owners:      []string{"test@user.com"},
				Description: "Describe the rotation",
				Calendar:    "cal@cal",
				Email: rotang.Email{
					Subject: "You're on call!",
					Body:    "Darn",
				},
				Shifts: rotang.ShiftConfig{
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
					Email:     "test1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		rota: jsonRota{
			Cfg: rotang.Configuration{
				Config: rotang.Config{
					Name:        "Test Rotation",
					Owners:      []string{"test@user.com"},
					Description: "Describe the rotation",
					Calendar:    "cal@cal",
					Email: rotang.Email{
						Subject: "You're on call!",
						Body:    "Darn",
					},
					Shifts: rotang.ShiftConfig{
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
						Email:     "test1@test.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "test2@test.com",
						ShiftName: "MTV All Day",
					},
				},
			},
			Members: []jsonMember{
				{
					Name:  "First Test",
					Email: "test1@test.com",
					TZ:    "America/Los_Angeles",
				}, {
					Name:  "Second Test",
					Email: "test2@test.com",
					TZ:    "America/Los_Angeles",
				},
			},
		},
		want: rotang.Configuration{
			Config: rotang.Config{
				Name:        "Test Rotation",
				Owners:      []string{"test@user.com"},
				Description: "Describe the rotation",
				Calendar:    "cal@cal",
				Email: rotang.Email{
					Subject: "You're on call!",
					Body:    "Darn",
				},
				Shifts: rotang.ShiftConfig{
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
					Email:     "test1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
	}, {
		name: "Rota Copy",
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		existingRota: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rotation",
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "test1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
		rota: jsonRota{
			Cfg: rotang.Configuration{
				Config: rotang.Config{
					Name:        "New Test Rotation",
					Owners:      []string{"test@user.com"},
					Description: "Describe the rotation",
					Calendar:    "cal@cal",
					Email: rotang.Email{
						Subject: "You're on call!",
						Body:    "Darn",
					},
					Shifts: rotang.ShiftConfig{
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
						Email:     "test1@test.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "test2@test.com",
						ShiftName: "MTV All Day",
					},
				},
			},
			Members: []jsonMember{
				{
					Name:  "First Test",
					Email: "test1@test.com",
					TZ:    "America/Los_Angeles",
				}, {
					Name:  "Second Test",
					Email: "test2@test.com",
					TZ:    "America/Los_Angeles",
				},
			},
		},
		want: rotang.Configuration{
			Config: rotang.Config{
				Name:        "New Test Rotation",
				Owners:      []string{"test@user.com"},
				Description: "Describe the rotation",
				Calendar:    "cal@cal",
				Email: rotang.Email{
					Subject: "You're on call!",
					Body:    "Darn",
				},
				Shifts: rotang.ShiftConfig{
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
					Email:     "test1@test.com",
					ShiftName: "MTV All Day",
				}, {
					Email:     "test2@test.com",
					ShiftName: "MTV All Day",
				},
			},
		},
	}, {
		name: "Not owner",
		fail: true,
		user: "not-test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		rota: jsonRota{
			Cfg: rotang.Configuration{
				Config: rotang.Config{
					Name:        "Test Rotation",
					Owners:      []string{"test@user.com"},
					Description: "Describe the rotation",
					Calendar:    "cal@cal",
					Email: rotang.Email{
						Subject: "You're on call!",
						Body:    "Darn",
					},
					Shifts: rotang.ShiftConfig{
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
						Email:     "test1@test.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "test2@test.com",
						ShiftName: "MTV All Day",
					},
				},
			},
			Members: []jsonMember{
				{
					Name:  "First Test",
					Email: "test1@test.com",
					TZ:    "America/Los_Angeles",
				}, {
					Name:  "Second Test",
					Email: "test2@test.com",
					TZ:    "America/Los_Angeles",
				},
			},
		},
	}, {
		name: "Shifts does not add up to 24h",
		fail: true,
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		rota: jsonRota{
			Cfg: rotang.Configuration{
				Config: rotang.Config{
					Name:        "Test Rotation",
					Owners:      []string{"test@user.com"},
					Description: "Describe the rotation",
					Calendar:    "cal@cal",
					Email: rotang.Email{
						Subject: "You're on call!",
						Body:    "Darn",
					},
					Shifts: rotang.ShiftConfig{
						Generator: "Fair",
						Shifts: []rotang.Shift{
							{
								Name:     "MTV All Day",
								Duration: fullDay,
							}, {
								Name:     "Syd Half Day",
								Duration: fullDay / 2,
							},
						},
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email:     "test1@test.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "test2@test.com",
						ShiftName: "MTV All Day",
					},
				},
			},
			Members: []jsonMember{
				{
					Name:  "First Test",
					Email: "test1@test.com",
					TZ:    "America/Los_Angeles",
				}, {
					Name:  "Second Test",
					Email: "test2@test.com",
					TZ:    "America/Los_Angeles",
				},
			},
		},
	}, {
		name: "Invalid Timezone",
		fail: true,
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		rota: jsonRota{
			Cfg: rotang.Configuration{
				Config: rotang.Config{
					Name:        "Test Rotation",
					Owners:      []string{"test@user.com"},
					Description: "Describe the rotation",
					Calendar:    "cal@cal",
					Email: rotang.Email{
						Subject: "You're on call!",
						Body:    "Darn",
					},
					Shifts: rotang.ShiftConfig{
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
						Email:     "test1@test.com",
						ShiftName: "MTV All Day",
					}, {
						Email:     "test2@test.com",
						ShiftName: "MTV All Day",
					},
				},
			},
			Members: []jsonMember{
				{
					Name:  "First Test",
					Email: "test1@test.com",
					TZ:    "America/Los_Angeles",
				}, {
					Name:  "Second Test",
					Email: "test2@test.com",
					TZ:    "America/Invalid",
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
					t.Fatalf("%s: s.CreateMember(_, _) failed: %v", tst.name, err)
				}
				defer h.memberStore(ctx).DeleteMember(ctx, m.Email)
			}
			if tst.existingRota != nil {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, tst.existingRota); err != nil {
					t.Fatalf("%s: s.CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, tst.existingRota.Config.Name)
			}

			tst.ctx.Context = templates.Use(tst.ctx.Context, &templates.Bundle{
				Loader: templates.FileSystemLoader(templatesLocation),
			}, nil)
			if tst.user != "" {
				tst.ctx.Context = auth.WithState(tst.ctx.Context, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.user),
				})
			}

			var jsonRota bytes.Buffer
			if err := json.NewEncoder(&jsonRota).Encode(tst.rota); err != nil {
				t.Fatalf("%s: json.Encode failed: %v", tst.name, err)
			}
			tst.ctx.Request = httptest.NewRequest("POST", "/createrota", &jsonRota)

			h.HandleRotaModify(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: HandleRotaModify(ctx) = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
			if recorder.Code != http.StatusOK {
				return
			}

			defer h.configStore(ctx).DeleteRotaConfig(ctx, tst.rota.Cfg.Config.Name)

			rota, err := h.configStore(ctx).RotaConfig(ctx, tst.rota.Cfg.Config.Name)
			if err != nil {
				t.Fatalf("%s: RotaConfig(ctx, %q) failed: %v", tst.name, tst.rota.Cfg.Config.Name, err)
			}

			if diff := pretty.Compare(tst.want, rota[0]); diff != "" {
				t.Fatalf("%s: HandleUpdateRota(ctx) differ -want +got,\n %s", tst.name, diff)
			}

		})
	}
}
