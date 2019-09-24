// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package skylab

import (
	"bytes"
	"context"
	"fmt"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_test_runner"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/isolated"
	"go.chromium.org/luci/common/logging"

	"github.com/golang/protobuf/jsonpb"

	"infra/cmd/cros_test_platform/internal/execution/isolate"
	"infra/cmd/cros_test_platform/internal/execution/swarming"
)

const resultsFileName = "results.json"

func getAutotestResult(ctx context.Context, sResult *swarming_api.SwarmingRpcsTaskResult, gf isolate.GetterFactory) (*skylab_test_runner.Result_Autotest, error) {
	if sResult == nil {
		return nil, errors.Reason("get result: nil swarming result").Err()
	}

	taskID := sResult.TaskId
	outputRef := sResult.OutputsRef
	if outputRef == nil {
		logging.Debugf(ctx, "task %s has no output ref, considering it failed due to incompleteness", taskID)
		return &skylab_test_runner.Result_Autotest{Incomplete: true}, nil
	}

	getter, err := gf(ctx, outputRef.Isolatedserver)
	if err != nil {
		return nil, errors.Annotate(err, "get result").Err()
	}

	logging.Debugf(ctx, "fetching result for task %s from isolate ref %+v", taskID, outputRef)
	content, err := getter.GetFile(ctx, isolated.HexDigest(outputRef.Isolated), resultsFileName)
	if err != nil {
		return nil, errors.Annotate(err, "get result for task %s", taskID).Err()
	}

	var result skylab_test_runner.Result

	err = jsonpb.Unmarshal(bytes.NewReader(content), &result)
	if err != nil {
		return nil, errors.Annotate(err, "get result for task %s", taskID).Err()
	}

	a := result.GetAutotestResult()
	if a == nil {
		return nil, errors.Reason("get result for task %s: no autotest result; other harnesses not yet supported", taskID).Err()
	}

	return a, nil
}

func toTaskResult(testName string, attempt *attempt, attemptNum int, urler swarming.URLer) *steps.ExecuteResponse_TaskResult {
	// TODO(akeshet): Determine this URL in a more principled way. See crbug.com/987487
	// for context.
	logURL := fmt.Sprintf(
		"https://stainless.corp.google.com/browse/chromeos-autotest-results/swarming-%s/",
		attempt.taskID,
	)

	return &steps.ExecuteResponse_TaskResult{
		Name: testName,
		State: &test_platform.TaskState{
			LifeCycle: taskStateToLifeCycle[attempt.state],
			Verdict:   attempt.Verdict(),
		},
		TaskUrl: urler.GetTaskURL(attempt.taskID),
		LogUrl:  logURL,
		Attempt: int32(attemptNum),
	}
}
