// This is a lightweight WCT runner that only cares about chrome.

//go:generate go run gen/gen.go
package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"html/template"
	"math/rand"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"golang.org/x/net/context"

	"github.com/chromedp/chromedp"
	"github.com/chromedp/chromedp/runner"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
)

type arrayFlags []string

func (i *arrayFlags) String() string {
	return strings.Join(*i, ", ")
}

func (i *arrayFlags) Set(value string) error {
	if value == "" {
		return errors.New("dependency directory required")
	}
	*i = append(*i, value)
	return nil
}

var depDirsFlags arrayFlags

var (
	chromeBin  = flag.String("chrome", "", "location of chrome binary")
	userDir    = flag.String("dir", "/tmp/", "user directory")
	debugPort  = flag.String("debug-port", "9222", "chrome debugger port")
	baseDir    = flag.String("base", "./", "location of elements to test")
	pathPrefix = flag.String("prefix", "test", "path prefix for tests")
	bowerDir   = flag.String("bower", "bower_components/", "location of bower components")
	persist    = flag.Bool("persist", false, "keep server running")
	timeoutSec = flag.Int("timeout", 60, "timeout seconds")
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

type dependencyFS struct {
	deps []http.Dir
}

func (fs dependencyFS) Open(name string) (f http.File, err error) {
	for i := 0; i < len(fs.deps); i++ {
		f, err = fs.deps[i].Open(name)
		if err == nil {
			return f, err
		}
	}
	return f, err
}

func findFilesMatching(root string, filenameRegexp *regexp.Regexp) (results []string, err error) {
	err = filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if filenameRegexp.MatchString(path) {
			// Strip root from the path.
			if strings.Index(path, root) == 0 {
				path = filepath.Join(*pathPrefix, path[len(root):])
			}
			results = append(results, path)
		}
		return err
	})
	return results, err
}

type loaderVariables struct {
	Suites []string
}

func main() {
	flag.Var(&depDirsFlags, "dep", "dependency directories")
	flag.Parse()
	ctx := context.Background()
	ctx = gologger.StdConfig.Use(ctx)
	logging.SetLevel(ctx, logging.Debug)

	if *chromeBin == "" {
		logging.Errorf(ctx, "chrome flag must be set")
		os.Exit(1)
	}

	// The chromedriver lib won't let us force it to pick a random port, or
	// use a port reservation server. So make maxPortAttempts to pick one at
	// random from the range [portMin, portMin+portRange).  This is
	// inherently flaky, so we should upstream a fix PR to this chromedriver lib.
	rand.Seed(time.Now().UTC().UnixNano())
	var err error

	loaderTemplate, err := template.New("loader").Parse(loaderHTMLTemplate)
	if err != nil {
		logging.Errorf(ctx, "Error parsing loader template: %v", err)
		os.Exit(1)
	}

	testRegexp := regexp.MustCompile("[-_]test\\.(js|html)$")
	testDir := filepath.Join(*baseDir, *pathPrefix)
	tests, err := findFilesMatching(testDir, testRegexp)
	if err != nil {
		logging.Errorf(ctx, "Error walking %v: %v", *baseDir, err)
		// Tolerate filesystem errors and run the tests that can be found.
	}

	http.HandleFunc("/wct-loader", func(w http.ResponseWriter, r *http.Request) {
		err := loaderTemplate.Execute(w, loaderVariables{tests})
		if err != nil {
			logging.Errorf(ctx, "Error executing loader template: %v", err)
			os.Exit(1)
		}
	})

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

		if req.Failures > 0 {
			logging.Errorf(ctx, "Done: %d Passes, %d Failures", req.Passes, req.Failures)
		} else {
			logging.Infof(ctx, "Done: %d Passes, %d Failures", req.Passes, req.Failures)
		}

		if !*persist {
			doneCh <- req.Failures > 0
		}
	})

	var depHTTPDirs []http.Dir
	depHTTPDirs = append(depHTTPDirs, http.Dir(*baseDir))
	depHTTPDirs = append(depHTTPDirs, http.Dir(*bowerDir))
	for i := 0; i < len(depDirsFlags); i++ {
		depHTTPDirs = append(depHTTPDirs, http.Dir(depDirsFlags[i]))
	}

	http.Handle("/", http.FileServer(dependencyFS{deps: depHTTPDirs}))

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
	testURL := fmt.Sprintf("http://%s/wct-loader?wct=go", addr)

	ctxt, cancel := context.WithCancel(context.Background())
	defer cancel()

	var c *chromedp.CDP
	var debugPort int

	var infoLogger = func(prefix string) func(f string, i ...interface{}) {
		return func(f string, i ...interface{}) {
			// The cleans up stdout. Otherwise the chrome instance is way too verbose.
			logging.Infof(ctx, fmt.Sprintf("[%s] %s", prefix, f), i)
			return
		}
	}

	// Create chrome instance. Try to grab a random debug port.
	for i := 0; i < maxPortAttempts; i++ {
		debugPort = rand.Intn(portRange) + portMin
		logging.Infof(ctx, "attempting to start chrome with debug port %d", debugPort)
		c, err = chromedp.New(ctxt, chromedp.WithLogf(infoLogger("LOG")),
			chromedp.WithDebugf(infoLogger("DEBUG")),
			chromedp.WithErrorf(infoLogger("ERROR")),
			chromedp.WithRunnerOptions(runner.Path(*chromeBin), runner.NoSandbox, runner.RemoteDebuggingPort(debugPort)))
		if err == nil {
			break
		}
		logging.Errorf(ctx, "attempting to start chrome with debug port %d: %v", debugPort, err)
	}

	if err != nil {
		logging.Errorf(ctx, "error creating chrome instance: %v", err)
		os.Exit(1)
	}

	err = c.Run(ctxt, chromedp.Tasks{
		chromedp.Navigate(testURL),
	})
	if err != nil {
		logging.Errorf(ctx, "error running chromedp tasks: %v", err)
		os.Exit(1)
	}

	// If the user wants to run the test harness persistently, just loop
	// and print the doneCh results whenever they're sent.  This is
	// effectively the end of the program when *persist == true, because
	// the user is expected to Ctrl-C to kill the harness in this case.
	if *persist {
		select {
		case errors := <-doneCh:
			if errors {
				logging.Errorf(ctx, "FAILED\n")
			} else {
				logging.Infof(ctx, "PASSED\n")
			}
		}
	}

	// If we're running in non-persistent mode, just run the tests once
	// and exit after printing the results. This is the expected path
	// for continuous builders or other non-interactive use cases.
	select {
	case errors := <-doneCh:
		err = c.Shutdown(ctxt)
		if err != nil {
			logging.Errorf(ctx, "error shutting down chrome: %v", err)
		}

		err = c.Wait()
		if err != nil {
			logging.Errorf(ctx, "error waiting for chrome to finish: %v", err)
		}

		if errors {
			logging.Errorf(ctx, "FAILED\n")
			os.Exit(1)
		} else {
			logging.Infof(ctx, "PASSED\n")
		}
	case <-time.After(time.Duration(*timeoutSec) * time.Second):
		logging.Errorf(ctx, "TIMED OUT\n")
		os.Exit(1)
	}
}
