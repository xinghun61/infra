// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"fmt"
	"net/url"
	"os/exec"
	"strings"

	"golang.org/x/net/context"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/isolatedclient"
	"go.chromium.org/luci/common/logging"
)

func logCmd(ctx context.Context, arg0 string, args ...string) *exec.Cmd {
	ret := exec.CommandContext(ctx, arg0, args...)
	logging.Debugf(ctx, "Running - %s %v", arg0, args)
	return ret
}

func cmdErr(err error, reason string) error {
	if err != nil {
		ee, _ := err.(*exec.ExitError)
		outErr := ""
		if ee != nil {
			outErr = strings.TrimSpace(string(ee.Stderr))
			if len(outErr) > 128 {
				outErr = outErr[:128] + "..."
			}
		}
		err = errors.Annotate(err, reason+": %s", outErr).Err()
	}
	return err
}

func getIsolatedFlags(s *swarming.Service) (isolatedclient.Flags, error) {
	details, err := s.Server.Details().Do()
	if err != nil {
		return isolatedclient.Flags{}, err
	}
	return isolatedclient.Flags{
		ServerURL: details.DefaultIsolateServer,
		Namespace: details.DefaultIsolateNamespace,
	}, nil
}

// validateHost returns an error iff `host` is not, precisely, a hostname.
func validateHost(host string) error {
	// assume that host is a bare host. This means that we can add a scheme,
	// user/pass, a port, and a path to it, and then parsing it and retrieving
	// 'Hostname' should equal the original string.
	p, err := url.Parse(fmt.Sprintf("https://user:pass@%s:100/path", host))
	if err != nil {
		return errors.Annotate(err, "bad url %q", host).Err()
	}
	if p.Scheme != "https" || p.Port() != "100" || p.Path != "/path" || p.User.String() != "user:pass" || p.Hostname() != host {
		return errors.Reason("must only specify hostname: %q", host).Err()
	}
	return nil
}
