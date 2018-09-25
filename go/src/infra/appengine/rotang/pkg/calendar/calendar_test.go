package calendar

import (
	"context"
	"infra/appengine/rotang"
	"infra/appengine/rotang/pkg/datastore"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/server/router"
	"golang.org/x/oauth2"

	gcal "google.golang.org/api/calendar/v3"
)

func TestNew(t *testing.T) {

	tests := []struct {
		name   string
		fail   bool
		config *oauth2.Config
		token  *oauth2.Token
	}{
		{
			name:   "Success",
			config: &oauth2.Config{},
			token:  &oauth2.Token{},
		},
	}

	for _, tst := range tests {
		cal := New(tst.config, tst.token)
		if got, want := (cal == nil), tst.fail; got != want {
			t.Errorf("%s: New(_, _) = %t want: %t", tst.name, got, want)
			continue
		}

	}

}

func TestCreateEvent(t *testing.T) {
	ctx := gaetesting.TestingContext()
	datastore.TestTable(ctx)

	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name   string
		fail   bool
		ctx    *router.Context
		cfg    *rotang.Configuration
		shifts []rotang.ShiftEntry
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	}, {
		name: "Not implemented .. Yet",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	},
	}

	c := Calendar{}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			err := c.CreateEvent(tst.ctx, tst.cfg, tst.shifts)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: CreateEvent(ctx, _, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
		})
	}
}

func TestEvent(t *testing.T) {
	ctx := gaetesting.TestingContext()
	datastore.TestTable(ctx)

	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name  string
		fail  bool
		ctx   *router.Context
		cfg   *rotang.Configuration
		shift *rotang.ShiftEntry
		want  *rotang.ShiftEntry
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	}, {
		name: "Not implemented .. Yet",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	},
	}

	c := Calendar{}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			shift, err := c.Event(tst.ctx, tst.cfg, tst.shift)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: Event(ctx, _, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
			if err != nil {
				return
			}
			if diff := pretty.Compare(tst.want, shift); diff != "" {
				t.Fatalf("%s: Event(ctx, _, _) differ -want +got, %s", tst.name, diff)
			}
		})
	}
}

func TestEvents(t *testing.T) {
	ctx := gaetesting.TestingContext()
	datastore.TestTable(ctx)

	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name string
		fail bool
		ctx  *router.Context
		cfg  *rotang.Configuration
		from time.Time
		to   time.Time
		want []rotang.ShiftEntry
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	},
	}

	c := Calendar{}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			shifts, err := c.Events(tst.ctx, tst.cfg, tst.from, tst.to)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: Events(ctx, _, %v, %v) = %t want: %t, err: %v", tst.name, tst.from, tst.to, got, want, err)
			}
			if err != nil {
				return
			}
			if diff := pretty.Compare(tst.want, shifts); diff != "" {
				t.Fatalf("%s: Event(ctx, _, _, %v, %v) differ -want +got, %s", tst.name, tst.from, tst.to, diff)
			}
		})
	}
}

func timeMustParse(in string) time.Time {
	t, err := time.ParseInLocation(dayFormat, in, time.UTC)
	if err != nil {
		panic(err)
	}
	return t
}

func TestEventsToShifts(t *testing.T) {
	tests := []struct {
		name     string
		fail     bool
		rota     string
		event    *gcal.Events
		shiftCfg *rotang.ShiftConfig
		want     []rotang.ShiftEntry
	}{{
		name: "Empty args Context",
		fail: true,
	}, {
		name: "Simple success",
		rota: "Test Rota",
		event: &gcal.Events{
			Items: []*gcal.Event{
				{
					Attendees: []*gcal.EventAttendee{
						{
							Email:          "test1@test.com",
							ResponseStatus: "accepted",
						}, {
							Email:          "test2@test.com",
							ResponseStatus: "accepted",
						}, {
							Email:          "test3@test.com",
							ResponseStatus: "accepted",
						},
					},
					Summary: "Test Rota",
					Start: &gcal.EventDateTime{
						Date:     "2017-10-16",
						DateTime: "",
						TimeZone: "",
					},
					End: &gcal.EventDateTime{
						Date:     "2017-10-23",
						DateTime: "",
						TimeZone: "",
					},
				}, {
					Attendees: []*gcal.EventAttendee{
						{
							Email:          "test1@test.com",
							ResponseStatus: "accepted",
						}, {
							Email:          "test2@test.com",
							ResponseStatus: "accepted",
						}, {
							Email:          "test3@test.com",
							ResponseStatus: "accepted",
						},
					},
					Summary: "Test Rota",
					Start: &gcal.EventDateTime{
						Date:     "2017-10-23",
						DateTime: "",
						TimeZone: "",
					},
					End: &gcal.EventDateTime{
						Date:     "2017-10-30",
						DateTime: "",
						TimeZone: "",
					},
				},
			},
		},
		shiftCfg: &rotang.ShiftConfig{
			Shifts: []rotang.Shift{
				{
					Name:     "Test all day",
					Duration: 24 * time.Hour,
				},
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name:    "Test all day",
				Comment: "Generated from calendar event",
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "Test all day",
						Email:     "test1@test.com",
					}, {
						ShiftName: "Test all day",
						Email:     "test2@test.com",
					}, {
						ShiftName: "Test all day",
						Email:     "test3@test.com",
					},
				},
				StartTime: timeMustParse("2017-10-16"),
				EndTime:   timeMustParse("2017-10-23"),
			}, {
				Name:    "Test all day",
				Comment: "Generated from calendar event",
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "Test all day",
						Email:     "test1@test.com",
					}, {
						ShiftName: "Test all day",
						Email:     "test2@test.com",
					}, {
						ShiftName: "Test all day",
						Email:     "test3@test.com",
					},
				},
				StartTime: timeMustParse("2017-10-23"),
				EndTime:   timeMustParse("2017-10-30"),
			},
		},
	}, {
		name: "ParseLocation fail end",
		rota: "Test Rota",
		fail: true,
		event: &gcal.Events{
			Items: []*gcal.Event{
				{
					Attendees: []*gcal.EventAttendee{
						{
							Email:          "test1@test.com",
							ResponseStatus: "accepted",
						}, {
							Email:          "test2@test.com",
							ResponseStatus: "accepted",
						}, {
							Email:          "test3@test.com",
							ResponseStatus: "accepted",
						},
					},
					Summary: "Test Rota",
					Start: &gcal.EventDateTime{
						Date:     "2017-10-16",
						DateTime: "",
						TimeZone: "",
					},
					End: &gcal.EventDateTime{
						Date:     "2017-10-23",
						DateTime: "",
						TimeZone: "Edsbyn/Sverige",
					},
				},
			},
		},
		shiftCfg: &rotang.ShiftConfig{
			Shifts: []rotang.Shift{
				{
					Name:     "Test all day",
					Duration: 24 * time.Hour,
				},
			},
		},
	}, {
		name: "ParseLocation fail start",
		rota: "Test Rota",
		fail: true,
		event: &gcal.Events{
			Items: []*gcal.Event{
				{
					Attendees: []*gcal.EventAttendee{
						{
							Email:          "test1@test.com",
							ResponseStatus: "accepted",
						}, {
							Email:          "test2@test.com",
							ResponseStatus: "accepted",
						}, {
							Email:          "test3@test.com",
							ResponseStatus: "accepted",
						},
					},
					Summary: "Test Rota",
					Start: &gcal.EventDateTime{
						Date:     "2017-10-16",
						DateTime: "",
						TimeZone: "Edsbyn/Sverige",
					},
					End: &gcal.EventDateTime{
						Date:     "2017-10-23",
						DateTime: "",
						TimeZone: "",
					},
				},
			},
		},
		shiftCfg: &rotang.ShiftConfig{
			Shifts: []rotang.Shift{
				{
					Name:     "Test all day",
					Duration: 24 * time.Hour,
				},
			},
		},
	}, {
		name: "Multiple shifts",
		rota: "Test Rota",
		event: &gcal.Events{
			Items: []*gcal.Event{
				{
					Attendees: []*gcal.EventAttendee{
						{
							Email:          "test1@test.com",
							ResponseStatus: "accepted",
						}, {
							Email:          "test2@test.com",
							ResponseStatus: "accepted",
						},
					},
					Summary: "Test Rota - Shift1",
					Start: &gcal.EventDateTime{
						Date:     "2017-10-16",
						DateTime: "",
						TimeZone: "",
					},
					End: &gcal.EventDateTime{
						Date:     "2017-10-23",
						DateTime: "",
						TimeZone: "",
					},
				}, {
					Attendees: []*gcal.EventAttendee{
						{
							Email:          "test3@test.com",
							ResponseStatus: "accepted",
						}, {
							Email:          "test4@test.com",
							ResponseStatus: "accepted",
						},
					},
					Summary: "Test Rota - Shift2",
					Start: &gcal.EventDateTime{
						Date:     "2017-10-23",
						DateTime: "",
						TimeZone: "",
					},
					End: &gcal.EventDateTime{
						Date:     "2017-10-30",
						DateTime: "",
						TimeZone: "",
					},
				},
			},
		},
		shiftCfg: &rotang.ShiftConfig{
			Shifts: []rotang.Shift{
				{
					Name:     "Shift1",
					Duration: 12 * time.Hour,
				}, {
					Name:     "Shift2",
					Duration: 12 * time.Hour,
				},
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name:    "Shift1",
				Comment: "Generated from calendar event",
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "Shift1",
						Email:     "test1@test.com",
					}, {
						ShiftName: "Shift1",
						Email:     "test2@test.com",
					},
				},
				StartTime: timeMustParse("2017-10-16"),
				EndTime:   timeMustParse("2017-10-23"),
			}, {
				Name:    "Shift2",
				Comment: "Generated from calendar event",
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "Shift2",
						Email:     "test3@test.com",
					}, {
						ShiftName: "Shift2",
						Email:     "test4@test.com",
					},
				},
				StartTime: timeMustParse("2017-10-23"),
				EndTime:   timeMustParse("2017-10-30"),
			},
		},
	}, {
		name: "No shifts",
		rota: "Test Rota",
		fail: true,
		event: &gcal.Events{
			Items: []*gcal.Event{
				{
					Attendees: []*gcal.EventAttendee{
						{
							Email:          "test1@test.com",
							ResponseStatus: "accepted",
						}, {
							Email:          "test2@test.com",
							ResponseStatus: "accepted",
						},
					},
					Summary: "Test Rota - Shift1",
					Start: &gcal.EventDateTime{
						Date:     "2017-10-16",
						DateTime: "",
						TimeZone: "",
					},
					End: &gcal.EventDateTime{
						Date:     "2017-10-23",
						DateTime: "",
						TimeZone: "",
					},
				}, {
					Attendees: []*gcal.EventAttendee{
						{
							Email:          "test3@test.com",
							ResponseStatus: "accepted",
						}, {
							Email:          "test4@test.com",
							ResponseStatus: "accepted",
						},
					},
					Summary: "Test Rota - Shift2",
					Start: &gcal.EventDateTime{
						Date:     "2017-10-23",
						DateTime: "",
						TimeZone: "",
					},
					End: &gcal.EventDateTime{
						Date:     "2017-10-30",
						DateTime: "",
						TimeZone: "",
					},
				},
			},
		},
		shiftCfg: &rotang.ShiftConfig{},
	}, {
		name: "User declined",
		rota: "Test Rota",
		event: &gcal.Events{
			Items: []*gcal.Event{
				{
					Attendees: []*gcal.EventAttendee{
						{
							Email:          "test1@test.com",
							ResponseStatus: "accepted",
						}, {
							Email:          "test2@test.com",
							ResponseStatus: "declined",
						},
					},
					Summary: "Test Rota - Shift1",
					Start: &gcal.EventDateTime{
						Date:     "2017-10-16",
						DateTime: "",
						TimeZone: "",
					},
					End: &gcal.EventDateTime{
						Date:     "2017-10-23",
						DateTime: "",
						TimeZone: "",
					},
				}, {
					Attendees: []*gcal.EventAttendee{
						{
							Email:          "test3@test.com",
							ResponseStatus: "tentative",
						}, {
							Email:          "test4@test.com",
							ResponseStatus: "needsAction",
						},
					},
					Summary: "Test Rota - Shift2",
					Start: &gcal.EventDateTime{
						Date:     "2017-10-23",
						DateTime: "",
						TimeZone: "",
					},
					End: &gcal.EventDateTime{
						Date:     "2017-10-30",
						DateTime: "",
						TimeZone: "",
					},
				},
			},
		},
		shiftCfg: &rotang.ShiftConfig{
			Shifts: []rotang.Shift{
				{
					Name:     "Shift1",
					Duration: 12 * time.Hour,
				}, {
					Name:     "Shift2",
					Duration: 12 * time.Hour,
				},
			},
		},
		want: []rotang.ShiftEntry{
			{
				Name:    "Shift1",
				Comment: "Generated from calendar event",
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "Shift1",
						Email:     "test1@test.com",
					},
				},
				StartTime: timeMustParse("2017-10-16"),
				EndTime:   timeMustParse("2017-10-23"),
			}, {
				Name:    "Shift2",
				Comment: "Generated from calendar event",
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "Shift2",
						Email:     "test3@test.com",
					}, {
						ShiftName: "Shift2",
						Email:     "test4@test.com",
					},
				},
				StartTime: timeMustParse("2017-10-23"),
				EndTime:   timeMustParse("2017-10-30"),
			},
		},
	},
	}

	for _, tst := range tests {
		shifts, err := eventsToShifts(tst.event, tst.rota, tst.shiftCfg)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: eventsToShifts(_, %q, _) = %t want: %t, err: %v", tst.name, tst.rota, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		if diff := pretty.Compare(tst.want, shifts); diff != "" {
			t.Errorf("%s: eventsToShifts(_, %q, _) differ -want +got, %s", tst.name, tst.rota, diff)
		}
	}
}

func TestUpdateEvent(t *testing.T) {
	ctx := gaetesting.TestingContext()
	datastore.TestTable(ctx)

	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name  string
		fail  bool
		ctx   *router.Context
		cfg   *rotang.Configuration
		shift *rotang.ShiftEntry
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	}, {
		name: "Not implemented .. Yet",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	},
	}

	c := Calendar{}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			err := c.UpdateEvent(tst.ctx, tst.cfg, tst.shift)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: UpdateEvent(ctx, _, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
		})
	}
}

func TestDeleteEvent(t *testing.T) {
	ctx := gaetesting.TestingContext()
	datastore.TestTable(ctx)

	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name  string
		fail  bool
		ctx   *router.Context
		cfg   *rotang.Configuration
		shift *rotang.ShiftEntry
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	}, {
		name: "Not implemented .. Yet",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	},
	}

	c := Calendar{}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			err := c.DeleteEvent(tst.ctx, tst.cfg, tst.shift)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: DeleteEvent(ctx, _, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
		})
	}
}
