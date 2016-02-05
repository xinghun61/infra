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
)

const monorailURL = "https://bugs.chromium.org/p/%s/issues/detail?id=%s"

var (
	date       = flag.String("since-date", "", "YYYY-MM-DD. All changes since this date.")
	hash       = flag.String("since-hash", "", "All changes since this long hash.")
	bugRE      = regexp.MustCompile("\n    BUG=([0-9]+)")
	monorailRE = regexp.MustCompile("\n    BUG=([a-z]+):([0-9]+)")
	authorRE   = regexp.MustCompile("\nAuthor:.+<(.+)>")
	hashRE     = regexp.MustCompile("commit (.*)\n")
)

type commit struct {
	hash      string
	author    string
	committer string
	bugs      []string
}

func parseCommit(s string) *commit {
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
		c.author = a[1]
	}

	hashes := hashRE.FindAllStringSubmatch(s, -1)
	for _, h := range hashes {
		c.hash = h[1]
	}

	if strings.Trim(c.author, "\n\t ") == "" {
		fmt.Print(s)
	}
	return c
}

func main() {
	flag.Parse()
	var cmd *exec.Cmd
	switch {
	case *hash != "":
		cmd = exec.Command("git", "log", fmt.Sprintf("%s..", *hash), ".")
	case *date != "":
		cmd = exec.Command("git", "log", "--since", *date, ".")
	default:
		fmt.Printf("Please specify either --hash or --date\n")
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
	commits := re.Split(text, -1)[1:]

	commitsByBug := map[string][]*commit{}
	commitsByAuthor := map[string][]*commit{}
	authors := map[string]bool{}
	bugs := map[string]bool{}
	bugsByAuthor := map[string]map[string]bool{}

	for _, cstr := range commits {
		c := parseCommit(cstr)
		for _, b := range c.bugs {
			commitsByBug[b] = append(commitsByBug[b], c)
			bugs[b] = true
			if _, ok := bugsByAuthor[c.author]; !ok {
				bugsByAuthor[c.author] = map[string]bool{}
			}
			bugsByAuthor[c.author][b] = true
		}
		commitsByAuthor[c.author] = append(commitsByAuthor[c.author], c)
		authors[c.author] = true
	}

	fixed := []string{}
	for b := range bugs {
		fixed = append(fixed, b)
	}

	toNotify := []string{}
	for a := range authors {
		toNotify = append(toNotify, a)
	}

	fmt.Printf("%d Patches since %s %s\n", len(commits), *hash, *date)
	fmt.Printf("%d Authors:\n%v\n\n", len(toNotify), strings.Join(toNotify, ", "))
	fmt.Printf("%d Bugs\n", len(fixed))

	for a, bugs := range bugsByAuthor {
		fmt.Printf("\n%s's bugs:\n", a)
		for b := range bugs {
			fmt.Printf("%s\n", b)
		}
	}
}
