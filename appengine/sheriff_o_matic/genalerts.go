// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// genalerts is a command line utility to POST generated alerts json to
// sheriff-o-matic. Typically you would use this on a local development
// instance or http://sheriff-o-matic-staging.appspot.com/alerts
// Example:
// % go run genalerts.go -s 42 -n 1000 -url http://localhost:8080/alerts
// Uses 42 as the random seed and posts 1000 alerts to localhost:8080/alerts

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"net/http/httputil"
	"net/url"
)

var (
	r *rand.Rand

	labels = [][]string{
		{"", "last_", "latest_", "failing_", "passing_"},
		{"build", "builder", "revision"},
		{"", "s", "_url", "_reason", "_name"},
	}
	tests = [][]string{
		{"Activity", "Async", "Browser", "Content", "Input"},
		{"Manager", "Card", "Sandbox", "Container"},
		{"Test."},
		{"", "Basic", "Empty", "More"},
		{"Mouse", "App", "Selection", "Network", "Grab"},
		{"Input", "Click", "Failure", "Capture"},
	}

	n         = flag.Uint("n", 1, "Number of alerts to generate")
	seed      = flag.Int64("s", 0, "Seed for the random number generator")
	postUrl   = flag.String("url", "", "URL to POST the alerts to")
	alsoPrint = flag.Bool("p", false, "Print to stdout, if url has been specified")
)

func randn(l, u int64) int64 {
	return r.Int63n(u-l) + u
}

func randStr(s [][]string) string {
	ret := ""
	for _, p := range s {
		ret += p[r.Uint32()%uint32(len(p))]
	}
	return ret
}

func label() string { return randStr(labels) }

func test() interface{} { return randStr(tests) }

func time() interface{} { return float64(randn(1407976107614, 1408076107614)) / float64(101.0) }

func build() interface{} { return randn(2737, 2894) }

func revision() interface{} { return randn(288849, 289415) }

type genfunc func() interface{}

func choice(f ...genfunc) interface{} {
	return f[r.Uint32()%uint32(len(f))]()
}

func litArray() []interface{} {
	ret := make([]interface{}, 0)
	for i := 0; i < int(randn(0, 10)); i++ {
		ret = append(ret, choice(time, build, revision))
	}

	return ret
}

func litMap() map[string]interface{} {
	ret := make(map[string]interface{})
	for i := 0; i < int(randn(3, 9)); i++ {
		switch r.Uint32() % 4 {
		case 0:
			ret[label()] = litArray()
		default:
			ret[label()] = choice(build, revision, test)
		}
	}
	return ret
}

func newValue() interface{} {
	switch r.Uint32() % 6 {
	case 0:
		return litArray()
	case 1:
		return litMap()
	default:
		return choice(time, build, revision, test)
	}
}

func newAlert() map[string]interface{} {
	ret := make(map[string]interface{})
	nlabel := int(randn(6, 9))

	for i := 0; i < nlabel; i++ {
		ret[label()] = newValue()
	}

	return ret
}

func main() {
	flag.Parse()
	r = rand.New(rand.NewSource(*seed))

	alerts := make([]map[string]interface{}, 0)

	for i := uint(0); i < *n; i++ {
		alerts = append(alerts, newAlert())
	}

	alertsWrapper := map[string]interface{}{
		"alerts": alerts,
	}

	b, err := json.MarshalIndent(alertsWrapper, "", "\t")
	if err != nil {
		log.Fatalf("%v", err)
	}

	if *postUrl == "" || *alsoPrint {
		fmt.Printf("%s\n", b)
	}

	if *postUrl != "" {
		resp, err := http.PostForm(*postUrl, url.Values{"content": []string{string(b)}})
		if err != nil {
			log.Fatalf("%v", err)
		}
		rb, err := httputil.DumpResponse(resp, true)
		if err != nil {
			log.Fatalf("%v", err)
		}
		log.Printf("%v\n", string(rb))
	}

	log.Printf("json size: %v\n", len(b))
}
