// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"sort"
	"time"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"
	"google.golang.org/api/googleapi"

	"infra/cmd/skylab/internal/flagx"
	"infra/cmd/skylab/internal/site"
)

const progName = "skylab"

type taskPriority struct {
	name  string
	level int
}

var taskPriorityMap = map[string]int{
	"Weekly":    230,
	"CTS":       215,
	"Daily":     200,
	"PostBuild": 170,
	"Default":   140,
	"Build":     110,
	"PFQ":       80,
	"CQ":        50,
	"Super":     49,
}
var defaultTaskPriorityKey = "Default"
var defaultTaskPriority = taskPriorityMap[defaultTaskPriorityKey]

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

func sortedPriorities() []taskPriority {
	s := make([]taskPriority, 0, len(taskPriorityMap))
	for k, v := range taskPriorityMap {
		s = append(s, taskPriority{k, v})
	}

	sort.Slice(s, func(i, j int) bool {
		return s[i].level < s[j].level
	})
	return s
}

func sortedPriorityKeys() []string {
	sp := sortedPriorities()
	k := make([]string, 0, len(sp))
	for _, p := range sp {
		k = append(k, p.name)
	}
	return k
}

var retryableCodes = map[int]bool{
	http.StatusInternalServerError: true, // 500
	http.StatusBadGateway:          true, // 502
	http.StatusServiceUnavailable:  true, // 503
	http.StatusGatewayTimeout:      true, // 504
	http.StatusInsufficientStorage: true, // 507
}

// withGoogleAPIRetries calls a function, retrying calls that return
// a retryable googleapi.Error error code.
//
// The function is retried up to maxAttempts times, or until the supplied
// context expires.
//
// If any attempt returns a non-retryable error or a non-googleapi error,
// then that error is returned.
//
// If the final attempt returns an error, then that error is returned.
//
// TODO(akeshet): Don't roll our own retry function if we can avoid it. Or, if
// we really must roll our own, add exponential backoff to it.
func withGoogleAPIRetries(ctx context.Context, maxAttempts int, f func() error) error {
	if maxAttempts < 1 {
		panic("maxAttempts must be >1")
	}
	var err error
	for i := 0; i < maxAttempts; i++ {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		err = f()
		if err == nil {
			return nil
		}
		apiErr, ok := err.(*googleapi.Error)
		if !ok {
			return err
		}
		if retryableCodes[apiErr.Code] {
			return err
		}
	}
	return err
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
	if err := withGoogleAPIRetries(ctx, 5, createTask); err != nil {
		return nil, err
	}
	return resp, nil
}
