package main

import (
	"net/http"
	"net/url"
	"testing"
	"time"

	"infra/monitoring/analyzer"
	"infra/monitoring/client"
	testclient "infra/monitoring/client/test"
	"infra/monitoring/messages"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func noopAlertWriter(ctx context.Context, alerts *messages.AlertsSummary, tree string, transport http.RoundTripper) error {
	return nil
}

func urlParse(s string, t *testing.T) *url.URL {
	p, err := url.Parse(s)
	if err != nil {
		t.Errorf("failed to parse %s: %s", s, err)
	}
	return p
}

func TestMainLoop(t *testing.T) {
	Convey("mainLoop", t, func() {
		Convey("nulls", func() {
			err := mainLoop(nil, nil, nil, nil, noopAlertWriter)
			So(err, ShouldBeNil)
		})

		a := &analyzer.Analyzer{}
		trees := map[string]bool{
			"chromium": true,
		}

		gkts["chromium"] = []messages.TreeMasterConfig{
			{
				BuildDB: "chromium.json",
				Masters: map[messages.MasterLocation][]string{
					messages.MasterLocation{URL: *urlParse("https://build.chromium.org/p/chromium", t)}: []string{"*"},
				},
			},
		}

		mc := &testclient.MockReader{}
		ctx := client.WithReader(context.Background(), mc)

		t := http.DefaultTransport
		err := mainLoop(ctx, a, trees, t, noopAlertWriter)

		So(err, ShouldBeNil)
	})
}

func TestRun(t *testing.T) {
	Convey("run", t, func() {
		reader := testclient.MockReader{}
		ctx := client.WithReader(context.Background(), reader)
		gks := []*messages.GatekeeperConfig{}
		gkts := map[string][]messages.TreeMasterConfig{}

		err := run(ctx, http.DefaultTransport, time.Second, time.Second, gks, gkts)
		So(err, ShouldBeNil)
	})
}
