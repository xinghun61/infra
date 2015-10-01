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
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
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

type apiItem struct {
	ID      string `json:"id"`
	Name    string `json:"name"`
	Version string `json:"version"`
}

type apiList struct {
	Items []apiItem `json:"items"`
}

func fixImportPath(path string) {
	err := filepath.Walk(path, func(path string, info os.FileInfo, err error) error {
		if strings.HasSuffix(path, "-gen.go") {
			fmt.Println("fixing import line in", path)
			if err != nil {
				panic(err)
			}
			wholeFile, err := ioutil.ReadFile(path)
			if err != nil {
				panic(err)
			}
			newFile := bytes.Replace(wholeFile,
				[]byte("// import \"google.golang.org/api"),
				[]byte("// import \"infra/gae/epclient"),
				-1)
			err = ioutil.WriteFile(path, newFile, info.Mode())
			if err != nil {
				panic(err)
			}
		}
		return nil
	})
	if err != nil {
		panic(err)
	}
}

func generate() {
	// generate api-list.json
	genlist := exec.Command("google-api-go-generator", "-discoveryurl", discoveryURL, "-gendir", *outDir, "-cache=false", "-api=\"\"")
	genlist.Stdout = os.Stdout
	genlist.Stderr = os.Stderr
	genlist.Run()

	apiListFile, err := os.Open(filepath.Join(*outDir, "api-list.json"))
	if err != nil {
		panic(err)
	}
	defer apiListFile.Close()

	al := apiList{}
	err = json.NewDecoder(apiListFile).Decode(&al)
	if err != nil {
		panic(err)
	}

	for _, itm := range al.Items {
		gencmd := exec.Command("google-api-go-generator", "-discoveryurl", discoveryURL,
			"-gendir", *outDir, "-cache=false", "-api="+itm.ID)
		gencmd.Stdout = os.Stdout
		gencmd.Stderr = os.Stderr
		err = gencmd.Run()
		if err != nil {
			panic(err)
		}
		fixImportPath(filepath.Join(*outDir, itm.Name, itm.Version))
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
