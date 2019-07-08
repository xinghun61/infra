// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package compilerproxylog

import (
	"fmt"
	"io"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode"
)

var (
	// <op> http=<code> <info>
	httpErrorRE = regexp.MustCompile(`^([^ ]*) *http=([0-9]{3}) *(.*)$`)
	dateLineRE  = regexp.MustCompile(`Date: [^\\]*\\r\\n`)
)

// CompileMode is mode of compilation.
type CompileMode int

const (
	// Compiling is normal compiling (-c).
	Compiling CompileMode = iota

	// Precompiling is precompiling header (-c for header).
	Precompiling

	// Linking is other compilation mode.
	Linking

	// NumCompileMode is number of CompilerMode.
	NumCompileMode int = iota
)

func (cm CompileMode) String() string {
	switch cm {
	case Compiling:
		return "compiling"
	case Precompiling:
		return "precompiling"
	case Linking:
		return "linking"
	}
	return fmt.Sprintf("unknown-mode[%d]", int(cm))
}

// HTTPError is a http error detected by compiler proxy.
type HTTPError struct {
	Op   string
	Code int
	Resp string
}

// TaskLog is a Task's log.
type TaskLog struct {
	// ID is task id.
	ID string

	// BuildID is build id for the task.
	BuildID string

	// Desc is task description. (e.g. input_filename).
	Desc string

	// CompileMode is compile mode of the task.
	CompileMode CompileMode

	// AcceptTime is a time when this task is accepted by compiler_proxy.
	AcceptTime time.Time

	// StartTime is a time when compiler_proxy started to handle this task.
	StartTime time.Time

	// EndTime is a time when compiler_proxy finished to handle this task.
	EndTime time.Time

	// Logs are logs associated with the task.
	Logs []Logline

	// HTTPErrors are http errors happened in the task.
	HTTPErrors []HTTPError

	// Response is a response type of the task. (e.g. "goma success").
	Response string
}

// Duration is total task duration (i.e. gomacc time).
func (t *TaskLog) Duration() time.Duration {
	return t.EndTime.Sub(t.AcceptTime)
}

// RunDuration is task duration of CompileTask.
func (t *TaskLog) RunDuration() time.Duration {
	return t.EndTime.Sub(t.StartTime)
}

// Pending is pending duration until the task is handled as CompileTask.
func (t *TaskLog) Pending() time.Duration {
	return t.StartTime.Sub(t.AcceptTime)
}

// TaskLogs is a list of TaskLogs.
// It would be used to sort a list of TaskLogs by id.
type TaskLogs []*TaskLog

func (tl TaskLogs) Len() int           { return len(tl) }
func (tl TaskLogs) Swap(i, j int)      { tl[i], tl[j] = tl[j], tl[i] }
func (tl TaskLogs) Less(i, j int) bool { return tl[i].ID < tl[j].ID }

// ByDuration sorts a list of TaskLogs by duration.
type ByDuration struct{ TaskLogs }

// Less is used to sort a list of TaskLogs by Duration.
func (tl ByDuration) Less(i, j int) bool {
	if id, jd := tl.TaskLogs[i].Duration(), tl.TaskLogs[j].Duration(); id != jd {
		return id < jd
	}
	return tl.TaskLogs.Less(i, j)
}

// ByRunDuration sorts a list of TaskLogs by run duration.
type ByRunDuration struct{ TaskLogs }

// Less is used to sort a list of TaskLogs by RunDuration.
func (tl ByRunDuration) Less(i, j int) bool {
	if ir, jr := tl.TaskLogs[i].RunDuration(), tl.TaskLogs[j].RunDuration(); ir != jr {
		return ir < jr
	}
	return tl.TaskLogs.Less(i, j)
}

// ByPending sorts a list of TaskLogs by pending.
type ByPending struct{ TaskLogs }

// Less is used to sort a list of TaskLogs by Pending.
func (tl ByPending) Less(i, j int) bool {
	if ip, jp := tl.TaskLogs[i].Pending(), tl.TaskLogs[j].Pending(); ip != jp {
		return ip < jp
	}
	return tl.TaskLogs.Less(i, j)
}

// ClassifyByCompileMode classifies TaskLog by CompileMode.
func ClassifyByCompileMode(tl []*TaskLog) [NumCompileMode][]*TaskLog {
	var ctl [NumCompileMode][]*TaskLog
	for _, t := range tl {
		ctl[t.CompileMode] = append(ctl[t.CompileMode], t)
	}
	return ctl
}

// ClassifyByResponse classifies TaskLog by response.
func ClassifyByResponse(tl []*TaskLog) map[string][]*TaskLog {
	ctl := make(map[string][]*TaskLog)
	for _, t := range tl {
		ctl[t.Response] = append(ctl[t.Response], t)
	}
	return ctl
}

type taskEvent struct {
	t time.Time
	s bool
}

type taskEvents []taskEvent

func (te taskEvents) Len() int           { return len(te) }
func (te taskEvents) Swap(i, j int)      { te[i], te[j] = te[j], te[i] }
func (te taskEvents) Less(i, j int) bool { return te[i].t.Before(te[j].t) }

// DurationDistribution returns duration distribution by # of tasks.
func DurationDistribution(st time.Time, tl []*TaskLog) []time.Duration {
	var events []taskEvent
	for _, task := range tl {
		events = append(events, taskEvent{
			t: task.StartTime,
			s: true,
		})
		events = append(events, taskEvent{
			t: task.EndTime,
			s: false,
		})
	}
	sort.Sort(taskEvents(events))
	dd := []time.Duration{0}
	jobs := 0
	tm := st
	for _, e := range events {
		dd[jobs] += e.t.Sub(tm)
		tm = e.t
		if e.s {
			jobs++
			if jobs > len(dd)-1 {
				dd = append(dd, time.Duration(0))
			}
			continue
		}
		jobs--
		if jobs < 0 {
			jobs = 0
		}
	}
	for len(dd) > 0 {
		if dd[len(dd)-1] == 0 {
			dd = dd[:len(dd)-1]
			continue
		}
		break
	}
	return dd
}

// CompilerProxyLog represents parsed compiler_proxy INFO log.
type CompilerProxyLog struct {
	// Filename is a filename of the compiler_proxy INFO log.
	Filename string

	// Created is a timestamp when the compiler_proxy INFO log was created.
	Created time.Time

	// Closed is a timestamp when the compiler_proxy INFO log was closed.
	Closed time.Time

	// Machine is a machine where the compiler_proxy INFO log was created.
	Machine string

	// GomaRevision is goma revision of the compiler_proxy.
	GomaRevision string

	// GomaVersion is goma version of the compiler_proxy if it is released one.
	GomaVersion string

	// CompilerProxyIDPrefix is compiler_proxy_id prefix.
	CompilerProxyIDPrefix string

	// BuildIDs is build_id appeared in compiler_proxy log.
	// on bot, it will be one build id.
	BuildIDs []string

	// GomaFlags is goma configuration flags.
	GomaFlags string

	// GomaLimits is goma limits.
	GomaLimits string

	// CrashDump is crash dump filename if any.
	CrashDump string

	// Stats is compiler_proxy stats.
	Stats string

	// Histogram is compiler_proxy histogram.
	Histogram string

	// HTTPErrors is http errors detected in compiler proxy log.
	// value is task id.
	HTTPErrors map[HTTPError][]string

	// tasks is a map of TaskLogs by task id.
	tasks map[string]*TaskLog
}

// parseTaskLine parses line as `Task:(\d+) (.*)`.
func parseTaskLine(line string) []string {
	const task = "Task:"
	taskIdx := strings.Index(line, task)
	if taskIdx == -1 {
		return nil
	}
	afterTask := line[taskIdx+len(task):]
	afterTaskID := strings.TrimLeftFunc(afterTask, unicode.IsDigit)
	if afterTaskID == afterTask {
		return nil
	}

	if !strings.HasPrefix(afterTaskID, " ") {
		return nil
	}

	taskID := afterTask[:len(afterTask)-len(afterTaskID)]

	return []string{line, taskID, afterTaskID[1:]}
}

// Parse parses compiler_proxy.
func Parse(fname string, rd io.Reader) (*CompilerProxyLog, error) {
	cpl := &CompilerProxyLog{
		Filename:   fname,
		HTTPErrors: make(map[HTTPError][]string),
		tasks:      make(map[string]*TaskLog),
	}
	gp, err := NewGlogParser(rd)
	if err != nil {
		return nil, err
	}
	cpl.Created = gp.Created
	cpl.Machine = gp.Machine

	parseSpecial := func(field *string, searchPrefix string, includePrefix, skipFirstLine bool) func([]string) bool {
		return func(logtext []string) bool {
			if *field != "" {
				return false
			}

			if idx := strings.Index(logtext[0], searchPrefix); idx >= 0 {
				var lines []string
				if !skipFirstLine {
					if !includePrefix {
						idx += len(searchPrefix)
					}
					lines = []string{logtext[0][idx:]}
				}
				lines = append(lines, logtext[1:]...)
				*field = strings.Join(lines, "\n")
				return true
			}
			return false
		}
	}
	parseSpecials := []func([]string) bool{
		parseSpecial(&cpl.GomaRevision, "goma built revision ", false, false),
		parseSpecial(&cpl.GomaVersion, "goma version:", false, false),
		parseSpecial(&cpl.CompilerProxyIDPrefix, "compiler_proxy_id_prefix:", false, false),
		parseSpecial(&cpl.GomaFlags, "goma flags:", false, false),
		parseSpecial(&cpl.GomaLimits, "max incoming:", true, false),
		parseSpecial(&cpl.CrashDump, " Crash Dump ", false, false),
		parseSpecial(&cpl.Stats, " Dumping stats...", false, true),
		parseSpecial(&cpl.Histogram, " Dumping histogram...", false, true),
	}
	buildids := make(map[string]bool)
Lines:
	for gp.Next() {
		log := gp.Logline()
		if log.Timestamp.After(cpl.Closed) {
			cpl.Closed = log.Timestamp
		}
		for _, p := range parseSpecials {
			if p(log.Lines) {
				continue Lines
			}
		}
		m := parseTaskLine(log.Lines[0])
		if m != nil {
			t := cpl.taskLog(m[1], log.Timestamp, log)
			taskLog := m[2]

			const buildid = "build_id:"
			if strings.HasPrefix(taskLog, buildid) {
				bid := strings.TrimPrefix(taskLog, buildid)
				t.BuildID = bid
				if buildids[bid] {
					continue Lines
				}
				buildids[bid] = true
				cpl.BuildIDs = append(cpl.BuildIDs, bid)
				continue Lines
			}

			const start = "Start "
			if startIdx := strings.Index(taskLog, start); startIdx != -1 {
				t.StartTime = log.Timestamp
				t.CompileMode, t.Desc = parseStart(taskLog[startIdx+len(start):])
				continue Lines
			}

			const reply = "ReplyResponse: "
			if replyIdx := strings.Index(taskLog, reply); replyIdx != -1 {
				t.EndTime = log.Timestamp
				t.Response = taskLog[replyIdx+len(reply):]
			}

			m := httpErrorRE.FindStringSubmatch(taskLog)
			if m != nil {
				op := m[1]
				code, err := strconv.Atoi(m[2])
				if err != nil {
					// [0-9]{3} must be int.
					return nil, fmt.Errorf("%s: http code %q; %v", t.ID, m[2], err)
				}
				resp := dateLineRE.ReplaceAllString(m[3], "")
				herr := HTTPError{
					Op:   op,
					Code: code,
					Resp: resp,
				}
				t.HTTPErrors = append(t.HTTPErrors, herr)
				cpl.HTTPErrors[herr] = append(cpl.HTTPErrors[herr], t.ID)
				continue Lines
			}
		}
	}
	if err := gp.Err(); err != nil {
		return nil, err
	}
	return cpl, nil
}

func parseStart(s string) (CompileMode, string) {
	switch {
	case strings.HasPrefix(s, "precompiling "):
		return Precompiling, s[len("precompiling "):]
	case strings.HasPrefix(s, "linking "):
		return Linking, s[len("linking "):]
	default:
		return Compiling, s
	}
}

func (cpl *CompilerProxyLog) taskLog(id string, tm time.Time, logLine Logline) *TaskLog {
	if t, ok := cpl.tasks[id]; ok {
		t.Logs = append(t.Logs, logLine)
		return t
	}
	t := &TaskLog{
		ID:         id,
		AcceptTime: tm,
		Logs:       []Logline{logLine},
	}
	cpl.tasks[id] = t
	return t
}

// Duration returns duration of running time of compiler_proxy.
func (cpl *CompilerProxyLog) Duration() time.Duration {
	return cpl.Closed.Sub(cpl.Created)
}

// TaskLogs reports TaskLogs sorted by task id.
func (cpl *CompilerProxyLog) TaskLogs() []*TaskLog {
	var tasks []*TaskLog
	for _, t := range cpl.tasks {
		tasks = append(tasks, t)
	}
	sort.Sort(TaskLogs(tasks))
	return tasks
}
