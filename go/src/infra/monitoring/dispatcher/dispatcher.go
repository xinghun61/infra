// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Dispatcher usage:
// go run infra/monitoring/dispatcher
// Expects gatekeeper.json to be in the current directory.
// Runs a single check, prints out diagnosis and exits.
// TODO(seanmccullough): Run continuously.  Also, consider renaming to 'patrol'
// or 'scanner' because that's really what this thing does.

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"os"
	"strings"
	"time"

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

	log = gologger.Get()

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
		fmt.Printf("Runs a single check, prints out diagnosis and exits.\n")
		flag.PrintDefaults()
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

	masterNames := []string{}
	if *masterOnly != "" {
		masterNames = append(masterNames, *masterOnly)
	}

	err := readJSONFile(*gatekeeperJSON, &gk)
	if err != nil {
		log.Errorf("Error reading gatekeeper json: %v", err)
		os.Exit(1)
	}

	err = readJSONFile(*gatekeeperTreesJSON, &gkt)
	if err != nil {
		log.Errorf("Error reading gatekeeper json: %v", err)
		os.Exit(1)
	}

	a := analyzer.New(client.New(*dataURL), 2, 5)

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

	bes, errs := a.Client.BuildExtracts(masterNames)
	log.Infof("Build Extracts read: %d", len(bes))
	log.Infof("Errors: %d", len(errs))
	for url, err := range errs {
		log.Errorf("Error reading build extract from %s : %s", url, err)
	}

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
			os.Exit(1)
		}

		if err := ioutil.WriteFile("alerts.json", abytes, 0644); err != nil {
			log.Errorf("Couldn't write to alerts.json: %v", err)
			os.Exit(1)
		}
	} else {
		log.Infof("Posting alerts to %s", *dataURL)
		err := a.Client.PostAlerts(alerts)
		if err != nil {
			log.Errorf("Couldn't post alerts: %v", err)
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
