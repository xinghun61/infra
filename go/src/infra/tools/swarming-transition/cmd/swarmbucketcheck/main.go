// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"flag"
	"fmt"
	"net/http"
	"os"
	"sort"
	"strings"
	"time"

	"github.com/luci/luci-go/common/api/buildbucket/buildbucket/v1"
)

var since = flag.Int64("since", 0, "analyze builds since this timestamp. Defaults to 10 days ago.")
var bucket = flag.String("bucket", "", `buildbucket bucket name, e.g. "master.tryserver.infra"`)
var builders = flag.String("builder", "", `comma-separated list of builder names without swarming suffix, e.g. "Infra Presubmit"`)

const swarmingSuffix = " (Swarming)"

func fetchBuilds(bucket, builder string, startingFrom time.Time) ([]*buildbucket.ApiBuildMessage, error) {
	client, err := buildbucket.New(http.DefaultClient)
	if err != nil {
		return nil, err
	}
	client.BasePath = "https://cr-buildbucket.appspot.com/_ah/api/buildbucket/v1/"

	req := client.Search()
	req.Bucket(bucket)
	req.Tag("builder:" + builder)
	req.Status("COMPLETED")
	req.MaxBuilds(100)

	var result []*buildbucket.ApiBuildMessage
	for {
		res, err := req.Do()
		if err != nil {
			return result, err
		}
		if res.Error != nil {
			return result, fmt.Errorf(res.Error.Message)
		}

		for _, b := range res.Builds {
			if parseTimestamp(b.CreatedTs).Before(startingFrom) {
				return result, nil
			}
			result = append(result, b)
		}

		if len(res.Builds) == 0 || res.NextCursor == "" {
			break
		}
		req.StartCursor(res.NextCursor)
	}
	return result, nil
}

type buildSet struct {
	builds     []*buildbucket.ApiBuildMessage
	bestResult string
}

// groupBuilds groups builds by buildset tag.
func groupBuilds(builds []*buildbucket.ApiBuildMessage) map[string]*buildSet {
	results := map[string]*buildSet{}
	for _, b := range builds {
		tags := parseTags(b.Tags)
		buildSetName := tags["buildset"]
		if buildSetName == "" {
			fmt.Printf("skipped build %d: no buildset tag\n", b.Id)
			continue
		}
		set := results[buildSetName]
		if set == nil {
			set = &buildSet{}
			results[buildSetName] = set
		}

		set.builds = append(set.builds, b)
		if set.bestResult == "" || b.Result == "SUCCESS" {
			set.bestResult = b.Result
		}
	}
	return results
}

// medianTime returns median completed_time - created_time of successful builds.
func medianTime(builds []*buildbucket.ApiBuildMessage) time.Duration {
	if len(builds) == 0 {
		return 0
	}
	durations := make(durationSlice, 0, len(builds))
	for _, b := range builds {
		if b.Result != "SUCCESS" {
			continue
		}
		created := parseTimestamp(b.CreatedTs)
		completed := parseTimestamp(b.CompletedTs)
		durations = append(durations, completed.Sub(created))
	}
	sort.Sort(durations)
	return durations[len(durations)/2]
}

func run() error {
	flag.Parse()
	if *bucket == "" {
		return fmt.Errorf("bucket is not specified")
	}
	if *builders == "" {
		return fmt.Errorf("builders are not specified")
	}
	if len(flag.Args()) > 0 {
		return fmt.Errorf("unexpected arguments: %s", flag.Args())
	}

	var startingFrom time.Time
	var duration time.Duration
	if *since == 0 {
		duration = 240 * time.Hour
		startingFrom = time.Now().Add(-duration)
	} else {
		startingFrom = time.Unix(*since, 0)
		duration = time.Since(startingFrom)
	}

	for i, builder := range strings.Split(*builders, ",") {
		builder = strings.TrimSpace(builder)
		if builder == "" {
			continue
		}

		if i > 0 {
			fmt.Println()
		}
		fmt.Printf("builder %q\n", builder)
		if err := compareBuilder(builder, startingFrom); err != nil {
			return err
		}
	}
	return nil
}

func compareBuilder(builder string, startingFrom time.Time) error {
	fmt.Printf("searching for all builds since timestamp %d till %d...\n",
		startingFrom.Unix(), time.Now().Unix())
	// We will actually fetch builds after after time.Now too, but it is fine.
	swarmingBuilds, err := fetchBuilds(*bucket, builder+swarmingSuffix, startingFrom)
	if err != nil {
		return fmt.Errorf("could not fetch builds: %s", err)
	}
	if len(swarmingBuilds) == 0 {
		fmt.Printf("no swarming builds for builder %q\n", builder)
		return nil
	}
	buildbotBuilds, err := fetchBuilds(*bucket, builder, startingFrom)
	if err != nil {
		return fmt.Errorf("could not fetch builds: %s", err)
	}
	if len(buildbotBuilds) == 0 {
		fmt.Printf("no buildbot builds for builder %q\n", builder)
		return nil
	}

	swarmingBuildSets := groupBuilds(swarmingBuilds)
	buildbotBuildSets := groupBuilds(buildbotBuilds)

	consistentN := 0
	inconsistentN := 0
	for setName, swarmingSet := range swarmingBuildSets {
		buildbotSet := buildbotBuildSets[setName]
		if buildbotSet == nil {
			fmt.Printf("no buildbot builds for buildset %s\n", setName)
			continue
		}
		if buildbotSet.bestResult == swarmingSet.bestResult {
			consistentN++
			continue
		}
		inconsistentN++

		fmt.Printf("%s is inconsistent\n", setName)
		for _, b := range swarmingSet.builds {
			fmt.Printf("  %s %s\n", b.Result, b.Url)
		}
		for _, b := range buildbotSet.builds {
			fmt.Printf("  %s %s\n", b.Result, b.Url)
		}
	}

	fmt.Printf("%0.2f%% consistent build sets, %d buildbot builds, %d swarming builds\n",
		100*float64(consistentN)/float64(consistentN+inconsistentN), len(buildbotBuilds), len(swarmingBuilds))

	swarmingTime := medianTime(swarmingBuilds)
	buildbotTime := medianTime(buildbotBuilds)
	factor := float64(buildbotTime) / float64(swarmingTime)
	if factor >= 1 {
		fmt.Printf("swarming is %.1fx faster\n", factor)
	} else {
		fmt.Printf("swarming is %.1fx slower\n", 1/factor)
	}
	fmt.Printf("median times: buildbot %s, swarming %s\n", buildbotTime, swarmingTime)

	return nil
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func parseTags(tags []string) map[string]string {
	result := make(map[string]string, len(tags))
	for _, t := range tags {
		parts := strings.SplitN(t, ":", 2)
		if len(parts) == 2 {
			result[parts[0]] = parts[1]
		}
	}
	return result
}

func parseTimestamp(ts int64) time.Time {
	if ts == 0 {
		return time.Time{}
	}
	return time.Unix(ts/1000000, 0)
}

type durationSlice []time.Duration

func (a durationSlice) Len() int           { return len(a) }
func (a durationSlice) Swap(i, j int)      { a[i], a[j] = a[j], a[i] }
func (a durationSlice) Less(i, j int) bool { return a[i] < a[j] }
