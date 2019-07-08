// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Program skylab_swarming_worker executes a Skylab task via Lucifer.
//
// skylab_swarming_worker uses lucifer_run_job to actually run the autotest
// job. Once lucifer_run_job is kicked off, skylab_swarming_worker handles Lucifer
// events, translating them to task updates and runtime status updates of the
// swarming bot. If the swarming task is canceled, lucifer_swarming_worker aborts
// the Lucifer run.
//
// The following environment variables control skylab_swarming_worker
// execution.
//
// Per-bot variables:
//
//   ADMIN_SERVICE: Admin service host, e.g. foo.appspot.com.
//   AUTOTEST_DIR: Path to the autotest checkout on server.
//   LUCIFER_TOOLS_DIR: Path to the lucifer installation.
//   PARSER_PATH: Path to the autotest_status_parser installation.
//   SKYLAB_DUT_ID: skylab_inventory id of the DUT that belongs to this bot.
//
// Per-task variables:
//
//   SWARMING_TASK_ID: task id of the swarming task being serviced.

package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"strings"

	"github.com/pkg/errors"
	lflag "go.chromium.org/luci/common/flag"
	"go.chromium.org/luci/common/logging/gologger"

	"infra/cmd/skylab_swarming_worker/internal/autotest/constants"
	"infra/cmd/skylab_swarming_worker/internal/event"
	"infra/cmd/skylab_swarming_worker/internal/fifo"
	"infra/cmd/skylab_swarming_worker/internal/lucifer"
	"infra/cmd/skylab_swarming_worker/internal/parser"
	"infra/cmd/skylab_swarming_worker/internal/swmbot"
	"infra/cmd/skylab_swarming_worker/internal/swmbot/harness"
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
	adminService        string
	forceFreshInventory bool
	xClientTest         bool
	xKeyvals            map[string]string
	xProvisionLabels    []string
	xTestArgs           string
	deployActions       string
	isolatedOutdir      string
}

func parseArgs() *args {
	a := &args{}

	flag.StringVar(&a.taskName, "task-name", "",
		"Name of the task to run. For autotest, this is the NAME attribute in control file")
	flag.StringVar(&a.logdogAnnotationURL, "logdog-annotation-url", "",
		"LogDog annotation URL, like logdog://HOST/PROJECT/PREFIX/+/annotations")
	flag.StringVar(&a.adminService, "admin-service", "",
		"Admin service host, e.g. foo.appspot.com")
	flag.BoolVar(&a.forceFreshInventory, "force-fresh", false,
		"Use fresh inventory information. This flag can increase task runtime.")
	flag.BoolVar(&a.xClientTest, "client-test", false,
		"This is a client side test")
	flag.Var(lflag.CommaList(&a.xProvisionLabels), "provision-labels",
		"Labels to provision, comma separated")
	flag.Var(lflag.JSONMap(&a.xKeyvals), "keyvals",
		"JSON string of job keyvals")
	flag.StringVar(&a.xTestArgs, "test-args", "",
		"Test args (meaning depends on test)")
	flag.StringVar(&a.deployActions, "actions", "",
		"Actions to execute for a deploytask")
	flag.StringVar(&a.isolatedOutdir, "isolated-outdir", "",
		"Directory to place isolated output into. Generate no isolated output if not set.")
	flag.Parse()

	return a
}

const gcpProject = "chromeos-skylab"

func mainInner(a *args) error {
	ctx := context.Background()
	// Set up Go logger for LUCI libraries.
	ctx = gologger.StdConfig.Use(ctx)
	b := swmbot.GetInfo()
	log.Printf("Swarming bot config: %#v", b)
	annotWriter, err := openLogDogWriter(ctx, a.logdogAnnotationURL)
	if err != nil {
		return err
	}
	defer annotWriter.Close()
	i, err := harness.Open(ctx, b, harnessOptions(a)...)
	if err != nil {
		return err
	}
	defer i.Close()
	ta := lucifer.TaskArgs{
		AbortSock:  filepath.Join(i.ResultsDir, "abort_sock"),
		GCPProject: gcpProject,
		ResultsDir: i.ResultsDir,
	}
	if a.logdogAnnotationURL != "" {
		// Set up FIFO, pipe, and goroutines like so:
		//
		//        worker -> LogDog pipe
		//                      ^
		// lucifer -> FIFO -go-/
		//
		// Both the worker and Lucifer need to write to LogDog.
		fifoPath := filepath.Join(i.ResultsDir, "logdog.fifo")
		fc, err := fifo.NewCopier(annotWriter, fifoPath)
		if err != nil {
			return err
		}
		defer fc.Close()
		ta.LogDogFile = fifoPath
	}
	if err := runLuciferTask(i, a, annotWriter, ta); err != nil {
		return errors.Wrap(err, "run lucifer task")
	}
	if a.isolatedOutdir != "" {
		blob, err := parser.GetResults(i.ParserArgs())
		if err != nil {
			return errors.Wrap(err, "results parsing")
		}

		if err := writeResultsFile(a.isolatedOutdir, blob); err != nil {
			return errors.Wrap(err, "writing results to isolated output file")
		}
	}
	if err := i.Close(); err != nil {
		return err
	}
	return nil
}

func harnessOptions(a *args) []harness.Option {
	var ho []harness.Option
	if updatesInventory(a.taskName) {
		ho = append(ho, harness.UpdateInventory("repair"))
	}
	if a.forceFreshInventory {
		ho = append(ho, harness.WaitForFreshInventory)
	}
	return ho
}

// updatesInventory returns true if the task should update the inventory
func updatesInventory(taskName string) bool {
	task, _ := getAdminTask(taskName)
	return task == "repair"
}

func runLuciferTask(i *harness.Info, a *args, logdogOutput io.Writer, ta lucifer.TaskArgs) error {
	if n, ok := getAdminTask(a.taskName); ok {
		if err := runAdminTask(i, n, logdogOutput, ta); err != nil {
			return errors.Wrap(err, "run admin task")
		}
	} else if isDeployTask(a.taskName) {
		if err := runDeployTask(i, a.deployActions, logdogOutput, ta); err != nil {
			return errors.Wrap(err, "run deploy task")
		}
	} else {
		if err := runTest(i, a, logdogOutput, ta); err != nil {
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

// isDeployTask determines if the given task name corresponds to a deploy task.
func isDeployTask(name string) bool {
	return name == "deploy"
}

// runTest runs a test.
func runTest(i *harness.Info, a *args, logdogOutput io.Writer, ta lucifer.TaskArgs) (err error) {
	// TODO(ayatane): Always reboot between each test for now.
	tc := prejobTaskControl{
		runReset:     true,
		rebootBefore: RebootAlways,
	}
	r := lucifer.TestArgs{
		TaskArgs:           ta,
		Hosts:              []string{i.DUTName},
		TaskName:           a.taskName,
		XTestArgs:          a.xTestArgs,
		XClientTest:        a.xClientTest,
		XKeyvals:           a.xKeyvals,
		XLevel:             lucifer.LuciferLevelSkylabProvision,
		XLocalOnlyHostInfo: true,
		// TODO(ayatane): hostDirty, hostProtected not implemented
		XPrejobTask:      choosePrejobTask(tc, true, false),
		XProvisionLabels: a.xProvisionLabels,
	}

	cmd := lucifer.TestCommand(i.LuciferConfig(), r)
	f := event.ForwardAbortSignal(r.AbortSock)
	defer f.Close()
	lr, err := runLuciferCommand(i, logdogOutput, cmd)
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

func choosePrejobTask(tc prejobTaskControl, hostDirty, hostProtected bool) constants.AdminTaskType {
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
		return constants.Reset
	case willReboot:
		return constants.Cleanup
	case willVerify:
		return constants.Verify
	default:
		return constants.NoTask
	}
}

// runAdminTask runs an admin task.  name is the name of the task.
func runAdminTask(i *harness.Info, name string, logdogOutput io.Writer, ta lucifer.TaskArgs) (err error) {
	r := lucifer.AdminTaskArgs{
		TaskArgs: ta,
		Host:     i.DUTName,
		Task:     name,
	}

	cmd := lucifer.AdminTaskCommand(i.LuciferConfig(), r)
	f := event.ForwardAbortSignal(r.AbortSock)
	defer f.Close()
	if _, err := runLuciferCommand(i, logdogOutput, cmd); err != nil {
		return errors.Wrap(err, "run lucifer failed")
	}
	return nil
}

// runDeployTask runs a deploy task using lucifer.
//
// actions is a possibly empty comma separated list of deploy actions to run
func runDeployTask(i *harness.Info, actions string, logdogOutput io.Writer, ta lucifer.TaskArgs) error {
	r := lucifer.DeployTaskArgs{
		TaskArgs: ta,
		Host:     i.DUTName,
		Actions:  actions,
	}

	cmd := lucifer.DeployTaskCommand(i.LuciferConfig(), r)
	f := event.ForwardAbortSignal(r.AbortSock)
	defer f.Close()
	if _, err := runLuciferCommand(i, logdogOutput, cmd); err != nil {
		return errors.Wrap(err, "run deploy task")
	}
	return nil
}

// TODO(zamorzaev): move this into the isolate client.
const resultsFileName = "results.json"

// writeResultsFile writes the results blob to "results.json" inside the given dir.
func writeResultsFile(outdir string, b []byte) error {
	f := filepath.Join(outdir, resultsFileName)
	return ioutil.WriteFile(f, b, 0644)
}
