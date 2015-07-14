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
	"github.com/luci/luci-go/common/logging/gologger"

	"infra/monitoring/analyzer"
	"infra/monitoring/client"
	"infra/monitoring/messages"
)

var (
	dataURL             = flag.String("data_url", "", "Url where alerts are stored")
	masterFilter        = flag.String("master-filter", "", "Filter out masters that contain this string")
	masterOnly          = flag.String("master", "", "Only check this master")
	mastersOnly         = flag.Bool("masters-only", false, "Just check for master alerts, not builders")
	gatekeeperJSON      = flag.String("gatekeeper", "gatekeeper.json", "Location of gatekeeper json file")
	gatekeeperTreesJSON = flag.String("gatekeeper-trees", "gatekeeper_trees.json", "Location of gatekeeper json file")
	treeOnly            = flag.String("tree", "", "Only check this tree")
	builderOnly         = flag.String("builder", "", "Only check this builder")
	buildOnly           = flag.Int64("build", 0, "Only check this build")
	maxErrs             = flag.Int("max-errs", 1, "Max consecutive errors per loop attempt")
	durationStr         = flag.String("duration", "10s", "Max duration to loop for")
	cycleStr            = flag.String("cycle", "1s", "Cycle time for loop")
	snapshot            = flag.String("record-snapshot", "", "save a snapshot of infra responses to this path, which will be created if it does not already exist.")
	replay              = flag.String("replay-snapshot", "", "replay a snapshot of infra responses from this path, which should have been created previously by running with --record-snapshot.")

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

type loopResults struct {
	// success is true if no errors, or all failed attempts succeeded on within maxErrs
	// subsequent attempts.
	success bool
	// overruns counts the total number of overruns.
	overruns int
	// errs counts total number of errors, some may have been retried.
	errs int
}

/*
This is slightly different from what outer_loop.py does.

outer_loop.py (very roughly) runs this loop:
  run task
  sleep for sleep_timeout
  if now - start_time > duration:
    return
  back to top of loop

Because sleep_timeout always happens on every iteration, a persistent
one-time increase in runtime for the task will lead to less frequent
runs of the task.

This implementation OTOH tries to make task runtime and frequency of
task runs independent. If the task runtime increases by a constant factor,
the subsequent task completion times will simply all shift forward by that
amount. The frequency of starts and completions will be the same, just
phase-shifted.

However, if runtime *exceeds* the requested cycle time, the overall
frequency will again decrease. This is mitigated somewhat by logging
errors on task overruns, and is something we should probably consider an
alertable condition.

TODO: A more robust mechanism would specify overrun policies

Inspired by
https://chromium.googlesource.com/infra/infra/+/master/infra/libs/service_utils/outer_loop.py
*/
func loop(f func() error, cycle, duration time.Duration, maxErrs int, c clock.Clock) *loopResults {
	// TODO: ts_mon stuff.
	ret := &loopResults{success: true}

	startTime := c.Now()

	tmr := c.NewTimer()
	tmr.Reset(0 * time.Second) // Run the first one right away.
	defer tmr.Stop()

	nextCycle := cycle
	consecErrs := 0
	for {
		<-tmr.GetC()
		t0 := c.Now()
		err := f()
		dur := c.Now().Sub(t0)
		if dur > cycle {
			log.Errorf("Task overran by %v (%v - %v)", (dur - cycle), dur, cycle)
			ret.overruns++
		}

		if err != nil {
			log.Errorf("Got an error: %v", err)
			ret.errs++
			if consecErrs++; consecErrs >= maxErrs {
				ret.success = false
				return ret
			}
		} else {
			consecErrs = 0
		}

		if c.Now().Sub(startTime) > duration {
			tmr.Stop()
			return ret
		}

		nextCycle = cycle - dur
		if tmr.Reset(nextCycle) {
			log.Errorf("Timer was still active")
		}
	}
}

func analyzeBuildExtract(a *analyzer.MasterAnalyzer, masterName string, b *messages.BuildExtract) []messages.Alert {
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

	masterNames := []string{}
	if *masterOnly != "" {
		masterNames = append(masterNames, *masterOnly)
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

	a := analyzer.New(r, 2, 5)
	w := client.NewWriter(*dataURL)

	for masterURL, masterCfgs := range gk.Masters {
		if len(masterCfgs) != 1 {
			log.Errorf("Multiple configs for master: %s", masterURL)
			os.Exit(1)
		}
		masterName := masterFromURL(masterURL)
		a.MasterCfgs[masterName] = masterCfgs[0]
	}

	a.TreeOnly = *treeOnly
	a.MasterOnly = *masterOnly
	a.BuilderOnly = *builderOnly
	a.BuildOnly = *buildOnly

	if *treeOnly != "" {
		if t, ok := gkt[*treeOnly]; ok {
			for _, url := range t.Masters {
				masterNames = append(masterNames, masterFromURL(url))
			}
		} else {
			log.Errorf("Unrecoginzed tree: %s", *treeOnly)
			os.Exit(1)
		}
	}

	bes := map[string]*messages.BuildExtract{}
	for _, masterName := range masterNames {
		be, err := a.Reader.BuildExtract(masterName)
		if be != nil {
			bes[masterName] = be
		}
		if err != nil {
			log.Errorf("Error reading build extract from %s : %s", masterName, err)
		}
	}

	log.Infof("Build Extracts read: %d", len(bes))

	// This is the polling/analysis/alert posting function, which will run in a loop until
	// a timeout or max errors is reached.
	f := func() error {
		alerts := &messages.Alerts{}
		for masterName, be := range bes {
			alerts.Alerts = append(alerts.Alerts, analyzeBuildExtract(a, masterName, be)...)
		}
		alerts.Timestamp = messages.TimeToEpochTime(time.Now())

		if *dataURL == "" {
			log.Infof("No data_url provided. Writing to alerts.json")

			abytes, err := json.MarshalIndent(alerts, "", "\t")
			if err != nil {
				log.Errorf("Couldn't marshal alerts json: %v", err)
				return err
			}

			if err := ioutil.WriteFile("alerts.json", abytes, 0644); err != nil {
				log.Errorf("Couldn't write to alerts.json: %v", err)
				return err
			}
		} else {
			log.Infof("Posting alerts to %s", *dataURL)
			err := w.PostAlerts(alerts)
			if err != nil {
				log.Errorf("Couldn't post alerts: %v", err)
				return err
			}
		}

		log.Infof("Filtered failures: %v", filteredFailures)
		a.Reader.DumpStats()
		log.Infof("Elapsed time: %v", time.Since(start))

		return nil
	}

	loopResults := loop(f, cycle, duration, *maxErrs, clock.GetSystemClock())

	if !loopResults.success {
		log.Errorf("Failed to run loop, %v errors", loopResults.errs)
		os.Exit(1)
	}
}
