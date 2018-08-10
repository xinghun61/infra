package datastore

import (
	"sort"
	"testing"
	"time"

	"infra/appengine/rotang"

	"golang.org/x/net/context"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"
)

func newTestContext() context.Context {
	ctx := gaetesting.TestingContext()
	testing := datastore.GetTestable(ctx)
	testing.Consistent(true)
	testing.AutoIndex(true)
	return ctx
}

var locationUTC = func() *time.Location {
	utcTZ, err := time.LoadLocation("UTC")
	if err != nil {
		panic(err)
	}
	return utcTZ
}()

func TestMemberOf(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		ctx        context.Context
		email      string
		memberPool []rotang.Member
		rotas      []rotang.Configuration
		want       []string
	}{{
		name:  "Failed context",
		fail:  true,
		ctx:   ctxCancel,
		email: "doesntmatter@google.com",
		memberPool: []rotang.Member{
			{
				Name:  "Test Bot",
				Email: "letestbot@google.com",
			},
			{
				Name:  "Test Sheriff",
				Email: "testsheriff@google.com",
			},
			{
				Name:  "Another Test Sheriff",
				Email: "anothersheriff@google.com",
			},
		},
		rotas: []rotang.Configuration{
			{
				Config: rotang.Config{
					Description:    "Test description",
					Name:           "Sheriff Oncall Rotation",
					Calendar:       "testCalendarLink@testland.com",
					DaysToSchedule: 10,
					Email: rotang.Email{
						Subject: "Chrome OS build sheriff reminder",
						Body:    "Some reminder",
					},
					Shifts: rotang.ShiftConfig{
						ShiftMembers: 1,
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email: "letestbot@google.com",
					},
					{
						Email: "testsheriff@google.com",
					},
					{
						Email: "anothersheriff@google.com",
					},
				},
			},
		},
		want: []string{"doesntmatter@google.com"},
	}, {
		name:  "Member of single rota",
		ctx:   ctx,
		email: "matters@google.com",
		memberPool: []rotang.Member{
			{
				Name:  "Test Bot",
				Email: "matters@google.com",
			},
			{
				Name:  "Test Sheriff",
				Email: "testsheriff@google.com",
			},
			{
				Name:  "Another Test Sheriff",
				Email: "anothersheriff@google.com",
			},
		},
		rotas: []rotang.Configuration{
			{
				Config: rotang.Config{
					Description:    "Test description",
					Name:           "Sheriff Oncall Rotation",
					Calendar:       "testCalendarLink@testland.com",
					DaysToSchedule: 10,
					Email: rotang.Email{
						Subject: "Chrome OS build sheriff reminder",
						Body:    "Some reminder",
					},
					Shifts: rotang.ShiftConfig{
						ShiftMembers: 1,
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email: "matters@google.com",
					},
					{
						Email: "testsheriff@google.com",
					},
					{
						Email: "anothersheriff@google.com",
					},
				},
			},
		},
		want: []string{"Sheriff Oncall Rotation"},
	}, {
		name:  "Member of multiple rotas",
		ctx:   ctx,
		email: "matters@google.com",
		memberPool: []rotang.Member{
			{
				Name:  "Test Bot",
				Email: "matters@google.com",
			},
			{
				Name:  "Test Sheriff",
				Email: "testsheriff@google.com",
			},
			{
				Name:  "Another Test Sheriff",
				Email: "anothersheriff@google.com",
			},
		},
		rotas: []rotang.Configuration{
			{
				Config: rotang.Config{
					Description:    "Test description",
					Name:           "Sheriff Oncall Rotation",
					Calendar:       "testCalendarLink@testland.com",
					DaysToSchedule: 10,
					Email: rotang.Email{
						Subject: "Chrome OS build sheriff reminder",
						Body:    "Some reminder",
					},
					Shifts: rotang.ShiftConfig{
						ShiftMembers: 1,
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email: "matters@google.com",
					},
					{
						Email: "testsheriff@google.com",
					},
					{
						Email: "anothersheriff@google.com",
					},
				},
			}, {
				Config: rotang.Config{
					Description:    "Test description",
					Name:           "Test Rota",
					Calendar:       "testCalendarLink@testland.com",
					DaysToSchedule: 10,
					Email: rotang.Email{
						Subject: "Chrome OS build sheriff reminder",
						Body:    "Some reminder",
					},
					Shifts: rotang.ShiftConfig{
						ShiftMembers: 1,
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email: "matters@google.com",
					},
					{
						Email: "testsheriff@google.com",
					},
					{
						Email: "anothersheriff@google.com",
					},
				},
			},
		},
		want: []string{"Sheriff Oncall Rotation", "Test Rota"},
	}, {
		name:  "Not a member of any rotas",
		ctx:   ctx,
		email: "matters@google.com",
		memberPool: []rotang.Member{
			{
				Name:  "Test Bot",
				Email: "matters@google.com",
			},
			{
				Name:  "Test Sheriff",
				Email: "testsheriff@google.com",
			},
			{
				Name:  "Another Test Sheriff",
				Email: "anothersheriff@google.com",
			},
		},
		rotas: []rotang.Configuration{
			{
				Config: rotang.Config{
					Description:    "Test description",
					Name:           "Sheriff Oncall Rotation",
					Calendar:       "testCalendarLink@testland.com",
					DaysToSchedule: 10,
					Email: rotang.Email{
						Subject: "Chrome OS build sheriff reminder",
						Body:    "Some reminder",
					},
					Shifts: rotang.ShiftConfig{
						ShiftMembers: 1,
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email: "testsheriff@google.com",
					},
					{
						Email: "anothersheriff@google.com",
					},
				},
			}, {
				Config: rotang.Config{
					Description:    "Test description",
					Name:           "Test Rota",
					Calendar:       "testCalendarLink@testland.com",
					DaysToSchedule: 10,
					Email: rotang.Email{
						Subject: "Chrome OS build sheriff reminder",
						Body:    "Some reminder",
					},
					Shifts: rotang.ShiftConfig{
						ShiftMembers: 1,
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email: "testsheriff@google.com",
					},
					{
						Email: "anothersheriff@google.com",
					},
				},
			},
		},
	}, {
		name:  "Member of some rotas",
		ctx:   ctx,
		email: "matters@google.com",
		memberPool: []rotang.Member{
			{
				Name:  "Test Bot",
				Email: "matters@google.com",
			},
			{
				Name:  "Test Sheriff",
				Email: "testsheriff@google.com",
			},
			{
				Name:  "Another Test Sheriff",
				Email: "anothersheriff@google.com",
			},
		},
		rotas: []rotang.Configuration{
			{
				Config: rotang.Config{
					Description:    "Test description",
					Name:           "Sheriff Oncall Rotation",
					Calendar:       "testCalendarLink@testland.com",
					DaysToSchedule: 10,
					Email: rotang.Email{
						Subject: "Chrome OS build sheriff reminder",
						Body:    "Some reminder",
					},
					Shifts: rotang.ShiftConfig{
						ShiftMembers: 1,
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email: "matters@google.com",
					},
					{
						Email: "testsheriff@google.com",
					},
					{
						Email: "anothersheriff@google.com",
					},
				},
			}, {
				Config: rotang.Config{
					Description:    "Test description",
					Name:           "Test Rota",
					Calendar:       "testCalendarLink@testland.com",
					DaysToSchedule: 10,
					Email: rotang.Email{
						Subject: "Chrome OS build sheriff reminder",
						Body:    "Some reminder",
					},
					Shifts: rotang.ShiftConfig{
						ShiftMembers: 1,
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email: "testsheriff@google.com",
					},
					{
						Email: "anothersheriff@google.com",
					},
				},
			}, {
				Config: rotang.Config{
					Description:    "Test description",
					Name:           "Second Test Rota",
					Calendar:       "testCalendarLink@testland.com",
					DaysToSchedule: 10,
					Email: rotang.Email{
						Subject: "Chrome OS build sheriff reminder",
						Body:    "Some reminder",
					},
					Shifts: rotang.ShiftConfig{
						ShiftMembers: 1,
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email: "matters@google.com",
					},
					{
						Email: "testsheriff@google.com",
					},
					{
						Email: "anothersheriff@google.com",
					},
				},
			},
		},
		want: []string{"Sheriff Oncall Rotation", "Second Test Rota"},
	},
	}

	s, err := New(ctx)
	if err != nil {
		t.Fatalf("New(_) failed: %v", err)
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := s.CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: s.CreateMember(_, _) failed: %v", tst.name, err)
				}
				defer s.DeleteMember(ctx, m.Email)
			}
			for _, cfg := range tst.rotas {
				if err := s.CreateRotaConfig(ctx, &cfg); err != nil {
					t.Fatalf("%s: s.CreateRotaConfig(_, _) failed: %v", tst.name, err)
				}
				defer s.DeleteRotaConfig(ctx, cfg.Config.Name)
			}
			res, err := s.MemberOf(tst.ctx, tst.email)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: s.MemberOf(_, %q) = %t want: %t, err: %v", tst.name, tst.email, got, want, err)
			}
			if err != nil {
				return
			}
			sort.Strings(tst.want)
			sort.Strings(res)
			if diff := pretty.Compare(tst.want, res); diff != "" {
				t.Fatalf("%s: s.MemberOf(_, %q) differs -want +got: %s", tst.name, tst.email, diff)
			}
		})
	}
}

func TestMember(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name  string
		ctx   context.Context
		fail  bool
		email string
		store []rotang.Member
		want  rotang.Member
	}{{
		name:  "Canceled context",
		fail:  true,
		email: "notmatter@test.se",
		ctx:   ctxCancel,
		store: []rotang.Member{
			{
				Email: "notmatter@test.se",
			},
		},
	}, {
		name:  "Success fetching member",
		ctx:   ctx,
		email: "oncall@dot.com",
		store: []rotang.Member{
			{
				Name:      "Primary Oncaller",
				Email:     "oncall@dot.com",
				ShiftName: "MTV shift",
				TZ:        *locationUTC,
			},
		},
		want: rotang.Member{
			Name:      "Primary Oncaller",
			Email:     "oncall@dot.com",
			ShiftName: "MTV shift",
			TZ:        *locationUTC,
		},
	}, {
		name:  "Member not found",
		fail:  true,
		ctx:   ctx,
		email: "notfound@dot.com",
		store: []rotang.Member{
			{
				Name:      "Primary Oncaller",
				Email:     "oncall@dot.com",
				ShiftName: "MTV shift",
				TZ:        *locationUTC,
			},
		},
		want: rotang.Member{
			Name:      "Primary Oncaller",
			Email:     "oncall@dot.com",
			ShiftName: "MTV shift",
			TZ:        *locationUTC,
		},
	}, {
		name: "Empty eMail",
		fail: true,
		ctx:  ctx,
		store: []rotang.Member{
			{
				Name:      "Primary Oncaller",
				Email:     "oncall@dot.com",
				ShiftName: "MTV shift",
				TZ:        *locationUTC,
			},
		},
	},
	}

	store, err := New(ctx)
	if err != nil {
		t.Fatalf("New(_) failed: %v", err)
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, sm := range tst.store {
				if err := store.CreateMember(ctx, &sm); err != nil {
					t.Fatalf("%s: store.CreateMember(_, _) failed: %v", tst.name, err)
				}
				defer func() {
					if err := store.DeleteMember(ctx, sm.Email); err != nil {
						t.Logf("%s: store.DeleteMember(ctx, sm.Email) failed: %v", tst.name, err)
					}
				}()
			}
			m, err := store.Member(tst.ctx, tst.email)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: store.Member(_, %q) = %t want: %t, err: %v", tst.name, tst.email, got, want, err)
			}
			if err != nil {
				return
			}
			if diff := pretty.Compare(tst.want, m); diff != "" {
				t.Fatalf("%s: store.Member(_, %q) differs -want +got: %s", tst.name, tst.email, diff)
			}
		})
	}
}

func TestUpdateMember(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name   string
		fail   bool
		ctx    context.Context
		store  []rotang.Member
		update *rotang.Member
	}{{
		name: "Canceled context",
		fail: true,
		ctx:  ctxCancel,
	}, {
		name: "Update sucess",
		ctx:  ctx,
		store: []rotang.Member{
			{
				Name:      "Before update",
				Email:     "oncall@dot.com",
				ShiftName: "MTV shift",
				TZ:        *locationUTC,
			},
		},
		update: &rotang.Member{
			Name:      "After update",
			Email:     "oncall@dot.com",
			ShiftName: "MTV shift",
			TZ:        *locationUTC,
		},
	}, {
		name: "No email",
		fail: true,
		ctx:  ctx,
		store: []rotang.Member{
			{
				Name:      "Before update",
				Email:     "oncall@dot.com",
				ShiftName: "MTV shift",
				TZ:        *locationUTC,
			},
		},
		update: &rotang.Member{
			Name:      "After update",
			ShiftName: "MTV shift",
			TZ:        *locationUTC,
		},
	}, {
		name: "Member not exist",
		fail: true,
		ctx:  ctx,
		store: []rotang.Member{
			{
				Name:      "Before update",
				Email:     "oncall@dot.com",
				ShiftName: "MTV shift",
				TZ:        *locationUTC,
			},
		},
		update: &rotang.Member{
			Name:      "After update",
			Email:     "not-exist@dot.com",
			ShiftName: "MTV shift",
			TZ:        *locationUTC,
		},
	}}

	store, err := New(ctx)
	if err != nil {
		t.Fatalf("New(_) failed: %v", err)
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, sm := range tst.store {
				if err := store.CreateMember(ctx, &sm); err != nil {
					t.Fatalf("%s: store.CreateMember(_, _) failed: %v", tst.name, err)
				}
				defer func() {
					if err := store.DeleteMember(ctx, sm.Email); err != nil {
						t.Logf("%s: store.DeleteMember(ctx, sm.Email) failed: %v", tst.name, err)
					}
				}()
			}
			err := store.UpdateMember(tst.ctx, tst.update)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: store.UpdateMember(_, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
			if err != nil {
				return
			}
			m, err := store.Member(ctx, tst.update.Email)
			if err != nil {
				t.Fatalf("%s: store.Member(_, %q) failed: %v", tst.name, tst.update.Email, err)
			}
			if diff := pretty.Compare(tst.update, m); diff != "" {
				t.Fatalf("%s: store.Member(_, %q) differ -want +got: %s", tst.name, tst.update.Email, diff)
			}
		})
	}
}

func TestDeleteMember(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name  string
		fail  bool
		ctx   context.Context
		email string
		store []rotang.Member
	}{{
		name:  "Canceled context",
		fail:  true,
		email: "a@b.com",
		ctx:   ctxCancel,
		store: []rotang.Member{
			{
				Name:      "Primary Oncaller",
				Email:     "oncall@dot.com",
				ShiftName: "MTV shift",
				TZ:        *locationUTC,
			},
		},
	}, {
		name:  "Delete success",
		email: "oncall@dot.com",
		ctx:   ctx,
		store: []rotang.Member{
			{
				Name:      "Primary Oncaller",
				Email:     "oncall@dot.com",
				ShiftName: "MTV shift",
				TZ:        *locationUTC,
			},
		},
	}, {
		name:  "Delete not-exist",
		email: "noexist@dot.com",
		ctx:   ctx,
		store: []rotang.Member{
			{
				Name:      "Primary Oncaller",
				Email:     "oncall@dot.com",
				ShiftName: "MTV shift",
				TZ:        *locationUTC,
			},
		},
	},
	}

	store, err := New(ctx)
	if err != nil {
		t.Fatalf("New(_) failed: %v", err)
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, sm := range tst.store {
				if err := store.CreateMember(ctx, &sm); err != nil {
					t.Fatalf("%s: store.CreateMember(_, _) failed: %v", tst.name, err)
				}
				defer func() {
					if err := store.DeleteMember(ctx, sm.Email); err != nil {
						t.Logf("%s: store.DeleteMember(ctx, sm.Email) failed: %v", tst.name, err)
					}
				}()
			}
			err := store.DeleteMember(tst.ctx, tst.email)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: store.DeleteMember(_, %q) = %t want: %t, err: %v", tst.name, tst.email, got, want, err)
			}
		})
	}
}

func TestCreateMember(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name   string
		ctx    context.Context
		fail   bool
		email  string
		store  []rotang.Member
		create *rotang.Member
	}{{
		name:  "Canceled context",
		fail:  true,
		email: "notmatter@test.se",
		ctx:   ctxCancel,
		create: &rotang.Member{
			Email: "notmatter@test.se",
		},
	}, {
		name:  "Success creating member",
		ctx:   ctx,
		email: "oncall@dot.com",
		create: &rotang.Member{
			Name:      "Primary Oncaller",
			Email:     "oncall@dot.com",
			ShiftName: "MTV shift",
			TZ:        *locationUTC,
		},
	}, {
		name: "Empty eMail",
		fail: true,
		ctx:  ctx,
		create: &rotang.Member{
			Name:      "Primary Oncaller",
			ShiftName: "MTV shift",
			TZ:        *locationUTC,
		},
	}, {
		name:  "Already existing member",
		fail:  true,
		ctx:   ctx,
		email: "oncall@dot.com",
		store: []rotang.Member{
			{
				Name:      "Primary Oncaller",
				Email:     "oncall@dot.com",
				ShiftName: "MTV shift",
				TZ:        *locationUTC,
			},
		},
		create: &rotang.Member{
			Name:      "Primary Oncaller",
			Email:     "oncall@dot.com",
			ShiftName: "MTV shift",
			TZ:        *locationUTC,
		},
	},
	}

	store, err := New(ctx)
	if err != nil {
		t.Fatalf("New(_) failed: %v", err)
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, sm := range tst.store {
				if err := store.CreateMember(ctx, &sm); err != nil {
					t.Fatalf("%s: store.CreateMember(_, _) failed: %v", tst.name, err)
				}
				defer func() {
					if err := store.DeleteMember(ctx, sm.Email); err != nil {
						t.Logf("%s: store.DeleteMember(ctx, sm.Email) failed: %v", tst.name, err)
					}
				}()
			}
			err := store.CreateMember(tst.ctx, tst.create)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: store.CreateMember(_, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
			if err != nil {
				return
			}
			defer func() {
				if err := store.DeleteMember(ctx, tst.email); err != nil {
					t.Logf("%s: store.DeleteMember(ctx, sm.Email) failed: %v", tst.name, err)
				}
			}()

			m, err := store.Member(ctx, tst.email)
			if err != nil {
				t.Fatalf("%s: store.Member(_, %q) failed: %v", tst.name, tst.email, err)
			}
			if err != nil {
				return
			}
			if diff := pretty.Compare(tst.create, m); diff != "" {
				t.Fatalf("%s: store.Member(_, %q) differs -want +got: %s", tst.name, tst.email, diff)
			}
		})
	}
}

func TestStoreConfiguration(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		ctx        context.Context
		fail       bool
		in         rotang.Configuration
		memberPool []rotang.Member
	}{
		{
			name: "Store success",
			ctx:  ctx,
			in: rotang.Configuration{
				Config: rotang.Config{
					Description:    "Test description",
					Name:           "Sheriff Oncall Rotation",
					Calendar:       "testCalendarLink@testland.com",
					DaysToSchedule: 10,
					Email: rotang.Email{
						Subject: "Chrome OS build sheriff reminder",
						Body:    "Some reminder",
					},
					Shifts: rotang.ShiftConfig{
						ShiftMembers: 1,
					},
				},
				Members: []rotang.ShiftMember{
					{
						Email: "letestbot@google.com",
					},
					{
						Email: "testsheriff@google.com",
					},
					{
						Email: "anothersheriff@google.com",
					},
				},
			},
			memberPool: []rotang.Member{
				{
					Name:  "Test Bot",
					Email: "letestbot@google.com",
				},
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
				{
					Name:  "Another Test Sheriff",
					Email: "anothersheriff@google.com",
				},
			},
		}, {
			name: "Store invalid context",
			ctx:  ctxCancel,
			in: rotang.Configuration{
				Config: rotang.Config{
					Name: "bleh",
				},
			},
			fail: true,
		},
	}

	store, err := New(ctx)
	if err != nil {
		t.Fatalf("New(_) failed: %v", err)
	}

L1:
	for _, tst := range tests {
		for _, m := range tst.memberPool {
			if err := store.CreateMember(ctx, &m); err != nil {
				t.Errorf("%s: store.CreateMember(_, _) failed: %v", tst.name, err)
				continue L1
			}
			// TODO(olakar): Fix this.
			defer store.DeleteMember(ctx, m.Email)
		}
		err := store.CreateRotaConfig(tst.ctx, &tst.in)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: datastore.StoreRota() = %t want: %t, err: %v", tst.name, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		got, err := store.RotaConfig(ctx, tst.in.Config.Name)
		if err != nil {
			t.Fatalf("%s: FetchRota(ctx, %q) failed: %v", tst.name, tst.in.Config.Name, err)
		}
		sort.Slice(tst.in.Members, func(i, j int) bool {
			return tst.in.Members[i].Email < tst.in.Members[j].Email
		})
		sort.Slice(got[0].Members, func(i, j int) bool {
			return got[0].Members[i].Email < got[0].Members[j].Email
		})
		if diff := pretty.Compare(tst.in, got[0]); diff != "" {
			t.Errorf("%s: FetchRota(ctx, \"Chrome OS Build Sheriff\") differs -want +got: %v", tst.name, diff)
		}
	}
}

func TestUpdateRotaConfig(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		ctx        context.Context
		memberPool []rotang.Member
		put        []rotang.Configuration
		update     *rotang.Configuration
	}{
		{
			name: "Canceled context",
			fail: true,
			ctx:  ctxCancel,
			memberPool: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
			},
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test update",
					},
				},
			},
			update: &rotang.Configuration{
				Config: rotang.Config{
					Name:        "test update",
					Description: "Updatet desc",
				},
			},
		}, {
			name: "Simple working",
			ctx:  ctx,
			memberPool: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
			},
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test update",
					},
				},
			},
			update: &rotang.Configuration{
				Config: rotang.Config{
					Name:        "test update",
					Description: "Updatet desc",
					Shifts:      rotang.ShiftConfig{},
				},
			},
		}, {
			name: "Configuration don't exist",
			ctx:  ctx,
			fail: true,
			memberPool: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
			},
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "Something different",
					},
				},
			},
			update: &rotang.Configuration{
				Config: rotang.Config{
					Name:        "test update",
					Description: "Updatet desc",
					Shifts:      rotang.ShiftConfig{},
				},
			},
		},
	}

	s, err := New(ctx)
	if err != nil {
		t.Fatalf("New(_) failed: %v", err)
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := s.CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: store.CreateMember(_, _) failed: %v", tst.name, err)
				}
				defer s.DeleteMember(ctx, m.Email)
			}
			for _, cfg := range tst.put {
				if err := s.CreateRotaConfig(ctx, &cfg); err != nil {
					t.Fatalf("%s: s.StoreRotaConfig(ctx, _) failed: %v", tst.name, err)
				}
				defer s.DeleteRotaConfig(ctx, cfg.Config.Name)
			}
			err := s.UpdateRotaConfig(tst.ctx, tst.update)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: s.UpdateRotaConfig(_, _) = %t want: %t, err: %v", tst.name, got, want, err)
			}
			if err != nil {
				return
			}
			res, err := s.RotaConfig(ctx, tst.update.Config.Name)
			if err != nil {
				t.Fatalf("%s: s.RotaConfig(_, %q) failed: %v", tst.name, tst.update.Config.Name, err)
			}
			if diff := pretty.Compare(tst.update, res[0]); diff != "" {
				t.Fatalf("%s: s.UpdateRotaConfig(_, _) differs -want +got: %s", tst.name, diff)
			}

		})
	}
}

func TestFetchConfiguration(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		ctx        context.Context
		memberPool []rotang.Member
		put        []rotang.Configuration
		get        string
		want       []rotang.Configuration
	}{
		{
			name: "Single Fetch",
			ctx:  ctx,
			memberPool: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
			},
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
					},
				},
			},
			get: "test fetch",
			want: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
					},
				},
			},
		},
		{
			name: "Fetch non exist",
			fail: true,
			ctx:  ctx,
			memberPool: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
			},
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
					},
				},
			},
			get: "test non exist",
			want: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
					},
				},
			},
		},
		{
			name: "Fetch cancelled ctx",
			fail: true,
			ctx:  ctxCancel,
			memberPool: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
			},
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
					},
				},
			},
			get: "test fetch",
		},
		{
			name: "Fetch multiple",
			ctx:  ctx,
			memberPool: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
			},
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "ChromeOS Sheriff",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
					},
				},
				{
					Config: rotang.Config{
						Name: "Chromium Sheriff",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
					},
				},
			},
			want: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "ChromeOS Sheriff",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
					},
				},
				{
					Config: rotang.Config{
						Name: "Chromium Sheriff",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
					},
				},
			},
		},
		{
			name: "Rota does not exist",
			fail: true,
			ctx:  ctx,
			memberPool: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
			},
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "ChromeOS Sheriff",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
					},
				},
			},
			get: "non-exist",
		},
		{
			name: "Fetch all no rotas",
			fail: true,
			ctx:  ctx,
		},
	}

	s, err := New(ctx)
	if err != nil {
		t.Fatalf("New(_) failed: %v", err)
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := s.CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: s.CreateMember(_, _) failed: %v", tst.name, err)
				}
				defer s.DeleteMember(ctx, m.Email)
			}
			for _, cfg := range tst.put {
				if err := s.CreateRotaConfig(ctx, &cfg); err != nil {
					t.Fatalf("%s: s.StoreRotaConfig(ctx,_) failed: %v", tst.name, err)
				}
				defer datastore.Delete(ctx, &DsRotaConfig{
					Key: rootKey(ctx),
					ID:  cfg.Config.Name,
				})
			}
			got, err := s.RotaConfig(tst.ctx, tst.get)
			if got, want := (err != nil), tst.fail; got != want {
				t.Errorf("%s: s.FetchRotaConfig(ctx,%q) = %t want: %t, err: %v", tst.name, tst.get, got, want, err)
				return
			}
			if err != nil {
				return
			}

			sort.Slice(got, func(i, j int) bool {
				return got[i].Config.Name < got[j].Config.Name
			})
			sort.Slice(tst.put, func(i, j int) bool {
				return tst.put[i].Config.Name < tst.put[j].Config.Name
			})
			if diff := pretty.Compare(tst.want, got); diff != "" {
				t.Errorf("%s: s.FetchRota(ctx, %q) differs -want +got: %s", tst.name, tst.get, diff)
			}
		})
	}
}

func TestDeleteConfiguration(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		memberPool []rotang.Member
		ctx        context.Context
		put        []rotang.Configuration
		in         string
	}{
		{
			name: "Delete success",
			ctx:  ctx,
			memberPool: []rotang.Member{
				{
					Name:  "Test Bot",
					Email: "letestbot@google.com",
				},
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
				{
					Name:  "Another Test Sheriff",
					Email: "anothersheriff@google.com",
				},
			},
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
					},
				},
			},
			in: "test fetch",
		},
		{
			name: "Cancelled context",
			ctx:  ctxCancel,
			fail: true,
			memberPool: []rotang.Member{
				{
					Name:  "Test Bot",
					Email: "letestbot@google.com",
				},
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
				{
					Name:  "Another Test Sheriff",
					Email: "anothersheriff@google.com",
				},
			},
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
					},
				},
			},
			in: "test fetch",
		},
	}

	s, err := New(ctx)
	if err != nil {
		t.Fatalf("New(_) failed: %v", err)
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := s.CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: store.CreateMember(_, _) failed: %v", tst.name, err)
				}
				defer s.DeleteMember(ctx, m.Email)
			}
			for _, cfg := range tst.put {
				if err := s.CreateRotaConfig(ctx, &cfg); err != nil {
					t.Fatalf("%s: s.StoraRotaConfig(ctx,_) failed: %v", tst.name, err)
				}
				defer datastore.Delete(ctx, &DsRotaConfig{
					ID: cfg.Config.Name,
				})
			}
			if got, want := s.DeleteRotaConfig(tst.ctx, tst.in) != nil, tst.fail; got != want {
				t.Errorf("%s: s.DeleteRotaConfig(ctx, %q) = %t want: %t, err: %v", tst.name, tst.in, got, want, got)
				return
			}
		})
	}
}

func TestAddMember(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		memberPool []rotang.Member
		ctx        context.Context
		put        rotang.Configuration
		rota       string
		in         rotang.ShiftMember
		want       []rotang.ShiftMember
	}{
		{
			name: "AddMember success",
			ctx:  ctx,
			memberPool: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
				{
					Name:  "Another Test Sheriff",
					Email: "brandnew@google.com",
				},
			},
			rota: "test fetch",
			put: rotang.Configuration{
				Config: rotang.Config{
					Name: "test fetch",
				},
				Members: []rotang.ShiftMember{
					{
						Email: "testsheriff@google.com",
					},
				},
			},
			in: rotang.ShiftMember{
				Email: "brandnew@google.com",
			},
			want: []rotang.ShiftMember{
				{
					Email: "testsheriff@google.com",
				}, {
					Email: "brandnew@google.com",
				},
			},
		},
		{
			name: "Expired context",
			ctx:  ctxCancel,
			memberPool: []rotang.Member{
				{
					Name:  "Another Test Sheriff",
					Email: "brandnew@google.com",
				},
			},
			rota: "Dont matter",
			fail: true,
			in: rotang.ShiftMember{
				Email: "brandnew@google.com",
			},
			put: rotang.Configuration{
				Config: rotang.Config{
					Name: "Dont matter",
				},
				Members: []rotang.ShiftMember{
					{
						Email: "brandnew@google.com",
					},
				},
			},
		},
		{
			name: "Rota no exist",
			ctx:  ctx,
			memberPool: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
			},
			fail: true,
			rota: "Dont exist",
			put: rotang.Configuration{
				Config: rotang.Config{
					Name: "test fetch",
				},
				Members: []rotang.ShiftMember{
					{
						Email: "testsheriff@google.com",
					},
				},
			},
		},
		{
			name: "Existing member",
			fail: true,
			memberPool: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
			},
			ctx:  ctx,
			rota: "test fetch",
			put: rotang.Configuration{
				Config: rotang.Config{
					Name: "test fetch",
				},
				Members: []rotang.ShiftMember{
					{
						Email: "testsheriff@google.com",
					},
				},
			},
			in: rotang.ShiftMember{
				Email: "testsheriff@google.com",
			},
			want: []rotang.ShiftMember{
				{
					Email: "testsheriff@google.com",
				},
			},
		},
	}

	s, err := New(ctx)
	if err != nil {
		t.Fatalf("New(_) failed: %v", err)
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := s.CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: store.CreateMember(_, _) failed: %v", tst.name, err)
				}
				defer s.DeleteMember(ctx, m.Email)
			}

			if err := s.CreateRotaConfig(ctx, &tst.put); err != nil {
				t.Fatalf("%s: s.CreateRotaConfig(ctx,_) failed: %v", tst.name, err)
			}
			defer s.DeleteRotaConfig(ctx, tst.put.Config.Name)

			err := s.AddRotaMember(tst.ctx, tst.rota, tst.in)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: s.AddRotaMember(ctx, %q, _) = %t want: %t, err: %v", tst.name, tst.rota, got, want, err)
			}
			if err != nil {
				return
			}
			resRota, err := s.RotaConfig(ctx, tst.put.Config.Name)
			if err != nil {
				t.Fatalf("%s: s.RotaConfig(ctx, %q) failed: %v", tst.name, tst.put.Config.Name, err)
			}
			if len(resRota) != 1 {
				t.Fatalf("%s: s.RotaConfig(ctx, %q) = %d want: %d, number of results differ", tst.name, tst.put.Config.Name, len(resRota), -1)
			}
			sort.Slice(resRota[0].Members, func(i, j int) bool {
				return resRota[0].Members[i].Email < resRota[0].Members[j].Email
			})
			sort.Slice(tst.want, func(i, j int) bool {
				return tst.want[i].Email < tst.want[j].Email
			})
			if diff := pretty.Compare(tst.want, resRota[0].Members); diff != "" {
				t.Fatalf("%s: s.AddRotaMember(ctx, %q, _) differs -want +got: %s", tst.name, tst.rota, diff)
			}
		})
	}
}

func TestDeleteRotaMember(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name       string
		fail       bool
		memberPool []rotang.Member
		ctx        context.Context
		put        []rotang.Configuration
		rota       string
		email      string
		want       []rotang.ShiftMember
	}{
		{
			name: "Delete Success",
			ctx:  ctx,
			memberPool: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
			},
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
					},
				},
			},
			rota:  "test fetch",
			email: "testsheriff@google.com",
		},
		{
			name: "Expired Context",
			ctx:  ctxCancel,
			memberPool: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
			},
			fail: true,
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
					},
				},
			},
			rota:  "test fetch",
			email: "testsheriff@google.com",
		},
		{
			name: "Delete with multiple rotas and members",
			ctx:  ctx,
			memberPool: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
				},
				{
					Name:  "Test Sheriff2",
					Email: "testsheriff2@google.com",
				},
				{
					Name:  "Test Sheriff3",
					Email: "testsheriff3@google.com",
				},
			},
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "rota-one",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
						{
							Email: "testsheriff2@google.com",
						},
						{
							Email: "testsheriff3@google.com",
						},
					},
				},
				{
					Config: rotang.Config{
						Name: "rota-two",
					},
					Members: []rotang.ShiftMember{
						{
							Email: "testsheriff@google.com",
						},
						{
							Email: "testsheriff2@google.com",
						},
						{
							Email: "testsheriff3@google.com",
						},
					},
				},
			},
			rota:  "rota-one",
			email: "testsheriff2@google.com",
			want: []rotang.ShiftMember{
				{
					Email: "testsheriff@google.com",
				},
				{
					Email: "testsheriff3@google.com",
				},
			},
		},
	}

	s, err := New(ctx)
	if err != nil {
		t.Fatalf("New(_) failed: %v", err)
	}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, m := range tst.memberPool {
				if err := s.CreateMember(ctx, &m); err != nil {
					t.Fatalf("%s: store.CreateMember(_, _) failed: %v", tst.name, err)
				}
				defer s.DeleteMember(ctx, m.Email)
			}
			for _, cfg := range tst.put {
				if err := s.CreateRotaConfig(ctx, &cfg); err != nil {
					t.Fatalf("%s: s.StoraRotaConfig(ctx,_) failed: %v", tst.name, err)
				}
				defer s.DeleteRotaConfig(ctx, cfg.Config.Name)
			}
			err := s.DeleteRotaMember(tst.ctx, tst.rota, tst.email)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: s.DeleteRotaMember(ctx, %q, %q) = %t want: %t, err: %v", tst.name, tst.rota, tst.email, got, want, err)
			}
			if err != nil {
				return
			}
			resRota, err := s.RotaConfig(ctx, tst.rota)
			if err != nil {
				t.Fatalf("%s: s.FetchRotaConfig(ctx, %q) failed: %v", tst.name, tst.rota, err)
			}
			if len(resRota) != 1 {
				t.Fatalf("%s: s.FetchRotaConfig(ctx, %q) = %d want: %d, number of results differ", tst.name, tst.rota, len(resRota), -1)
			}
			sort.Slice(resRota[0].Members, func(i, j int) bool {
				return resRota[0].Members[i].Email < resRota[0].Members[j].Email
			})
			sort.Slice(tst.want, func(i, j int) bool {
				return tst.want[i].Email < tst.want[j].Email
			})
			if diff := pretty.Compare(tst.want, resRota[0].Members); diff != "" {
				t.Fatalf("%s: s.DeleteRotaMember(ctx, %q, %s) differs -want +got: %s", tst.name, tst.rota, tst.email, diff)
			}
		})
	}
}
