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
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"strings"

	"github.com/pkg/errors"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/logdog/common/types"

	"infra/cmd/skylab_swarming_worker/internal/autotest"
	"infra/cmd/skylab_swarming_worker/internal/fifo"
	"infra/cmd/skylab_swarming_worker/internal/flagx"
	"infra/cmd/skylab_swarming_worker/internal/lucifer"
	"infra/cmd/skylab_swarming_worker/internal/swarming"
	"infra/cmd/skylab_swarming_worker/internal/swarming/harness"
)

func main() {
	log.SetPrefix(fmt.Sprintf("%s: ", filepath.Base(os.Args[0])))
	log.Printf("Starting with args: %s", os.Args)
	a := parseArgs()
	if err := mainInner(a); err != nil {
		log.Fatalf("Error: %s", err)
	}
	log.Printf("Exited successfully")
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

func mainInner(a *args) error {
	ctx := context.Background()
	// Set up Go logger for LUCI libraries.
	ctx = gologger.StdConfig.Use(ctx)
	b := swarming.NewBotFromEnv()
	log.Printf("Swarming bot config: %#v", b)
	return harness.Run(b,
		func(b *swarming.Bot, i *harness.Info) error {
			ta := lucifer.TaskArgs{
				AbortSock:  filepath.Join(i.ResultsDir, "abort_sock"),
				GCPProject: gcpProject,
				ResultsDir: i.ResultsDir,
			}
			var annotWriter io.Writer
			annotWriter = os.Stdout

			if a.logdogAnnotationURL != "" {
				// Set up FIFO, pipe, and goroutines like so:
				//
				//        worker -> LogDog pipe
				//                      ^
				// lucifer -> FIFO -go-/
				//
				// Both the worker and Lucifer need to write to LogDog.
				log.Printf("Setting up LogDog stream")
				streamAddr, err := types.ParseURL(a.logdogAnnotationURL)
				if err != nil {
					return errors.Wrapf(err, "invalid LogDog annotation URL %s",
						a.logdogAnnotationURL)
				}
				lc, err := openLogDog(ctx, streamAddr)
				if err != nil {
					return err
				}
				defer lc.Close()
				annotWriter = lc.Stdout()

				fifoPath := filepath.Join(i.ResultsDir, "logdog.fifo")
				fc, err := fifo.NewCopier(annotWriter, fifoPath)
				if err != nil {
					return err
				}
				defer fc.Close()
				ta.LogDogFile = fifoPath
			}
			if err := runLuciferTask(b, i, a, annotWriter, ta); err != nil {
				return errors.Wrap(err, "run lucifer task")
			}
			return nil
		},
	)
}

func runLuciferTask(b *swarming.Bot, i *harness.Info, a *args, logdogOutput io.Writer, ta lucifer.TaskArgs) error {
	if n, ok := getAdminTask(a.taskName); ok {
		if err := runAdminTask(b, i, n, logdogOutput, ta); err != nil {
			return errors.Wrap(err, "run admin task")
		}
	} else {
		if err := runTest(b, i, a, logdogOutput, ta); err != nil {
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
func runTest(b *swarming.Bot, i *harness.Info, a *args, logdogOutput io.Writer, ta lucifer.TaskArgs) (err error) {
	// TODO(ayatane): Always reboot between each test for now.
	tc := prejobTaskControl{
		runReset:     true,
		rebootBefore: RebootAlways,
	}
	r := lucifer.RunJobArgs{
		TaskArgs:           ta,
		Hosts:              []string{i.DUTName},
		TaskName:           a.taskName,
		XClientTest:        a.xClientTest,
		XKeyvals:           a.xKeyvals,
		XLevel:             lucifer.LuciferLevelSkylabProvision,
		XLocalOnlyHostInfo: true,
		// TODO(ayatane): hostDirty, hostProtected not implemented
		XPrejobTask:      choosePrejobTask(tc, true, false),
		XProvisionLabels: a.xProvisionLabels,
	}

	lr, err := runLuciferJob(b, i, logdogOutput, r)
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
func runAdminTask(b *swarming.Bot, i *harness.Info, name string, logdogOutput io.Writer, ta lucifer.TaskArgs) (err error) {
	r := lucifer.AdminTaskArgs{
		TaskArgs: ta,
		Host:     i.DUTName,
		Task:     name,
	}

	if _, err := runLuciferAdminTask(b, i, logdogOutput, r); err != nil {
		return errors.Wrap(err, "run lucifer failed")
	}
	return nil
}
