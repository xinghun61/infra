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
	"flag"
	"fmt"
	"io/ioutil"
	"os"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unsafe"

	"github.com/luci/luci-go/common/runtime/paniccatcher"
)

var (
	logHeader = C.CString("CIT_DeviceWatchdog")
)

type logLevel int

const (
	logInfo = iota
	logWarning
	logError
)

const (
	stdInFd  = 0
	stdOutFd = 1
	stdErrFd = 2
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

// Spawn a child process via fork, create new process group, chdir and
// redirect std in and out to /dev/null.
func daemonize() (int, error) {
	ret, _, errno := syscall.Syscall(syscall.SYS_FORK, 0, 0, 0)
	pid := int(ret)
	if errno != 0 {
		return 0, errno
	}
	if pid > 0 {
		return pid, nil
	}

	_, err := syscall.Setsid()
	if err != nil {
		return 0, err
	}

	f, err := os.Open("/dev/null")
	if err != nil {
		return 0, err
	}
	fd := f.Fd()
	syscall.Dup2(int(fd), stdInFd)
	syscall.Dup2(int(fd), stdOutFd)
	syscall.Dup2(int(fd), stdErrFd)

	return pid, nil
}

// Read from /proc/uptime. Expected format:
// "uptime_in_seconds cpu_idle_time_in_seconds"
func getDeviceUptime() (time.Duration, error) {
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
	return fmt.Errorf("I just rebooted. How am I still alive?!?\n")
}

func realMain() int {
	maxUptimeFlag := flag.Int("max-uptime", 120, "Maximum uptime in minutes before a reboot is triggered.")
	flag.Parse()

	os.Chdir("/")
	pid, err := daemonize()
	if err != nil {
		logcatLog(logError, "Failed to daemonize: %s", err.Error())
		return 1
	}
	if pid > 0 {
		logcatLog(logInfo, "Child spawned with pid %d, exiting parent\n", pid)
		return 0
	}

	maxUptime := time.Duration(*maxUptimeFlag) * time.Minute
	for {
		uptime, err := getDeviceUptime()
		if err != nil {
			logcatLog(logError, "Failed to get uptime: %s", err.Error())
			return 1
		}

		if uptime > maxUptime {
			logcatLog(logInfo, "Max uptime exceeded: (%s > %s)\n", uptime, maxUptime)
			break
		}
		logcatLog(logInfo, "No need to reboot, uptime < max_uptime: (%s < %s)\n", uptime, maxUptime)
		time.Sleep(maxUptime - uptime + time.Second)
	}
	if err = rebootDevice(); err != nil {
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
