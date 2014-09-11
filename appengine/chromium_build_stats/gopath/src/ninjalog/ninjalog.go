// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ninjalog

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strconv"
	"strings"
	"time"
)

// Step is one step in ninja_log file.
// time is measured from ninja start time.
type Step struct {
	Start time.Duration
	End   time.Duration
	// modification time, but not convertable to absolute real time.
	// on POSIX, time_t is used, but on Windows different type is used.
	// htts://github.com/martine/ninja/blob/master/src/timestamp.h
	Restat  int
	Out     string
	CmdHash string
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

func (s ByEnd) Less(i, j int) bool { return s.Steps[i].End < s.Steps[j].End }

// ByDuration is used to sort by duration.
type ByDuration struct{ Steps }

func (s ByDuration) Less(i, j int) bool { return s.Steps[i].Duration() < s.Steps[j].Duration() }

// Metadata is data added by compile.py.
type Metadata struct {
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

	// Env is environment variables.
	Env map[string]string `json:"env"`

	// CompilerProxyInfo is a path name of associated compiler_proxy.INFO log.
	CompilerProxyInfo string `json:"compiler_proxy_info"`
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

// Parse parses .ninja_log file, with chromium's compile.py metadata.
func Parse(fname string, r io.Reader) (*NinjaLog, error) {
	b := bufio.NewReader(r)
	scanner := bufio.NewScanner(b)
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
	if err := parseMetadata(scanner.Bytes(), &nlog.Metadata); err != nil {
		return nil, fmt.Errorf("error at %d: %v", lineno, err)
	}
	return nlog, nil
}

func lineToStep(line string) (Step, error) {
	var step Step
	fields := strings.Split(line, "\t")
	if len(fields) < 5 {
		return step, fmt.Errorf("few fields:%d", len(fields))
	}
	s, err := strconv.Atoi(fields[0])
	if err != nil {
		return step, fmt.Errorf("bad start %s:%v", fields[0], err)
	}
	e, err := strconv.Atoi(fields[1])
	if err != nil {
		return step, fmt.Errorf("bad end %s:%v", fields[1], err)
	}
	rs, err := strconv.Atoi(fields[2])
	if err != nil {
		return step, fmt.Errorf("bad restat %s:%v", fields[2], err)
	}
	step.Start = time.Duration(s) * time.Millisecond
	step.End = time.Duration(e) * time.Millisecond
	step.Restat = rs
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
	return json.Unmarshal(buf, metadata)
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

// Dedup dedupes steps. step may have the same start and end.
// Dedup only returns the first step for these steps.
// steps will be sorted by start time.
func Dedup(steps []Step) []Step {
	sort.Sort(Steps(steps))
	var dedup []Step
	var last Step
	for _, s := range steps {
		if s.Start == last.Start && s.End == last.End {
			continue
		}
		dedup = append(dedup, s)
		last = s
	}
	return dedup
}

// Flow returns concurrent steps by time.
// steps in every []Step will not have time overlap.
// steps will be sorted by start time.
func Flow(steps []Step) [][]Step {
	sort.Sort(Steps(steps))
	var threads [][]Step

	for _, s := range steps {
		tid := -1
		for i, th := range threads {
			if len(th) == 0 {
				panic(fmt.Errorf("thread %d has no entry", i))
			}
			if th[len(th)-1].End <= s.Start {
				tid = i
				break
			}
		}
		if tid == -1 {
			threads = append(threads, nil)
			tid = len(threads) - 1
		}
		threads[tid] = append(threads[tid], s)
	}
	return threads
}
