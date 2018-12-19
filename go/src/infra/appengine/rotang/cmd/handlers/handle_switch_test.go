package handlers

import (
	"infra/appengine/rotang"
	"testing"
)

func TestSafeToMigrate(t *testing.T) {
	tests := []struct {
		name string
		fail bool
		rota *rotang.Configuration
		cfgs []rotang.Configuration
		want bool
	}{{
		name: "Safe",
		rota: &rotang.Configuration{
			Config: rotang.Config{
				Name:     "Test Rota",
				Calendar: "TestCal",
			},
		},
		cfgs: []rotang.Configuration{
			{
				Config: rotang.Config{
					Name:     "Test Rota",
					Calendar: "TestCal",
				},
			}, {
				Config: rotang.Config{
					Name:     "Another Test Rota",
					Calendar: "AnotherTestCal",
				},
			},
		},
		want: true,
	}, {
		name: "Unsafe",
		rota: &rotang.Configuration{
			Config: rotang.Config{
				Name:     "Test Rota",
				Calendar: "TestCal",
			},
		},
		cfgs: []rotang.Configuration{
			{
				Config: rotang.Config{
					Name:     "Test Rota",
					Calendar: "TestCal",
				},
			}, {
				Config: rotang.Config{
					Name:     "Another Test Rota",
					Calendar: "TestCal",
				},
			},
		},
	}, {
		name: "Last to migrate",
		rota: &rotang.Configuration{
			Config: rotang.Config{
				Name:     "Test Rota",
				Calendar: "TestCal",
			},
		},
		cfgs: []rotang.Configuration{
			{
				Config: rotang.Config{
					Name:     "Test Rota",
					Calendar: "TestCal",
				},
			}, {
				Config: rotang.Config{
					Name:     "Another Test Rota",
					Calendar: "TestCal",
					Enabled:  true,
				},
			},
		},
		want: true,
	}, {
		name: "No configs",
		rota: &rotang.Configuration{
			Config: rotang.Config{
				Name:     "Test Rota",
				Calendar: "TestCal",
			},
		},
		fail: true,
	}}

	ctx := newTestContext()
	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, cfg := range tst.cfgs {
				if err := h.configStore(ctx).CreateRotaConfig(ctx, &cfg); err != nil {
					t.Fatalf("%s: CreateRotaConfig(ctx, _) failed: %v", tst.name, err)
				}
				defer h.configStore(ctx).DeleteRotaConfig(ctx, cfg.Config.Name)
			}
			safe, err := h.safeToMigrateCalendar(ctx, tst.rota)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: safeToMigrate(ctx, _) = %t, want: %t, err: %v", tst.name, got, want, err)
			}
			if got, want := safe, tst.want; got != want {
				t.Errorf("%s: safeToMigrate(ctx, _) = %t, want: %t", tst.name, got, want)
			}
		})
	}

}
