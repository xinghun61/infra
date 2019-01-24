// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag"

	"infra/cmd/skylab/internal/site"
)

// CreateTest subcommand: create a test task.
var CreateTest = &subcommands.Command{
	UsageLine: "create-test {-board BOARD | -model MODEL} -pool POOL -image IMAGE [-timeout-mins TIMEOUT_MINS] [-client-test] [-tag KEY:VALUE...] [-keyval KEY:VALUE] [-test-args ARGS] TEST_NAME [DIMENSION_KEY:VALUE...]",
	ShortDesc: "Create a test task, with the given test name and swarming dimensions",
	LongDesc:  "Create a test task, with the given test name and swarming dimensions.",
	CommandRun: func() subcommands.CommandRun {
		c := &createTestRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.BoolVar(&c.client, "client-test", false, "Task is a client-side test.")
		c.Flags.StringVar(&c.image, "image", "", "Fully specified image name to run test against, e.g. reef-canary/R73-11580.0.0")
		c.Flags.StringVar(&c.board, "board", "", "Board to run test on.")
		c.Flags.StringVar(&c.model, "model", "", "Model to run test on.")
		// TODO(akeshet): Decide on whether these should be specified in their proto
		// format (e.g. DUT_POOL_BVT) or in a human readable format, e.g. bvt. Provide a
		// list of common choices.
		c.Flags.StringVar(&c.pool, "pool", "", "Device pool to run test on.")
		c.Flags.IntVar(&c.timeoutMins, "timeout-mins", 20, "Time (counting from when the task starts) after which task will be killed if it hasn't completed.")
		c.Flags.Var(flag.StringSlice(&c.tags), "tag", "Swarming tag for test; may be specified multiple times.")
		c.Flags.Var(flag.StringSlice(&c.keyvals), "keyval", "Autotest keyval for test. Key may not contain : character. May be specified multiple times.")
		c.Flags.StringVar(&c.testArgs, "test-args", "", "Test arguments string (meaning depends on test).")
		c.Flags.StringVar(&c.qsAccount, "qs-account", "", "QuotaScheduler account to use for this task (optional)")
		return c
	},
}

type createTestRun struct {
	subcommands.CommandRunBase
	authFlags   authcli.Flags
	envFlags    envFlags
	client      bool
	image       string
	board       string
	model       string
	pool        string
	timeoutMins int
	tags        []string
	keyvals     []string
	testArgs    string
	qsAccount   string
}

// validateArgs ensures that the command line arguments are
func (c *createTestRun) validateArgs() error {
	if c.Flags.NArg() == 0 {
		return NewUsageError(c.Flags, "missing test name")
	}

	if c.board == "" && c.model == "" {
		return NewUsageError(c.Flags, "missing -board or a -model")
	}

	if c.pool == "" {
		return NewUsageError(c.Flags, "missing -pool")
	}

	if c.image == "" {
		return NewUsageError(c.Flags, "missing -image")
	}

	return nil
}

func (c *createTestRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *createTestRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if err := c.validateArgs(); err != nil {
		return err
	}

	taskName := c.Flags.Arg(0)
	userDimensions := c.Flags.Args()[1:]

	dimensions := make([]string, 2)
	dimensions[0] = "pool:ChromeOSSkylab"
	dimensions[1] = "dut_state:ready"
	if c.board != "" {
		dimensions = append(dimensions, "label-board:"+c.board)
	}
	if c.model != "" {
		dimensions = append(dimensions, "label-model:"+c.model)
	}
	if c.pool != "" {
		dimensions = append(dimensions, "label-pool:"+c.pool)
	}

	dimensions = append(dimensions, userDimensions...)

	provisionableLabels := make([]string, 0, 1)
	if c.image != "" {
		provisionableLabels = append(provisionableLabels, "provisionable-cros-version:"+c.image)
	}

	keyvals, err := toKeyvalMap(c.keyvals)
	if err != nil {
		return err
	}

	e := c.envFlags.Env()

	logdogURL := generateAnnotationURL(e)
	slices, err := getSlices(taskName, c.client, logdogURL, provisionableLabels, dimensions, keyvals, c.testArgs, c.timeoutMins)
	if err != nil {
		return errors.Annotate(err, "create test").Err()
	}

	tags := append(c.tags, "skylab-tool:create-test", "log_location:"+logdogURL, "luci_project:"+e.LUCIProject)
	if c.qsAccount != "" {
		tags = append(tags, "qs_account:"+c.qsAccount)
	}

	req := newTaskRequest(taskName, tags, slices, defaultTaskPriority)

	ctx := cli.GetContext(a, c, env)
	s, err := newSwarmingService(ctx, c.authFlags, e)
	if err != nil {
		return err
	}

	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	resp, err := s.Tasks.New(req).Context(ctx).Do()
	if err != nil {
		return errors.Annotate(err, "create test").Err()
	}

	fmt.Fprintf(a.GetOut(), "Created Swarming task %s\n", swarmingTaskURL(e, resp.TaskId))
	return nil
}

// toPairs converts a slice of strings in foo:bar form to a slice of swarming rpc string pairs.
func toPairs(dimensions []string) ([]*swarming.SwarmingRpcsStringPair, error) {
	pairs := make([]*swarming.SwarmingRpcsStringPair, len(dimensions))
	for i, d := range dimensions {
		k, v := strpair.Parse(d)
		if v == "" {
			return nil, fmt.Errorf("malformed dimension with key '%s' has no value", k)
		}
		pairs[i] = &swarming.SwarmingRpcsStringPair{Key: k, Value: v}
	}
	return pairs, nil
}

func toKeyvalMap(keyvals []string) (map[string]string, error) {
	m := make(map[string]string, len(keyvals))
	for _, s := range keyvals {
		k, v := strpair.Parse(s)
		if v == "" {
			return nil, fmt.Errorf("malformed keyval with key '%s' has no value", k)
		}
		if _, ok := m[k]; ok {
			return nil, fmt.Errorf("keyval with key %s specified more than once", k)
		}
		m[k] = v
	}
	return m, nil
}

func taskSlice(command []string, dimensions []*swarming.SwarmingRpcsStringPair, timeoutMins int) *swarming.SwarmingRpcsTaskSlice {
	return &swarming.SwarmingRpcsTaskSlice{
		// TODO(akeshet): Determine correct expiration time.
		ExpirationSecs:  30,
		WaitForCapacity: false,
		Properties: &swarming.SwarmingRpcsTaskProperties{
			Command:              command,
			Dimensions:           dimensions,
			ExecutionTimeoutSecs: int64(timeoutMins * 60),
		},
	}
}

// getSlices generates and returns the set of swarming task slices for the given test task.
func getSlices(taskName string, clientTest bool, annotationURL string, provisionableDimensions []string,
	dimensions []string, keyvals map[string]string, testArgs string, timeoutMins int) ([]*swarming.SwarmingRpcsTaskSlice, error) {
	basePairs, err := toPairs(dimensions)
	if err != nil {
		return nil, errors.Annotate(err, "create slices").Err()
	}
	provisionablePairs, err := toPairs(provisionableDimensions)
	if err != nil {
		return nil, errors.Annotate(err, "create slices").Err()
	}

	s0cmd := skylabWorkerCommand(taskName, clientTest, keyvals, annotationURL, nil, testArgs)
	s0Dims := append(basePairs, provisionablePairs...)
	s0 := taskSlice(s0cmd, s0Dims, timeoutMins)

	if len(provisionableDimensions) == 0 {
		return []*swarming.SwarmingRpcsTaskSlice{s0}, nil
	}

	s1cmd := skylabWorkerCommand(taskName, clientTest, keyvals, annotationURL, provisionableDimensions, testArgs)
	s1Dims := basePairs
	s1 := taskSlice(s1cmd, s1Dims, timeoutMins)

	return []*swarming.SwarmingRpcsTaskSlice{s0, s1}, nil
}

// skylabWorkerCommand returns a commandline slice for skylab_swarming_worker, as it should
// be run on a bot.
//
// Note: provisionDimensions (if supplied) may be suppled with their "provisionable-" prefix,
// and this prefix will be tripped to turn them into provisionable labels.
func skylabWorkerCommand(taskName string, clientTest bool, keyvals map[string]string, annotationURL string,
	provisionDimensions []string, testArgs string) []string {
	cmd := []string{}
	cmd = append(cmd, "/opt/infra-tools/skylab_swarming_worker")
	cmd = append(cmd, "-task-name", taskName)
	if clientTest {
		cmd = append(cmd, "-client-test")
	}
	if len(keyvals) > 0 {
		keyvalsJSON, err := json.Marshal(keyvals)
		if err != nil {
			// keyvals is a string-to-string map, there should be no chance of an error here.
			panic(err)
		}
		cmd = append(cmd, "-keyvals", string(keyvalsJSON))
	}
	if annotationURL != "" {
		cmd = append(cmd, "-logdog-annotation-url", annotationURL)
	}
	if testArgs != "" {
		cmd = append(cmd, "-test-args", testArgs)
	}
	provisionableLabels := make([]string, len(provisionDimensions))
	for i, l := range provisionDimensions {
		provisionableLabels[i] = strings.TrimPrefix(l, "provisionable-")
	}
	if len(provisionableLabels) != 0 {
		cmd = append(cmd, "-provision-labels", strings.Join(provisionableLabels, ","))
	}
	return cmd
}
