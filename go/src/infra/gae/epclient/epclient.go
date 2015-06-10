// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// The following comment allows `go generate` to correctly generate clients
// for all endpoints services located in the "infra/gae/epservice" package.
//go:generate goapp run epclient.go

// EPClient will auto-generate endpoints clients from Google Cloud Endpoint
// service definitions. The tool assumes that:
//   * all go endpoint service definitions occur in a package which has
//     a public method `RegisterEndpointsService(*endpoints.Server) error`, and
//     that calling this method will register the endpoints service with the
//     provided server or return an error.
//   * goapp exists in PATH (and understands all the import paths in the
//     defined services)
//   * google-api-go-generator exists in PATH.
package main

import (
	"flag"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

var (
	servicePackagesBase = flag.String("pkgs", "infra",
		"base Go package to walk to find service definitions.")
	outDir = flag.String("outdir", ".",
		"The directory to generate the client libraries in.")
)

const discoveryURL = "http://localhost:8080/_ah/api/discovery/v1/apis"

func boom(err error) {
	if err != nil {
		panic(err)
	}
}

func parseFlags() {
	var err error
	flag.Parse()
	if *outDir == "" {
		if *outDir, err = os.Getwd(); err != nil {
			panic(err)
		}
	}
	if *outDir, err = filepath.Abs(*outDir); err != nil {
		panic(err)
	}
}

func startServer() func() {
	boom(exec.Command("goapp", "install", "infra/gae/epservice").Run())
	server := exec.Command("epservice", "-base", *servicePackagesBase)
	server.Stdout = os.Stdout
	server.Stderr = os.Stderr
	if err := server.Start(); err != nil {
		panic(err)
	}

	deadline := time.Now().Add(time.Second * 5)
	for {
		if time.Now().After(deadline) {
			panic("waited too long for server to start!")
		}
		rsp, err := http.Get(discoveryURL)
		if err == nil && rsp.StatusCode == 200 {
			break
		}
		time.Sleep(time.Millisecond * 200)
	}
	fmt.Println("Discovery service up")

	return func() {
		server.Process.Signal(os.Interrupt)
		server.Wait()
	}
}

func generate() {
	gencmd := exec.Command("google-api-go-generator", "-discoveryurl", discoveryURL, "-gendir", *outDir, "-cache=false")
	gencmd.Stdout = os.Stdout
	gencmd.Stderr = os.Stderr
	if err := gencmd.Run(); err != nil {
		panic(err)
	}
}

func mustHave(executable string) {
	_, err := exec.LookPath(executable)
	if err != nil {
		panic(executable + " must be on your path")
	}
}

func main() {
	mustHave("goapp")
	mustHave("google-api-go-generator")

	parseFlags()

	stop := startServer()
	defer stop()
	generate()

	// inject DoWithRetries methods.
}
