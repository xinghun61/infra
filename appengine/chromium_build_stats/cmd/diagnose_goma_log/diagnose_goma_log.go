// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// diagnose_goma_log diagnoses goma's compiler_proxy.INFO log file.
//
// usage:
//  ../../goenv.sh goapp run diagnose_goma_log.go --filename /tmp/compiler_proxy.INFO
//
package main

import (
	"bufio"
	"compress/gzip"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"sort"
	"time"

	"compilerproxylog"
)

var (
	filename = flag.String("filename", "compiler_proxy.INFO", "filename of compiler_proxy.INFO")
)

func reader(fname string, rd io.Reader) (io.Reader, error) {
	if filepath.Ext(fname) != ".gz" {
		return bufio.NewReaderSize(rd, 512*1024), nil
	}
	return gzip.NewReader(bufio.NewReaderSize(rd, 512*1024))
}

func diagnose(fname string) {
	f, err := os.Open(fname)
	if err != nil {
		log.Fatal(err)
	}
	defer f.Close()
	rd, err := reader(fname, f)
	if err != nil {
		log.Fatal(err)
	}

	cpl, err := compilerproxylog.Parse(fname, rd)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println("Filename:", cpl.Filename)
	fmt.Println("Created:", cpl.Created)
	fmt.Println("Machine:", cpl.Machine)
	fmt.Println("GomaRevision:", cpl.GomaRevision)
	fmt.Println("GomaVersion:", cpl.GomaVersion)
	fmt.Println("GomaFlags:", cpl.GomaFlags)
	fmt.Println("GomaLimits:", cpl.GomaLimits)
	fmt.Println("CrashDump:", cpl.CrashDump)
	fmt.Println("Stats:", cpl.Stats)

	fmt.Println("")
	fmt.Println("duration:", cpl.Duration())

	tasks := cpl.TaskLogs()
	fmt.Println("tasks:", len(tasks))
	fmt.Println("tasks/sec:", float64(len(tasks))/cpl.Duration().Seconds())
	fmt.Println("")

	var duration time.Duration
	for _, t := range tasks {
		duration += t.Duration()
	}
	tasksByCompileMode := compilerproxylog.ClassifyByCompileMode(tasks)
	for i, tasks := range tasksByCompileMode {
		mode := compilerproxylog.CompileMode(i)
		fmt.Println(mode, ": # of tasks: ", len(tasks))
		if len(tasks) == 0 {
			fmt.Println("")
			continue
		}

		tr := compilerproxylog.ClassifyByResponse(tasks)
		var resps []string
		for r := range tr {
			resps = append(resps, r)
		}
		fmt.Println("  replies:")
		for _, r := range resps {
			fmt.Println("    ", r, len(tr[r]))
		}
		sort.Sort(sort.Reverse(compilerproxylog.ByDuration{TaskLogs: tasks}))
		var duration time.Duration
		for _, t := range tasks {
			duration += t.Duration()
		}
		fmt.Println("  durations:")
		fmt.Println("      ave  :", duration/time.Duration(len(tasks)))
		fmt.Println("      max  :", tasks[0].Duration())
		for _, q := range []int{98, 91, 75, 50, 25, 9, 2} {
			fmt.Printf("       %2d%% : %s\n", q, tasks[int(float64(len(tasks)*q)/100.0)].Duration())
		}
		fmt.Println("      min  :", tasks[len(tasks)-1].Duration())
		fmt.Println("  long tasks:")
		for i := 0; i < 5; i++ {
			if i >= len(tasks) {
				break
			}
			fmt.Printf("   #%d %s %s\n", i, tasks[i].ID, tasks[i].Duration())
			fmt.Println("    ", tasks[i].Desc)
			fmt.Println("    ", tasks[i].Response)
		}
		fmt.Println("")
	}

	dd := compilerproxylog.DurationDistribution(cpl.Created, tasks)
	fmt.Println("Duration per num active tasks")
	for i, d := range dd {
		fmt.Printf(" %3d tasks: %s\n", i, d)
	}
}

func main() {
	flag.Parse()

	diagnose(*filename)
}
