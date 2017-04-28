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

	"github.com/luci/luci-go/common/data/stringset"
)

const monorailURL = "https://bugs.chromium.org/p/%s/issues/detail?id=%s"

var (
	appName    = flag.String("app", "", "Name of the application")
	date       = flag.String("date", "", "YYYY-MM-DD. Release date.")
	sinceDate  = flag.String("since-date", "", "YYYY-MM-DD. All changes since this date.")
	sinceHash  = flag.String("since-hash", "", "All changes since this long hash.")
	bugRE      = regexp.MustCompile(`\n    BUG[=:][\s]*([0-9]+)`)
	monorailRE = regexp.MustCompile(`\n    BUG[=:][\s]*([a-z]+):([0-9]+)`)
	authorRE   = regexp.MustCompile("\nAuthor:.+<(.+)>")
	hashRE     = regexp.MustCompile("commit (.*)\n")
	reviewRE   = regexp.MustCompile("\n    (Review-Url|Reviewed-on): (.*)\n")
	extraPaths = flag.String("extra-paths", "", "Comma-separated list of extra paths to check.")

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
	Bugs    map[string]stringset.Set
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
	bugs := bugRE.FindAllStringSubmatch(strings.ToUpper(s), -1)
	for _, b := range bugs {
		c.bugs = append(c.bugs, fmt.Sprintf("https://crbug.com/%s", b[1]))
	}

	monorailBugs := monorailRE.FindAllStringSubmatch(strings.ToUpper(s), -1)
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
		return "", "", fmt.Errorf("could not determine currently deployed version")
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

func getUpdates(path string) (stringset.Set, []*commit, stringset.Set, map[string]stringset.Set) {
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
	authors := stringset.New(5)
	bugs := stringset.New(5)
	bugsByAuthor := map[string]stringset.Set{}
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
			bugs.Add(b)
			if _, ok := bugsByAuthor[c.Author]; !ok {
				bugsByAuthor[c.Author] = stringset.New(5)
			}
			bugsByAuthor[c.Author].Add(b)
		}
		commitsByAuthor[c.Author] = append(commitsByAuthor[c.Author], c)
		authors.Add(c.Author)
	}

	return authors, commits, bugs, bugsByAuthor
}

func main() {
	flag.Usage = usage
	flag.Parse()
	paths := flag.Args()
	if len(paths) == 0 {
		paths = []string{"."}
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

	authors, commits, bugs, bugsByAuthor := stringset.New(5), []*commit{}, stringset.New(5), map[string]stringset.Set{}
	for _, path := range paths {
		a, c, b, bba := getUpdates(path)
		authors = authors.Union(a)
		commits = append(commits, c...)
		bugs = bugs.Union(b)
		for author, bugs := range bba {
			if _, ok := bugsByAuthor[author]; !ok {
				bugsByAuthor[author] = stringset.New(5)
			}
			bugsByAuthor[author] = bugsByAuthor[author].Union(bugs)
		}
	}

	if *date == "" {
		today := time.Now().Format("2006-01-02")
		date = &today
	}

	data := tmplData{
		AppName: *appName,
		Date:    *date,
		NumBugs: bugs.Len(),
		Since:   fmt.Sprintf("%s (%s)", *sinceHash, *sinceDate),
		Authors: authors.ToSlice(),
		Commits: commits,
		Bugs:    bugsByAuthor,
	}

	f := bufio.NewWriter(os.Stdout)
	markdownTmpl.Execute(f, data)

	f.Flush()
}
