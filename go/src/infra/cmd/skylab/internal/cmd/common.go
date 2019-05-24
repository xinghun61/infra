// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bufio"
	"context"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/retry"
	"go.chromium.org/luci/common/retry/transient"
	"google.golang.org/api/googleapi"

	"infra/cmd/skylab/internal/flagx"
	"infra/cmd/skylab/internal/site"
)

const progName = "skylab"

var defaultTaskPriority = 140

type commonFlags struct {
	debug bool
}

func (f *commonFlags) Register(fl *flag.FlagSet) {
	fl.BoolVar(&f.debug, "debug", false, "Enable debug output.")
}

func (f commonFlags) DebugLogger(a subcommands.Application) *log.Logger {
	out := ioutil.Discard
	if f.debug {
		out = a.GetErr()
	}
	return log.New(out, progName, log.LstdFlags|log.Lshortfile)
}

type envFlags struct {
	dev bool
}

func (f *envFlags) Register(fl *flag.FlagSet) {
	fl.BoolVar(&f.dev, "dev", false, "Run in dev environment.")
}

func (f envFlags) Env() site.Environment {
	if f.dev {
		return site.Dev
	}
	return site.Prod
}

type removalReason struct {
	bug     string
	comment string
	expire  time.Time
}

func (rr *removalReason) Register(f *flag.FlagSet) {
	f.StringVar(&rr.bug, "bug", "", "Bug link for why DUT is being removed.  Required.")
	f.StringVar(&rr.comment, "comment", "", "Short comment about why DUT is being removed.")
	f.Var(flagx.RelativeTime{T: &rr.expire}, "expires-in", "Expire removal reason in `days`.")
}

// httpClient returns an HTTP client with authentication set up.
func httpClient(ctx context.Context, f *authcli.Flags) (*http.Client, error) {
	o, err := f.Options()
	if err != nil {
		return nil, errors.Annotate(err, "failed to get auth options").Err()
	}
	a := auth.NewAuthenticator(ctx, auth.OptionalLogin, o)
	c, err := a.Client()
	if err != nil {
		return nil, errors.Annotate(err, "failed to create HTTP client").Err()
	}
	return c, nil
}

const swarmingAPISuffix = "_ah/api/swarming/v1/"

func newSwarmingService(ctx context.Context, auth authcli.Flags, env site.Environment) (*swarming.Service, error) {
	cl, err := httpClient(ctx, &auth)
	if err != nil {
		return nil, errors.Annotate(err, "create swarming client").Err()
	}

	s, err := swarming.New(cl)
	if err != nil {
		return nil, errors.Annotate(err, "create swarming client").Err()
	}

	s.BasePath = env.SwarmingService + swarmingAPISuffix
	return s, nil
}

type taskInfo struct {
	Name string `json:"task_name"`
	ID   string `json:"task_id"`
	URL  string `json:"task_url"`
}

func swarmingTaskURL(e site.Environment, taskID string) string {
	return fmt.Sprintf("%stask?id=%s", e.SwarmingService, taskID)
}

// UserErrorReporter reports a detailed error message to the user.
//
// PrintError() uses a UserErrorReporter to print multi-line user error details
// along with the actual error.
type UserErrorReporter interface {
	// Report a user-friendly error through w.
	ReportUserError(w io.Writer)
}

// PrintError reports errors back to the user.
//
// Detailed error information is printed if err is a UserErrorReporter.
func PrintError(w io.Writer, err error) {
	if u, ok := err.(UserErrorReporter); ok {
		u.ReportUserError(w)
	} else {
		fmt.Fprintf(w, "%s: %s\n", progName, err)
	}
}

// NewUsageError creates a new error that also reports flags usage error
// details.
func NewUsageError(flags flag.FlagSet, format string, a ...interface{}) error {
	return &usageError{
		error: fmt.Errorf(format, a...),
		flags: flags,
	}
}

type usageError struct {
	error
	flags flag.FlagSet
}

func (e *usageError) ReportUserError(w io.Writer) {
	fmt.Fprintf(w, "%s\n\nUsage:\n\n", e.error)
	e.flags.Usage()
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

// swarmingRetryableCodes defines error codes from swarming RPCs that are to be
// considered transient and retryable.
var swarmingRetryableCodes = map[int]bool{
	http.StatusInternalServerError: true, // 500
	http.StatusBadGateway:          true, // 502
	http.StatusServiceUnavailable:  true, // 503
	http.StatusGatewayTimeout:      true, // 504
	http.StatusInsufficientStorage: true, // 507
}

// swarmingRetryParams defines the retry strategy for handling transient errors
// from swarming RPCs.
func swarmingRetryParams() retry.Iterator {
	return &retry.ExponentialBackoff{
		Limited: retry.Limited{
			Delay:   500 * time.Millisecond,
			Retries: 5,
		},
		Multiplier: 2,
	}
}

// swarmingTagErrorIfTransient applies tags to swarming RPC errors that are
// transient and should be retried.
func swarmingTagErrorIfTransient(err error) error {
	if err == nil {
		return err
	}

	if e, ok := err.(net.Error); ok && e.Temporary() {
		return transient.Tag.Apply(err)
	}

	if e, ok := err.(*googleapi.Error); ok && swarmingRetryableCodes[e.Code] {
		return transient.Tag.Apply(err)
	}

	return err
}

// swarmingCallWithRetries calls the given function, retrying transient swarming
// errors, with swarming-appropriate backoff and delay.
func swarmingCallWithRetries(ctx context.Context, f func() error) error {
	taggedFunc := func() error {
		return swarmingTagErrorIfTransient(f())
	}
	return retry.Retry(ctx, transient.Only(swarmingRetryParams), taggedFunc, nil)
}

// swarmingCreateTaskWithRetries calls swarming's NewTaskRequest rpc, retrying
// transient errors.
func swarmingCreateTaskWithRetries(ctx context.Context, s *swarming.Service, req *swarming.SwarmingRpcsNewTaskRequest) (*swarming.SwarmingRpcsTaskRequestMetadata, error) {
	var resp *swarming.SwarmingRpcsTaskRequestMetadata
	createTask := func() error {
		var err error
		resp, err = s.Tasks.New(req).Context(ctx).Do()
		return err
	}

	if err := swarmingCallWithRetries(ctx, createTask); err != nil {
		return nil, err
	}
	return resp, nil
}

func getSwarmingResultsForIds(ctx context.Context, IDs []string, s *swarming.Service) ([]*swarming.SwarmingRpcsTaskResult, error) {
	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	results := make([]*swarming.SwarmingRpcsTaskResult, len(IDs))
	for i, ID := range IDs {
		var r *swarming.SwarmingRpcsTaskResult
		getResult := func() error {
			var err error
			r, err = s.Task.Result(ID).Context(ctx).Do()
			return err
		}
		if err := swarmingCallWithRetries(ctx, getResult); err != nil {
			return nil, errors.Annotate(err, fmt.Sprintf("get swarming result for task %s", ID)).Err()
		}
		results[i] = r
	}
	return results, nil
}

func getSwarmingResultsForTags(ctx context.Context, s *swarming.Service, tags []string) ([]*swarming.SwarmingRpcsTaskResult, error) {
	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	var results *swarming.SwarmingRpcsTaskList
	getResults := func() error {
		var err error
		results, err = s.Tasks.List().Tags(tags...).Context(ctx).Do()
		return err
	}
	if err := swarmingCallWithRetries(ctx, getResults); err != nil {
		return nil, errors.Annotate(err, fmt.Sprintf("get swarming result for tags %s", tags)).Err()
	}

	return results.Items, nil
}

func getSwarmingRequestsForIds(ctx context.Context, IDs []string, s *swarming.Service) ([]*swarming.SwarmingRpcsTaskRequest, error) {
	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	requests := make([]*swarming.SwarmingRpcsTaskRequest, len(IDs))
	for i, ID := range IDs {
		var request *swarming.SwarmingRpcsTaskRequest
		getRequest := func() error {
			var err error
			request, err = s.Task.Request(ID).Context(ctx).Do()
			return err
		}
		if err := swarmingCallWithRetries(ctx, getRequest); err != nil {
			return nil, errors.Annotate(err, fmt.Sprintf("rerun task %s", ID)).Err()
		}
		requests[i] = request
	}
	return requests, nil
}

func prompt(s string) bool {
	fmt.Fprintf(os.Stderr, s)
	reader := bufio.NewReader(os.Stdin)
	answer, _ := reader.ReadString('\n')
	answer = strings.TrimSpace(answer)
	return answer == "y" || answer == "Y"
}

// printTaskInfo displays a list of user-friendly list of tasks (with a given
// upper limit), with a header of the form "Found X tasks to <showText>:"
func printTaskInfo(results []*swarming.SwarmingRpcsTaskResult, showLimit int, showText string, siteEnv site.Environment) {
	fmt.Fprintln(os.Stderr, strings.Repeat("-", 80))
	fmt.Fprintf(os.Stderr, "Found %d tasks to %s:\n", len(results), showText)
	for i, r := range results {
		if i < showTaskLimit {
			fmt.Fprintf(os.Stderr, "%s\n", swarmingTaskURL(siteEnv, r.TaskId))
		} else {
			break
		}
	}
	if len(results) > showTaskLimit {
		fmt.Fprintf(os.Stderr, "... and %d more tasks\n", len(results)-showTaskLimit)
	}
	fmt.Fprintln(os.Stderr, strings.Repeat("-", 80))
}
