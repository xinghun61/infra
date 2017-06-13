// This is a lightweight WCT runner that only cares about chrome.
// It does require chromedriver to be installed on the build machine.
// Install from https://sites.google.com/a/chromium.org/chromedriver/downloads
// To run wct tests using this app (from ../):
// xvfb-run go run wct/wct.go -chromedriver=/usr/local/google/home/$USER/Downloads/chromedriver -base=frontend

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"math/rand"
	"net"
	"net/http"
	"os"
	"time"

	"golang.org/x/net/context"

	"github.com/fedesog/webdriver"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/gologger"
)

var (
	chromedriverBin = flag.String("chromedriver", "", "location of chromedriver binary. Install from https://sites.google.com/a/chromium.org/chromedriver/downloads")
	baseDir         = flag.String("base", "", "location of elements to test")
)

const (
	maxPortAttempts = 10
	portRange       = 1000
	portMin         = 5000
)

// ResultRequest is sent from the client at the end of an individual test run.
type ResultRequest struct {
	// File is the name of the test heml file.
	File string `json:"file"`
	// Suite is the name of the test suite within the file.
	Suite string `json:"suite"`
	// Test is the name of the test within the suite.
	Test string `json:"test"`
	// State is the result of the test run.
	State string `json:"state"`
}

// DoneRequest is sent from the client at the end of all test runs.
type DoneRequest struct {
	// Passes is the number of individual tests that passed.
	Passes int `json:"passes"`
	// Failures is the number of individual tests that failed.
	Failures int `json:"failures"`
}

func main() {
	flag.Parse()
	ctx := context.Background()
	ctx = gologger.StdConfig.Use(ctx)
	logging.SetLevel(ctx, logging.Debug)

	// The chromedriver lib won't let us force it to pick a random port, or
	// use a port reservation server. So make maxPortAttempts to pick one at
	// random from the range [portMin, portMin+portRange).  This is
	// inherently flaky, so we should upstream a fix PR to this chromedriver lib.
	rand.Seed(time.Now().UTC().UnixNano())
	var err error
	chromeDriver := webdriver.NewChromeDriver(*chromedriverBin)
	for i := 0; i < maxPortAttempts; i++ {
		chromeDriver.Port = rand.Intn(portRange) + portMin
		err = chromeDriver.Start()
		if err == nil {
			break
		}
		logging.Errorf(ctx, "attempting to start chromedriver located at %q on port %d: %v", *chromedriverBin, chromeDriver.Port, err)
	}
	if err != nil {
		logging.Errorf(ctx, "starting chromedriver located at %q: on port %d (last attempt): %v", *chromedriverBin, chromeDriver.Port, err)
		os.Exit(-1)
	}

	desired := webdriver.Capabilities{"Platform": "Linux"}
	session, err := chromeDriver.NewSession(desired, desired)
	if err != nil {
		logging.Errorf(ctx, "starting chromedriver session: %v", err)
		os.Exit(-1)
	}

	http.HandleFunc("/result", func(w http.ResponseWriter, r *http.Request) {
		req := &ResultRequest{}
		if err := json.NewDecoder(r.Body).Decode(req); err != nil {
			logging.Infof(ctx, "error decoding result: %v", err)
			return
		}

		if req.State != "passed" {
			logging.Errorf(ctx, "%s#%s (%s): %s\n", req.File, req.Suite, req.Test, req.State)
		} else {
			logging.Infof(ctx, "%s#%s (%s): %s\n", req.File, req.Suite, req.Test, req.State)
		}
		w.Write([]byte("ok"))
	})

	doneCh := make(chan bool)
	http.HandleFunc("/done", func(w http.ResponseWriter, r *http.Request) {
		req := &DoneRequest{}
		if err := json.NewDecoder(r.Body).Decode(req); err != nil {
			logging.Errorf(ctx, "error decoding result: %v", err)
			return
		}

		session.Delete()
		chromeDriver.Stop()

		if req.Failures > 0 {
			logging.Errorf(ctx, "Done: %d Passes, %d Failures", req.Passes, req.Failures)
			os.Exit(-1)
		}

		logging.Infof(ctx, "Done: %d Passes, %d Failures", req.Passes, req.Failures)
		doneCh <- true
	})

	fs := http.FileServer(http.Dir(*baseDir))
	http.Handle("/", fs)
	addrCh := make(chan string)
	go func() {
		listener, err := net.Listen("tcp", "127.0.0.1:0")
		if err != nil {
			logging.Errorf(ctx, "getting a listener: %v", err)
			os.Exit(1)
		}
		logging.Infof(ctx, "test http server listening on %s", listener.Addr().String())
		addrCh <- listener.Addr().String()
		panic(http.Serve(listener, nil))
	}()

	addr := <-addrCh
	testURL := fmt.Sprintf("http://%s/test/?wct=go", addr)
	err = session.Url(testURL)
	if err != nil {
		logging.Errorf(ctx, "opening url for session: %v", err)
	}
	<-doneCh
}
