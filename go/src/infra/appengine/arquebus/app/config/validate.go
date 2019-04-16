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
	assignerIDRegex = `^([a-z0-9]+-?)*[a-z0-9]$`
)

func validateConfig(c *validation.Context, configSet, path string, content []byte) error {
	cfg := &Config{}
	if err := proto.UnmarshalText(string(content), cfg); err != nil {
		c.Errorf("not a valid Config proto message: %s", err)
		return nil
	}
	// check duplicate IDs.
	seen := stringset.New(len(cfg.Assigners))
	for i, assigner := range cfg.Assigners {
		c.Enter("assigner #%d:%s", i+1, assigner.Id)
		if !seen.Add(assigner.Id) {
			c.Errorf("duplicate id")
		}
		validateAssigner(c, assigner)
		c.Exit()
	}
	return nil
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
	rotation := source.GetRotation()
	email := source.GetEmail()

	if rotation != "" {
		validateRotation(c, rotation)
	} else if email != "" {
		validateEmail(c, email)
	} else {
		c.Errorf("missing value")
	}
}

func validateRotation(c *validation.Context, rotation string) {
	// The value of Rotation should be a valid URL without Scheme specified.
	u, err := url.Parse(rotation)
	if err != nil {
		c.Errorf("invalid rotation: %s", err)
	} else if u.Scheme != "" {
		c.Errorf("scheme must not be specified: %s", u.Scheme)
	}

	// position is a required parameter for rotation values.
	position := u.Query().Get("position")
	if position == "" {
		c.Errorf("missing position")
	} else if position != "primary" && position != "secondary" {
		c.Errorf("invalid position value: %s", position)
	}
}

func validateEmail(c *validation.Context, email string) {
	// All Monorail users should be valid email addresses.
	if _, err := mail.ParseAddress(email); err != nil {
		c.Errorf("invalid email: %s", err)
	}
}
