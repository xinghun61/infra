// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package monorail

import "fmt"

// Validate checks the message for errors.
func (i *IssueRef) Validate() error {
	if i == nil {
		return fmt.Errorf("is nil")
	}
	if i.ProjectId == "" {
		return fmt.Errorf("no projectId")
	}
	if i.IssueId == 0 {
		return fmt.Errorf("no issueId")
	}
	return nil
}

// Validate checks the message for errors.
func (a *AtomPerson) Validate() error {
	if a == nil {
		return fmt.Errorf("is nil")
	}
	if a.Name == "" {
		return fmt.Errorf("no name")
	}
	return nil
}

// Validate checks the message for errors.
func (i *Issue) Validate() error {
	if i == nil {
		return fmt.Errorf("is nil")
	}
	if i.ProjectId == "" {
		return fmt.Errorf("no projectId")
	}
	if i.Status == "" {
		return fmt.Errorf("no status")
	}
	for _, ref := range i.BlockedOn {
		if err := ref.Validate(); err != nil {
			return fmt.Errorf("blockedOn: %s", err)
		}
	}

	seen := map[string]struct{}{}
	for _, cc := range i.Cc {
		if err := cc.Validate(); err != nil {
			return fmt.Errorf("cc: %s", err)
		}
		// Monorail does not like duplicates in CC list.
		if _, saw := seen[cc.Name]; saw {
			return fmt.Errorf("cc: duplicate %s", cc.Name)
		}
		seen[cc.Name] = struct{}{}
	}

	for _, c := range i.Components {
		if c == "" {
			return fmt.Errorf("empty component")
		}
	}

	for _, label := range i.Labels {
		if label == "" {
			return fmt.Errorf("empty label")
		}
	}

	if i.Owner != nil {
		if err := i.Owner.Validate(); err != nil {
			return err
		}
	}

	return nil
}

// Validate checks the message for errors.
func (i *InsertIssueRequest) Validate() error {
	if err := i.Issue.Validate(); err != nil {
		return fmt.Errorf("issue: %s", err)
	}
	if i.Issue.Id != 0 {
		return fmt.Errorf("issue: must not have id")
	}
	return nil
}

// Validate checks the message for errors.
func (l *ListCommentsRequest) Validate() error {
	if l == nil {
		return fmt.Errorf("is nil")
	}
	if l.GetMaxResults() < 0 {
		return fmt.Errorf("max_results must be >= 0")
	}
	if l.GetStartIndex() < 0 {
		return fmt.Errorf("start_index must be >= 0")
	}
	if err := l.Issue.Validate(); err != nil {
		return fmt.Errorf("issue: %s", err)
	}
	return nil
}
