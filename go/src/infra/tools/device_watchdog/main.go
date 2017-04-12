// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build android

// Watchdog daemon for android devices. It will attempt to reboot the device
// if its uptime exceeds a specified maximum.
package main

/*
#cgo LDFLAGS: -landroid -llog

#include <android/log.h>
#include <string.h>
*/
import "C"

import (
	"errors"
	"flag"
	"fmt"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"text/template"
	"time"
	"unsafe"

	"github.com/VividCortex/godaemon"
	"github.com/luci/luci-go/common/runtime/paniccatcher"
	"github.com/luci/luci-go/common/sync/parallel"
	"golang.org/x/net/context"
)

var (
	stateDumpDir = "/data/watchdog/"
	logHeader    = C.CString("CIT_DeviceWatchdog")
	errTimeout   = errors.New("timeout")
)

type state struct {
	USB       string
	Battery   string
	DiskStats string
	DiskUsage string
	Processes string
}

var stateBody = `USB state:
{{.USB}}

Battery state:
{{.Battery}}

Disk state:
{{.DiskStats}}

Disk usage:
{{.DiskUsage}}

Process dump:
{{.Processes}}
`

const (
	stdInFd  = 0
	stdOutFd = 1
	stdErrFd = 2
)

type logLevel int

const (
	logInfo = iota
	logWarning
	logError
)

func (l logLevel) getLogLevel() C.int {
	switch l {
	case logInfo:
		return C.ANDROID_LOG_INFO
	case logWarning:
		return C.ANDROID_LOG_WARN
	case logError:
		return C.ANDROID_LOG_ERROR
	default:
		panic("Unknown log level.")
	}
}

func logcatLog(level logLevel, format string, args ...interface{}) {
	cmsg := C.CString(fmt.Sprintf(format, args...))
	defer C.free(unsafe.Pointer(cmsg))
	C.__android_log_write(level.getLogLevel(), logHeader, cmsg)
}

func runWithContext(c context.Context, cmd string, args ...string) string {
	out, err := exec.CommandContext(c, cmd, args...).Output()
	if err != nil {
		return fmt.Sprintf("Error: %s", err)
	}
	return string(out)
}

func getState(c context.Context) state {
	s := state{}
	_ = parallel.FanOutIn(func(workC chan<- func() error) {
		workC <- func() error {
			s.USB = runWithContext(c, "/system/bin/dumpsys", "usb")
			return nil
		}
		workC <- func() error {
			s.Battery = runWithContext(c, "/system/bin/dumpsys", "battery")
			return nil
		}
		workC <- func() error {
			s.DiskStats = runWithContext(c, "/system/bin/dumpsys", "diskstats")
			return nil
		}
		workC <- func() error {
			s.DiskUsage = runWithContext(c, "/system/bin/df")
			return nil
		}
		workC <- func() error {
			s.Processes = runWithContext(c, "/system/bin/ps")
			return nil
		}
	})
	return s
}

func dumpState(c context.Context) error {
	if err := os.MkdirAll(stateDumpDir, 0755); err != nil {
		return err
	}

	fileName := time.Now().Format("20060102_150405") + ".log"
	f, err := os.Create(filepath.Join(stateDumpDir, fileName))
	if err != nil {
		return err
	}

	s := getState(c)
	t := template.Must(template.New("").Parse(stateBody))
	if err := t.Execute(f, s); err != nil {
		return err
	}
	// Explicitly flush the changes to disk here to avoid the subsequent
	// reboot from occuring before the system automatically flushes.
	if err := f.Sync(); err != nil {
		return err
	}
	return f.Close()
}

func dumpStateWithTimeout(timeout time.Duration) error {
	c := make(chan error)

	ctx, cancelFunc := context.WithTimeout(context.Background(), timeout)
	defer cancelFunc()

	go func() {
		c <- dumpState(ctx)
	}()

	select {
	case err := <-c:
		return err
	case <-ctx.Done():
		return ctx.Err()
	}
}

type uptimeResult struct {
	Uptime time.Duration
	Err    error
}

// Read from /proc/uptime. Expected format:
// "uptime_in_seconds cpu_idle_time_in_seconds"
// Return the uptime via a channel for use with timeouts.
func readUptime() (time.Duration, error) {
	bytes, err := ioutil.ReadFile("/proc/uptime")
	if err != nil {
		return 0, fmt.Errorf("unable to open /proc/uptime: %s", err.Error())
	}
	// Split on the space to get uptime and drop cpu idle time.
	uptimeFields := strings.Fields(string(bytes))
	if len(uptimeFields) == 0 {
		return 0, fmt.Errorf("unable to parse /proc/uptime")
	}
	uptime, err := strconv.ParseFloat(uptimeFields[0], 64)
	if err != nil {
		return 0, fmt.Errorf("unable to parse uptime: %s", err.Error())
	}
	return time.Duration(uptime * float64(time.Second)), nil
}

func getUptime(requestQueue chan<- chan<- uptimeResult, timeoutPeriod time.Duration) (time.Duration, error) {
	request := make(chan uptimeResult, 1)
	defer close(request)

	timer := time.NewTimer(timeoutPeriod)
	defer timer.Stop()

	select {
	case requestQueue <- request:
		break
	case <-timer.C:
		return 0, errTimeout
	}

	select {
	case resp := <-request:
		return resp.Uptime, resp.Err
	case <-timer.C:
		return 0, errTimeout
	}
}

// Reboot device by writing to sysrq-trigger. See:
// https://www.kernel.org/doc/Documentation/sysrq.txt
func rebootDevice() error {
	fd, err := os.OpenFile("/proc/sysrq-trigger", os.O_WRONLY, 0)
	if err != nil {
		return fmt.Errorf("Can't open /proc/sysrq-trigger: %s", err.Error())
	}
	defer fd.Close()
	_, err = fd.Write([]byte("b"))
	if err != nil {
		return fmt.Errorf("Can't reboot: %s", err.Error())
	}
	return errors.New("I just rebooted. How am I still alive?!?")
}

func realMain() int {
	godaemon.MakeDaemon(&godaemon.DaemonAttr{})

	maxUptimeFlag := flag.Int("max-uptime", 120, "Maximum uptime in minutes before a reboot is triggered.")
	flag.Parse()

	requestQueue := make(chan chan<- uptimeResult)
	go func() {
		for request := range requestQueue {
			uptime, err := readUptime()
			request <- uptimeResult{Uptime: uptime, Err: err}
		}
	}()
	defer close(requestQueue)

	maxUptime := time.Duration(*maxUptimeFlag) * time.Minute
	consecutiveTimeouts := 0
	const maxTimeouts = 5
	for {
		uptime, err := getUptime(requestQueue, 5*time.Second)
		switch err {
		case nil:
			consecutiveTimeouts = 0
		case errTimeout:
			consecutiveTimeouts++
		default:
			logcatLog(logError, "Failed to get uptime: %s", err.Error())
			return 1
		}
		if consecutiveTimeouts >= maxTimeouts {
			logcatLog(logError, "%d consective timeouts when fetching uptime. Triggering reboot", consecutiveTimeouts)
			break
		}
		if consecutiveTimeouts > 0 {
			logcatLog(logError, "Timeout when fetching uptime. Sleeping for 60s and trying again.")
			time.Sleep(60 * time.Second)
			continue
		}

		if uptime > maxUptime {
			logcatLog(logInfo, "Max uptime exceeded: (%s > %s)\n", uptime, maxUptime)
			break
		}
		logcatLog(logInfo, "No need to reboot, uptime < max_uptime: (%s < %s)\n", uptime, maxUptime)
		// Add an additional second to the sleep to ensure it doesn't
		// sleep several times in less than a second.
		time.Sleep(maxUptime - uptime + time.Second)
	}
	// Try to dump state of the device to a file before rebooting for later
	// investigation. Do so within a timeout to avoid blocking the reboot.
	if err := dumpStateWithTimeout(10 * time.Second); err != nil {
		logcatLog(logError, "Unable to dump state to filesystem: %s", err.Error())
	}
	if err := rebootDevice(); err != nil {
		logcatLog(logError, "Failed to reboot device: %s", err.Error())
		return 1
	}
	return 0
}

func main() {
	paniccatcher.Do(func() {
		os.Exit(realMain())
	}, func(p *paniccatcher.Panic) {
		logcatLog(logError, "Panic: %s\n%s", p.Reason, p.Stack)
		os.Exit(1)
	})
}
