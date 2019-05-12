// Copyright 2019 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package config

import (
	"regexp"
	"time"

	"net/mail"
	"net/url"

	"github.com/golang/protobuf/proto"
	"github.com/golang/protobuf/ptypes"

	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/config/validation"
)

const (
	// The regex rule that all assigner IDs must conform to.
	assignerIDRegex   = `^([a-z0-9]+-?)*[a-z0-9]$`
	rotationNameRegex = `^([[:alnum:]][[:word:]- ]?)*[[:alnum:]]$`
)

func validateConfig(c *validation.Context, configSet, path string, content []byte) error {
	cfg := &Config{}
	if err := proto.UnmarshalText(string(content), cfg); err != nil {
		c.Errorf("not a valid Config proto message: %s", err)
		return nil
	}

	validateAccessGroup(c, cfg.AccessGroup)
	validateMonorailHostname(c, cfg.MonorailHostname)
	validateAssigners(c, cfg.Assigners)
	validateRotangHostname(c, cfg.RotangHostname)
	return nil
}

func validateAccessGroup(c *validation.Context, group string) {
	c.Enter("access_group: %s", group)
	if group == "" {
		c.Errorf("empty value is not allowed")
	}
	c.Exit()
}

func validateMonorailHostname(c *validation.Context, hostname string) {
	c.Enter("monorail_hostname")
	if hostname == "" {
		c.Errorf("empty value is not allowed")
	} else if _, err := url.Parse(hostname); err != nil {
		c.Errorf("invalid hostname: %s", hostname)
	}
	c.Exit()
}

func validateRotangHostname(c *validation.Context, hostname string) {
	c.Enter("rotang_hostname")
	if hostname == "" {
		c.Errorf("empty value is not allowed")
	} else if _, err := url.Parse(hostname); err != nil {
		c.Errorf("invalid hostname: %s", hostname)
	}
	c.Exit()
}

func validateAssigners(c *validation.Context, assigners []*Assigner) {
	// check duplicate IDs.
	seen := stringset.New(len(assigners))
	for i, assigner := range assigners {
		c.Enter("assigner #%d:%s", i+1, assigner.Id)
		if !seen.Add(assigner.Id) {
			c.Errorf("duplicate id")
		}
		validateAssigner(c, assigner)
		c.Exit()
	}
}

func validateAssigner(c *validation.Context, assigner *Assigner) {
	// to make URLs short and simple when they are made with assigner ids.
	re := regexp.MustCompile(assignerIDRegex)
	if !re.MatchString(assigner.Id) {
		c.Errorf(
			"invalid id; only lowercase alphabet letters and numbers are " +
				"allowed. A hyphen may be placed between letters and numbers",
		)
	}

	// owners should be all valid email addresses.
	for _, owner := range assigner.Owners {
		c.Enter("owner %q", owner)
		if _, err := mail.ParseAddress(owner); err != nil {
			c.Errorf("invalid email address: %s", err)
		}
		c.Exit()
	}

	if assigner.Interval == nil {
		c.Errorf("missing interval")
	} else {
		d, err := ptypes.Duration(assigner.Interval)
		if err != nil {
			c.Errorf("invalid interval: %s", err)
		} else if d < time.Minute {
			c.Errorf("interval should be at least one minute")
		}
	}

	if assigner.IssueQuery == nil {
		c.Errorf("missing issue_query")
	} else {
		c.Enter("issue_query")
		if assigner.IssueQuery.Q == "" {
			c.Errorf("missing q")
		}
		if len(assigner.IssueQuery.ProjectNames) == 0 {
			c.Errorf("missing project_names")
		}
		c.Exit()
	}

	if len(assigner.Assignees) == 0 {
		c.Errorf("missing assignees")
	}
	for i, source := range assigner.Assignees {
		c.Enter("assignee %d", i+1)
		validateUserSource(c, source)
		c.Exit()
	}
	for i, source := range assigner.Ccs {
		c.Enter("cc %d", i+1)
		validateUserSource(c, source)
		c.Exit()
	}
}

func validateUserSource(c *validation.Context, source *UserSource) {
	if oncall := source.GetOncall(); oncall != nil {
		validateOncall(c, oncall)
	} else if email := source.GetEmail(); email != "" {
		validateEmail(c, email)
	} else {
		c.Errorf("missing value")
	}
}

func validateOncall(c *validation.Context, oncall *Oncall) {
	re := regexp.MustCompile(rotationNameRegex)
	if !re.MatchString(oncall.Rotation) {
		c.Errorf(
			"invalid id; only alphabet and numeric characters are allowed, " +
				"but a space, hyphen, or underscore may be put between " +
				"the first and last characters.",
		)
	}
	if oncall.Position == Oncall_UNSET {
		c.Errorf("missing oncall position")
	}
}

func validateEmail(c *validation.Context, email string) {
	// All Monorail users should be valid email addresses.
	if _, err := mail.ParseAddress(email); err != nil {
		c.Errorf("invalid email: %s", err)
	}
}
