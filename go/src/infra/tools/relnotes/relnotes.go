// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
CLI tool to generate release notes based on git logs in the current directory.
Usage examples:
go run relnotes.go -since-hash 7bb5fff0fcb57b467a8f907aeee9117e09106d06
or
go run relnotes.go -since-date 2016-02-04
*/
package main

import (
	"bufio"
	"flag"
	"fmt"
	"io/ioutil"
	"os"
	"os/exec"
	"regexp"
	"strings"
	"text/template"
	"time"

	"golang.org/x/net/context"
	"golang.org/x/oauth2/google"
	"gopkg.in/yaml.v2"

	appengine "google.golang.org/api/appengine/v1"
)

const monorailURL = "https://bugs.chromium.org/p/%s/issues/detail?id=%s"

var (
	appName    = flag.String("app", "", "Name of the application")
	date       = flag.String("date", "", "YYYY-MM-DD. Release date.")
	sinceDate  = flag.String("since-date", "", "YYYY-MM-DD. All changes since this date.")
	sinceHash  = flag.String("since-hash", "", "All changes since this long hash.")
	bugRE      = regexp.MustCompile("\n    BUG[=:][[:space:]]+([0-9]+)")
	monorailRE = regexp.MustCompile("\n    BUG[=:][[:space:]]+([a-z]+):([0-9]+)")
	authorRE   = regexp.MustCompile("\nAuthor:.+<(.+)>")
	hashRE     = regexp.MustCompile("commit (.*)\n")
	reviewRE   = regexp.MustCompile("\n    (Review-Url|Reviewed-on): (.*)\n")

	markdownTxt = `
# Release Notes {{.AppName}} {{.Date}}

- {{len .Commits}} commits, {{.NumBugs}} bugs affected since {{.Since}}
- {{len .Authors}} Authors:
{{- range .Authors}}
  - {{ . }}
{{- end}}

## Changes in this release

{{range .Commits -}}
- [{{.Summary}}]({{.ReviewURL}}) ({{.Author}})
{{end}}

## Bugs updated, by author
{{range $author, $bugs := .Bugs -}}
- {{$author}}:
  {{range $bug, $unused := $bugs -}}
  -  [{{$bug}}]({{$bug}})
  {{end}}
{{end}}
`
	markdownTmpl = template.Must(template.New("markdown").Parse(markdownTxt))
)

type tmplData struct {
	AppName string
	Date    string
	NumBugs int
	Since   string
	Authors []string
	Commits []*commit
	Bugs    map[string]map[string]bool
}

type commit struct {
	hash      string
	Author    string
	committer string
	Summary   string
	ReviewURL string
	bugs      []string
}

func parsecommit(s string) *commit {
	c := &commit{}
	bugs := bugRE.FindAllStringSubmatch(s, -1)
	for _, b := range bugs {
		c.bugs = append(c.bugs, fmt.Sprintf("https://crbug.com/%s", b[1]))
	}

	monorailBugs := monorailRE.FindAllStringSubmatch(s, -1)
	for _, b := range monorailBugs {
		c.bugs = append(c.bugs, fmt.Sprintf(monorailURL, b[1], b[2]))
	}

	authors := authorRE.FindAllStringSubmatch(s, -1)
	for _, a := range authors {
		c.Author = a[1]
	}

	hashes := hashRE.FindAllStringSubmatch(s, -1)
	for _, h := range hashes {
		c.hash = h[1]
	}

	c.Summary = strings.Trim(strings.Split(s, "\n")[4], " \t")
	reviewURL := reviewRE.FindAllStringSubmatch(s, -1)
	if len(reviewURL) > 0 && len(reviewURL[0]) > 2 {
		c.ReviewURL = reviewURL[0][2]
	}

	if strings.Trim(c.Author, "\n\t ") == "" {
		fmt.Print(s)
	}
	return c
}

func usage() {
	fmt.Fprintf(os.Stderr, "Usage of %s <flags> [relative path]:\n", os.Args[0])
	flag.PrintDefaults()
}

func gaeService() (*appengine.APIService, error) {
	creds := os.Getenv("GOOGLE_APPLICATION_CREDENTIALS")
	if creds == "" {
		fmt.Printf("Warning: you do not have the GOOGLE_APPLICATION_CREDENTIALS environment variable set. Cloud API calls may not work properly.\n")
	} else {
		fmt.Printf("Using GOOGLE_APPLICATION_CREDENTIALS: %s\n", creds)
	}

	ctx := context.Background()
	client, err := google.DefaultClient(ctx, appengine.CloudPlatformScope)
	if err != nil {
		return nil, err
	}
	appengineService, err := appengine.New(client)
	return appengineService, err
}

// getDeployedApp returns the hash and date string, or an error.
func getDeployedApp(service, module string) (string, string, error) {
	gaeSvc, err := gaeService()
	if err != nil {
		return "", "", err
	}

	appsSvc := appengine.NewAppsService(gaeSvc)
	versionsListCall := appsSvc.Services.Versions.List(*appName, "default")
	versionsList, err := versionsListCall.Do()
	if err != nil {
		return "", "", err
	}
	var deployedVers *appengine.Version
	// This is a heuristic to determine which version is "deployed" - use
	// the latest verison (by creation timestamp) that is "SERVING". More
	// accurate would be to look at traffic splits and pick the one that
	// has the most (or all) traffic going to it. Unfortunately the API
	// doesn't appear to expose that information(!).
	for _, vers := range versionsList.Versions {
		if vers.ServingStatus == "SERVING" && (deployedVers == nil ||
			deployedVers.CreateTime < vers.CreateTime) {
			deployedVers = vers
		}
	}

	if deployedVers == nil {
		return "", "", fmt.Errorf("Could not determine currently deployed version.\n")
	}

	versRE := regexp.MustCompile("([0-9]+)-([0-9a-f]+)")
	matches := versRE.FindAllStringSubmatch(deployedVers.Id, -1)

	return matches[0][2], deployedVers.CreateTime, nil
}

func getAppNameFromYAML() (string, error) {
	type appStruct struct {
		Application string
	}

	in, err := os.Open("app.yaml")
	if err != nil {
		return "", err
	}

	b, err := ioutil.ReadAll(in)
	if err != nil {
		return "", err
	}

	app := &appStruct{}
	if err := yaml.Unmarshal(b, app); err != nil {
		return "", err
	}

	return app.Application, nil
}

func main() {
	flag.Usage = usage
	flag.Parse()
	args := flag.Args()
	path := "."
	if len(args) > 0 {
		path = args[0]
	}

	if *appName == "" {
		s, err := getAppNameFromYAML()
		if err != nil {
			fmt.Printf("Error getting app name from app.yaml: %v", err)
			os.Exit(1)
		}
		appName = &s
		fmt.Printf("Got app name from app.yaml: %s\n", *appName)
	}

	if *sinceHash == "" && *sinceDate == "" {
		hash, date, err := getDeployedApp(*appName, "default")
		if err != nil {
			fmt.Printf("Error trying to get currently deployed app hash: %v\n", err)
			fmt.Printf("Please specify either --since-hash or --since-date\n")
			os.Exit(1)
		}
		sinceHash = &hash
		sinceDate = &date
	}

	var cmd *exec.Cmd
	switch {
	case *sinceHash != "":
		cmd = exec.Command("git", "log", fmt.Sprintf("%s..", *sinceHash), path)
	case *sinceDate != "":
		cmd = exec.Command("git", "log", "--since", *sinceDate, path)
	default:
		fmt.Printf("Please specify either --since-hash or --since-date\n")
		os.Exit(1)
	}
	cmd.Stderr = os.Stderr

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		fmt.Printf("Error getting stdout: %v", err)
		os.Exit(1)
	}
	cmd.Start()
	r := bufio.NewReader(stdout)
	bytes, err := ioutil.ReadAll(r)
	if err != nil {
		fmt.Printf("Error reading stdout: %v", err)
		os.Exit(1)
	}
	text := string(bytes)
	re := regexp.MustCompile("(^|\n)commit ")
	commitMsgs := re.Split(text, -1)[1:]

	commitsByBug := map[string][]*commit{}
	commitsByAuthor := map[string][]*commit{}
	authors := map[string]bool{}
	bugs := map[string]bool{}
	bugsByAuthor := map[string]map[string]bool{}
	summaries := []string{}
	commits := []*commit{}

	for _, cstr := range commitMsgs {
		c := parsecommit(cstr)
		if c.ReviewURL == "" {
			continue
		}
		commits = append(commits, c)
		summaries = append(summaries, c.Summary)
		for _, b := range c.bugs {
			commitsByBug[b] = append(commitsByBug[b], c)
			bugs[b] = true
			if _, ok := bugsByAuthor[c.Author]; !ok {
				bugsByAuthor[c.Author] = map[string]bool{}
			}
			bugsByAuthor[c.Author][b] = true
		}
		commitsByAuthor[c.Author] = append(commitsByAuthor[c.Author], c)
		authors[c.Author] = true
	}

	fixed := []string{}
	for b := range bugs {
		fixed = append(fixed, b)
	}

	toNotify := []string{}
	for a := range authors {
		toNotify = append(toNotify, a)
	}

	if *date == "" {
		today := time.Now().Format("2006-01-02")
		date = &today
	}

	data := tmplData{
		AppName: *appName,
		Date:    *date,
		NumBugs: len(fixed),
		Since:   fmt.Sprintf("%s (%s)", *sinceHash, *sinceDate),
		Authors: toNotify,
		Commits: commits,
		Bugs:    bugsByAuthor,
	}

	f := bufio.NewWriter(os.Stdout)
	markdownTmpl.Execute(f, data)

	f.Flush()
}
