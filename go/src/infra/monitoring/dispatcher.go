// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Dispatcher usage:
// go run infra/monitoring/dispatcher.go
// Expects gatekeeper.json to be in the current director.
// Runs a single check, prints out diagnosis and exits.
// TODO(seanmccullough): Run continuously.

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"net/http"
	"os"
	"strings"
	"sync"

	"github.com/Sirupsen/logrus"

	"infra/monitoring/messages"
)

var (
	dataURL             = flag.String("data_url", "", "Url where alerts are stored")
	masterFilter        = flag.String("master-filter", "", "Filter out masters that contain this string")
	gatekeeperJSON      = flag.String("gatekeeper", "gatekeeper.json", "Location of gatekeeper json file")
	gatekeeperTreesJSON = flag.String("gatekeeper-trees", "gatekeeper_trees.json", "Location of gatekeeper json file")

	log = logrus.New()
)

func init() {
	flag.Usage = func() {
		fmt.Printf("Runs a single check, prints out diagnosis and exits.\n")
		flag.PrintDefaults()
	}
}

func analyzeBuildExtract(url string, b *messages.BuildExtract) {
	builderAlerts, staleMasterAlerts := MasterAlerts(url, b)
	for _, ba := range builderAlerts {
		log.Infof("Builder Alert: %v", ba)
	}

	for _, sma := range staleMasterAlerts {
		log.Infof("Stale Masters Alert: %v", sma)
	}
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

// getJSON does a simple HTTP GET on a JSON endpoint.
//
// Returns the status code and the error, if any.
func getJSON(c *http.Client, url string, v interface{}) (int, error) {
	log.Infof("Fetching json: %s", url)
	if c == nil {
		c = http.DefaultClient
	}
	resp, err := c.Get(url)
	if err != nil {
		return 0, fmt.Errorf("couldn't resolve %s: %s", url, err)
	}
	defer resp.Body.Close()
	if err := json.NewDecoder(resp.Body).Decode(v); err != nil {
		return resp.StatusCode, fmt.Errorf("bad response %s: %s", url, err)
	}
	ct := strings.ToLower(resp.Header.Get("Content-Type"))
	expected := "application/json"
	if ct != expected {
		return resp.StatusCode, fmt.Errorf("unexpected Content-Type, expected \"%s\", got \"%s\"", expected, ct)
	}
	if resp.StatusCode >= 400 {
		return resp.StatusCode, fmt.Errorf("http status %d", resp.StatusCode)
	}
	return resp.StatusCode, nil
}

func fetchBuildExtracts(urls []string) (map[string]*messages.BuildExtract, map[string]error) {
	var wg sync.WaitGroup

	type r struct {
		url string
		be  *messages.BuildExtract
		err error
	}

	c := make(chan r, len(urls))

	for _, u := range urls {
		wg.Add(1)
		go func(url string) {
			out := r{url: url}
			defer func() {
				c <- out
				wg.Done()
			}()

			out.be = &messages.BuildExtract{}
			_, out.err = getJSON(nil, url, out.be)
		}(u)
	}

	ret := map[string]*messages.BuildExtract{}
	errs := map[string]error{}
	for _ = range urls {
		r := <-c
		if r.err != nil {
			errs[r.url] = r.err
		} else {
			ret[r.url] = r.be
		}
	}

	return ret, errs
}

func masterURLs(masters map[string]interface{}, filter string) ([]string, error) {
	ret := []string{}
	for k := range masters {
		if filter == "" || !strings.Contains(k, filter) {
			ret = append(ret, strings.Replace(k, "https://build.chromium.org/p",
				"https://chrome-build-extract.appspot.com/get_master", 1))
		}
	}

	return ret, nil
}

func main() {
	flag.Parse()

	gk := &struct {
		Masters map[string]interface{} `json:"masters"`
	}{}
	err := readJSONFile(*gatekeeperJSON, &gk)
	if err != nil {
		log.Fatalf("Error reading gatekeeper json: %v", err)
	}

	mURLs, err := masterURLs(gk.Masters, *masterFilter)
	if err != nil {
		log.Fatalf("Error reading master URLs from gatekeeper json: %v", err)
	}

	bes, errs := fetchBuildExtracts(mURLs)
	log.Infof("Build Extracts read: %d", len(bes))
	log.Infof("Errors: %d", len(errs))
	for url, err := range errs {
		log.Errorf("Error reading build extract from %s : %s", url, err)
	}

	for url, be := range bes {
		analyzeBuildExtract(url, be)
	}

	if len(errs) > 0 {
		os.Exit(1)
	}
}
