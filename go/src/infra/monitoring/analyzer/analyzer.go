// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package analyzer

import (
	"errors"
	"fmt"
	"net/url"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/Sirupsen/logrus"

	"infra/monitoring/client"
	"infra/monitoring/messages"
)

const (
	// StepCompletedRun is a synthetic step name used to indicate the build run is complete.
	StepCompletedRun  = "completed run"
	treeCloserPri     = 0
	staleMasterSev    = 0
	staleBuilderSev   = 0
	hungBuilderSev    = 1
	idleBuilderSev    = 1
	offlineBuilderSev = 1
)

var (
	log = logrus.New()
)

var (
	errNoBuildSteps = errors.New("No build steps")
)

// StepAnalyzer reasons about a stepFailure and produces a set of reasons for the
// failure.  It also indicates whether or not it recognizes the stepFailure.
type StepAnalyzer interface {
	// Analyze returns a list of reasons for the step failure, and a boolean
	// value indicating whether or not the step failure was recognized by
	// the analyzer.
	Analyze(f stepFailure) (*StepAnalyzerResult, error)
}

// StepAnalyzerResult is the result of running analysis on a stepFailure.
type StepAnalyzerResult struct {
	// Recognized is true if the StepFailureAnalyzer recognized the stepFailure.
	Recognized bool

	// Reasons lists the reasons for the stepFailure determined by the StepFailureAnalyzer.
	Reasons []string
}

// MasterAnalyzer runs the process of checking masters, builders, test results and so on,
// in order to produce alerts.
type MasterAnalyzer struct {
	// MaxRecentBuilds is the maximum number of recent builds to check, per builder.
	MaxRecentBuilds int

	// MinRecentBuilds is the minimum number of recent builds to check, per builder.
	MinRecentBuilds int

	// StepAnalzers are the set of build step failure analyzers to be checked on
	// build step failures.
	StepAnalyzers []StepAnalyzer

	// Client is the Client implementation for fetching json from CBE, builds, etc.
	Client client.Client

	// HungBuilerThresh is the maxumum length of time a builder may be in state "building"
	// before triggering a "hung builder" alert.
	HungBuilderThresh time.Duration

	// OfflineBuilderThresh is the maximum length of time a builder may be in state "offline"
	//  before triggering an "offline builder" alert.
	OfflineBuilderThresh time.Duration

	// IdleBuilderCountThresh is the maximum number of builds a builder may have in queue
	// while in the "idle" state before triggering an "idle builder" alert.
	IdleBuilderCountThresh int64

	// StaleMasterThreshold is the maximum age that master data from CBE can be before
	// triggering a "stale master" alert.
	StaleMasterThreshold time.Duration

	// bCache is a map of build cache key to Build message.
	bCache map[string]*messages.Builds
	// bLock protects bCache
	bLock *sync.Mutex

	// These limit the scope analysis, useful for debugging.
	TreeOnly    string
	MasterOnly  string
	BuilderOnly string
	BuildOnly   int64

	// now is useful for mocking the system clock in testing.
	now func() time.Time
}

// New returns a new Analyzer. If client is nil, it assigns a default implementation.
// maxBuilds is the maximum number of builds to check, per builder.
func New(c client.Client, minBuilds, maxBuilds int) *MasterAnalyzer {
	if c == nil {
		c = client.New()
	}

	return &MasterAnalyzer{
		Client:                 c,
		MaxRecentBuilds:        maxBuilds,
		MinRecentBuilds:        minBuilds,
		HungBuilderThresh:      3 * time.Hour,
		OfflineBuilderThresh:   90 * time.Minute,
		IdleBuilderCountThresh: 50,
		StaleMasterThreshold:   10 * time.Minute,
		StepAnalyzers: []StepAnalyzer{
			&TestFailureAnalyzer{Client: c},
			&CompileFailureAnalyzer{Client: c},
		},

		now: func() time.Time {
			return time.Now()
		},

		bCache: map[string]*messages.Builds{},
		bLock:  &sync.Mutex{},
	}
}

// MasterAlerts returns alerts generated from the master at URL.
func (a *MasterAnalyzer) MasterAlerts(url string, be *messages.BuildExtract) []messages.Alert {
	ret := []messages.Alert{}

	// Copied logic from builder_messages.
	// No created_timestamp should be a warning sign, no?
	if be.CreatedTimestamp == messages.EpochTime(0) {
		return ret
	}

	elapsed := a.now().Sub(be.CreatedTimestamp.Time())
	if elapsed > a.StaleMasterThreshold {
		ret = append(ret, messages.Alert{
			Key:      fmt.Sprintf("stale master: %v", url),
			Title:    "Stale Master Data",
			Body:     fmt.Sprintf("%s elapsed since last update (%s).", elapsed, be.CreatedTimestamp.Time()),
			Severity: staleMasterSev,
			Time:     messages.TimeToEpochTime(a.now()),
			Links:    []messages.Link{{"Master", url}},
			// No type or extension for now.
		})
	}
	if elapsed < 0 {
		// Add this to the alerts returned, rather than just log it?
		log.Errorf("Master %s timestamp is newer than current time (%s): %s old.", url, a.now(), elapsed)
	}

	return ret
}

// BuilderAlerts returns alerts generated from builders connected to the master at url.
func (a *MasterAnalyzer) BuilderAlerts(url string, be *messages.BuildExtract) []messages.Alert {
	mn, err := masterName(url)
	if err != nil {
		log.Fatalf("Couldn't parse %s: %s", url, err)
	}

	// TODO: Collect activeBuilds from be.Slaves.RunningBuilds
	type r struct {
		bn     string
		b      messages.Builders
		alerts []messages.Alert
		err    []error
	}
	c := make(chan r, len(be.Builders))

	// TODO: get a list of all the running builds from be.Slaves? It
	// appears to be used later on in the original py.
	scannedBuilders := []string{}
	for bn, b := range be.Builders {
		if a.BuilderOnly != "" && bn != a.BuilderOnly {
			continue
		}
		scannedBuilders = append(scannedBuilders, bn)
		go func(bn string, b messages.Builders) {
			out := r{bn: bn, b: b}
			defer func() {
				c <- out
			}()

			// This blocks on IO, hence the goroutine.
			a.warmBuildCache(mn, bn, b.CachedBuilds)
			// Each call to builderAlerts may trigger blocking json fetches,
			// but it has a data dependency on the above cache-warming call, so
			// the logic remains serial.
			out.alerts, out.err = a.builderAlerts(mn, bn, &b)
		}(bn, b)
	}

	ret := []messages.Alert{}
	for _, bn := range scannedBuilders {
		r := <-c
		if len(r.err) != 0 {
			// TODO: add a special alert for this too?
			log.Errorf("Error getting alerts for builder %s: %v", bn, r.err)
		} else {
			ret = append(ret, r.alerts...)
		}
	}

	return ret
}

// masterName extracts the name of the master from the master's URL.
func masterName(URL string) (string, error) {
	mURL, err := url.Parse(URL)
	if err != nil {
		return "", err
	}
	pathParts := strings.Split(mURL.Path, "/")
	if len(pathParts) < 2 {
		return "", fmt.Errorf("Couldn't parse master name from %s", URL)
	}
	// -2 to lop the /json off the http://.../{master.name}/json suffix
	return pathParts[len(pathParts)-2], nil
}

func cacheKeyForBuild(master, builder string, number int64) string {
	return filepath.FromSlash(
		fmt.Sprintf("%s/%s/%d.json", url.QueryEscape(master), url.QueryEscape(builder), number))
}

// TODO: actually write the on-disk cache.
func filenameForCacheKey(cc string) string {
	cc = strings.Replace(cc, "/", "_", -1)
	return fmt.Sprintf("/tmp/dispatcher.cache/%s", cc)
}

func alertKey(master, builder, step, reason string) string {
	return fmt.Sprintf("%s.%s.%s.%s", master, builder, step, reason)
}

func (a *MasterAnalyzer) warmBuildCache(master, builder string, recentBuildIDs []int64) {
	v := url.Values{}
	v.Add("master", master)
	v.Add("builder", builder)

	URL := fmt.Sprintf("https://chrome-build-extract.appspot.com/get_builds?%s", v.Encode())
	res := struct {
		Builds []messages.Builds `json:"builds"`
	}{}

	// TODO: add FetchBuilds to the client interface. Take a list of {master, builder} and
	// return (map[{master, builder}][]Builds, map [{master, builder}]error)
	// That way we can do all of these in parallel.

	status, err := a.Client.JSON(URL, &res)
	if err != nil {
		log.Errorf("Error (%d) fetching %s: %s", status, URL, err)
	}

	a.bLock.Lock()
	for _, b := range res.Builds {
		// TODO: consider making res.Builds be []*messages.Builds instead of []messages.Builds
		ba := b
		a.bCache[cacheKeyForBuild(master, builder, b.Number)] = &ba
	}
	a.bLock.Unlock()
}

// This type is used for sorting build IDs.
type buildIDs []int64

func (a buildIDs) Len() int           { return len(a) }
func (a buildIDs) Swap(i, j int)      { a[i], a[j] = a[j], a[i] }
func (a buildIDs) Less(i, j int) bool { return a[i] > a[j] }

// latestBuildStep returns the latest build step name and update time, and an error
// if there were any errors.
func (a *MasterAnalyzer) latestBuildStep(b *messages.Builds) (lastStep string, lastUpdate messages.EpochTime, err error) {
	if len(b.Steps) == 0 {
		return "", messages.TimeToEpochTime(a.now()), errNoBuildSteps
	}
	if len(b.Times) > 1 && b.Times[1] != 0 {
		return StepCompletedRun, b.Times[1], nil
	}

	for _, step := range b.Steps {
		if len(step.Times) > 1 && step.Times[1] > lastUpdate {
			// Step is done.
			lastUpdate = step.Times[1]
			lastStep = step.Name
		} else if len(step.Times) > 0 && step.Times[0] > lastUpdate {
			// Step has started.
			lastUpdate = step.Times[0]
			lastStep = step.Name
		}
	}
	return
}

// TODO: also check the build slaves to see if there are alerts for currently running builds that
// haven't shown up in CBE yet.
func (a *MasterAnalyzer) builderAlerts(mn string, bn string, b *messages.Builders) ([]messages.Alert, []error) {
	alerts := []messages.Alert{}
	errs := []error{}

	recentBuildIDs := b.CachedBuilds
	// Should be a *reverse* sort.
	sort.Sort(buildIDs(recentBuildIDs))
	if len(recentBuildIDs) > a.MaxRecentBuilds {
		recentBuildIDs = recentBuildIDs[:a.MaxRecentBuilds]
	}
	if len(recentBuildIDs) == 0 {
		// TODO: Make an alert for this?
		log.Errorf("No recent builds for %s.%s", mn, bn)
		return alerts, errs
	}
	log.Infof("Checking %d most recent builds for alertable step failures: %s/%s", len(recentBuildIDs), mn, bn)

	// Check for alertable step failures.
	stepFailureAlerts := map[string]messages.Alert{}
	firstFailureInstance := map[string]int64{}

	for i, buildID := range recentBuildIDs {
		failures, err := a.stepFailures(mn, bn, buildID)
		if err != nil {
			errs = append(errs, err)
		}
		if len(failures) == 0 && i > a.MinRecentBuilds {
			// Bail as soon as we find a successful build prior to the most recent couple of builds.
			break
		}

		as, err := a.stepFailureAlerts(failures)
		if err != nil {
			errs = append(errs, err)
		}

		lastKey := ""
		// This probably isn't exactly what we want since multiple builders may have the same alert firing.
		// This just merges build ranges on a per-builder basis.
		for _, alr := range as {
			// Only keep the most recent alert.  Since recentBuildIDs is
			// sorted newest build first, ignore older instances of the alert.
			if _, ok := stepFailureAlerts[alr.Key]; !ok {
				stepFailureAlerts[alr.Key] = alr
			}
			if alr.Key == lastKey || lastKey == "" {
				if bf, ok := alr.Extension.(messages.BuildFailure); ok {
					firstFailureInstance[alr.Key] = bf.Builders[0].FirstFailure
				} else {
					log.Errorf("Couldn't cast alert extension to BuildFailure: %s", alr.Key)
				}
			}
			lastKey = alr.Key
		}
	}

	for _, alr := range stepFailureAlerts {
		alr.Extension.(messages.BuildFailure).Builders[0].FirstFailure = firstFailureInstance[alr.Key]
		alerts = append(alerts, alr)
	}

	// Check for stale/idle/offline builders.  Latest build is the first in the list.
	lastBuildID := recentBuildIDs[0]
	log.Infof("Checking last build ID: %d", lastBuildID)

	// TODO: get this from cache.
	a.bLock.Lock()
	lastBuild := a.bCache[cacheKeyForBuild(mn, bn, lastBuildID)]
	a.bLock.Unlock()
	if lastBuild == nil {
		var err error
		lastBuild, err = a.Client.Build(mn, bn, lastBuildID)
		if err != nil {
			errs = append(errs, fmt.Errorf("Couldn't get latest build %d for %s.%s: %s", lastBuildID, mn, bn, err))
			return alerts, errs
		}
	}

	// Examining only the latest build is probably suboptimal since if it's still in progress it might
	// not have hit a step that is going to fail and has failed repeatedly for the last few builds.
	// AKA "Reliable failures".  TODO: Identify "Reliable failures"
	lastStep, lastUpdated, err := a.latestBuildStep(lastBuild)
	if err != nil {
		errs = append(errs, fmt.Errorf("Couldn't get latest build step for %s.%s: %v", mn, bn, err))
		return alerts, errs

	}
	elapsed := a.now().Sub(lastUpdated.Time())
	links := []messages.Link{
		{"Builder", fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s", mn, bn)},
		{"Last build", fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s/builds/%d", mn, bn, lastBuildID)},
		{"Last build step", fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s/builds/%d/steps/%s", mn, bn, lastBuildID, lastStep)},
	}

	switch b.State {
	case messages.StateBuilding:
		if elapsed > a.HungBuilderThresh && lastStep != StepCompletedRun {
			alerts = append(alerts, messages.Alert{
				Key:      fmt.Sprintf("%s.%s.hung", mn, bn),
				Title:    fmt.Sprintf("%s.%s is hung in step %s.", mn, bn, lastStep),
				Body:     fmt.Sprintf("%s.%s has been building for %v (last step update %s), past the alerting threshold of %v", mn, bn, elapsed, lastUpdated.Time(), a.HungBuilderThresh),
				Severity: hungBuilderSev,
				Time:     messages.TimeToEpochTime(a.now()),
				Links:    links,
			})
			// Note, just because it's building doesn't mean it's in a good state. If the last N builds
			// all failed (for some large N) then this might still be alertable.
		}
	case messages.StateOffline:
		if elapsed > a.OfflineBuilderThresh {
			alerts = append(alerts, messages.Alert{
				Key:      fmt.Sprintf("%s.%s.offline", mn, bn),
				Title:    fmt.Sprintf("%s.%s is offline.", mn, bn),
				Body:     fmt.Sprintf("%s.%s has been offline for %v (last step update %s %v), past the alerting threshold of %v", mn, bn, elapsed, lastUpdated.Time(), float64(lastUpdated), a.OfflineBuilderThresh),
				Severity: offlineBuilderSev,
				Time:     messages.TimeToEpochTime(a.now()),
				Links:    links,
			})
		}
	case messages.StateIdle:
		if b.PendingBuilds > a.IdleBuilderCountThresh {
			alerts = append(alerts, messages.Alert{
				Key:      fmt.Sprintf("%s.%s.idle", mn, bn),
				Title:    fmt.Sprintf("%s.%s is idle with too many pending builds.", mn, bn),
				Body:     fmt.Sprintf("%s.%s is idle with %d pending builds, past the alerting threshold of %d", mn, bn, b.PendingBuilds, a.IdleBuilderCountThresh),
				Severity: idleBuilderSev,
				Time:     messages.TimeToEpochTime(a.now()),
				Links:    links,
			})
		}
	default:
		log.Errorf("Unknown %s.%s builder state: %s", mn, bn, b.State)
	}

	return alerts, errs
}

// stepFailures returns the steps that have failed recently on builder bn.
func (a *MasterAnalyzer) stepFailures(mn string, bn string, bID int64) ([]stepFailure, error) {
	cc := cacheKeyForBuild(mn, bn, bID)

	var err error // To avoid re-scoping b in the nested conditional below with a :=.
	a.bLock.Lock()
	b, ok := a.bCache[cc]
	a.bLock.Unlock()
	if !ok {
		log.Infof("Cache miss for %s", cc)
		b, err = a.Client.Build(mn, bn, bID)
		if err != nil || b == nil {
			log.Errorf("Error fetching build: %v", err)
			return nil, err
		}
	}

	ret := []stepFailure{}

	for _, s := range b.Steps {
		if !s.IsFinished || len(s.Results) == 0 {
			continue
		}
		// Because Results in the json data is a homogeneous array, the unmarshaler
		// doesn't have any type information to assert about it. We have to do
		// some ugly runtime type assertion ourselves.
		if r, ok := s.Results[0].(float64); ok {
			if r == 0 || r == 1 {
				// This 0/1 check seems to be a convention or heuristic. A 0 or 1
				// result is apparently "ok", accoring to the original python code.
				continue
			}
		} else {
			log.Errorf("Couldn't unmarshal first step result into an int: %v", s.Results[0])
		}

		// We have a failure of some kind, so queue it up to check later.
		ret = append(ret, stepFailure{
			masterName:  mn,
			builderName: bn,
			build:       *b,
			step:        s,
		})
	}

	return ret, nil
}

// stepFailureAlerts returns alerts generated from step failures. It applies filtering
// logic specified in the gatekeeper config to ignore some failures.
func (a *MasterAnalyzer) stepFailureAlerts(failures []stepFailure) ([]messages.Alert, error) {
	ret := []messages.Alert{}
	type res struct {
		f   stepFailure
		a   *messages.Alert
		err error
	}

	// Might not need full capacity buffer, since some failures are ignored below.
	rs := make(chan res, len(failures))

	scannedFailures := []stepFailure{}
	for _, f := range failures {
		// goroutine/channel because the reasonsForFailure call potentially
		// blocks on IO.
		if f.step.Name == "steps" {
			continue
			// The actual breaking step will appear later.
		}
		scannedFailures = append(scannedFailures, f)
		go func(f stepFailure) {
			alr := messages.Alert{
				Title: fmt.Sprintf("Builder step failure: %s.%s", f.masterName, f.builderName),
				Time:  messages.EpochTime(a.now().Unix()),
				Type:  "buildfailure",
			}

			// If the builder has been failing on the same step for multiple builds in a row,
			// we should have only one alert but indicate the range of builds affected.
			// These are set in FirstFailure and LastFailure.
			bf := messages.BuildFailure{
				// FIXME: group builders?
				Builders: []messages.AlertedBuilder{
					{
						Name:          f.builderName,
						URL:           fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s", f.masterName, f.builderName),
						FirstFailure:  f.build.Number,
						LatestFailure: f.build.Number,
					},
				},
				// TODO: RegressionRanges:
				// look into Builds.SourceStamp.Changes.
			}

			reasons := a.reasonsForFailure(f)
			for _, r := range reasons {
				bf.Reasons = append(bf.Reasons, messages.Reason{
					TestName: r,
					Step:     f.step.Name,
					URL:      f.URL(),
				})
			}

			alr.Extension = bf
			if len(bf.Reasons) == 0 {
				alr.Key = alertKey(f.masterName, f.builderName, f.step.Name, "")
				log.Warnf("No reasons for step failure: %s", alr.Key)
			} else {
				// Should the key include all of the reasons?
				alr.Key = alertKey(f.masterName, f.builderName, f.step.Name, reasons[0])
			}
			rs <- res{
				f:   f,
				a:   &alr,
				err: nil,
			}
		}(f)
	}

	for _ = range scannedFailures {
		r := <-rs
		if r.a != nil {
			ret = append(ret, *r.a)
		}
	}

	return ret, nil
}

// reasonsForFailure examines the step failure and applies some heuristics to
// to find the cause. It may make blocking IO calls in the process.
func (a *MasterAnalyzer) reasonsForFailure(f stepFailure) []string {
	ret := []string{}
	recognized := false
	log.Infof("Checking for reasons for failure step: %v", f.step.Name)
	for _, sfa := range a.StepAnalyzers {
		res, err := sfa.Analyze(f)
		if err != nil {
			// TODO: return something that contains errors *and* reasons.
			log.Errorf("Error get reasons from StepAnalyzer: %v", err)
			continue
		}
		if res.Recognized {
			recognized = true
			ret = append(ret, res.Reasons...)
		}
	}

	if !recognized {
		// TODO: log and report frequently encountered unrecognized builder step
		// failure names.
		log.Errorf("Unrecognized step step failure type, unable to find reasons: %s", f.step.Name)
	}

	return ret
}

// unexpected returns the set of expected xor actual.
func unexpected(expected, actual []string) []string {
	e, a := make(map[string]bool), make(map[string]bool)
	for _, s := range expected {
		e[s] = true
	}
	for _, s := range actual {
		a[s] = true
	}

	ret := []string{}
	for k := range e {
		if !a[k] {
			ret = append(ret, k)
		}
	}

	for k := range a {
		if !e[k] {
			ret = append(ret, k)
		}
	}

	return ret
}

type stepFailure struct {
	masterName  string
	builderName string
	build       messages.Builds
	step        messages.Steps
}

// Sigh.  build.chromium.org doesn't accept + as an escaped space in URL paths.
func oldEscape(s string) string {
	return strings.Replace(url.QueryEscape(s), "+", "%20", -1)
}

// URL returns a url to builder step failure page.
func (f stepFailure) URL() string {
	return fmt.Sprintf("https://build.chromium.org/p/%s/builders/%s/builds/%d/steps/%s",
		f.masterName, oldEscape(f.builderName), f.build.Number, oldEscape(f.step.Name))
}
