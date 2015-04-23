// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Dispatcher usage:
// go run infra/monitoring/dispatcher
// Expects gatekeeper.json to be in the current directory.
// Runs a single check, prints out diagnosis and exits.
// TODO(seanmccullough): Run continuously.

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"os"
	"time"

	"github.com/Sirupsen/logrus"

	"infra/monitoring/analyzer"
	"infra/monitoring/messages"
)

var (
	dataURL             = flag.String("data_url", "", "Url where alerts are stored")
	masterFilter        = flag.String("master-filter", "", "Filter out masters that contain this string")
	masterOnly          = flag.String("master", "", "Only check this master")
	mastersOnly         = flag.Bool("masters-only", false, "Just check for master alerts, not builders")
	gatekeeperJSON      = flag.String("gatekeeper", "gatekeeper.json", "Location of gatekeeper json file")
	gatekeeperTreesJSON = flag.String("gatekeeper-trees", "gatekeeper_trees.json", "Location of gatekeeper json file")

	log = logrus.New()

	// gk is the gatekeeper config.
	gk = &struct {
		// Weird. Are there ever multiple configs per master key?
		Masters map[string][]messages.MasterConfig `json:"masters"`
	}{}
	filteredFailures = uint64(0)
)

func init() {
	flag.Usage = func() {
		fmt.Printf("Runs a single check, prints out diagnosis and exits.\n")
		flag.PrintDefaults()
	}
}

func analyzeBuildExtract(a *analyzer.Analyzer, url string, b *messages.BuildExtract) []messages.Alert {
	ret := a.MasterAlerts(url, b)
	if *mastersOnly {
		return ret
	}

	return append(ret, a.BuilderAlerts(url, b)...)
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

func main() {
	start := time.Now()
	flag.Parse()

	mURLs := []string{}
	if *masterOnly != "" {
		mURLs = append(mURLs, *masterOnly)
	}

	err := readJSONFile(*gatekeeperJSON, &gk)
	if err != nil {
		log.Fatalf("Error reading gatekeeper json: %v", err)
	}

	// Use a direct reference to the client implementation so we can
	// report request processing stats.
	a := analyzer.New(nil, 10)

	bes, errs := a.Client.BuildExtracts(mURLs)
	log.Infof("Build Extracts read: %d", len(bes))
	log.Infof("Errors: %d", len(errs))
	for url, err := range errs {
		log.Errorf("Error reading build extract from %s : %s", url, err)
	}

	alerts := &messages.Alerts{}

	for url, be := range bes {
		alerts.Alerts = append(alerts.Alerts, analyzeBuildExtract(a, url, be)...)
	}
	alerts.Timestamp = messages.TimeToEpochTime(time.Now())

	if *dataURL == "" {
		log.Infof("No data_url provided. Writing to alerts.json")

		abytes, err := json.MarshalIndent(alerts, "", "\t")
		if err != nil {
			log.Errorf("Couldn't marshal alerts json: %v", err)
			os.Exit(1)
		}

		if err := ioutil.WriteFile("alerts.json", abytes, 0644); err != nil {
			log.Errorf("Couldn't write to alerts.json: %v", err)
			os.Exit(1)
		}
	}

	log.Infof("Filtered failures: %v", filteredFailures)
	a.Client.DumpStats()
	log.Infof("Elapsed time: %v", time.Since(start))
	if len(errs) > 0 {
		os.Exit(1)
	}
}
