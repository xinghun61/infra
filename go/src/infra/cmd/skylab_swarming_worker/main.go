// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Program skylab_swarming_worker executes a Skylab task via Lucifer.

skylab_swarming_worker uses lucifer_run_job to actually run the autotest
job. Once lucifer_run_job is kicked off, skylab_swarming_worker handles Lucifer
events, translating them to task updates and runtime status updates of the
swarming bot. If the swarming task is canceled, lucifer_swarming_worker aborts
the Lucifer run.

Following environment variables control skylab_swarming_worker execution.
Per-bot variables:
  AUTOTEST_DIR: Path to the autotest checkout on server.
  LUCIFER_TOOLS_DIR: Path to the lucifer installation.
  INVENTORY_TOOLS_DIR: Path to the skylab inventory tools intallation.
  INVENTORY_DATA_DIR: Path to the skylab_inventory data checkout.
  INVENTORY_ENVIRONMENT: skylab_inventory environment this bot is part of.
  SKYLAB_DUT_ID: skylab_inventory id of the DUT that belongs to this bot.
Per-task variables:
  SWARMING_TASK_ID: task id of the swarming task being serviced.
*/
package main

import (
	"context"
	"flag"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/pkg/errors"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/logdog/common/types"

	"infra/cmd/skylab_swarming_worker/internal/autotest"
	"infra/cmd/skylab_swarming_worker/internal/flagx"
	"infra/cmd/skylab_swarming_worker/internal/log"
	"infra/cmd/skylab_swarming_worker/internal/lucifer"
	"infra/cmd/skylab_swarming_worker/internal/swarming"
	"infra/cmd/skylab_swarming_worker/internal/swarming/harness"
)

func main() {
	log.Setup()
	log.Printf("skylab_swarming_worker starting with args: %s", os.Args)
	a := parseArgs()
	if err := runSwarmingTask(a); err != nil {
		log.Fatalf("Error: %s", err)
	}
}

type args struct {
	taskName            string
	logdogAnnotationURL string
	xClientTest         bool
	xKeyvals            map[string]string
	xProvisionLabels    []string
}

func parseArgs() *args {
	a := &args{}

	flag.StringVar(&a.taskName, "task-name", "",
		"Name of the task to run. For autotest, this is the NAME attribute in control file")
	flag.StringVar(&a.logdogAnnotationURL, "logdog-annotation-url", "",
		"LogDog annotation URL, like logdog://HOST/PROJECT/PREFIX/+/annotations")
	flag.BoolVar(&a.xClientTest, "client-test", false,
		"This is a client side test")
	flag.Var(flagx.CommaList(&a.xProvisionLabels), "provision-labels",
		"Labels to provision, comma separated")
	flag.Var(flagx.JSONMap(&a.xKeyvals), "keyvals",
		"JSON string of job keyvals")
	flag.Parse()

	return a
}

const gcpProject = "chromeos-skylab"

func runSwarmingTask(a *args) (err error) {
	ctx := context.Background()
	// Set up Go logger for LUCI libraries.
	ctx = gologger.StdConfig.Use(ctx)
	b := swarming.NewBotFromEnv()
	log.Printf("Swarming bot config: %#v", b)
	if err := b.LoadDUTName(); err != nil {
		return errors.Wrap(err, "load DUT name")
	}
	if err := b.LoadBotInfo(); err != nil {
		return errors.Wrap(err, "load bot info")
	}
	defer func() {
		if err2 := b.DumpBotInfo(); err == nil && err2 != nil {
			err = errors.Wrap(err2, "dump bot info")
		}
	}()
	return harness.Run(b,
		func(b *swarming.Bot, resultsDir string) error {
			var wg sync.WaitGroup
			var err2 error
			var w *os.File
			if a.logdogAnnotationURL != "" {
				streamAddr, err := types.ParseURL(a.logdogAnnotationURL)
				if err != nil {
					return errors.Errorf("invalid LogDog annotation URL %s: %s",
						a.logdogAnnotationURL, err)
				}
				var r *os.File
				r, w, err = os.Pipe()
				if err != nil {
					return errors.Wrap(err, "make LogDog pipe")
				}
				defer r.Close()
				defer w.Close()
				wg.Add(1)
				go func() {
					defer wg.Done()
					if err := copyToLogDog(ctx, streamAddr, r); err != nil {
						err2 = errors.Wrapf(err, "output to LogDog")
					}
				}()
			}
			ta := lucifer.TaskArgs{
				AbortSock:  filepath.Join(resultsDir, "abort_sock"),
				GCPProject: gcpProject,
				ResultsDir: resultsDir,
				LogDogPipe: w,
			}
			if err := runLuciferTask(b, a, w, ta, b.DUTName()); err != nil {
				return errors.Wrap(err, "run lucifer task")
			}
			if w != nil {
				w.Close()
			}
			log.Printf("Waiting for LogDog copy")
			wg.Wait()
			return err2
		},
	)
}

func runLuciferTask(b *swarming.Bot, a *args, logdogOutput io.Writer, ta lucifer.TaskArgs, dutName string) error {
	if n, ok := getAdminTask(a.taskName); ok {
		if err := runAdminTask(b, n, logdogOutput, ta, dutName); err != nil {
			return errors.Wrap(err, "run admin task")
		}
	} else {
		if err := runTest(b, a, logdogOutput, ta, dutName); err != nil {
			return errors.Wrap(err, "run test")
		}
	}
	return nil
}

// getAdminTask returns the admin task name if the given task is an
// admin task.  If the given task is not an admin task, ok will be
// false.
func getAdminTask(name string) (task string, ok bool) {
	if strings.HasPrefix(name, "admin_") {
		return strings.TrimPrefix(name, "admin_"), true
	}
	return "", false
}

// runTest runs a test.
func runTest(b *swarming.Bot, a *args, logdogOutput io.Writer, ta lucifer.TaskArgs, dutName string) (err error) {
	// TODO(ayatane): Always reboot between each test for now.
	tc := prejobTaskControl{
		runReset:     true,
		rebootBefore: RebootAlways,
	}
	r := lucifer.RunJobArgs{
		TaskArgs:           ta,
		Hosts:              []string{dutName},
		TaskName:           a.taskName,
		XClientTest:        a.xClientTest,
		XKeyvals:           a.xKeyvals,
		XLevel:             lucifer.LuciferLevelSkylabProvision,
		XLocalOnlyHostInfo: true,
		// TODO(ayatane): hostDirty, hostProtected not implemented
		XPrejobTask:      choosePrejobTask(tc, true, false),
		XProvisionLabels: a.xProvisionLabels,
	}

	lr, err := runLuciferJob(b, logdogOutput, r)
	if err != nil {
		return errors.Wrap(err, "run lucifer failed")
	}
	if lr.TestsFailed > 0 {
		return errors.Errorf("%d tests failed", lr.TestsFailed)
	}
	return nil
}

type rebootBefore int

// Reboot type values.
const (
	RebootNever rebootBefore = iota
	RebootIfDirty
	RebootAlways
)

// prejobTaskControl groups values used to control whether to run
// prejob tasks for tests.  Note that there are subtle interactions
// between these values, e.g., runReset may run verify as part of
// reset even if runVerify is false, but runReset will fail if
// rebootBefore is RebootNever because that restricts cleanup, which
// runs as part of reset.
type prejobTaskControl struct {
	runVerify    bool
	runReset     bool
	rebootBefore rebootBefore
}

func choosePrejobTask(tc prejobTaskControl, hostDirty, hostProtected bool) autotest.AdminTaskType {
	willVerify := (tc.runReset || tc.runVerify) && !hostProtected

	var willReboot bool
	switch tc.rebootBefore {
	case RebootAlways:
		willReboot = true
	case RebootIfDirty:
		willReboot = hostDirty || (tc.runReset && willVerify)
	case RebootNever:
		willReboot = false
	}

	switch {
	case willReboot && willVerify:
		return autotest.Reset
	case willReboot:
		return autotest.Cleanup
	case willVerify:
		return autotest.Verify
	default:
		return autotest.NoTask
	}
}

// runAdminTask runs an admin task.  name is the name of the task.
func runAdminTask(b *swarming.Bot, name string, logdogOutput io.Writer, ta lucifer.TaskArgs, dutName string) (err error) {
	r := lucifer.AdminTaskArgs{
		TaskArgs: ta,
		Host:     dutName,
		Task:     name,
	}

	if _, err := runLuciferAdminTask(b, logdogOutput, r); err != nil {
		return errors.Wrap(err, "run lucifer failed")
	}
	return nil
}
