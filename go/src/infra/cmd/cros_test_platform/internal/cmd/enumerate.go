// Copyright 2098 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"

	"io/ioutil"
	"os"
	"path/filepath"

	"infra/cmd/cros_test_platform/internal/autotest/artifacts"
	"infra/cmd/cros_test_platform/internal/autotest/testspec"
	"infra/cmd/cros_test_platform/internal/enumeration"
	"infra/cmd/cros_test_platform/internal/site"

	"github.com/maruel/subcommands"
	"go.chromium.org/chromiumos/infra/proto/go/chromite/api"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/gcloud/gs"
)

// Enumerate is the `enumerate` subcommand implementation.
var Enumerate = &subcommands.Command{
	UsageLine: "enumerate -input_json /path/to/input.json -output_json /path/to/output.json",
	ShortDesc: "Enumerate tasks to execute for a request.",
	LongDesc: `Enumerate tasks to execute for a request.

Step input and output is JSON encoded protobuf defined at
https://chromium.googlesource.com/chromiumos/infra/proto/+/master/src/test_platform/steps/enumeration.proto`,
	CommandRun: func() subcommands.CommandRun {
		c := &enumerateRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.Flags.StringVar(&c.inputPath, "input_json", "", "Path that contains JSON encoded test_platform.steps.EnumerationRequest")
		c.Flags.StringVar(&c.outputPath, "output_json", "", "Path where JSON encoded test_platform.steps.EnumerationResponse should be written.")
		c.Flags.BoolVar(&c.multiRequest, "multi_request", false, "If true, handle multiple requests at once (transitional flag: crbug.com/1008135).")
		return c
	},
}

type enumerateRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags

	inputPath    string
	outputPath   string
	multiRequest bool
}

func (c *enumerateRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	err := c.innerRun(a, args, env)
	if err != nil {
		fmt.Fprintf(a.GetErr(), "%s\n", err)
	}
	return exitCode(err)
}

func (c *enumerateRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if err := c.processCLIArgs(args); err != nil {
		return err
	}
	ctx := cli.GetContext(a, c, env)
	ctx = setupLogging(ctx)

	requests, err := c.readRequests()
	if err != nil {
		return err
	}
	if len(requests) == 0 {
		return errors.Reason("zero requests").Err()
	}
	gsPath, err := c.gsPath(requests)
	if err != nil {
		return err
	}

	workspace, err := ioutil.TempDir("", "enumerate")
	if err != nil {
		return err
	}
	defer func() {
		os.RemoveAll(workspace)
	}()
	lp, err := c.downloadArtifacts(ctx, gsPath, workspace)
	if err != nil {
		return err
	}

	tm, writableErr := computeMetadata(lp, workspace)
	if writableErr != nil && tm == nil {
		// Catastrophic error. There is no reasonable response to write.
		return writableErr
	}

	resps := make([]*steps.EnumerationResponse, len(requests))
	merr := errors.NewMultiError()
	for i, r := range requests {
		if ts, err := c.enumerate(tm, r); err != nil {
			merr = append(merr, err)
		} else {
			resps[i] = &steps.EnumerationResponse{AutotestInvocations: ts}
		}
	}
	if merr.First() != nil {
		return merr
	}
	return c.writeResponseWithError(resps, writableErr)
}

func (c *enumerateRun) processCLIArgs(args []string) error {
	if len(args) > 0 {
		return errors.Reason("have %d positional args, want 0", len(args)).Err()
	}
	if c.inputPath == "" {
		return errors.Reason("-input_json not specified").Err()
	}
	if c.outputPath == "" {
		return errors.Reason("-output_json not specified").Err()
	}
	return nil
}

func (c *enumerateRun) readRequests() ([]*steps.EnumerationRequest, error) {
	if c.multiRequest {
		rs, err := c.readMultiRequest()
		if err != nil {
			return nil, err
		}
		return rs.Requests, nil
	}
	r, err := c.readSingleRequest()
	if err != nil {
		return nil, err
	}
	return []*steps.EnumerationRequest{r}, nil
}

func (c *enumerateRun) writeResponseWithError(resps []*steps.EnumerationResponse, err error) error {
	if c.multiRequest {
		return writeResponseWithError(
			c.outputPath,
			&steps.EnumerationResponses{
				Responses: resps,
			},
			err,
		)
	}
	if len(resps) > 1 {
		panic(fmt.Sprintf("multiple responses without -multi_request: %s", resps))
	}
	return writeResponseWithError(c.outputPath, resps[0], err)
}

func (c *enumerateRun) readMultiRequest() (*steps.EnumerationRequests, error) {
	var requests steps.EnumerationRequests
	if err := readRequest(c.inputPath, &requests); err != nil {
		return nil, err
	}
	return &requests, nil
}

func (c *enumerateRun) readSingleRequest() (*steps.EnumerationRequest, error) {
	var request steps.EnumerationRequest
	if err := readRequest(c.inputPath, &request); err != nil {
		return nil, err
	}
	return &request, nil
}

func (c *enumerateRun) gsPath(requests []*steps.EnumerationRequest) (gs.Path, error) {
	if len(requests) == 0 {
		panic("zero requests")
	}

	m := requests[0].GetMetadata().GetTestMetadataUrl()
	if m == "" {
		return "", errors.Reason("empty request.metadata.test_metadata_url in %s", requests[0]).Err()
	}
	for _, r := range requests[1:] {
		o := r.GetMetadata().GetTestMetadataUrl()
		if o != m {
			return "", errors.Reason("mismatched test metadata URLs: %s vs %s", m, o).Err()
		}
	}
	return gs.Path(m), nil
}

func (c *enumerateRun) downloadArtifacts(ctx context.Context, gsDir gs.Path, workspace string) (artifacts.LocalPaths, error) {
	outDir := filepath.Join(workspace, "artifacts")
	if err := os.Mkdir(outDir, 0750); err != nil {
		return artifacts.LocalPaths{}, errors.Annotate(err, "download artifacts").Err()
	}
	client, err := c.newGSClient(ctx)
	if err != nil {
		return artifacts.LocalPaths{}, errors.Annotate(err, "download artifacts").Err()
	}
	lp, err := artifacts.DownloadFromGoogleStorage(ctx, client, gsDir, outDir)
	if err != nil {
		return artifacts.LocalPaths{}, errors.Annotate(err, "download artifacts").Err()
	}
	return lp, err
}

func (c *enumerateRun) newGSClient(ctx context.Context) (gs.Client, error) {
	t, err := newAuthenticatedTransport(ctx, &c.authFlags)
	if err != nil {
		return nil, errors.Annotate(err, "create GS client").Err()
	}
	return gs.NewProdClient(ctx, t)
}

func (c *enumerateRun) enumerate(tm *api.TestMetadataResponse, request *steps.EnumerationRequest) ([]*steps.EnumerationResponse_AutotestInvocation, error) {
	var ts []*steps.EnumerationResponse_AutotestInvocation

	g, err := enumeration.GetForTests(tm.Autotest, request.TestPlan.Test)
	if err != nil {
		return nil, err
	}
	ts = append(ts, g...)

	ts = append(ts, enumeration.GetForSuites(tm.Autotest, request.TestPlan.Suite)...)
	ts = append(ts, enumeration.GetForEnumeration(request.TestPlan.GetEnumeration())...)
	return ts, nil
}

func computeMetadata(localPaths artifacts.LocalPaths, workspace string) (*api.TestMetadataResponse, error) {
	extracted := filepath.Join(workspace, "extracted")
	if err := os.Mkdir(extracted, 0750); err != nil {
		return nil, errors.Annotate(err, "compute metadata").Err()
	}
	if err := artifacts.ExtractControlFiles(localPaths, extracted); err != nil {
		return nil, errors.Annotate(err, "compute metadata").Err()
	}
	return testspec.Get(extracted)
}
