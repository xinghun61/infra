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
	"go.chromium.org/gae/service/mail"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"golang.org/x/net/context"
)

type testableMail struct{}

func (t *testableMail) Send(ctx context.Context, msg *mail.Message) error {
	return mail.Send(ctx, msg)
}

var midnight = time.Date(2006, 1, 2, 0, 0, 0, 0, time.UTC)

const pacificTZ = "US/Pacific"

func TestJobEmail(t *testing.T) {

	mtvTime, err := time.LoadLocation(pacificTZ)
	if err != nil {
		t.Fatalf("time.LoadLocation(%q) failed: %v", pacificTZ, err)
	}

	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		ctx        *router.Context
		cfg        *rotang.Configuration
		time       time.Time
		memberPool []rotang.Member
		shifts     []rotang.ShiftEntry
		want       []mail.Message
	}{{
		name: "Canceled context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "Test Rota",
				Enabled:     true,
			},
		},
	}, {
		name: "No rotations",
		fail: true,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
	}, {
		name: "Don't send email when notify is 0",
		time: midnight,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "Test Rota",
				Enabled:     true,
				Email: rotang.Email{
					Subject:          "Some subject",
					Body:             "Some Body",
					DaysBeforeNotify: 0,
				},
				Shifts: rotang.ShiftConfig{
					StartTime: midnight,
					Length:    1,
					Skip:      2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV all day",
							Duration: 8 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email: "oncaller@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller@oncall.com",
					},
				},
				StartTime: midnight.Add(4 * 24 * time.Hour),
				EndTime:   midnight.Add(8*time.Hour + 4*24*time.Hour),
			},
		},
	}, {
		name: "No email if rota is not enabled",
		time: midnight,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "Test Rota",
				Email: rotang.Email{
					Subject:          "Some subject",
					Body:             "Some Body",
					DaysBeforeNotify: 4,
				},
				Shifts: rotang.ShiftConfig{
					StartTime: midnight,
					Length:    1,
					Skip:      2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV all day",
							Duration: 8 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email: "oncaller@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller@oncall.com",
					},
				},
				StartTime: midnight.Add(4 * 24 * time.Hour),
				EndTime:   midnight.Add(8*time.Hour + 4*24*time.Hour),
			},
		},
	}, {
		name: "Email success",
		time: midnight,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Enabled:     true,
				Name:        "Test Rota",
				Email: rotang.Email{
					Subject: `Upcoming On-call shift for rotation: {{.RotaName}} {{.ShiftEntry.StartTime.In .Member.TZ}} to {{.ShiftEntry.EndTime.In .Member.TZ}}`,
					Body: `Hi {{.Member.Name}}.
This is  a friendly reminder that you're oncall for {{.RotaName}} from {{.ShiftEntry.StartTime.In .Member.TZ}} to {{.ShiftEntry.EndTime.In .Member.TZ}}`,
					DaysBeforeNotify: 4,
				},
				Shifts: rotang.ShiftConfig{
					StartTime: midnight,
					Length:    1,
					Skip:      2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV all day",
							Duration: 24 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email:     "oncaller@oncall.com",
					ShiftName: "MTV all day",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller@oncall.com",
				Name:  "Test Namesson",
				TZ:    *mtvTime,
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email:     "oncaller@oncall.com",
						ShiftName: "MTV all day",
					},
				},
				StartTime: midnight.Add(4 * 24 * time.Hour),
				EndTime:   midnight.Add(5 * 24 * time.Hour),
			},
		},
		want: []mail.Message{
			{
				Sender:  "admin@example.com",
				To:      []string{"oncaller@oncall.com"},
				Subject: "Upcoming On-call shift for rotation: Test Rota 2006-01-05 16:00:00 -0800 PST to 2006-01-06 16:00:00 -0800 PST",
				Body: `Hi Test Namesson.
This is  a friendly reminder that you're oncall for Test Rota from 2006-01-05 16:00:00 -0800 PST to 2006-01-06 16:00:00 -0800 PST`,
			},
		},
	}, {
		name: "Nobody on call",
		time: midnight,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "Test Rota",
				Enabled:     true,
				Email: rotang.Email{
					Subject:          "Some subject",
					Body:             "Some Body",
					DaysBeforeNotify: 4,
				},
				Shifts: rotang.ShiftConfig{
					StartTime: midnight,
					Length:    1,
					Skip:      2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV all day",
							Duration: 8 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email: "oncaller@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller@oncall.com",
					},
				},
				StartTime: midnight.Add(8 * 24 * time.Hour),
				EndTime:   midnight.Add(8*time.Hour + 8*24*time.Hour),
			},
		},
	}, {
		name: "Multiple Emails",
		time: midnight,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "Test Rota",
				Enabled:     true,
				Email: rotang.Email{
					Subject:          "Some subject",
					Body:             "Some Body",
					DaysBeforeNotify: 4,
				},
				Shifts: rotang.ShiftConfig{
					StartTime: midnight,
					Length:    1,
					Skip:      2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV all day",
							Duration: 8 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email: "oncaller@oncall.com",
				},
				{
					Email: "secondary@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "oncaller@oncall.com",
			},
			{
				Email: "secondary@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						Email: "oncaller@oncall.com",
					},
					{
						Email: "secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(4 * 24 * time.Hour),
				EndTime:   midnight.Add(8*time.Hour + 4*24*time.Hour),
			},
		},
		want: []mail.Message{
			{
				Sender:  "admin@example.com",
				To:      []string{"oncaller@oncall.com"},
				Subject: "Some subject",
				Body:    "Some Body",
			},
			{
				Sender:  "admin@example.com",
				To:      []string{"secondary@oncall.com"},
				Subject: "Some subject",
				Body:    "Some Body",
			},
		},
	}, {
		name: "Multiple Shifts",
		time: midnight,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "Test Rota",
				Enabled:     true,
				Email: rotang.Email{
					Subject:          "Some subject",
					Body:             "Some Body",
					DaysBeforeNotify: 4,
				},
				Shifts: rotang.ShiftConfig{
					StartTime: midnight,
					Length:    1,
					Skip:      2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV Office Hours",
							Duration: 8 * time.Hour,
						},
						{
							Name:     "SYD Office Hours",
							Duration: 8 * time.Hour,
						},
						{
							Name:     "EU Office Hours",
							Duration: 8 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email: "us_oncaller@oncall.com",
				},
				{
					Email: "us_secondary@oncall.com",
				},
				{
					Email: "syd_oncaller@oncall.com",
				},
				{
					Email: "syd_secondary@oncall.com",
				},
				{
					Email: "eu_oncaller@oncall.com",
				},
				{
					Email: "eu_secondary@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "us_oncaller@oncall.com",
			},
			{
				Email: "us_secondary@oncall.com",
			},
			{
				Email: "syd_oncaller@oncall.com",
			},
			{
				Email: "syd_secondary@oncall.com",
			},
			{
				Email: "eu_oncaller@oncall.com",
			},
			{
				Email: "eu_secondary@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "us_oncaller@oncall.com",
					},
					{
						Email: "us_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(4 * 24 * time.Hour),
				EndTime:   midnight.Add(8*time.Hour + 4*24*time.Hour),
			}, {
				Name: "SYD Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "syd_oncaller@oncall.com",
					},
					{
						Email: "syd_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(8*time.Hour + 4*24*time.Hour),
				EndTime:   midnight.Add(16*time.Hour + 4*24*time.Hour),
			}, {
				Name: "EU Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "eu_oncaller@oncall.com",
					},
					{
						Email: "eu_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(16*time.Hour + 4*24*time.Hour),
				EndTime:   midnight.Add(24*time.Hour + 4*24*time.Hour),
			},
		},
		want: []mail.Message{
			{
				Sender:  "admin@example.com",
				To:      []string{"us_oncaller@oncall.com"},
				Subject: "Some subject",
				Body:    "Some Body",
			},
			{
				Sender:  "admin@example.com",
				To:      []string{"us_secondary@oncall.com"},
				Subject: "Some subject",
				Body:    "Some Body",
			},
			{
				Sender:  "admin@example.com",
				To:      []string{"syd_oncaller@oncall.com"},
				Subject: "Some subject",
				Body:    "Some Body",
			},
			{
				Sender:  "admin@example.com",
				To:      []string{"syd_secondary@oncall.com"},
				Subject: "Some subject",
				Body:    "Some Body",
			},
			{
				Sender:  "admin@example.com",
				To:      []string{"eu_oncaller@oncall.com"},
				Subject: "Some subject",
				Body:    "Some Body",
			},
			{
				Sender:  "admin@example.com",
				To:      []string{"eu_secondary@oncall.com"},
				Subject: "Some subject",
				Body:    "Some Body",
			},
		},
	}, {
		name: "Multiple day Shifts",
		time: midnight,
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Description: "Test",
				Name:        "Test Rota",
				Enabled:     true,
				Email: rotang.Email{
					Subject:          "Some subject",
					Body:             "Some Body",
					DaysBeforeNotify: 4,
				},
				Shifts: rotang.ShiftConfig{
					StartTime: midnight,
					Length:    5,
					Skip:      2,
					Shifts: []rotang.Shift{
						{
							Name:     "MTV Office Hours",
							Duration: 8 * time.Hour,
						},
						{
							Name:     "SYD Office Hours",
							Duration: 8 * time.Hour,
						},
						{
							Name:     "EU Office Hours",
							Duration: 8 * time.Hour,
						},
					},
				},
			},
			Members: []rotang.ShiftMember{
				{
					Email: "us_oncaller@oncall.com",
				},
				{
					Email: "us_secondary@oncall.com",
				},
				{
					Email: "syd_oncaller@oncall.com",
				},
				{
					Email: "syd_secondary@oncall.com",
				},
				{
					Email: "eu_oncaller@oncall.com",
				},
				{
					Email: "eu_secondary@oncall.com",
				},
			},
		},
		memberPool: []rotang.Member{
			{
				Email: "us_oncaller@oncall.com",
			},
			{
				Email: "us_secondary@oncall.com",
			},
			{
				Email: "syd_oncaller@oncall.com",
			},
			{
				Email: "syd_secondary@oncall.com",
			},
			{
				Email: "eu_oncaller@oncall.com",
			},
			{
				Email: "eu_secondary@oncall.com",
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "us_oncaller@oncall.com",
					},
					{
						Email: "us_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(4 * 24 * time.Hour),
				EndTime:   midnight.Add(8*time.Hour + 4*24*time.Hour),
			}, {
				Name: "SYD Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "syd_oncaller@oncall.com",
					},
					{
						Email: "syd_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(8*time.Hour + 4*24*time.Hour),
				EndTime:   midnight.Add(16*time.Hour + 4*24*time.Hour),
			}, {
				Name: "EU Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "eu_oncaller@oncall.com",
					},
					{
						Email: "eu_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(16*time.Hour + 4*24*time.Hour),
				EndTime:   midnight.Add(24*time.Hour + 4*24*time.Hour),
			},
			{
				Name: "MTV Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "us_oncaller@oncall.com",
					},
					{
						Email: "us_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(5 * time.Hour),
				EndTime:   midnight.Add(8*time.Hour + 5*24*time.Hour),
			}, {
				Name: "SYD Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "syd_oncaller@oncall.com",
					},
					{
						Email: "syd_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(8*time.Hour + 5*24*time.Hour),
				EndTime:   midnight.Add(16*time.Hour + 5*24*time.Hour),
			}, {
				Name: "EU Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "eu_oncaller@oncall.com",
					},
					{
						Email: "eu_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(16*time.Hour + 5*24*time.Hour),
				EndTime:   midnight.Add(24*time.Hour + 5*24*time.Hour),
			},
			{
				Name: "MTV Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "us_oncaller@oncall.com",
					},
					{
						Email: "us_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(6 * time.Hour),
				EndTime:   midnight.Add(8*time.Hour + 6*24*time.Hour),
			}, {
				Name: "SYD Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "syd_oncaller@oncall.com",
					},
					{
						Email: "syd_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(8*time.Hour + 6*24*time.Hour),
				EndTime:   midnight.Add(16*time.Hour + 6*24*time.Hour),
			}, {
				Name: "EU Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "eu_oncaller@oncall.com",
					},
					{
						Email: "eu_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(16*time.Hour + 6*24*time.Hour),
				EndTime:   midnight.Add(24*time.Hour + 6*24*time.Hour),
			},
			{
				Name: "MTV Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "us_oncaller@oncall.com",
					},
					{
						Email: "us_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(7 * time.Hour),
				EndTime:   midnight.Add(8*time.Hour + 7*24*time.Hour),
			}, {
				Name: "SYD Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "syd_oncaller@oncall.com",
					},
					{
						Email: "syd_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(8*time.Hour + 7*24*time.Hour),
				EndTime:   midnight.Add(16*time.Hour + 7*24*time.Hour),
			}, {
				Name: "EU Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "eu_oncaller@oncall.com",
					},
					{
						Email: "eu_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(16*time.Hour + 7*24*time.Hour),
				EndTime:   midnight.Add(24*time.Hour + 7*24*time.Hour),
			},
			{
				Name: "MTV Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "us_oncaller@oncall.com",
					},
					{
						Email: "us_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(8 * time.Hour),
				EndTime:   midnight.Add(8*time.Hour + 8*24*time.Hour),
			}, {
				Name: "SYD Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "syd_oncaller@oncall.com",
					},
					{
						Email: "syd_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(8*time.Hour + 8*24*time.Hour),
				EndTime:   midnight.Add(16*time.Hour + 8*24*time.Hour),
			}, {
				Name: "EU Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "eu_oncaller@oncall.com",
					},
					{
						Email: "eu_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(16*time.Hour + 8*24*time.Hour),
				EndTime:   midnight.Add(24*time.Hour + 8*24*time.Hour),
			},
			{
				Name: "MTV Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "us_oncaller@oncall.com",
					},
					{
						Email: "us_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(9 * time.Hour),
				EndTime:   midnight.Add(8*time.Hour + 9*24*time.Hour),
			}, {
				Name: "SYD Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "syd_oncaller@oncall.com",
					},
					{
						Email: "syd_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(8*time.Hour + 9*24*time.Hour),
				EndTime:   midnight.Add(16*time.Hour + 9*24*time.Hour),
			}, {
				Name: "EU Office Hours",
				OnCall: []rotang.ShiftMember{
					{
						Email: "eu_oncaller@oncall.com",
					},
					{
						Email: "eu_secondary@oncall.com",
					},
				},
				StartTime: midnight.Add(16*time.Hour + 9*24*time.Hour),
				EndTime:   midnight.Add(24*time.Hour + 9*24*time.Hour),
			},
		},
		want: []mail.Message{
			{
				Sender:  "admin@example.com",
				To:      []string{"us_oncaller@oncall.com"},
				Subject: "Some subject",
				Body:    "Some Body",
			},
			{
				Sender:  "admin@example.com",
				To:      []string{"us_secondary@oncall.com"},
				Subject: "Some subject",
				Body:    "Some Body",
			},
			{
				Sender:  "admin@example.com",
				To:      []string{"syd_oncaller@oncall.com"},
				Subject: "Some subject",
				Body:    "Some Body",
			},
			{
				Sender:  "admin@example.com",
				To:      []string{"syd_secondary@oncall.com"},
				Subject: "Some subject",
				Body:    "Some Body",
			},
			{
				Sender:  "admin@example.com",
				To:      []string{"eu_oncaller@oncall.com"},
				Subject: "Some subject",
				Body:    "Some Body",
			},
			{
				Sender:  "admin@example.com",
				To:      []string{"eu_secondary@oncall.com"},
				Subject: "Some subject",
				Body:    "Some Body",
			},
		},
	}}

	opts := Options{
		URL:         "http://localhost:8080",
		Generators:  &algo.Generators{},
		MailSender:  &testableMail{},
		MailAddress: "admin@example.com",
		Calendar:    &calendar.Calendar{},
	}
	setupStoreHandlers(&opts, datastore.New)
	h, err := New(&opts)
	if err != nil {
		t.Fatalf("New failed: %v", err)
	}

	testMail := mail.GetTestable(ctx)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			if tst.cfg != nil {
				for _, m := range tst.memberPool {
					if err := h.memberStore(ctx).CreateMember(ctx, &m); err != nil {
						t.Fatalf("%s: s.CreateMember(_, _) failed: %v", tst.name, err)
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
			}

			testMail.Reset()
			ctx := clock.Set(tst.ctx.Context, testclock.New(tst.time))

			tst.ctx.Context = templates.Use(ctx, &templates.Bundle{
				Loader: templates.FileSystemLoader(templatesLocation),
			}, nil)

			h.JobEmail(tst.ctx)

			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Fatalf("%s: JobEmail() = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
			}
			if recorder.Code != http.StatusOK {
				return
			}

			var gotMsg []mail.Message
			for _, m := range testMail.SentMessages() {
				gotMsg = append(gotMsg, m.Message)
			}

			if diff := pretty.Compare(tst.want, gotMsg); diff != "" {
				t.Fatalf("%s: JobEmail(ctx) differ -want +got, %s", tst.name, diff)
			}
		})
	}
}
