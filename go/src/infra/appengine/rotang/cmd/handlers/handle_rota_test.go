package handlers

import (
	"infra/appengine/rotang"
	"infra/appengine/rotang/pkg/datastore"
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
)

func baseTime() time.Time {
	return time.Date(2018, 9, 28, 0, 0, 0, 0, mtvTime)
}

func TestCleanOwners(t *testing.T) {
	tests := []struct {
		name   string
		fail   bool
		email  string
		owners string
		want   []string
	}{{
		name:   "Single entry",
		email:  "testuser@test.com",
		owners: "testuser@test.com ",
		want:   []string{"testuser@test.com"},
	}, {
		name:   "Multiple entries",
		email:  "testuser@test.com",
		owners: "first@test.com,second@test.com, testuser@test.com , third@test.com",
		want:   []string{"first@test.com", "second@test.com", "testuser@test.com", "third@test.com"},
	}, {
		name:   "Owner not in list",
		fail:   true,
		email:  "testuser@test.com",
		owners: "first@test.com,second@test.com, third@test.com",
		want:   []string{"first@test.com", "second@test.com", "third@test.com"},
	},
	}

	for _, tst := range tests {
		res, err := cleanOwners(tst.email, tst.owners)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: cleanOwners(%q, %q) = %t want: %t, err: %v", tst.name, tst.email, tst.owners, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		if diff := pretty.Compare(tst.want, res); diff != "" {
			t.Errorf("%s: cleanOwners(%q, %q) differs -want +got, %s", tst.name, tst.email, tst.owners, diff)
		}
	}
}

func TestFillIntegers(t *testing.T) {

	tests := []struct {
		name   string
		fail   bool
		values url.Values
		want   rotang.Config
	}{{
		name: "Working",
		values: url.Values{
			"EmailNotify":      {"7"},
			"Expiration":       {"4"},
			"ShiftsToSchedule": {"5"},
			"shiftLength":      {"5"},
			"shiftSkip":        {"2"},
			"shiftMembers":     {"2"},
			"shiftStart":       {"00:00"},
		},
		want: rotang.Config{
			Expiration:       4,
			ShiftsToSchedule: 5,
			Email: rotang.Email{
				DaysBeforeNotify: 7,
			},
			Shifts: rotang.ShiftConfig{
				Length:       5,
				Skip:         2,
				ShiftMembers: 2,
				StartTime:    baseTime(),
			},
		},
	}, {
		name: "Failing",
		fail: true,
		values: url.Values{
			"EmailNotify":      {"7"},
			"Expiration":       {"4"},
			"ShiftsToSchedule": {"Not a Number"},
			"shiftLength":      {"5"},
			"shiftSkip":        {"2"},
			"shiftMembers":     {"2"},
			"shiftStart":       {"13:37"},
		},
		want: rotang.Config{
			Expiration:       4,
			ShiftsToSchedule: 5,
			Email: rotang.Email{
				DaysBeforeNotify: 7,
			},
			Shifts: rotang.ShiftConfig{
				Length:       5,
				Skip:         2,
				ShiftMembers: 2,
				StartTime:    baseTime(),
			},
		},
	}}

	for _, tst := range tests {
		ctx := &router.Context{
			Request: &http.Request{
				Form: tst.values,
			},
		}
		var cfg rotang.Config
		err := fillIntegers(ctx, &cfg)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: fillIntegers(_, _) = %t want: %t, err: %v", tst.name, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		if diff := pretty.Compare(tst.want, cfg); diff != "" {
			t.Errorf("%s: fillIntegers(_, _) differ -want +got %s", tst.name, diff)
		}
	}
}

func TestFillShifts(t *testing.T) {
	tests := []struct {
		name   string
		fail   bool
		values url.Values
		want   []rotang.Shift
	}{{
		name: "Single shift",
		values: url.Values{
			"addShiftName":     {"MTV All Day"},
			"addShiftDuration": {"24"},
		},
		want: []rotang.Shift{
			{
				Name:     "MTV All Day",
				Duration: 24 * time.Hour,
			},
		},
	}, {
		name: "Multiple Shifts",
		values: url.Values{
			"addShiftName":     {"MTV Half Day", "SYD Half Day"},
			"addShiftDuration": {"12", "12"},
		},
		want: []rotang.Shift{
			{
				Name:     "MTV Half Day",
				Duration: 12 * time.Hour,
			}, {
				Name:     "SYD Half Day",
				Duration: 12 * time.Hour,
			},
		},
	}, {
		name: "Not a number",
		fail: true,
		values: url.Values{
			"addShiftName":     {"MTV Half Day", "SYD Half Day"},
			"addShiftDuration": {"12", "Not a number"},
		},
	},
	}

	for _, tst := range tests {
		ctx := &router.Context{
			Request: &http.Request{
				Form: tst.values,
			},
		}
		shifts, err := fillShifts(ctx)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: fillShifts(ctx) = %t want: %t, err: %v", tst.name, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		if diff := pretty.Compare(tst.want, shifts); diff != "" {
			t.Errorf("%s: fillShifts(ctx) differs -want +got, %s", tst.name, diff)
		}
	}
}

func TestFillMembers(t *testing.T) {
	tests := []struct {
		name       string
		fail       bool
		values     url.Values
		memberPool []rotang.Member
		want       []rotang.ShiftMember
	}{{
		name: "Add single member",
		values: url.Values{
			"members": {"aa@aa.com"},
		},
		memberPool: []rotang.Member{
			{
				Email: "aa@aa.com",
			},
		},
		want: []rotang.ShiftMember{
			{
				Email: "aa@aa.com",
			},
		},
	}, {
		name: "Add multiple members",
		values: url.Values{
			"members":            {"aa@aa.com", "bb@bb.com"},
			"addEmail":           {"cc@cc.com", "dd@dd.com"},
			"addName":            {"Cc", "Dd"},
			"addMemberShiftName": {"", ""},
			"addTZ":              {"", ""},
		},
		memberPool: []rotang.Member{
			{
				Email: "aa@aa.com",
			},
			{
				Email: "bb@bb.com",
			},
		},
		want: []rotang.ShiftMember{
			{
				Email: "cc@cc.com",
			},
			{
				Email: "dd@dd.com",
			},
			{
				Email: "aa@aa.com",
			},
			{
				Email: "bb@bb.com",
			},
		},
	}, {
		name: "Member not in pool",
		fail: true,
		values: url.Values{
			"members": {"aa@aa.com"},
		},
		want: []rotang.ShiftMember{
			{
				Email: "aa@aa.com",
			},
		},
	}, {
		name: "Member with empty email",
		values: url.Values{
			"members":            {"aa@aa.com", "bb@bb.com"},
			"addEmail":           {"cc@cc.com", ""},
			"addName":            {"Cc", "Dd"},
			"addMemberShiftName": {"", ""},
			"addTZ":              {"", ""},
		},
		memberPool: []rotang.Member{
			{
				Email: "aa@aa.com",
			},
			{
				Email: "bb@bb.com",
			},
		},
		want: []rotang.ShiftMember{
			{
				Email: "cc@cc.com",
			},
			{
				Email: "aa@aa.com",
			},
			{
				Email: "bb@bb.com",
			},
		},
	},
	}

	testContext := newTestContext()
	ds := datastore.New(testContext)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := ds.CreateMember(testContext, &m); err != nil {
					t.Fatalf("%s: ds.CreateMember(ctx, _) failed: %v)", tst.name, err)
				}
				defer ds.DeleteMember(testContext, m.Email)
			}
			ctx := &router.Context{
				Context: testContext,
				Request: &http.Request{
					Form: tst.values,
				},
			}
			members, err := fillMembers(ctx, ds)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: fillMembers(_, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
			if err != nil {
				return
			}
			if diff := pretty.Compare(tst.want, members); diff != "" {
				t.Fatalf("%s: fillMembers(_, _) differs -want +got %s", tst.name, diff)
			}
		})
	}
}

func TestUpdateGET(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name       string
		rota       string
		fail       bool
		cfg        *rotang.Configuration
		ctx        *router.Context
		user       string
		memberPool []rotang.Member
	}{{
		name: "GET Success",
		user: "test@test.com",
		rota: "Test Rota",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@test.com"},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "member@test.com",
			},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/updaterota"),
		},
	}, {
		name: "Not logged in",
		fail: true,
		rota: "Test Rota",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@test.com"},
			},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/updaterota"),
		},
	}, {
		name: "No rota",
		fail: true,
		user: "test@test.com",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"test@test.com"},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "member@test.com",
			},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/updaterota"),
		},
	}, {
		name: "Not in owners",
		user: "test@test.com",
		fail: true,
		rota: "Test Rota",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:   "Test Rota",
				Owners: []string{"nottest@test.com"},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "member@test.com",
			},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/updaterota"),
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
				t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, tst.cfg.Config.Name)
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
			h.HandleUpdateRota(tst.ctx)
			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: HandleCreateRota(ctx) = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
		})
	}
}

func TestGETHandlerCreateRota(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name       string
		fail       bool
		ctx        *router.Context
		user       string
		memberPool []rotang.Member
	}{{
		name: "No members in the pool",
		user: "test@test.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/createrota"),
		},
	}, {
		name: "GET Success",
		user: "test@test.com",
		memberPool: []rotang.Member{
			{
				Email: "member@test.com",
			},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/createrota"),
		},
	}, {
		name: "Not logged in",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/createrota"),
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
			tst.ctx.Context = templates.Use(tst.ctx.Context, &templates.Bundle{
				Loader: templates.FileSystemLoader(templatesLocation),
			}, nil)
			if tst.user != "" {
				tst.ctx.Context = auth.WithState(tst.ctx.Context, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.user),
				})
			}
			h.HandleCreateRota(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: HandleCreateRota(ctx) = %t want: %t, res: %v", tst.name, got, want, recorder.Code)
			}
		})
	}
}

func TestHandleCreateRota(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		user       string
		values     url.Values
		ctx        *router.Context
		memberPool []rotang.Member
		want       rotang.Configuration
	}{{
		name: "Canceled context",
		fail: true,
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Not logged in",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Success",
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		values: url.Values{
			"Name":                 {"Test Rota"},
			"Description":          {"Test create rota"},
			"Calendar":             {"a@b.com"},
			"EmailSubjectTemplate": {"{{Subject}}"},
			"EmailBodyTemplate":    {"{{Body}}"},
			"Owners":               {"test@user.com"},
			"EmailNotify":          {"7"},
			"Expiration":           {"4"},
			"ShiftsToSchedule":     {"5"},
			"shiftLength":          {"5"},
			"shiftSkip":            {"2"},
			"shiftMembers":         {"2"},
			"shiftStart":           {"00:00"},
			"members":              {"aa@aa.com", "bb@bb.com"},
			"addName":              {"First", "Second", "Third"},
			"addMemberShiftName":   {"", "", ""},
			"addEmail":             {"first@first.com", "second@second.com", "third@third.com"},
			"addTZ":                {"America/Los_Angeles", "US/Eastern", "Asia/Tokyo"},
		},
		memberPool: []rotang.Member{
			{
				Email: "aa@aa.com",
			},
			{
				Email: "bb@bb.com",
			},
		},
		want: rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Description:      "Test create rota",
				Calendar:         "a@b.com",
				Expiration:       4,
				Owners:           []string{"test@user.com"},
				ShiftsToSchedule: 5,
				Email: rotang.Email{
					DaysBeforeNotify: 7,
					Subject:          "{{Subject}}",
					Body:             "{{Body}}",
				},
				Shifts: rotang.ShiftConfig{
					Length:       5,
					Skip:         2,
					ShiftMembers: 2,
					StartTime:    baseTime().UTC(),
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email: "first@first.com",
				},
				{
					Email: "second@second.com",
				},
				{
					Email: "third@third.com",
				},
				{
					Email: "aa@aa.com",
				},
				{
					Email: "bb@bb.com",
				},
			},
		},
	}, {
		name: "Add member mismatched fields",
		user: "test@user.com",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		values: url.Values{
			"Name":                 {"Test Rota"},
			"Description":          {"Test create rota"},
			"Calendar":             {"a@b.com"},
			"EmailSubjectTemplate": {"{{Subject}}"},
			"EmailBodyTemplate":    {"{{Body}}"},
			"Owners":               {"test@user.com"},
			"EmailNotify":          {"7"},
			"Expiration":           {"4"},
			"ShiftsToSchedule":     {"5"},
			"shiftLength":          {"5"},
			"shiftSkip":            {"2"},
			"shiftMembers":         {"2"},
			"shiftStart":           {"00:00"},
			"members":              {"aa@aa.com", "bb@bb.com"},
			"addName":              {"First", "Second", "Third"},
			"addEmail":             {"first@first.com", "second@second.com"},
			"addTZ":                {"America/Los_Angeles", "US/Eastern", "Asia/Tokyo"},
		},
		memberPool: []rotang.Member{
			{
				Email: "aa@aa.com",
			},
			{
				Email: "bb@bb.com",
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
			tst.ctx.Context = templates.Use(tst.ctx.Context, &templates.Bundle{
				Loader: templates.FileSystemLoader(templatesLocation),
			}, nil)
			if tst.user != "" {
				tst.ctx.Context = auth.WithState(tst.ctx.Context, &authtest.FakeState{
					Identity: identity.Identity("user:" + tst.user),
				})
			}
			tst.ctx.Request = httptest.NewRequest("POST", "/createrota", nil)
			tst.ctx.Request.Form = tst.values
			h.HandleCreateRota(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusFound), tst.fail; got != want {
				t.Fatalf("%s: HandleCreateRota() = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
			if recorder.Code != http.StatusFound {
				return
			}
			// Fetch the configuration.
			config, err := h.configStore(ctx).RotaConfig(ctx, tst.values["Name"][0])
			if err != nil {
				t.Fatalf("%s: Rotation(ctx, %q) failed: %v", tst.name, tst.values["Name"][0], err)
			}
			defer h.configStore(ctx).DeleteRotaConfig(ctx, tst.values["Name"][0])
			if diff := pretty.Compare(&tst.want, config[0]); diff != "" {
				t.Fatalf("%s: HandleCreateRota(ctx) differ -want +got, %s", tst.name, diff)
			}
		})
	}
}

func TestHandleUpdateRota(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	testTime, err := time.Parse("15:04", "13:37")
	if err != nil {
		t.Fatalf("time.Parse() failed: %v", err)
	}

	tests := []struct {
		name       string
		fail       bool
		user       string
		cfg        *rotang.Configuration
		values     url.Values
		ctx        *router.Context
		memberPool []rotang.Member
		want       rotang.Configuration
	}{{
		name: "Canceled context",
		fail: true,
		user: "test@user.com",
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
		name: "Not logged in",
		fail: true,
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
			},
		},
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Success",
		user: "test@user.com",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		values: url.Values{
			"Name":                 {"Test Rota"},
			"Description":          {"Changed Test create rota"},
			"Calendar":             {"changed@calendar.com"},
			"EmailSubjectTemplate": {"{{Subject Changed}}"},
			"EmailBodyTemplate":    {"{{Body Changed}}"},
			"Owners":               {"test@user.com,test2@user.com"},
			"EmailNotify":          {"1"},
			"Expiration":           {"2"},
			"ShiftsToSchedule":     {"3"},
			"shiftLength":          {"4"},
			"shiftSkip":            {"5"},
			"shiftMembers":         {"6"},
			"shiftStart":           {"00:00"},
			"memberName":           {"aa@aa.com", "bb@bb.com"},
			"memberShiftName":      {"FirstShift", "SecondShift"},
			"addName":              {"First", "Second", "Third"},
			"addMemberShiftName":   {"FirstShift", "SecondShift", "ThirdShift"},
			"addEmail":             {"first@first.com", "second@second.com", "third@third.com"},
			"addTZ":                {"America/Los_Angeles", "US/Eastern", "Asia/Tokyo"},
		},
		memberPool: []rotang.Member{
			{
				Email: "aa@aa.com",
			},
			{
				Email: "bb@bb.com",
			},
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Description:      "Test create rota",
				Calendar:         "a@b.com",
				Expiration:       4,
				Owners:           []string{"test@user.com"},
				ShiftsToSchedule: 5,
				Email: rotang.Email{
					DaysBeforeNotify: 7,
					Subject:          "{{Subject}}",
					Body:             "{{Body}}",
				},
				Shifts: rotang.ShiftConfig{
					Length:       5,
					Skip:         2,
					ShiftMembers: 2,
					StartTime:    testTime,
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "aa@aa.com",
					ShiftName: "FirstShift",
				},
				{
					Email:     "bb@bb.com",
					ShiftName: "SecondShift",
				},
			},
		},
		want: rotang.Configuration{
			Config: rotang.Config{
				Name:             "Test Rota",
				Description:      "Changed Test create rota",
				Calendar:         "changed@calendar.com",
				Expiration:       2,
				Owners:           []string{"test@user.com", "test2@user.com"},
				ShiftsToSchedule: 3,
				Email: rotang.Email{
					DaysBeforeNotify: 1,
					Subject:          "{{Subject Changed}}",
					Body:             "{{Body Changed}}",
				},
				Shifts: rotang.ShiftConfig{
					Length:       4,
					Skip:         5,
					ShiftMembers: 6,
					StartTime:    baseTime().UTC(),
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "first@first.com",
					ShiftName: "FirstShift",
				},
				{
					Email:     "second@second.com",
					ShiftName: "SecondShift",
				},
				{
					Email:     "third@third.com",
					ShiftName: "ThirdShift",
				},
				{
					Email:     "aa@aa.com",
					ShiftName: "FirstShift",
				},
				{
					Email:     "bb@bb.com",
					ShiftName: "SecondShift",
				},
			},
		},
	}, {
		name: "Add member mismatched fields",
		user: "test@user.com",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name: "Test Rota",
			},
		},
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		values: url.Values{
			"Name":                 {"Test Rota"},
			"Description":          {"Test create rota"},
			"Calendar":             {"a@b.com"},
			"EmailSubjectTemplate": {"{{Subject}}"},
			"EmailBodyTemplate":    {"{{Body}}"},
			"Owners":               {"test@user.com"},
			"EmailNotify":          {"7"},
			"Expiration":           {"4"},
			"ShiftsToSchedule":     {"5"},
			"shiftLength":          {"5"},
			"shiftSkip":            {"2"},
			"shiftMembers":         {"2"},
			"shiftStart":           {"13:37"},
			"members":              {"aa@aa.com", "bb@bb.com"},
			"addName":              {"First", "Second", "Third"},
			"addEmail":             {"first@first.com", "second@second.com"},
			"addTZ":                {"America/Los_Angeles", "US/Eastern", "Asia/Tokyo"},
		},
		memberPool: []rotang.Member{
			{
				Email: "aa@aa.com",
			},
			{
				Email: "bb@bb.com",
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
			if err := h.configStore(ctx).CreateRotaConfig(ctx, tst.cfg); err != nil {
				t.Fatalf("%s: s.CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
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
			tst.ctx.Request = httptest.NewRequest("POST", "/createrota", nil)
			tst.ctx.Request.Form = tst.values
			h.HandleUpdateRota(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusFound), tst.fail; got != want {
				t.Fatalf("%s: HandleUpdateRota() = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
			if recorder.Code != http.StatusFound {
				return
			}
			// Fetch the configuration.
			config, err := h.configStore(ctx).RotaConfig(ctx, tst.values["Name"][0])
			if err != nil {
				t.Fatalf("%s: Rotation(ctx, %q) failed: %v", tst.name, tst.values["Name"][0], err)
			}
			defer h.configStore(ctx).DeleteRotaConfig(ctx, tst.values["Name"][0])
			if diff := pretty.Compare(&tst.want, config[0]); diff != "" {
				t.Fatalf("%s: HandleCreateRota(ctx) differ -want +got, %s", tst.name, diff)
			}
		})
	}
}
