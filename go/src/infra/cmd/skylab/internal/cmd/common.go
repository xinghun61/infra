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
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/golang/protobuf/jsonpb"
	"github.com/maruel/subcommands"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"
	lflag "go.chromium.org/luci/common/flag"

	"infra/cmd/skylab/internal/site"
	"infra/libs/skylab/common/errctx"
	"infra/libs/skylab/swarming"
)

const progName = "skylab"

var defaultTaskPriority = 140

var jsonPBMarshaller = &jsonpb.Marshaler{
	EmitDefaults: true,
}

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
	f.Var(lflag.RelativeTime{T: &rr.expire}, "expires-in", "Expire removal reason in `days`.")
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

type taskInfo struct {
	Name string `json:"task_name"`
	ID   string `json:"task_id"`
	URL  string `json:"task_url"`
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
func toPairs(dimensions []string) ([]*swarming_api.SwarmingRpcsStringPair, error) {
	pairs := make([]*swarming_api.SwarmingRpcsStringPair, len(dimensions))
	for i, d := range dimensions {
		k, v := strpair.Parse(d)
		if v == "" {
			return nil, fmt.Errorf("malformed dimension with key '%s' has no value", k)
		}
		pairs[i] = &swarming_api.SwarmingRpcsStringPair{Key: k, Value: v}
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

func prompt(s string) bool {
	fmt.Fprintf(os.Stderr, s)
	reader := bufio.NewReader(os.Stdin)
	answer, _ := reader.ReadString('\n')
	answer = strings.TrimSpace(answer)
	return answer == "y" || answer == "Y"
}

func maybeWithTimeout(ctx context.Context, timeoutMins int) (context.Context, func(error)) {
	if timeoutMins >= 0 {
		return errctx.WithTimeout(ctx, time.Duration(timeoutMins)*time.Minute,
			fmt.Errorf("timed out after %d minutes while waiting for task(s) to complete", timeoutMins))
	}
	return errctx.WithCancel(ctx)
}

// printTaskInfo displays a list of user-friendly list of tasks (with a given
// upper limit), with a header of the form "Found X tasks to <showText>:"
func printTaskInfo(results []*swarming_api.SwarmingRpcsTaskResult, showLimit int, showText string, siteEnv site.Environment) {
	fmt.Fprintln(os.Stderr, strings.Repeat("-", 80))
	fmt.Fprintf(os.Stderr, "Found %d tasks to %s:\n", len(results), showText)
	for i, r := range results {
		if i < showTaskLimit {
			fmt.Fprintf(os.Stderr, "%s\n", swarming.TaskURL(siteEnv.SwarmingService, r.TaskId))
		} else {
			break
		}
	}
	if len(results) > showTaskLimit {
		fmt.Fprintf(os.Stderr, "... and %d more tasks\n", len(results)-showTaskLimit)
	}
	fmt.Fprintln(os.Stderr, strings.Repeat("-", 80))
}
