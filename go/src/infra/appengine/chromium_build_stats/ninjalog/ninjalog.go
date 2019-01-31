// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ninjalog

import (
	"bufio"
	crand "crypto/rand"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"math/big"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/golang/protobuf/ptypes"

	npb "infra/appengine/chromium_build_stats/ninjaproto"
)

// Step is one step in ninja_log file.
// time is measured from ninja start time.
type Step struct {
	Start time.Duration
	End   time.Duration
	// modification time, but not convertible to absolute real time.
	// on POSIX, time_t is used, but on Windows different type is used.
	// htts://github.com/martine/ninja/blob/master/src/timestamp.h
	Restat  int
	Out     string
	CmdHash string

	// other outs for the same CmdHash if dedup'ed.
	Outs []string
}

// Duration reports step's duration.
func (s Step) Duration() time.Duration {
	return s.End - s.Start
}

// Steps is a list of Step.
// It could be used to sort by start time.
type Steps []Step

func (s Steps) Len() int      { return len(s) }
func (s Steps) Swap(i, j int) { s[i], s[j] = s[j], s[i] }
func (s Steps) Less(i, j int) bool {
	if s[i].Start != s[j].Start {
		return s[i].Start < s[j].Start
	}
	if s[i].End != s[j].End {
		return s[i].End < s[j].End
	}
	return s[i].Out < s[j].Out
}

// Reverse reverses steps.
// It would be more efficient if steps is already sorted than using sort.Reverse.
func (s Steps) Reverse() {
	for i, j := 0, len(s)-1; i < j; i, j = i+1, j-1 {
		s[i], s[j] = s[j], s[i]
	}
}

// ByEnd is used to sort by end time.
type ByEnd struct{ Steps }

// Less is used to sort a list by Steps End time.
func (s ByEnd) Less(i, j int) bool { return s.Steps[i].End < s.Steps[j].End }

// ByDuration is used to sort by duration.
type ByDuration struct{ Steps }

// Less is used to sort a list by Steps Duration.
func (s ByDuration) Less(i, j int) bool { return s.Steps[i].Duration() < s.Steps[j].Duration() }

// ByWeightedTime is used to sort by weighted time.
type ByWeightedTime struct {
	Weighted map[string]time.Duration
	Steps
}

// Less is used to sort a list by Weighted duration.
func (s ByWeightedTime) Less(i, j int) bool {
	return s.Weighted[s.Steps[i].Out] < s.Weighted[s.Steps[j].Out]
}

// Metadata is data added by compile.py or json sent from ninjalog uploader.
type Metadata struct {
	// BuildID is identifier of build used in buildbucket api v2 (go/buildbucket-api-v2)
	// Or some random number representing an invocation of build.
	BuildID int64 `json:"build_id"`

	// Platform is platform of buildbot.
	Platform string `json:"platform"`

	// Argv is argv of compile.py
	Argv []string `json:"argv"`

	// Cwd is current working directory of compile.py
	Cwd string `json:"cwd"`

	// Compiler is compiler used.
	Compiler string `json:"compiler"`

	// Cmdline is command line of ninja.
	Cmdline []string `json:"cmdline"`

	// Exit is exit status of ninja.
	Exit int `json:"exit"`

	// Hostname is hostname of builder.
	Hostname string `json:"hostname"`

	// StepName is stepname to distinguish multiple compile steps in a build.
	StepName string `json:"step_name"`

	// CPUCore is the number of cpu cores.
	CPUCore int32 `json:"cpu_core"`

	// BuildConfigs is content of args.gn.
	BuildConfigs map[string]string `json:"build_configs"`

	// Env is environment variables.
	Env map[string]string `json:"env"`

	// CompilerProxyInfo is a path name of associated compiler_proxy.INFO log.
	CompilerProxyInfo string `json:"compiler_proxy_info"`

	// Jobs is number of parallel process in a build.
	Jobs int `json:"jobs"`

	// Build target.
	Targets []string `json:"targets"`

	// Raw is raw string for metadata.
	Raw string
	// Error is error message of parsing metadata.
	Error string
}

// NinjaLog is parsed data of ninja_log file.
type NinjaLog struct {
	// Filename is a filename of ninja_log.
	Filename string

	// Start is start line of the last build in ninja_log file.
	Start int

	// Steps contains steps in the last build in ninja_log file.
	Steps []Step

	// Metadata is additional data found in ninja_log file.
	Metadata Metadata
}

const (
	initialBufSize = 4096
	maxBufSize     = 128 * 1024
)

// Parse parses .ninja_log file, with chromium's compile.py metadata.
func Parse(fname string, r io.Reader) (*NinjaLog, error) {
	b := bufio.NewReader(r)
	scanner := bufio.NewScanner(b)
	buf := make([]byte, initialBufSize)
	scanner.Buffer(buf, maxBufSize)
	nlog := &NinjaLog{Filename: fname}
	lineno := 0
	if !scanner.Scan() {
		if err := scanner.Err(); err != nil {
			return nil, err
		}
		return nil, fmt.Errorf("empty file?")
	}
	lineno++
	line := scanner.Text()
	if line != "# ninja log v5" {
		return nil, fmt.Errorf("unexpected format: %s", line)
	}
	nlog.Start = lineno
	var lastStep Step
	for scanner.Scan() {
		line := scanner.Text()
		if line == "# end of ninja log" {
			break
		}
		if line == "" {
			continue
		}
		step, err := lineToStep(line)
		if err != nil {
			return nil, fmt.Errorf("error at %d: %v", lineno, err)
		}
		if step.End < lastStep.End {
			nlog.Start = lineno
			nlog.Steps = nil
		}
		nlog.Steps = append(nlog.Steps, step)
		lastStep = step
		lineno++
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("error at %d: %v", lineno, err)
	}
	if !scanner.Scan() {
		if err := scanner.Err(); err != nil {
			return nil, fmt.Errorf("error at %d: %v", lineno, err)
		}
		// missing metadata?
		return nlog, nil
	}

	lineno++
	nlog.Metadata.Raw = scanner.Text()
	if err := parseMetadata([]byte(nlog.Metadata.Raw), &nlog.Metadata); err != nil {
		nlog.Metadata.Error = fmt.Sprintf("error at %d: %v", lineno, err)
	}
	return nlog, nil
}

func lineToStep(line string) (Step, error) {
	var step Step

	// Due to slowness of strings.Split in App Engine Go,
	// we use more faster implementation.
	fields := make([]string, 0, 5)
	for i := 0; i < 5; i++ {
		m := strings.IndexByte(line, '\t')
		if m < 0 {
			m = len(line)
		}
		fields = append(fields, line[:m])
		if m < len(line) {
			line = line[m+1:]
		}
	}

	if len(fields) < 5 {
		return step, fmt.Errorf("few fields:%d", len(fields))
	}
	s, err := strconv.ParseUint(fields[0], 10, 0)
	if err != nil {
		return step, fmt.Errorf("bad start %s:%v", fields[0], err)
	}
	e, err := strconv.ParseUint(fields[1], 10, 0)
	if err != nil {
		return step, fmt.Errorf("bad end %s:%v", fields[1], err)
	}
	rs, err := strconv.ParseUint(fields[2], 10, 0)
	if err != nil {
		return step, fmt.Errorf("bad restat %s:%v", fields[2], err)
	}
	step.Start = time.Duration(s) * time.Millisecond
	step.End = time.Duration(e) * time.Millisecond
	step.Restat = int(rs)
	step.Out = fields[3]
	step.CmdHash = fields[4]
	return step, nil
}

func stepToLine(s Step) string {
	return fmt.Sprintf("%d\t%d\t%d\t%s\t%s",
		s.Start.Nanoseconds()/int64(time.Millisecond),
		s.End.Nanoseconds()/int64(time.Millisecond),
		s.Restat,
		s.Out,
		s.CmdHash)
}

func parseMetadata(buf []byte, metadata *Metadata) error {
	if err := json.Unmarshal(buf, metadata); err != nil {
		return err
	}

	if metadata.Jobs == 0 {
		jobs, err := getJobs(metadata.Cmdline)
		if err != nil {
			return fmt.Errorf("failed to get jobs: %v", err)
		}
		metadata.Jobs = jobs
	}
	return nil
}

// Dump dumps steps as ninja log v5 format in w.
func Dump(w io.Writer, steps []Step) error {
	_, err := fmt.Fprintf(w, "# ninja log v5\n")
	if err != nil {
		return err
	}
	for _, s := range steps {
		_, err = fmt.Fprintln(w, stepToLine(s))
		if err != nil {
			return err
		}
	}
	return nil
}

// Dedup dedupes steps. step may have the same cmd hash.
// Dedup only returns the first step for these steps.
// steps will be sorted by start time.
func Dedup(steps []Step) []Step {
	m := make(map[string]*Step)
	sort.Sort(Steps(steps))
	var dedup []Step
	for _, s := range steps {
		if os := m[s.CmdHash]; os != nil {
			os.Outs = append(os.Outs, s.Out)
			continue
		}
		dedup = append(dedup, s)
		m[s.CmdHash] = &dedup[len(dedup)-1]
	}
	return dedup
}

// TotalTime returns startup time and end time of ninja, and accumulated time
// of all tasks.
func TotalTime(steps []Step) (startupTime, endTime, cpuTime time.Duration) {
	if len(steps) == 0 {
		return 0, 0, 0
	}
	steps = Dedup(steps)
	startup := steps[0].Start
	var end time.Duration
	for _, s := range steps {
		if s.Start < startup {
			startup = s.Start
		}
		if s.End > end {
			end = s.End
		}
		cpuTime += s.Duration()
	}
	return startup, end, cpuTime
}

// Flow returns concurrent steps by time.
// steps in every []Step will not have time overlap.
// steps will be sorted by start or end time depends on |sortByEnd|.
func Flow(steps []Step, sortByEnd bool) [][]Step {
	if sortByEnd {
		sort.Slice(steps, func(i, j int) bool {
			return steps[i].End >= steps[j].End
		})
	} else {
		sort.Sort(Steps(steps))
	}

	var threads [][]Step

	for _, s := range steps {
		tid := -1
		for i, th := range threads {
			if len(th) == 0 {
				panic(fmt.Errorf("thread %d has no entry", i))
			}

			if sortByEnd {
				if th[len(th)-1].Start >= s.End {
					tid = i
					break
				}
			} else {
				if th[len(th)-1].End <= s.Start {
					tid = i
					break
				}
			}
		}
		if tid == -1 {
			threads = append(threads, nil)
			tid = len(threads) - 1
		}
		threads[tid] = append(threads[tid], s)
	}

	if sortByEnd {
		for _, thread := range threads {
			Steps(thread).Reverse()
		}
	}

	return threads
}

// action represents an event's action. "start" or "end".
type action string

const (
	unknownAction action = ""
	startAction   action = "start"
	stopAction    action = "stop"
)

// event is an event of steps.
type event struct {
	time   time.Duration
	action action
	target string
}

// toEvent converts steps into events.
// events are sorted by its time.
func toEvent(steps []Step) []event {
	var events []event
	for _, s := range steps {
		events = append(events,
			event{
				time:   s.Start,
				action: startAction,
				target: s.Out,
			},
			event{
				time:   s.End,
				action: stopAction,
				target: s.Out,
			},
		)
	}
	sort.Slice(events, func(i, j int) bool {
		if events[i].time == events[j].time {
			// If a task starts and stops on the same time stamp
			// then the start will come first.
			return events[i].action < events[j].action
		}
		return events[i].time < events[j].time
	})
	return events
}

// WeightedTime calculates weighted time, which is elapsed time with
// each segment divided by the number of tasks that were running in paralle.
// This makes it a much better approximation of how "important" a slow step was.
// For example, A link that is entirely or mostly serialized will have a
// weighted time that is the same or similar to its elapsed time.
// A compile that runs in parallel with 999 other compiles will have a weighted
// time that is tiny.
func WeightedTime(steps []Step) map[string]time.Duration {
	if len(steps) == 0 {
		return nil
	}
	steps = Dedup(steps)
	events := toEvent(steps)
	weightedDuration := make(map[string]time.Duration)

	// Track the tasks which are currently running.
	runningTasks := make(map[string]time.Duration)

	// Record the time we have processed up to so we know how to calculate
	// time deltas.
	lastTime := events[0].time

	// Track the accumulated weighted time so that it can efficiently be
	// added to individual tasks.
	var lastWeightedTime time.Duration

	for _, event := range events {
		numRunning := len(runningTasks)
		if numRunning > 0 {
			// Update the total weighted time up to this moment.
			lastWeightedTime += (event.time - lastTime) / time.Duration(numRunning)
		}
		switch event.action {
		case startAction:
			// Record the total weighted task time when this task starts.
			runningTasks[event.target] = lastWeightedTime
		case stopAction:
			// Record the change in the total weighted task time while this task ran.
			weightedDuration[event.target] = lastWeightedTime - runningTasks[event.target]
			delete(runningTasks, event.target)
		}
		lastTime = event.time
	}
	return weightedDuration
}

// Stat represents statistics for build step.
type Stat struct {
	Type     string
	Count    int
	Time     time.Duration
	Weighted time.Duration
}

// StatsByType summarizes build step statistics with weighted and typeOf.
// Stats is sorted by Weighted, longer first.
func StatsByType(steps []Step, weighted map[string]time.Duration, typeOf func(Step) string) []Stat {
	if len(steps) == 0 {
		return nil
	}
	steps = Dedup(steps)
	m := make(map[string]int) // type to index of stats.
	var stats []Stat
	for _, step := range steps {
		t := typeOf(step)
		if i, ok := m[t]; ok {
			stats[i].Count++
			stats[i].Time += step.Duration()
			stats[i].Weighted += weighted[step.Out]
			continue
		}
		stats = append(stats, Stat{
			Type:     t,
			Count:    1,
			Time:     step.Duration(),
			Weighted: weighted[step.Out],
		})
		m[t] = len(stats) - 1
	}
	sort.Slice(stats, func(i, j int) bool {
		return stats[i].Weighted > stats[j].Weighted
	})
	return stats
}

// createdTimestamp is ptypes function name
var createdTimestamp = ptypes.TimestampNow

// ToProto converts ninjalog to structs of protocol buffer.
func ToProto(info *NinjaLog) []*npb.NinjaTask {
	var ninjaTasks []*npb.NinjaTask
	weightedTime := WeightedTime(info.Steps)
	steps := Dedup(info.Steps)
	timestamp := createdTimestamp()

	buildID := info.Metadata.BuildID
	if buildID == 0 {
		// Set random number if buildID is not set.
		// This is mainly for ninjalog from chromium developer.
		seed, _ := crand.Int(crand.Reader, big.NewInt(math.MaxInt64))
		buildID = seed.Int64()
	}

	os := npb.NinjaTask_UNKNOWN

	// Parse platform as it is returned from python's platform.system().
	switch platform := info.Metadata.Platform; {
	case platform == "Windows" || strings.Contains(platform, "CYGWIN"):
		os = npb.NinjaTask_WIN
	case platform == "Linux":
		os = npb.NinjaTask_LINUX
	case platform == "Darwin":
		os = npb.NinjaTask_MAC
	}

	var buildConfigs []*npb.NinjaTask_KeyValue
	for k, v := range info.Metadata.BuildConfigs {
		buildConfigs = append(buildConfigs, &npb.NinjaTask_KeyValue{
			Key:   k,
			Value: v,
		})
	}

	// Configuring order is matter for same key.
	sort.SliceStable(buildConfigs, func(i, j int) bool {
		return buildConfigs[i].Key < buildConfigs[j].Key
	})

	var targets []string

	if len(info.Metadata.Targets) != 0 {
		targets = info.Metadata.Targets
	} else {
		// Parse ninja's commandline to extract build targets, if targets is not given.

		// We assume info.Metadata.Cmdline[0] is ninja or ninja.exe
		for i := 1; i < len(info.Metadata.Cmdline); i++ {
			arg := info.Metadata.Cmdline[i]
			switch arg {
			case "-C", "-f", "-j", "-k", "-l", "-d", "-t", "-w":
				i++
				continue
			case "--version", "-v", "--verbose", "-n", "-h", "--help":
				continue
			}

			if strings.HasPrefix(arg, "-C") ||
				strings.HasPrefix(arg, "-f") ||
				strings.HasPrefix(arg, "-j") ||
				strings.HasPrefix(arg, "-k") ||
				strings.HasPrefix(arg, "-l") ||
				strings.HasPrefix(arg, "-d") ||
				strings.HasPrefix(arg, "-t") ||
				strings.HasPrefix(arg, "-w") {
				continue
			}

			targets = append(targets, arg)
		}
	}

	for _, s := range steps {
		ninjalog := &npb.NinjaTask{
			BuildId:      buildID,
			Targets:      targets,
			StepName:     info.Metadata.StepName,
			Jobs:         int64(info.Metadata.Jobs),
			Os:           os,
			CpuCore:      info.Metadata.CPUCore,
			BuildConfigs: buildConfigs,
			LogEntry: &npb.NinjaTask_LogEntry{
				Outputs:          append(s.Outs, s.Out),
				CommandHash:      s.CmdHash,
				StartDurationSec: s.Start.Seconds(),
				EndDurationSec:   s.End.Seconds(),
			},
			WeightedDurationSec: weightedTime[s.Out].Seconds(),
			CreatedAt:           timestamp,
		}
		sort.Strings(ninjalog.LogEntry.Outputs)
		ninjaTasks = append(ninjaTasks, ninjalog)
	}
	return ninjaTasks
}

func getJobs(cmdLine []string) (int, error) {
	strJobs := ""
	for i, c := range cmdLine {
		if !strings.HasPrefix(c, "-j") {
			continue
		}
		if c == "-j" { // the case ... []string{ ..., "-j", "50"}
			if i+1 < len(cmdLine) {
				strJobs = cmdLine[i+1]
			} else { // the error case ... []string{ ..., "-j"}
				return 0, fmt.Errorf("trailing -j: %v", cmdLine)
			}
		} else { // the case ... []string{ ..., "-j50"}
			strJobs = strings.TrimLeft(c, "-j")
		}
		break
	}
	// -j isn't found
	if strJobs == "" {
		return 0, nil
	}

	jobs, err := strconv.Atoi(strJobs)
	if err != nil { // the error case ... []string{ ..., "-j", "abc"}
		return 0, fmt.Errorf("failed to parse %v: %v", strJobs, err)
	}
	return jobs, nil
}
