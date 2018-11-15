package calendar

import (
	"infra/appengine/rotang"
	"infra/appengine/rotang/pkg/datastore"
	"net/http"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
	"golang.org/x/oauth2"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	gcal "google.golang.org/api/calendar/v3"
)

var midnight = time.Date(2006, 8, 2, 0, 0, 0, 0, time.UTC)

func newTestContext() context.Context {
	ctx := gaetesting.TestingContext()
	datastore.TestTable(ctx)
	return ctx
}

func fakeFailCred(ctx context.Context) (*http.Client, error) {
	return nil, status.Errorf(codes.Internal, "test fail")
}

func fakePassCred(ctx context.Context) (*http.Client, error) {
	return &http.Client{}, nil
}

func getRequest(url string) *http.Request {
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		panic(err)
	}
	return req
}

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
		cal := New(fakePassCred)
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
		name     string
		fail     bool
		credFunc func(context.Context) (*http.Client, error)
		ctx      *router.Context
		cfg      *rotang.Configuration
		shifts   []rotang.ShiftEntry
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Request: getRequest("/"),
		},
	}, {
		name:     "Failed credentials",
		fail:     true,
		credFunc: fakeFailCred,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
	}, {
		name:     "Success credentials",
		fail:     true,
		credFunc: fakePassCred,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
	},
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			c := New(tst.credFunc)
			_, err := c.CreateEvent(tst.ctx, tst.cfg, tst.shifts)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: CreateEvent(ctx, _, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
		})
	}
}

func TestFindTrooperEvent(t *testing.T) {
	tests := []struct {
		name   string
		fail   bool
		events *gcal.Events
		match  string
		at     time.Time
		want   []string
	}{{
		name: "Success",
		events: &gcal.Events{
			Items: []*gcal.Event{
				{
					Start: &gcal.EventDateTime{
						DateTime: midnight.Add(-fullDay).Format(time.RFC3339),
					},
					End: &gcal.EventDateTime{
						DateTime: midnight.Format(time.RFC3339),
					},
					Summary: "CCI-Trooper: not1, not2, not3",
				}, {
					Start: &gcal.EventDateTime{
						DateTime: midnight.Format(time.RFC3339),
					},
					End: &gcal.EventDateTime{
						DateTime: midnight.Add(fullDay).Format(time.RFC3339),
					},
					Summary: "CCI-Trooper: this1, this2, this3",
				}, {
					Start: &gcal.EventDateTime{
						DateTime: midnight.Add(fullDay).Format(time.RFC3339),
					},
					End: &gcal.EventDateTime{
						DateTime: midnight.Add(2 * fullDay).Format(time.RFC3339),
					},
					Summary: "CCI-Trooper: nope1, nope2, nope3",
				},
			},
		},
		match: "CCI-Trooper: ",
		at:    midnight,
		want:  []string{"this1", "this2", "this3"},
	}, {
		name: "No match",
		fail: true,
		events: &gcal.Events{
			Items: []*gcal.Event{
				{
					Start: &gcal.EventDateTime{
						DateTime: midnight.Add(-fullDay).Format(time.RFC3339),
					},
					End: &gcal.EventDateTime{
						DateTime: midnight.Format(time.RFC3339),
					},
					Summary: "CCI-Trooper: not1, not2, not3",
				}, {
					Start: &gcal.EventDateTime{
						DateTime: midnight.Format(time.RFC3339),
					},
					End: &gcal.EventDateTime{
						DateTime: midnight.Add(fullDay).Format(time.RFC3339),
					},
					Summary: "Nope-Trooper: this1, this2, this3",
				}, {
					Start: &gcal.EventDateTime{
						DateTime: midnight.Add(fullDay).Format(time.RFC3339),
					},
					End: &gcal.EventDateTime{
						DateTime: midnight.Add(2 * fullDay).Format(time.RFC3339),
					},
					Summary: "CCI-Trooper: nope1, nope2, nope3",
				},
			},
		},
		match: "CCI-Trooper: ",
		at:    midnight,
		want:  []string{"this1", "this2", "this3"},
	}, {
		name: "No shift found",
		fail: true,
		events: &gcal.Events{
			Items: []*gcal.Event{
				{
					Start: &gcal.EventDateTime{
						DateTime: midnight.Add(-fullDay).Format(time.RFC3339),
					},
					End: &gcal.EventDateTime{
						DateTime: midnight.Format(time.RFC3339),
					},
					Summary: "CCI-Trooper: not1, not2, not3",
				}, {
					Start: &gcal.EventDateTime{
						DateTime: midnight.Add(fullDay).Format(time.RFC3339),
					},
					End: &gcal.EventDateTime{
						DateTime: midnight.Add(2 * fullDay).Format(time.RFC3339),
					},
					Summary: "CCI-Trooper: nope1, nope2, nope3",
				},
			},
		},
		match: "CCI-Trooper: ",
		at:    midnight,
		want:  []string{"this1", "this2", "this3"},
	},
	}

	for _, tst := range tests {
		res, err := findTrooperEvent(tst.events, tst.match, tst.at)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: findTrooperEvent(_, %q, %v) = %t want: %t, err: %v", tst.name, tst.match, tst.at, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		if diff := pretty.Compare(tst.want, res); diff != "" {
			t.Errorf("%s: findTrooperEvent(_, %q, %v) differ -want +got, %s", tst.name, tst.match, tst.at, diff)
		}
	}
}

func TestEvent(t *testing.T) {
	ctx := gaetesting.TestingContext()
	datastore.TestTable(ctx)

	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name     string
		fail     bool
		credFunc func(context.Context) (*http.Client, error)
		ctx      *router.Context
		cfg      *rotang.Configuration
		shift    *rotang.ShiftEntry
		want     *rotang.ShiftEntry
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	}, {
		name:     "Failed credentials",
		fail:     true,
		credFunc: fakeFailCred,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Calendar: "calId",
			},
		},
		shift: &rotang.ShiftEntry{
			StartTime: midnight,
			EndTime:   midnight.Add(2 * 24 * time.Hour),
		},
	}, {
		name:     "Success credentials",
		fail:     true,
		credFunc: fakePassCred,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Calendar: "calId",
			},
		},
		shift: &rotang.ShiftEntry{
			StartTime: midnight,
			EndTime:   midnight.Add(2 * 24 * time.Hour),
		},
	},
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			c := New(tst.credFunc)
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

func TestTrooperOncaller(t *testing.T) {
	ctx := gaetesting.TestingContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name     string
		fail     bool
		credFunc func(context.Context) (*http.Client, error)
		ctx      *router.Context
		testTime time.Time
		match    string
		cal      string
		want     []rotang.ShiftEntry
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	}, {
		name:     "Failed credentials",
		fail:     true,
		credFunc: fakeFailCred,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
	}, {
		name:     "Success credentials",
		fail:     true,
		credFunc: fakePassCred,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
	},
	}

	for _, tst := range tests {
		c := New(tst.credFunc)
		_, err := c.TrooperOncall(tst.ctx, tst.cal, tst.match, tst.testTime)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: TrooperOncall(ctx, %q, %q, %v) = %t want: %t, err: %v", tst.name, tst.cal, tst.match, tst.testTime, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
	}
}

func TestTrooperToShifts(t *testing.T) {
	tests := []struct {
		name   string
		fail   bool
		events *gcal.Events
		match  string
		want   []rotang.ShiftEntry
	}{{
		name: "Success",
		events: &gcal.Events{
			Items: []*gcal.Event{
				{
					Start: &gcal.EventDateTime{
						DateTime: midnight.Add(-fullDay).Format(time.RFC3339),
					},
					End: &gcal.EventDateTime{
						DateTime: midnight.Format(time.RFC3339),
					},
					Summary: "CCI-Trooper: not1, not2, not3",
				}, {
					Start: &gcal.EventDateTime{
						DateTime: midnight.Format(time.RFC3339),
					},
					End: &gcal.EventDateTime{
						DateTime: midnight.Add(fullDay).Format(time.RFC3339),
					},
					Summary: "CCI-Trooper: this1, this2, this3",
				}, {
					Start: &gcal.EventDateTime{
						DateTime: midnight.Add(fullDay).Format(time.RFC3339),
					},
					End: &gcal.EventDateTime{
						DateTime: midnight.Add(2 * fullDay).Format(time.RFC3339),
					},
					Summary: "CCI-Trooper: nope1, nope2, nope3",
				},
			},
		},
		match: "CCI-Trooper: ",
		want: []rotang.ShiftEntry{
			{
				Name:      "troopers",
				StartTime: midnight.Add(-fullDay),
				EndTime:   midnight,
				OnCall: []rotang.ShiftMember{
					{
						Email: "not1@google.com",
					}, {
						Email: "not2@google.com",
					}, {
						Email: "not3@google.com",
					},
				},
			}, {
				Name:      "troopers",
				StartTime: midnight,
				EndTime:   midnight.Add(fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email: "this1@google.com",
					}, {
						Email: "this2@google.com",
					}, {
						Email: "this3@google.com",
					},
				},
			}, {
				Name:      "troopers",
				StartTime: midnight.Add(fullDay),
				EndTime:   midnight.Add(2 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						Email: "nope1@google.com",
					}, {
						Email: "nope2@google.com",
					}, {
						Email: "nope3@google.com",
					},
				},
			},
		},
	},
	}

	for _, tst := range tests {
		res, err := trooperToShifts(tst.events, tst.match)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: trooperToShifts(_, %q) = %t want: %t, err: %v", tst.name, tst.match, got, want, err)
			continue
		}
		if err != nil {
			continue
		}

		if diff := pretty.Compare(tst.want, res); diff != "" {
			t.Errorf("%s: trooperToShifte(_, %q) differ -want +got, %s", tst.name, tst.match, diff)
		}
	}

}

func TestTrooperShifts(t *testing.T) {
	ctx := gaetesting.TestingContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name     string
		fail     bool
		credFunc func(context.Context) (*http.Client, error)
		ctx      *router.Context
		from     time.Time
		to       time.Time
		match    string
		cal      string
		want     []rotang.ShiftEntry
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	}, {
		name:     "Failed credentials",
		fail:     true,
		credFunc: fakeFailCred,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
	}, {
		name:     "Success credentials",
		fail:     true,
		credFunc: fakePassCred,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
	},
	}

	for _, tst := range tests {
		c := New(tst.credFunc)
		_, err := c.TrooperShifts(tst.ctx, tst.cal, tst.match, tst.from, tst.to)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: TrooperShifts(ctx, %q, %q, %v, %v) = %t want: %t, err: %v", tst.name, tst.cal, tst.match, tst.from, tst.to, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
	}
}

func TestEvents(t *testing.T) {
	ctx := gaetesting.TestingContext()
	datastore.TestTable(ctx)

	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name     string
		fail     bool
		credFunc func(context.Context) (*http.Client, error)
		ctx      *router.Context
		cfg      *rotang.Configuration
		from     time.Time
		to       time.Time
		want     []rotang.ShiftEntry
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	}, {
		name:     "Failed credentials",
		fail:     true,
		credFunc: fakeFailCred,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
	}, {
		name:     "Success credentials",
		fail:     true,
		credFunc: fakePassCred,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Calendar: "calId",
			},
		},
	},
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			c := New(tst.credFunc)
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

func TestFindShifts(t *testing.T) {
	ctx := newTestContext()

	tests := []struct {
		name   string
		fail   bool
		shifts []rotang.ShiftEntry
		find   *rotang.ShiftEntry
		want   *rotang.ShiftEntry
	}{{
		name: "Shift found",
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(2 * 24 * time.Hour),
				EvtID:     "ID1",
			}, {
				Name:      "MTV All Day",
				StartTime: midnight.Add(2 * 24 * time.Hour),
				EndTime:   midnight.Add(4 * 24 * time.Hour),
				EvtID:     "ID2",
			},
		},
		find: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight.Add(2 * 24 * time.Hour),
			EndTime:   midnight.Add(4 * 24 * time.Hour),
		},
		want: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight.Add(2 * 24 * time.Hour),
			EndTime:   midnight.Add(4 * 24 * time.Hour),
			EvtID:     "ID2",
		},
	}, {
		name: "Shift ID found",
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(2 * 24 * time.Hour),
				EvtID:     "ID1",
			}, {
				Name:      "MTV All Day",
				StartTime: midnight.Add(2 * 24 * time.Hour),
				EndTime:   midnight.Add(4 * 24 * time.Hour),
				EvtID:     "ID2",
			},
		},
		find: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight.Add(2 * 24 * time.Hour),
			EndTime:   midnight.Add(4 * 24 * time.Hour),
			EvtID:     "ID2",
		},
		want: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight.Add(2 * 24 * time.Hour),
			EndTime:   midnight.Add(4 * 24 * time.Hour),
			EvtID:     "ID2",
		},
	}, {
		name: "Shift not found",
		fail: true,
		shifts: []rotang.ShiftEntry{
			{
				Name:      "MTV All Day",
				StartTime: midnight,
				EndTime:   midnight.Add(2 * 24 * time.Hour),
				EvtID:     "ID1",
			}, {
				Name:      "MTV All Day",
				StartTime: midnight.Add(2 * 24 * time.Hour),
				EndTime:   midnight.Add(4 * 24 * time.Hour),
				EvtID:     "ID2",
			},
		},
		find: &rotang.ShiftEntry{
			Name:      "MTV All Day",
			StartTime: midnight.Add(4 * 24 * time.Hour),
			EndTime:   midnight.Add(6 * 24 * time.Hour),
			EvtID:     "ID3",
		},
	},
	}

	for _, tst := range tests {
		shift, err := findShifts(ctx, tst.shifts, tst.find)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: findShifts(ctx, _, _) = %t want: %t, err: %v", tst.name, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		if diff := pretty.Compare(tst.want, shift); diff != "" {
			t.Errorf("%s: findShifts(crt, _, _) differ -want +got, %s", tst.name, diff)
		}
	}
}

func timeMustParse(in string) time.Time {
	t, err := time.ParseInLocation(dayFormat, in, mtvTime)
	if err != nil {
		panic(err)
	}
	return t
}

func TestShiftsToEvents(t *testing.T) {
	tests := []struct {
		name   string
		fail   bool
		cfg    *rotang.Configuration
		shifts []rotang.ShiftEntry
		want   []*gcal.Event
	}{{
		name: "Empty args",
		fail: true,
	}, {
		name: "Simple success",
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Name:        "Test Rota",
				Description: "Calendar desc",
				Shifts: rotang.ShiftConfig{
					Shifts: []rotang.Shift{
						{
							Name: "MTV All Day",
						},
					},
				},
			},
		},
		shifts: []rotang.ShiftEntry{
			{
				Name: "MTV All Day",
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "test1@test.com",
					},
				},
				StartTime: midnight,
				EndTime:   midnight.Add(2 * 24 * time.Hour),
			},
		},
		want: []*gcal.Event{
			{
				Summary: "Test Rota",
				Attendees: []*gcal.EventAttendee{
					{
						Email: "test1@test.com",
					},
				},
				Description: "Calendar desc",
				Start: &gcal.EventDateTime{
					DateTime: midnight.Format(time.RFC3339),
				},
				End: &gcal.EventDateTime{
					DateTime: midnight.Add(2 * 24 * time.Hour).Format(time.RFC3339),
				},
			},
		},
	},
	}

	for _, tst := range tests {
		shifts, err := shiftsToEvents(tst.cfg, tst.shifts)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: shiftsToEvents(_, _) = %t want: %t, err: %v", tst.name, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		if diff := pretty.Compare(tst.want, shifts); diff != "" {
			t.Errorf("%s: shiftsToEvents(_, _) differ -want +got, %s", tst.name, diff)
		}
	}
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
					Id:      "Test ID1",
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
					Id:      "Test ID2",
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
				EvtID:     "Test ID1",
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
				EvtID:     "Test ID2",
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
					Id:      "Test ID1",
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
					Id:      "Test ID1",
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
					Id:      "Test ID1",
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
					Id:      "Test ID2",
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
				EvtID:     "Test ID1",
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
				EvtID:     "Test ID2",
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
					Id:      "Test ID1",
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
					Id:      "Test ID2",
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
					Id:      "Test ID1",
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
					Id:      "Test ID2",
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
				EvtID:     "Test ID1",
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
				EvtID:     "Test ID2",
				StartTime: timeMustParse("2017-10-23"),
				EndTime:   timeMustParse("2017-10-30"),
			},
		},
	}, {
		name: "No Start Time",
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
					Id:      "Test ID1",
					Summary: "Test Rota",
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
					Id:      "Test ID2",
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
				StartTime: timeMustParse("2017-10-23"),
				EndTime:   timeMustParse("2017-10-30"),
				EvtID:     "Test ID2",
			},
		},
	}, {
		name: "No End Time",
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
					Id:      "Test ID1",
					Summary: "Test Rota",
					Start: &gcal.EventDateTime{
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
					Id:      "Test ID2",
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
				StartTime: timeMustParse("2017-10-23"),
				EndTime:   timeMustParse("2017-10-30"),
				EvtID:     "Test ID2",
			},
		},
	},
	}

	ctx := gaetesting.TestingContext()

	for _, tst := range tests {
		shifts, err := eventsToShifts(ctx, tst.event, tst.rota, tst.shiftCfg)
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
		name     string
		fail     bool
		credFunc func(context.Context) (*http.Client, error)
		ctx      *router.Context
		cfg      *rotang.Configuration
		shift    *rotang.ShiftEntry
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	}, {
		name:     "Failed credentials",
		fail:     true,
		credFunc: fakeFailCred,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
	}, {
		name:     "Success credentials",
		fail:     true,
		credFunc: fakePassCred,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Calendar: "Cal ID",
			},
		},
		shift: &rotang.ShiftEntry{
			StartTime: midnight,
			EndTime:   midnight.Add(2 * 24 * time.Hour),
		},
	},
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			c := New(tst.credFunc)
			_, err := c.UpdateEvent(tst.ctx, tst.cfg, tst.shift)
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
		name     string
		fail     bool
		credFunc func(context.Context) (*http.Client, error)
		ctx      *router.Context
		cfg      *rotang.Configuration
		shift    *rotang.ShiftEntry
	}{{
		name: "Canceled Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
		},
	}, {
		name:     "Failed credentials",
		fail:     true,
		credFunc: fakeFailCred,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
	}, {
		name:     "Success credentials",
		fail:     true,
		credFunc: fakePassCred,
		ctx: &router.Context{
			Context: ctx,
			Request: getRequest("/"),
		},
		cfg: &rotang.Configuration{
			Config: rotang.Config{
				Calendar: "Cal ID",
			},
		},
		shift: &rotang.ShiftEntry{
			StartTime: midnight,
			EndTime:   midnight.Add(2 * 24 * time.Hour),
		},
	},
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			c := New(tst.credFunc)
			err := c.DeleteEvent(tst.ctx, tst.cfg, tst.shift)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: DeleteEvent(ctx, _, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
		})
	}
}
