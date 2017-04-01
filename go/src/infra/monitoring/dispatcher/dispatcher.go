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
	"net"
	"net/http"
	"net/url"
	"os"
	"sort"
	"strings"
	"time"

	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/luci/luci-go/common/tsmon"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"

	"golang.org/x/net/context"

	"infra/libs/infraenv"
	"infra/monitoring/analyzer"
	"infra/monitoring/client"
	"infra/monitoring/looper"
	"infra/monitoring/messages"
)

type stringSlice []string

func (s *stringSlice) String() string {
	return strings.Join(*s, ",")
}

func (s *stringSlice) Set(value string) error {
	*s = strings.Split(value, ",")
	return nil
}

var (
	alertsBaseURL       = flag.String("base-url", "", "Base URL where alerts are stored. Will be appended with the tree name.")
	login               = flag.Bool("login", false, "interactive login")
	masterFilter        = flag.String("master-filter", "", "Filter out masters that contain this string")
	masterOnly          = flag.String("master", "", "Only check this master")
	mastersOnly         = flag.Bool("masters-only", false, "Just check for master alerts, not builders")
	gatekeeperJSON      = stringSlice([]string{"gatekeeper.json"})
	gatekeeperTreesJSON = stringSlice([]string{"gatekeeper_tree.json"})
	treesOnly           = flag.String("trees", "", "Comma separated list. Only check these trees")
	builderOnly         = flag.String("builder", "", "Only check this builder")
	buildOnly           = flag.Int64("build", 0, "Only check this build")
	maxErrs             = flag.Int("max-errs", 1, "Max consecutive errors per loop attempt")
	durationStr         = flag.String("duration", "5m", "Max duration to loop for")
	cycleStr            = flag.String("cycle", "1s", "Cycle time for loop")
	snapshot            = flag.String("record-snapshot", "", "Save a snapshot of infra responses to this path, which will be created if it does not already exist.")
	replay              = flag.String("replay-snapshot", "", "Replay a snapshot of infra responses from this path, which should have been created previously by running with --record-snapshot.")
	replayTime          = flag.String("replay-time", "", "Specify a simulated starting time for the replay in RFC3339 format, used with --replay-snapshot.")
	serviceAccountJSON  = flag.String("service-account", "", "Service account JSON file.")
	miloHost            = flag.String("milo-host", "", "Hostname of milo service to use instead of buildbot/CBE")

	duration, cycle time.Duration

	// gk is the gatekeeper config.
	gks = []*messages.GatekeeperConfig{}
	// gkt is the gatekeeper trees config.
	gkts    = map[string][]messages.TreeMasterConfig{}
	expvars = expvar.NewMap("dispatcher")

	// tsmon metrics
	iterations = metric.NewCounter("alerts_dispatcher/iterations",
		"Number of iterations of the main polling loop.",
		nil,
		field.String("status"))
	postErrors = metric.NewCounter("alerts_dispatcher/post_errors",
		"Number of posting errors.",
		nil)
	alertCount = metric.NewInt("alerts_dispatcher/alert_count",
		"Number of alerts generated.",
		nil,
		field.String("tree"))
)

func init() {
	flag.Usage = func() {
		fmt.Printf("By default runs a single check, saves any alerts to ./alerts.json and exits.")
		flag.PrintDefaults()
	}
}

func analyzeBuildExtract(ctx context.Context, a *analyzer.Analyzer, tree string, masterURL *messages.MasterLocation, b *messages.BuildExtract) []messages.Alert {
	ret := a.MasterAlerts(ctx, masterURL, b)
	if *mastersOnly {
		return ret
	}
	logging.Infof(ctx, "getting builder alerts for %s (tree %s)", masterURL, tree)
	return append(ret, a.BuilderAlerts(ctx, tree, masterURL, b)...)
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

func masterFromURL(masterURL *url.URL) string {
	parts := strings.Split(masterURL.Path, "/")
	return parts[len(parts)-1]
}

func fetchBuildExtracts(ctx context.Context, masters []messages.MasterLocation) map[messages.MasterLocation]*messages.BuildExtract {
	bes := map[messages.MasterLocation]*messages.BuildExtract{}
	type beResp struct {
		master *messages.MasterLocation
		err    error
		be     *messages.BuildExtract
	}

	res := make(chan beResp)
	for _, master := range masters {
		master := master
		go func() {
			r := beResp{
				master: &master,
			}
			r.be, r.err = client.BuildExtract(ctx, &master)
			if r.err != nil {
				logging.Errorf(ctx, "Error reading build extract from %s : %s", r.master.Name(), r.err)
			}
			res <- r
		}()
	}

	for range masters {
		r := <-res
		if r.be != nil {
			bes[*r.master] = r.be
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

type alertWriter func(ctx context.Context, alerts *messages.AlertsSummary, tree string, transport http.RoundTripper) error

func mainLoop(ctx context.Context, a *analyzer.Analyzer, trees map[string]bool, transport http.RoundTripper, writeAlerts alertWriter) error {
	done := make(chan interface{})
	errs := make(chan error)
	for treeName := range trees {
		tree := treeName
		go func() {
			expvars.Add(fmt.Sprintf("Tree-%s", tree), 1)
			defer expvars.Add(fmt.Sprintf("Tree-%s", tree), -1)
			logging.Infof(ctx, "Checking tree: %s", tree)
			masters := []messages.MasterLocation{}

			for _, t := range gkts[tree] {
				for url := range t.Masters {
					if a.MasterOnly == "" || (strings.Contains(url.String(), a.MasterOnly)) {
						masters = append(masters, url)
					}
				}
			}

			bes := fetchBuildExtracts(ctx, masters)
			logging.Infof(ctx, "Build Extracts read: %d", len(bes))

			alerts := &messages.AlertsSummary{
				RevisionSummaries: map[string]messages.RevisionSummary{},
			}
			for master, be := range bes {
				alerts.Alerts = append(alerts.Alerts, analyzeBuildExtract(ctx, a, tree, &master, be)...)
			}

			sort.Sort(messages.Alerts(alerts.Alerts))
			sort.Stable(bySeverity(alerts.Alerts))

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
			alertCount.Set(ctx, int64(len(alerts.Alerts)), tree)

			if err := writeAlerts(ctx, alerts, tree, transport); err != nil {
				errs <- err
			}

			logging.Infof(ctx, "Alerts posted: %v", len(alerts.Alerts))
			done <- nil
		}()
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

func writeAlerts(ctx context.Context, alerts *messages.AlertsSummary, tree string, transport http.RoundTripper) error {
	if *alertsBaseURL == "" {
		logging.Infof(ctx, "No data_url provided. Writing to %s-alerts.json", tree)

		abytes, err := json.MarshalIndent(alerts, "", "\t")
		if err != nil {
			logging.Errorf(ctx, "Couldn't marshal alerts json: %v", err)
			return err
		}

		if err := ioutil.WriteFile(fmt.Sprintf("%s-alerts.json", tree), abytes, 0644); err != nil {
			logging.Errorf(ctx, "Couldn't write to alerts.json: %v", err)
			return err
		}
	} else {
		alertsURL := fmt.Sprintf("%s/%s", *alertsBaseURL, tree)
		w := client.NewWriter(alertsURL, transport)
		logging.Errorf(ctx, "Posting alerts to %s", alertsURL)
		err := w.PostAlerts(ctx, alerts)
		if err != nil {
			logging.Errorf(ctx, "Couldn't post alerts: %v", err)
			postErrors.Add(ctx, 1)
			return err
		}
	}

	return nil
}

func main() {
	flag.Var(&gatekeeperJSON, "gatekeeper", "Location of gatekeeper json file. Can have multiple comma separated values.")
	flag.Var(&gatekeeperTreesJSON, "gatekeeper-trees", "Location of gatekeeper tree json file. Can have multiple comma separated values.")

	ctx := context.Background()
	ctx = gologger.StdConfig.Use(ctx)
	logging.SetLevel(ctx, logging.Debug)

	tsFlags := tsmon.NewFlags()
	tsFlags.Target.TargetType = "task"
	tsFlags.Flush = "auto"

	tsFlags.Register(flag.CommandLine)
	flag.Parse()

	if *snapshot != "" && *replay != "" {
		logging.Errorf(ctx, "Cannot use snapshot and replay flags at the same time.")
		os.Exit(1)
	}

	if err := tsmon.InitializeFromFlags(ctx, &tsFlags); err != nil {
		logging.Errorf(ctx, "tsmon couldn't initialize from flags: %v", err)
		os.Exit(1)
	}

	// Start serving expvars.
	go func() {
		listener, err := net.Listen("tcp", "127.0.0.1:0")
		if err != nil {
			logging.Errorf(ctx, "Listen: %s", err)
			os.Exit(1)
		}

		logging.Infof(ctx, "expvars listening on %v", listener.Addr())

		err = http.Serve(listener, nil)
		if err != nil {
			logging.Errorf(ctx, "http.Serve: %s", err)
			os.Exit(1)
		}
	}()

	if err := loadConfigsAndRun(ctx); err != nil {
		logging.Errorf(ctx, "Error loading configs and/or running: %v", err)
	}
}

func loadConfigsAndRun(ctx context.Context) error {
	authOptions := infraenv.DefaultAuthOptions()
	authOptions.Method = auth.ServiceAccountMethod
	if *login {
		authOptions.Method = auth.UserCredentialsMethod
	}
	authOptions.ServiceAccountJSONPath = *serviceAccountJSON
	authOptions.Scopes = []string{
		auth.OAuthScopeEmail,
		"https://www.googleapis.com/auth/projecthosting",
	}

	mode := auth.SilentLogin
	if *login {
		mode = auth.InteractiveLogin
	}

	transport, err := auth.NewAuthenticator(ctx, mode, authOptions).Transport()
	if err != nil {
		logging.Errorf(ctx, "AuthenticatedTransport: %v", err)
		if !*login {
			logging.Errorf(ctx, "Consider re-running with -login")
		}
		return err
	}

	duration, err := time.ParseDuration(*durationStr)
	if err != nil {
		logging.Errorf(ctx, "Error parsing duration: %v", err)
		return err
	}

	cycle, err := time.ParseDuration(*cycleStr)
	if err != nil {
		logging.Errorf(ctx, "Error parsing cycle: %v", err)
		return err
	}

	for _, gkFile := range gatekeeperJSON {
		gk := messages.GatekeeperConfig{}
		err = readJSONFile(gkFile, &gk)
		if err != nil {
			logging.Errorf(ctx, "Error reading gatekeeper json: %v", err)
			return err
		}

		gks = append(gks, &gk)
	}

	for _, treeFile := range gatekeeperTreesJSON {
		tree := make(map[string]messages.TreeMasterConfig)
		err = readJSONFile(treeFile, &tree)
		if err != nil {
			logging.Errorf(ctx, "Error reading gatekeeper trees json: %v", err)
			return err
		}

		for treeName, config := range tree {
			gkts[treeName] = append(gkts[treeName], config)
		}
	}

	r, err := client.NewReader(ctx)
	if err != nil {
		return err
	}

	switch {
	case *replay != "":
		r = client.NewReplay(*replay)
	case *miloHost != "":
		ctx = urlfetch.Set(ctx, transport)

		var err error
		r, err = client.NewMiloReader(ctx, *miloHost)
		if err != nil {
			return err
		}
	}
	if *snapshot != "" {
		r = client.NewSnapshot(r, *snapshot)
	}

	ctx = client.WithReader(ctx, r)
	return run(ctx, transport, cycle, duration, gks, gkts)
}

func run(ctx context.Context, transport http.RoundTripper, cycle, duration time.Duration, gks []*messages.GatekeeperConfig, gkts map[string][]messages.TreeMasterConfig) error {
	a := analyzer.New(5, 100)
	if *replayTime != "" {
		t, err := time.Parse(time.RFC3339, *replayTime)
		if err != nil {
			logging.Errorf(ctx, "Couldn't parse replay-time: %s", err)
			return err
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
			return err
		}
		stat, err := f.Stat()
		if err != nil {
			logging.Errorf(ctx, "Couldn't stat replay dir: %s", err)
			return err
		}
		start := time.Now()
		t := stat.ModTime()

		a.Now = func() time.Time {
			diff := time.Now().Sub(start)
			return t.Add(diff)
		}
	}

	a.Gatekeeper = analyzer.NewGatekeeperRules(ctx, gks, gkts)

	a.MasterOnly = *masterOnly
	a.BuilderOnly = *builderOnly
	a.BuildOnly = *buildOnly

	trees := map[string]bool{}
	if *treesOnly != "" {
		for _, treeOnly := range strings.Split(*treesOnly, ",") {
			trees[treeOnly] = true
		}
	} else {
		for treeName := range gkts {
			trees[treeName] = true
		}
	}

	for tree := range trees {
		if _, ok := gkts[tree]; !ok {
			return fmt.Errorf("Unrecognized tree name: %s", tree)
		}
	}

	// This is the polling/analysis/alert posting function, which will run in a loop until
	// a timeout or max errors is reached.
	f := func(ctx context.Context) error {
		err := mainLoop(ctx, a, trees, transport, writeAlerts)
		if err == nil {
			iterations.Add(ctx, 1, "success")
		} else {
			iterations.Add(ctx, 1, "failure")
		}
		return err
	}

	ctx, cancel := context.WithTimeout(ctx, duration)
	defer cancel()

	loopResults := looper.Run(ctx, f, cycle, *maxErrs, clock.GetSystemClock())

	tsmon.Shutdown(ctx)

	if !loopResults.Success {
		return fmt.Errorf("Failed to run loop, %v errors", loopResults.Errs)
	}

	return nil
}
