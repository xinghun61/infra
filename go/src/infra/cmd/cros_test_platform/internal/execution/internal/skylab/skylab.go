// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package skylab implements logic necessary for Skylab execution of an
// ExecuteRequest.
package skylab

import (
	"context"
	"time"

	"github.com/golang/protobuf/ptypes"

	build_api "go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/config"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_test_runner"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/swarming/proto/jsonrpc"

	"infra/cmd/cros_test_platform/internal/execution/internal/common"
	"infra/cmd/cros_test_platform/internal/execution/isolate"
	"infra/cmd/cros_test_platform/internal/execution/swarming"
	"infra/libs/skylab/inventory"
	"infra/libs/skylab/inventory/autotest/labels"
	"infra/libs/skylab/request"
	"infra/libs/skylab/worker"
)

// TaskSet encapsulates the running state of a set of tasks, to satisfy
// a Skylab Execution.
type TaskSet struct {
	testRuns     []*testRun
	params       *test_platform.Request_Params
	workerConfig *config.Config_SkylabWorker
	retries      int32
	// complete indicates that the TaskSet ran to completion of all tasks.
	complete bool
	// running indicates that the TaskSet is still running.
	running bool
}

type testRun struct {
	test     *build_api.AutotestTest
	attempts []*attempt
}

func (t *testRun) RequestArgs(params *test_platform.Request_Params, workerConfig *config.Config_SkylabWorker) (request.Args, error) {
	isClient, err := t.isClientTest()
	if err != nil {
		return request.Args{}, errors.Annotate(err, "create request args").Err()
	}

	provisionableDimensions, err := toProvisionableDimensions(params.SoftwareDependencies)
	if err != nil {
		return request.Args{}, errors.Annotate(err, "create request args").Err()
	}

	timeout, err := toTimeout(params)
	if err != nil {
		return request.Args{}, errors.Annotate(err, "create request args").Err()
	}

	cmd := &worker.Command{
		TaskName:        t.test.Name,
		ClientTest:      isClient,
		OutputToIsolate: true,
	}
	cmd.Config(wrap(workerConfig))

	labels, err := toInventoryLabels(params, t.test.Dependencies)
	if err != nil {
		return request.Args{}, errors.Annotate(err, "create request args").Err()
	}

	args := request.Args{
		Cmd:               *cmd,
		SchedulableLabels: *labels,
		// TODO(akeshet): Determine parent task ID correctly.
		ParentTaskID: "",
		// TODO(akeshet): Determine priority correctly.
		Priority:                0,
		ProvisionableDimensions: provisionableDimensions,
		SwarmingTags:            swarmingTags(cmd, workerConfig, params),
		Timeout:                 timeout,
	}

	return args, nil
}

func (t *testRun) isClientTest() (bool, error) {
	isClient, ok := isClientTest[t.test.ExecutionEnvironment]
	if !ok {
		return false, errors.Reason("unknown exec environment %s", t.test.ExecutionEnvironment).Err()
	}
	return isClient, nil
}

func swarmingTags(cmd *worker.Command, conf *config.Config_SkylabWorker, params *test_platform.Request_Params) []string {
	tags := []string{
		"luci_project:" + conf.LuciProject,
		"log_location:" + cmd.LogDogAnnotationURL,
	}
	if qa := params.GetScheduling().GetQuotaAccount(); qa != "" {
		tags = append(tags, "qs_account:"+qa)
	}
	return tags
}

type attempt struct {
	taskID string
	state  jsonrpc.TaskState
	// Note: If we ever begin supporting other harnesses's result formats
	// then this field will change to a *skylab_test_runner.Result.
	// For now, the autotest-specific variant is more convenient.
	autotestResult *skylab_test_runner.Result_Autotest
}

func (a *attempt) complete() bool {
	return a.autotestResult != nil
}

// NewTaskSet creates a new TaskSet.
func NewTaskSet(tests []*build_api.AutotestTest, params *test_platform.Request_Params, workerConfig *config.Config_SkylabWorker) *TaskSet {
	testRuns := make([]*testRun, len(tests))
	for i, test := range tests {
		testRuns[i] = &testRun{test: test}
	}
	return &TaskSet{
		testRuns:     testRuns,
		params:       params,
		workerConfig: workerConfig,
		running:      true,
	}
}

// LaunchAndWait launches a skylab execution and waits for it to complete,
// polling for new results periodically (TODO(akeshet): and retrying tests that
// need retry, based on retry policy).
//
// If the supplied context is cancelled prior to completion, or some other error
// is encountered, this method returns whatever partial execution response
// was visible to it prior to that error.
func (r *TaskSet) LaunchAndWait(ctx context.Context, swarming swarming.Client, gf isolate.GetterFactory) error {
	defer func() { r.running = false }()

	if err := r.launchAll(ctx, swarming); err != nil {
		return err
	}

	return r.wait(ctx, swarming, gf)
}

var isClientTest = map[build_api.AutotestTest_ExecutionEnvironment]bool{
	build_api.AutotestTest_EXECUTION_ENVIRONMENT_CLIENT: true,
	build_api.AutotestTest_EXECUTION_ENVIRONMENT_SERVER: false,
}

func (r *TaskSet) launchAll(ctx context.Context, swarming swarming.Client) error {
	for _, testRun := range r.testRuns {
		if err := r.launchSingle(ctx, swarming, testRun); err != nil {
			return err
		}
	}
	return nil
}

func (r *TaskSet) launchSingle(ctx context.Context, swarming swarming.Client, testRun *testRun) error {
	args, err := testRun.RequestArgs(r.params, r.workerConfig)
	if err != nil {
		return errors.Annotate(err, "launch test named %s", testRun.test.Name).Err()
	}

	req, err := request.New(args)
	if err != nil {
		return errors.Annotate(err, "launch test named %s", testRun.test.Name).Err()
	}

	resp, err := swarming.CreateTask(ctx, req)
	if err != nil {
		return errors.Annotate(err, "launch test named %s", testRun.test.Name).Err()
	}

	logging.Infof(ctx, "Launched test named %s as task %s", testRun.test.Name, swarming.GetTaskURL(resp.TaskId))

	testRun.attempts = append(testRun.attempts, &attempt{taskID: resp.TaskId})
	return nil
}

func (r *TaskSet) wait(ctx context.Context, swarming swarming.Client, gf isolate.GetterFactory) error {
	for {
		complete, err := r.tick(ctx, swarming, gf)
		if complete || err != nil {
			r.complete = complete
			return err
		}

		select {
		case <-ctx.Done():
			return errors.Annotate(ctx.Err(), "wait for tests").Err()
		case <-clock.After(ctx, 15*time.Second):
		}
	}
}

func (r *TaskSet) tick(ctx context.Context, client swarming.Client, gf isolate.GetterFactory) (complete bool, err error) {
	complete = true

	for _, testRun := range r.testRuns {
		latestAttempt := testRun.attempts[len(testRun.attempts)-1]
		if latestAttempt.complete() {
			continue
		}

		if err := r.fetchResults(ctx, latestAttempt, client, gf); err != nil {
			return false, errors.Annotate(err, "tick for task %s", latestAttempt.taskID).Err()
		}

		if !latestAttempt.complete() {
			complete = false
			continue
		}

		shouldRetry, err := r.shouldRetry(testRun)
		if err != nil {
			return false, errors.Annotate(err, "tick for task %s", latestAttempt.taskID).Err()
		}
		if shouldRetry {
			complete = false
			logging.Debugf(ctx, "retrying test %s", testRun.test.Name)
			if err := r.launchSingle(ctx, client, testRun); err != nil {
				return false, errors.Annotate(err, "tick for task %s: retry test", latestAttempt.taskID).Err()
			}
			r.retries++
		}
	}

	return complete, nil
}

// fetchResults fetches the latest swarming and isolate state of the given attempt,
// and updates the attempt accordingly.
func (r *TaskSet) fetchResults(ctx context.Context, a *attempt, client swarming.Client, gf isolate.GetterFactory) error {
	results, err := client.GetResults(ctx, []string{a.taskID})
	if err != nil {
		return errors.Annotate(err, "fetch results").Err()
	}

	result, err := unpackResult(results, a.taskID)
	if err != nil {
		return errors.Annotate(err, "fetch results").Err()
	}

	state, err := swarming.AsTaskState(result.State)
	if err != nil {
		return errors.Annotate(err, "fetch results").Err()
	}
	a.state = state

	switch {
	// Task ran to completion.
	case swarming.CompletedTaskStates[state]:
		r, err := getAutotestResult(ctx, result, gf)
		if err != nil {
			return errors.Annotate(err, "fetch results").Err()
		}
		a.autotestResult = r
	// Task no longer running, but didn't run to completion.
	case !swarming.UnfinishedTaskStates[state]:
		a.autotestResult = &skylab_test_runner.Result_Autotest{Incomplete: true}
	// Task is still running.
	default:
	}

	return nil
}

// shouldRetry computes if the given testRun should be retried.
//
// This will panic if the testRun has never been launched.
func (r *TaskSet) shouldRetry(testRun *testRun) (bool, error) {
	if r.params.Retry == nil {
		return false, nil
	}
	if !r.params.Retry.Allow {
		return false, nil
	}
	max := r.params.Retry.Max
	if max != 0 && r.retries >= max {
		return false, nil
	}
	if !testRun.test.AllowRetries {
		return false, nil
	}
	attempts := len(testRun.attempts)
	if attempts < 1 {
		return false, errors.Reason("should retry: can't retry a never-tried test").Err()
	}
	// Allow up to MaxRetries + 1 total attempts of a given test.
	if attempts > int(testRun.test.MaxRetries) {
		return false, nil
	}
	latestAttempt := testRun.attempts[attempts-1]
	switch verdict := flattenToVerdict(latestAttempt.autotestResult.GetTestCases()); verdict {
	case test_platform.TaskState_VERDICT_UNSPECIFIED:
		fallthrough
	case test_platform.TaskState_VERDICT_FAILED:
		return true, nil
	case test_platform.TaskState_VERDICT_NO_VERDICT:
		fallthrough
	case test_platform.TaskState_VERDICT_PASSED:
		return false, nil
	default:
		return false, errors.Reason("should retry: unknown verdict %s", verdict.String()).Err()
	}
}

func toInventoryLabels(params *test_platform.Request_Params, deps []*build_api.AutotestTaskDependency) (*inventory.SchedulableLabels, error) {
	flatDims := make([]string, len(deps))
	for i, dep := range deps {
		flatDims[i] = dep.Label
	}

	inv := labels.Revert(flatDims)

	if params.SoftwareAttributes.BuildTarget != nil {
		inv.Board = &params.SoftwareAttributes.BuildTarget.Name
	}
	if params.HardwareAttributes.Model != "" {
		inv.Model = &params.HardwareAttributes.Model
	}

	switch v := params.GetScheduling().GetPool().(type) {
	case *test_platform.Request_Params_Scheduling_ManagedPool_:
		pool, ok := poolMap[v.ManagedPool]
		if !ok {
			return nil, errors.Reason("unknown managed pool %s", v.ManagedPool.String()).Err()
		}
		inv.CriticalPools = append(inv.CriticalPools, pool)
	case *test_platform.Request_Params_Scheduling_UnmanagedPool:
		inv.SelfServePools = append(inv.SelfServePools, v.UnmanagedPool)
	case *test_platform.Request_Params_Scheduling_QuotaAccount:
		inv.CriticalPools = append(inv.CriticalPools, inventory.SchedulableLabels_DUT_POOL_QUOTA)
		// TODO(akeshet): In this case, we need to set the quota account correctly.
	}

	return inv, nil
}

const (
	// These prefixes are interpreted by autotest's provisioning behavior;
	// they are defined in the autotest repo, at utils/labellib.py
	prefixChromeOS   = "cros-version"
	prefixFirmwareRO = "fwro-version"
	prefixFirmwareRW = "fwrw-version"
)

func toProvisionableDimensions(deps []*test_platform.Request_Params_SoftwareDependency) ([]string, error) {
	builds, err := common.ExtractBuilds(deps)
	if err != nil {
		return nil, errors.Annotate(err, "get provisionable dimensions").Err()
	}

	var dims []string
	if b := builds.ChromeOS; b != "" {
		dims = append(dims, "provisionable-"+prefixChromeOS+":"+b)
	}
	if b := builds.FirmwareRO; b != "" {
		dims = append(dims, "provisionable-"+prefixFirmwareRO+":"+b)
	}
	if b := builds.FirmwareRW; b != "" {
		dims = append(dims, "provisionable-"+prefixFirmwareRW+":"+b)
	}

	return dims, nil
}

func toTimeout(params *test_platform.Request_Params) (time.Duration, error) {
	if params.Time == nil {
		return 0, errors.Reason("get timeout: nil params.time").Err()
	}
	duration, err := ptypes.Duration(params.Time.MaximumDuration)
	if err != nil {
		return 0, errors.Annotate(err, "get timeout").Err()
	}
	return duration, nil
}

func unpackResult(results []*swarming_api.SwarmingRpcsTaskResult, taskID string) (*swarming_api.SwarmingRpcsTaskResult, error) {
	if len(results) != 1 {
		return nil, errors.Reason("expected 1 result for task id %s, got %d", taskID, len(results)).Err()
	}

	result := results[0]
	if result.TaskId != taskID {
		return nil, errors.Reason("expected result for task id %s, got %s", taskID, result.TaskId).Err()
	}

	return result, nil
}

var poolMap = map[test_platform.Request_Params_Scheduling_ManagedPool]inventory.SchedulableLabels_DUTPool{
	test_platform.Request_Params_Scheduling_MANAGED_POOL_ARC_PRESUBMIT: inventory.SchedulableLabels_DUT_POOL_ARC_PRESUBMIT,
	test_platform.Request_Params_Scheduling_MANAGED_POOL_BVT:           inventory.SchedulableLabels_DUT_POOL_BVT,
	test_platform.Request_Params_Scheduling_MANAGED_POOL_CONTINUOUS:    inventory.SchedulableLabels_DUT_POOL_CONTINUOUS,
	test_platform.Request_Params_Scheduling_MANAGED_POOL_CQ:            inventory.SchedulableLabels_DUT_POOL_CQ,
	test_platform.Request_Params_Scheduling_MANAGED_POOL_CTS_PERBUILD:  inventory.SchedulableLabels_DUT_POOL_CTS_PERBUILD,
	test_platform.Request_Params_Scheduling_MANAGED_POOL_CTS:           inventory.SchedulableLabels_DUT_POOL_CTS,
	// TODO(akeshet): This mapping is inexact. Requests that specify a quota account should not
	// specify a pool, and should go routed to the quota pool automatically.
	test_platform.Request_Params_Scheduling_MANAGED_POOL_QUOTA:  inventory.SchedulableLabels_DUT_POOL_QUOTA,
	test_platform.Request_Params_Scheduling_MANAGED_POOL_SUITES: inventory.SchedulableLabels_DUT_POOL_SUITES,
}

var taskStateToLifeCycle = map[jsonrpc.TaskState]test_platform.TaskState_LifeCycle{
	jsonrpc.TaskState_BOT_DIED:  test_platform.TaskState_LIFE_CYCLE_ABORTED,
	jsonrpc.TaskState_CANCELED:  test_platform.TaskState_LIFE_CYCLE_CANCELLED,
	jsonrpc.TaskState_COMPLETED: test_platform.TaskState_LIFE_CYCLE_COMPLETED,
	// TODO(akeshet): This mapping is inexact. Add a lifecycle entry for this.
	jsonrpc.TaskState_EXPIRED:     test_platform.TaskState_LIFE_CYCLE_CANCELLED,
	jsonrpc.TaskState_KILLED:      test_platform.TaskState_LIFE_CYCLE_ABORTED,
	jsonrpc.TaskState_NO_RESOURCE: test_platform.TaskState_LIFE_CYCLE_REJECTED,
	jsonrpc.TaskState_PENDING:     test_platform.TaskState_LIFE_CYCLE_PENDING,
	jsonrpc.TaskState_RUNNING:     test_platform.TaskState_LIFE_CYCLE_RUNNING,
	// TODO(akeshet): This mapping is inexact. Add a lifecycle entry for this.
	jsonrpc.TaskState_TIMED_OUT: test_platform.TaskState_LIFE_CYCLE_ABORTED,
}

// Response constructs a response based on the current state of the
// TaskSet.
func (r *TaskSet) Response(swarming swarming.URLer) *steps.ExecuteResponse {
	resp := &steps.ExecuteResponse{}
	resp.TaskResults = toTaskResults(r.testRuns, swarming)

	var verdict test_platform.TaskState_Verdict
	var lifecycle test_platform.TaskState_LifeCycle

	switch {
	case r.complete:
		// The default verdict for a completed TaskSet is passed; if any tasks
		// failed, they will overwrite this below.
		verdict = test_platform.TaskState_VERDICT_PASSED
		lifecycle = test_platform.TaskState_LIFE_CYCLE_COMPLETED
	case r.running:
		lifecycle = test_platform.TaskState_LIFE_CYCLE_RUNNING
	default:
		// TODO(akeshet): The task set is neither running nor complete, so it
		// was cancelled due to an error while in flight. It's not clear yet
		// if this is the right lifecycle mapping for this state.
		lifecycle = test_platform.TaskState_LIFE_CYCLE_ABORTED
	}

	for _, t := range resp.TaskResults {
		switch t.State.Verdict {
		case test_platform.TaskState_VERDICT_UNSPECIFIED:
			fallthrough
		case test_platform.TaskState_VERDICT_FAILED:
			verdict = test_platform.TaskState_VERDICT_FAILED
			break
		}
	}

	resp.State = &test_platform.TaskState{
		Verdict:   verdict,
		LifeCycle: lifecycle,
	}

	return resp
}
