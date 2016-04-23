// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Dispatcher usage:
// go run infra/monitoring/dispatcher
// Expects gatekeeper.json to be in the current directory.

package main

import (
	"encoding/json"
	"expvar"
	"flag"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"sort"
	"strings"
	"time"

	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/gologger"

	"golang.org/x/net/context"

	"infra/monitoring/analyzer"
	"infra/monitoring/client"
	"infra/monitoring/looper"
	"infra/monitoring/messages"
)

var (
	alertsBaseURL       = flag.String("base-url", "", "Base URL where alerts are stored. Will be appended with the tree name.")
	login               = flag.Bool("login", false, "interactive login")
	masterFilter        = flag.String("master-filter", "", "Filter out masters that contain this string")
	masterOnly          = flag.String("master", "", "Only check this master")
	mastersOnly         = flag.Bool("masters-only", false, "Just check for master alerts, not builders")
	gatekeeperJSON      = flag.String("gatekeeper", "gatekeeper.json", "Location of gatekeeper json file")
	gatekeeperTreesJSON = flag.String("gatekeeper-trees", "gatekeeper_trees.json", "Location of gatekeeper json file")
	treesOnly           = flag.String("trees", "", "Comma separated list. Only check these trees")
	builderOnly         = flag.String("builder", "", "Only check this builder")
	buildOnly           = flag.Int64("build", 0, "Only check this build")
	maxErrs             = flag.Int("max-errs", 1, "Max consecutive errors per loop attempt")
	durationStr         = flag.String("duration", "10s", "Max duration to loop for")
	cycleStr            = flag.String("cycle", "1s", "Cycle time for loop")
	snapshot            = flag.String("record-snapshot", "", "Save a snapshot of infra responses to this path, which will be created if it does not already exist.")
	replay              = flag.String("replay-snapshot", "", "Replay a snapshot of infra responses from this path, which should have been created previously by running with --record-snapshot.")
	replayTime          = flag.String("replay-time", "", "Specify a simulated starting time for the replay in RFC3339 format, used with --replay-snapshot.")
	serviceAccountJSON  = flag.String("service-account", "", "Service account JSON file.")

	duration, cycle time.Duration

	// gk is the gatekeeper config.
	gk = &messages.GatekeeperConfig{}
	// gkt is the gatekeeper trees config.
	gkt              = map[string]messages.TreeMasterConfig{}
	filteredFailures = uint64(0)
	expvars          = expvar.NewMap("dispatcher")
)

func init() {
	flag.Usage = func() {
		fmt.Printf("By default runs a single check, saves any alerts to ./alerts.json and exits.")
		flag.PrintDefaults()
	}
}

func analyzeBuildExtract(ctx context.Context, a *analyzer.Analyzer, masterName string, b *messages.BuildExtract) []messages.Alert {
	ret := a.MasterAlerts(masterName, b)
	if *mastersOnly {
		return ret
	}
	logging.Infof(ctx, "getting builder alerts for %s", masterName)
	return append(ret, a.BuilderAlerts(masterName, b)...)
}

// readJSONFile reads a file and decode it as JSON.
func readJSONFile(filePath string, object interface{}) error {
	f, err := os.Open(filePath)
	if err != nil {
		return fmt.Errorf("failed to open %s: %s", filePath, err)
	}
	defer f.Close()
	if err = json.NewDecoder(f).Decode(object); err != nil {
		return fmt.Errorf("failed to decode %s: %s", filePath, err)
	}
	return nil
}

func masterFromURL(masterURL string) string {
	parts := strings.Split(masterURL, "/")
	return parts[len(parts)-1]
}

func fetchBuildExtracts(ctx context.Context, c client.Reader, masterNames []string) map[string]*messages.BuildExtract {
	bes := map[string]*messages.BuildExtract{}
	type beResp struct {
		name string
		err  error
		be   *messages.BuildExtract
	}

	res := make(chan beResp)
	for _, masterName := range masterNames {
		go func(mn string) {
			r := beResp{name: mn}
			r.be, r.err = c.BuildExtract(mn)
			if r.err != nil {
				logging.Errorf(ctx, "Error reading build extract from %s : %s", mn, r.err)
			}
			res <- r
		}(masterName)
	}

	for range masterNames {
		r := <-res
		if r.be != nil {
			bes[r.name] = r.be
		}
	}
	return bes
}

type bySeverity []messages.Alert

func (a bySeverity) Len() int      { return len(a) }
func (a bySeverity) Swap(i, j int) { a[i], a[j] = a[j], a[i] }
func (a bySeverity) Less(i, j int) bool {
	return a[i].Severity < a[j].Severity
}

func mainLoop(ctx context.Context, a *analyzer.Analyzer, trees map[string]bool) error {
	done := make(chan interface{})
	errs := make(chan error)
	for treeName := range trees {
		go func(tree string) {
			expvars.Add(fmt.Sprintf("Tree-%s", tree), 1)
			defer expvars.Add(fmt.Sprintf("Tree-%s", tree), -1)
			logging.Infof(ctx, "Checking tree: %s", tree)
			masterNames := []string{}
			t := gkt[tree]
			for _, url := range t.Masters {
				masterNames = append(masterNames, masterFromURL(url))
			}

			// TODO(seanmccullough): Plumb ctx through the rest of these calls.
			bes := fetchBuildExtracts(ctx, a.Reader, masterNames)
			logging.Infof(ctx, "Build Extracts read: %d", len(bes))

			alerts := &messages.Alerts{
				RevisionSummaries: map[string]messages.RevisionSummary{},
			}
			for masterName, be := range bes {
				alerts.Alerts = append(alerts.Alerts, analyzeBuildExtract(ctx, a, masterName, be)...)
			}

			sort.Sort(bySeverity(alerts.Alerts))

			// Make sure we have summaries for each revision implicated in a builder failure.
			for _, alert := range alerts.Alerts {
				if bf, ok := alert.Extension.(messages.BuildFailure); ok {
					for _, r := range bf.RegressionRanges {
						revs, err := a.GetRevisionSummaries(r.Revisions)
						if err != nil {
							logging.Errorf(ctx, "Couldn't get revision summaries: %v", err)
							continue
						}
						for _, rev := range revs {
							alerts.RevisionSummaries[rev.GitHash] = rev
						}
					}
				}
			}
			alerts.Timestamp = messages.TimeToEpochTime(time.Now())

			if *alertsBaseURL == "" {
				logging.Infof(ctx, "No data_url provided. Writing to %s-alerts.json", tree)

				abytes, err := json.MarshalIndent(alerts, "", "\t")
				if err != nil {
					logging.Errorf(ctx, "Couldn't marshal alerts json: %v", err)
					errs <- err
					return
				}

				if err := ioutil.WriteFile(fmt.Sprintf("%s-alerts.json", tree), abytes, 0644); err != nil {
					logging.Errorf(ctx, "Couldn't write to alerts.json: %v", err)
					errs <- err
					return
				}
			} else {
				alertsURL := fmt.Sprintf("%s/%s", *alertsBaseURL, tree)
				w := client.NewWriter(alertsURL)
				logging.Infof(ctx, "Posting alerts to %s", alertsURL)
				err := w.PostAlerts(alerts)
				if err != nil {
					logging.Errorf(ctx, "Couldn't post alerts: %v", err)
					errs <- err
					return
				}
			}

			logging.Infof(ctx, "Filtered failures: %v", filteredFailures)
			done <- nil
		}(treeName)
	}

	for range trees {
		select {
		case err := <-errs:
			return err
		case <-done:
		}
	}

	return nil
}

func main() {
	flag.Parse()

	ctx := context.Background()
	ctx = gologger.StdConfig.Use(ctx)
	ctx = logging.SetLevel(ctx, logging.Debug)

	authOptions := auth.Options{
		Context:                ctx,
		ServiceAccountJSONPath: *serviceAccountJSON,
		Scopes: []string{
			auth.OAuthScopeEmail,
			"https://www.googleapis.com/auth/projecthosting",
		},
	}

	mode := auth.OptionalLogin
	if *login {
		mode = auth.InteractiveLogin
	}

	transport, err := auth.NewAuthenticator(mode, authOptions).Transport()
	if err != nil {
		logging.Errorf(ctx, "AuthenticatedTransport: %v", err)
		if !*login {
			logging.Errorf(ctx, "Consider re-running with -login")
		}
		os.Exit(1)
	}

	// Start serving expvars.
	go func() {
		err := http.ListenAndServe(":12345", nil)
		if err != nil {
			logging.Errorf(ctx, "ListenAndServe: %v", err)
			os.Exit(1)
		}
	}()

	duration, err := time.ParseDuration(*durationStr)
	if err != nil {
		logging.Errorf(ctx, "Error parsing duration: %v", err)
		os.Exit(1)
	}

	cycle, err := time.ParseDuration(*cycleStr)
	if err != nil {
		logging.Errorf(ctx, "Error parsing cycle: %v", err)
		os.Exit(1)
	}

	err = readJSONFile(*gatekeeperJSON, &gk)
	if err != nil {
		logging.Errorf(ctx, "Error reading gatekeeper json: %v", err)
		os.Exit(1)
	}

	err = readJSONFile(*gatekeeperTreesJSON, &gkt)
	if err != nil {
		logging.Errorf(ctx, "Error reading gatekeeper trees json: %v", err)
		os.Exit(1)
	}

	if *snapshot != "" && *replay != "" {
		logging.Errorf(ctx, "Cannot use snapshot and replay flags at the same time.")
		os.Exit(1)
	}

	r := client.NewReader(transport)

	if *snapshot != "" {
		r = client.NewSnapshot(r, *snapshot)
	}

	if *replay != "" {
		r = client.NewReplay(*replay)
	}

	a := analyzer.New(r, 5, 100)
	if *replayTime != "" {
		t, err := time.Parse(time.RFC3339, *replayTime)
		if err != nil {
			logging.Errorf(ctx, "Couldn't parse replay-time: %s", err)
			os.Exit(1)
		}
		start := time.Now()
		a.Now = func() time.Time {
			diff := time.Now().Sub(start)
			return t.Add(diff)
		}
	} else if *replay != "" {
		f, err := os.Open(*replay)
		defer f.Close()
		if err != nil {
			logging.Errorf(ctx, "Couldn't open replay dir: %s", err)
			os.Exit(1)
		}
		stat, err := f.Stat()
		if err != nil {
			logging.Errorf(ctx, "Couldn't stat replay dir: %s", err)
			os.Exit(1)
		}
		start := time.Now()
		t := stat.ModTime()

		a.Now = func() time.Time {
			diff := time.Now().Sub(start)
			return t.Add(diff)
		}
	}

	a.Gatekeeper = analyzer.NewGatekeeperRules(*gk)

	a.MasterOnly = *masterOnly
	a.BuilderOnly = *builderOnly
	a.BuildOnly = *buildOnly

	trees := map[string]bool{}
	if *treesOnly != "" {
		for _, treeOnly := range strings.Split(*treesOnly, ",") {
			trees[treeOnly] = true
		}
	} else {
		for treeName := range gkt {
			trees[treeName] = true
		}
	}

	for tree := range trees {
		if _, ok := gkt[tree]; !ok {
			logging.Errorf(ctx, "Unrecognized tree name: %s", tree)
			os.Exit(1)
		}
	}

	// This is the polling/analysis/alert posting function, which will run in a loop until
	// a timeout or max errors is reached.
	f := func(ctx context.Context) error {
		return mainLoop(ctx, a, trees)
	}

	ctx, cancel := context.WithTimeout(ctx, duration)
	defer cancel()

	loopResults := looper.Run(ctx, f, cycle, *maxErrs, clock.GetSystemClock())

	if !loopResults.Success {
		logging.Errorf(ctx, "Failed to run loop, %v errors", loopResults.Errs)
		os.Exit(1)
	}
}
