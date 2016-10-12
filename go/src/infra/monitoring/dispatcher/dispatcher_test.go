package main

import (
	"net/http"
	"testing"
	"time"

	"infra/monitoring/analyzer"
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

		t := http.DefaultTransport
		err := mainLoop(context.Background(), a, trees, t)
		So(err, ShouldBeNil)
	})

	Convey("run", t, func() {
		reader := testclient.MockReader{}
		gks := []*messages.GatekeeperConfig{}
		gkts := map[string][]messages.TreeMasterConfig{}

		err := run(context.Background(), http.DefaultTransport, time.Second, time.Second, reader, gks, gkts)
		So(err, ShouldBeNil)
	})
}
