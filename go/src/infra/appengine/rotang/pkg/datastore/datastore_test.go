package datastore

import (
	"sort"
	"testing"
	"time"

	"infra/appengine/rotang/pkg/rotang"

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

func TestStore(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name string
		ctx  context.Context
		fail bool
		in   rotang.Configuration
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
				Rotation: rotang.Members{
					Members: []rotang.Member{
						{
							Name:  "French Test Bot",
							Email: "letestbot@google.com",
							TZ:    *locationUTC,
						},
						{
							Name:  "Test Sheriff",
							Email: "testsheriff@google.com",
							TZ:    *locationUTC,
						},
						{
							Name:  "Yet Another Test Sheriff",
							Email: "anothersheriff@google.com",
							TZ:    *locationUTC,
						},
					},
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

	store := New()

	for _, tst := range tests {
		err := store.StoreRotaConfig(tst.ctx, &tst.in)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: datastore.StoreRota() = %t want: %t, err: %v", tst.name, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		got, err := store.FetchRotaConfig(ctx, tst.in.Config.Name)
		if err != nil {
			t.Fatalf("%s: FetchRota(ctx, %q) failed: %v", tst.name, tst.in.Config.Name, err)
		}
		sort.Slice(tst.in.Rotation.Members, func(i, j int) bool {
			return tst.in.Rotation.Members[i].Email < tst.in.Rotation.Members[j].Email
		})
		sort.Slice(got[0].Rotation.Members, func(i, j int) bool {
			return got[0].Rotation.Members[i].Email < got[0].Rotation.Members[j].Email
		})
		if diff := pretty.Compare(tst.in, got[0]); diff != "" {
			t.Errorf("%s: FetchRota(ctx, \"Chrome OS Build Sheriff\") differs -want +got: %v", tst.name, diff)
		}
	}
}

func TestFetch(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name string
		fail bool
		ctx  context.Context
		put  []rotang.Configuration
		get  string
		want []rotang.Configuration
	}{
		{
			name: "Single Fetch",
			ctx:  ctx,
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
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
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
						},
					},
				},
			},
		},
		{
			name: "Fetch non exist",
			fail: true,
			ctx:  ctx,
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
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
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
						},
					},
				},
			},
		},
		{
			name: "Fetch cancelled ctx",
			fail: true,
			ctx:  ctxCancel,
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
						},
					},
				},
			},
			get: "test fetch",
		},
		{
			name: "Fetch multiple",
			ctx:  ctx,
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "ChromeOS Sheriff",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
						},
					},
				},
				{
					Config: rotang.Config{
						Name: "Chromium Sheriff",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
						},
					},
				},
			},
			want: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "ChromeOS Sheriff",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
						},
					},
				},
				{
					Config: rotang.Config{
						Name: "Chromium Sheriff",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
						},
					},
				},
			},
		},
		{
			name: "Overwrite",
			ctx:  ctx,
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "ChromeOS Sheriff",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
						},
					},
				},
				{
					Config: rotang.Config{
						Name: "ChromeOS Sheriff",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Second Test Sheriff",
								Email: "second+testsheriff@google.com",
								TZ:    *locationUTC,
							},
						},
					},
				},
			},
			want: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "ChromeOS Sheriff",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Second Test Sheriff",
								Email: "second+testsheriff@google.com",
								TZ:    *locationUTC,
							},
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
						},
					},
				},
			},
		},
		{
			name: "Rota does not exist",
			fail: true,
			ctx:  ctx,
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "ChromeOS Sheriff",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
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

	s := New()

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, cfg := range tst.put {
				if err := s.StoreRotaConfig(ctx, &cfg); err != nil {
					t.Fatalf("%s: s.StoreRotaConfig(ctx,_) failed: %v", tst.name, err)
				}
				defer datastore.Delete(ctx, &DsRotaConfig{
					ID: cfg.Config.Name,
				})
			}
			got, err := s.FetchRotaConfig(tst.ctx, tst.get)
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

func TestDelete(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name string
		fail bool
		ctx  context.Context
		put  []rotang.Configuration
		in   string
	}{
		{
			name: "Delete success",
			ctx:  ctx,
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
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
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
						},
					},
				},
			},
			in: "test fetch",
		},
	}

	s := New()

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, cfg := range tst.put {
				if err := s.StoreRotaConfig(ctx, &cfg); err != nil {
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
		name string
		fail bool
		ctx  context.Context
		put  rotang.Configuration
		rota string
		in   rotang.Member
		want []rotang.Member
	}{
		{
			name: "AddMember success",
			ctx:  ctx,
			rota: "test fetch",
			put: rotang.Configuration{
				Config: rotang.Config{
					Name: "test fetch",
				},
				Rotation: rotang.Members{
					Members: []rotang.Member{
						{
							Name:  "Test Sheriff",
							Email: "testsheriff@google.com",
						},
					},
				},
			},
			in: rotang.Member{
				Name:  "New member",
				Email: "brandnew@google.com",
			},
			want: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
					TZ:    *locationUTC,
				}, {
					Name:  "New member",
					Email: "brandnew@google.com",
					TZ:    *locationUTC,
				},
			},
		},
		{
			name: "Expired context",
			ctx:  ctxCancel,
			fail: true,
		},
		{
			name: "Rota no exist",
			ctx:  ctx,
			fail: true,
			rota: "Don not exist",
			put: rotang.Configuration{
				Config: rotang.Config{
					Name: "test fetch",
				},
				Rotation: rotang.Members{
					Members: []rotang.Member{
						{
							Name:  "Test Sheriff",
							Email: "testsheriff@google.com",
						},
					},
				},
			},
		},
		{
			name: "Existing member",
			ctx:  ctx,
			rota: "test fetch",
			put: rotang.Configuration{
				Config: rotang.Config{
					Name: "test fetch",
				},
				Rotation: rotang.Members{
					Members: []rotang.Member{
						{
							Name:  "Test Sheriff",
							Email: "testsheriff@google.com",
						},
					},
				},
			},
			in: rotang.Member{
				Name:  "Overwritten Test Sheriff",
				Email: "testsheriff@google.com",
			},
			want: []rotang.Member{
				{
					Name:  "Overwritten Test Sheriff",
					Email: "testsheriff@google.com",
					TZ:    *locationUTC,
				},
			},
		},
	}

	s := New()

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			if err := s.StoreRotaConfig(ctx, &tst.put); err != nil {
				t.Fatalf("%s: s.StoraRotaConfig(ctx,_) failed: %v", tst.name, err)
			}
			defer s.DeleteRotaConfig(ctx, tst.put.Config.Name)

			err := s.AddMember(tst.ctx, tst.rota, tst.in)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: s.AddMember(ctx, %q, _) = %t want: %t, err: %v", tst.name, tst.rota, got, want, err)
			}
			if err != nil {
				return
			}
			resRota, err := s.FetchRotaConfig(ctx, tst.put.Config.Name)
			if err != nil {
				t.Fatalf("%s: s.FetchRotaConfig(ctx, %q) failed: %v", tst.name, tst.put.Config.Name, err)
			}
			if len(resRota) != 1 {
				t.Fatalf("%s: s.FetchRotaConfig(ctx, %q) = %d want: %d, number of results differ", tst.name, tst.put.Config.Name, len(resRota), -1)
			}
			sort.Slice(resRota[0].Rotation.Members, func(i, j int) bool {
				return resRota[0].Rotation.Members[i].Email < resRota[0].Rotation.Members[j].Email
			})
			sort.Slice(tst.want, func(i, j int) bool {
				return tst.want[i].Email < tst.want[j].Email
			})
			if diff := pretty.Compare(tst.want, resRota[0].Rotation.Members); diff != "" {
				t.Fatalf("%s: s.AddMember(ctx, %q, _) differs -want +got: %s", tst.name, tst.rota, diff)
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
		put   []rotang.Configuration
		rota  string
		email string
		want  []rotang.Member
	}{
		{
			name: "Delete Success",
			ctx:  ctx,
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
							},
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
			fail: true,
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "test fetch",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
							{
								Name:  "Test Sheriff",
								Email: "testsheriff@google.com",
								TZ:    *locationUTC,
							},
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
			put: []rotang.Configuration{
				{
					Config: rotang.Config{
						Name: "rota-one",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
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
					},
				},
				{
					Config: rotang.Config{
						Name: "rota-two",
					},
					Rotation: rotang.Members{
						Members: []rotang.Member{
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
					},
				},
			},
			rota:  "rota-one",
			email: "testsheriff2@google.com",
			want: []rotang.Member{
				{
					Name:  "Test Sheriff",
					Email: "testsheriff@google.com",
					TZ:    *locationUTC,
				},
				{
					Name:  "Test Sheriff3",
					Email: "testsheriff3@google.com",
					TZ:    *locationUTC,
				},
			},
		},
	}

	s := New()

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, cfg := range tst.put {
				if err := s.StoreRotaConfig(ctx, &cfg); err != nil {
					t.Fatalf("%s: s.StoraRotaConfig(ctx,_) failed: %v", tst.name, err)
				}
				defer s.DeleteRotaConfig(ctx, cfg.Config.Name)
			}
			err := s.DeleteMember(tst.ctx, tst.rota, tst.email)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: s.DeleteMember(ctx, %q, %q) = %t want: %t, err: %v", tst.name, tst.rota, tst.email, got, want, err)
			}
			if err != nil {
				return
			}
			resRota, err := s.FetchRotaConfig(ctx, tst.rota)
			if err != nil {
				t.Fatalf("%s: s.FetchRotaConfig(ctx, %q) failed: %v", tst.name, tst.rota, err)
			}
			if len(resRota) != 1 {
				t.Fatalf("%s: s.FetchRotaConfig(ctx, %q) = %d want: %d, number of results differ", tst.name, tst.rota, len(resRota), -1)
			}
			sort.Slice(resRota[0].Rotation.Members, func(i, j int) bool {
				return resRota[0].Rotation.Members[i].Email < resRota[0].Rotation.Members[j].Email
			})
			sort.Slice(tst.want, func(i, j int) bool {
				return tst.want[i].Email < tst.want[j].Email
			})
			if diff := pretty.Compare(tst.want, resRota[0].Rotation.Members); diff != "" {
				t.Fatalf("%s: s.DeleteMember(ctx, %q, %s) differs -want +got: %s", tst.name, tst.rota, tst.email, diff)
			}
		})
	}
}
