// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Dispatcher usage:
// go run infra/monitoring/dispatcher
// Expects gatekeeper.json to be in the current directory.

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"os"
	"strings"
	"time"

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

	log             = gologger.Get()
	duration, cycle time.Duration

	// gk is the gatekeeper config.
	gk = &struct {
		// Weird. Are there ever multiple configs per master key?
		Masters map[string][]messages.MasterConfig `json:"masters"`
	}{}
	// gkt is the gatekeeper trees config.
	gkt              = map[string]messages.TreeMasterConfig{}
	filteredFailures = uint64(0)
)

func init() {
	flag.Usage = func() {
		fmt.Printf("By default runs a single check, saves any alerts to ./alerts.json and exits.")
		flag.PrintDefaults()
	}
}

func analyzeBuildExtract(a *analyzer.Analyzer, masterName string, b *messages.BuildExtract) []messages.Alert {
	ret := a.MasterAlerts(masterName, b)
	if *mastersOnly {
		return ret
	}
	log.Infof("getting builder alerts for %s", masterName)
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

func fetchBuildExtracts(c client.Reader, masterNames []string) map[string]*messages.BuildExtract {
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
				log.Errorf("Error reading build extract from %s : %s", mn, r.err)
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

func main() {
	start := time.Now()
	flag.Parse()

	duration, err := time.ParseDuration(*durationStr)
	if err != nil {
		log.Errorf("Error parsing duration: %v", err)
		os.Exit(1)
	}

	cycle, err := time.ParseDuration(*cycleStr)
	if err != nil {
		log.Errorf("Error parsing cycle: %v", err)
		os.Exit(1)
	}

	err = readJSONFile(*gatekeeperJSON, &gk)
	if err != nil {
		log.Errorf("Error reading gatekeeper json: %v", err)
		os.Exit(1)
	}

	err = readJSONFile(*gatekeeperTreesJSON, &gkt)
	if err != nil {
		log.Errorf("Error reading gatekeeper json: %v", err)
		os.Exit(1)
	}

	if *snapshot != "" && *replay != "" {
		log.Errorf("Cannot use snapshot and replay flags at the same time.")
		os.Exit(1)
	}

	r := client.NewReader()
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
			log.Errorf("Couldn't parse replay-time: %s", err)
			os.Exit(1)
		}
		start := time.Now()
		a.Now = func() time.Time {
			diff := time.Now().Sub(start)
			return t.Add(diff)
		}
	}

	for masterURL, masterCfgs := range gk.Masters {
		if len(masterCfgs) != 1 {
			log.Errorf("Multiple configs for master: %s", masterURL)
		}
		masterName := masterFromURL(masterURL)
		a.MasterCfgs[masterName] = masterCfgs[0]
	}

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
			log.Errorf("Unrecognized tree name: %s", tree)
			os.Exit(1)
		}
	}

	// This is the polling/analysis/alert posting function, which will run in a loop until
	// a timeout or max errors is reached.
	f := func(ctx context.Context) error {
		done := make(chan interface{})
		errs := make(chan error)
		for treeName := range trees {
			go func(tree string) {
				log.Infof("Checking tree: %s", tree)
				masterNames := []string{}
				t := gkt[tree]
				for _, url := range t.Masters {
					masterNames = append(masterNames, masterFromURL(url))
				}

				// TODO(seanmccullough): Plumb ctx through the rest of these calls.
				bes := fetchBuildExtracts(a.Reader, masterNames)
				log.Infof("Build Extracts read: %d", len(bes))

				alerts := &messages.Alerts{
					RevisionSummaries: map[string]messages.RevisionSummary{},
				}
				for masterName, be := range bes {
					alerts.Alerts = append(alerts.Alerts, analyzeBuildExtract(a, masterName, be)...)
				}

				// Make sure we have summaries for each revision implicated in a builder failure.
				for _, alert := range alerts.Alerts {
					if bf, ok := alert.Extension.(messages.BuildFailure); ok {
						for _, r := range bf.RegressionRanges {
							revs, err := a.GetRevisionSummaries(r.Revisions)
							if err != nil {
								log.Errorf("Couldn't get revision summaries: %v", err)
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
					log.Infof("No data_url provided. Writing to %s-alerts.json", tree)

					abytes, err := json.MarshalIndent(alerts, "", "\t")
					if err != nil {
						log.Errorf("Couldn't marshal alerts json: %v", err)
						errs <- err
						return
					}

					if err := ioutil.WriteFile(fmt.Sprintf("%s-alerts.json", tree), abytes, 0644); err != nil {
						log.Errorf("Couldn't write to alerts.json: %v", err)
						errs <- err
						return
					}
				} else {
					alertsURL := fmt.Sprintf("%s/%s", *alertsBaseURL, tree)
					w := client.NewWriter(alertsURL)
					log.Infof("Posting alerts to %s", alertsURL)
					err := w.PostAlerts(alerts)
					if err != nil {
						log.Errorf("Couldn't post alerts: %v", err)
						errs <- err
						return
					}
				}

				log.Infof("Filtered failures: %v", filteredFailures)
				a.Reader.DumpStats()
				log.Infof("Elapsed time: %v", time.Since(start))
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

	ctx, cancel := context.WithTimeout(context.Background(), duration)
	logging.Set(ctx, log)
	defer cancel()

	loopResults := looper.Run(ctx, f, cycle, *maxErrs, clock.GetSystemClock())

	if !loopResults.Success {
		log.Errorf("Failed to run loop, %v errors", loopResults.Errs)
		os.Exit(1)
	}
}
