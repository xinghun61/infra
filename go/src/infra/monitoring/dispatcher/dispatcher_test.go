package main

import (
	"net/http"
	"testing"
	"time"

	"infra/monitoring/analyzer"
	"infra/monitoring/client"
	testclient "infra/monitoring/client/test"
	"infra/monitoring/messages"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestMainLoop(t *testing.T) {
	Convey("mainLoop, nulls", t, func() {
		err := mainLoop(nil, nil, nil, nil)
		So(err, ShouldBeNil)
	})

	Convey("mainLoop", t, func() {
		a := &analyzer.Analyzer{}
		trees := map[string]bool{
			"chromium": true,
		}

		mc := &testclient.MockReader{}
		ctx := client.WithReader(context.Background(), mc)

		t := http.DefaultTransport
		err := mainLoop(ctx, a, trees, t)
		So(err, ShouldBeNil)
	})

	Convey("run", t, func() {
		reader := testclient.MockReader{}
		ctx := client.WithReader(context.Background(), reader)
		gks := []*messages.GatekeeperConfig{}
		gkts := map[string][]messages.TreeMasterConfig{}

		err := run(ctx, http.DefaultTransport, time.Second, time.Second, gks, gkts)
		So(err, ShouldBeNil)
	})
}
