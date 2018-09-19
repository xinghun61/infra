// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package monorail

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestValidation(t *testing.T) {
	t.Parallel()

	Convey("Validation", t, func() {
		type Validatable interface {
			Validate() error
		}
		good := func(v Validatable) {
			So(v.Validate(), ShouldBeNil)
		}
		bad := func(v Validatable) {
			So(v.Validate(), ShouldNotBeNil)
		}

		Convey("IssueRef", func() {
			good(&IssueRef{ProjectId: "chromium", IssueId: 1})
			bad((*IssueRef)(nil))
			bad(&IssueRef{})
			bad(&IssueRef{ProjectId: "chromium"})
			bad(&IssueRef{IssueId: 1})
		})

		Convey("AtomPerson", func() {
			good(&AtomPerson{Name: "bob"})
			bad((*AtomPerson)(nil))
			bad(&AtomPerson{})
		})

		Convey("Issue", func() {
			good(&Issue{Status: StatusStarted, ProjectId: "chromium"})
			good(&Issue{
				Summary:     "Write tests for monorail client",
				Author:      &AtomPerson{Name: "seanmccullough@chromium.org"},
				Owner:       &AtomPerson{Name: "nodir@chromium.org"},
				Status:      StatusStarted,
				Cc:          []*AtomPerson{{Name: "agable@chromium.org"}},
				Description: "We should keep our code coverage high, so write tests",
				Components:  []string{"Infra"},
				Labels:      []string{"M-53"},
				ProjectId:   "chromium",
			})

			bad((*Issue)(nil))
			bad(&Issue{})
			bad(&Issue{
				Status:    StatusStarted,
				BlockedOn: []*IssueRef{{}},
			})
			bad(&Issue{
				Status: StatusStarted,
				Cc:     []*AtomPerson{{Name: "a"}, {Name: "a"}},
			})
			bad(&Issue{
				Status:     StatusStarted,
				Components: []string{""},
			})
			bad(&Issue{
				Status: StatusStarted,
				Labels: []string{""},
			})
			bad(&Issue{
				Status: StatusStarted,
				Owner:  &AtomPerson{},
			})
		})
		Convey("InsertIssueRequest", func() {
			good(&InsertIssueRequest{
				Issue: &Issue{
					ProjectId:   "chromium",
					Summary:     "Write tests for monorail client",
					Author:      &AtomPerson{Name: "seanmccullough@chromium.org"},
					Owner:       &AtomPerson{Name: "nodir@chromium.org"},
					Status:      StatusStarted,
					Cc:          []*AtomPerson{{Name: "agable@chromium.org"}},
					Description: "We should keep our code coverage high, so write tests",
					Components:  []string{"Infra"},
					Labels:      []string{"M-53"},
				},
			})

			bad(&InsertIssueRequest{})
			bad(&InsertIssueRequest{
				Issue: &Issue{
					ProjectId: "chromium",
					Status:    StatusStarted,
					Id:        1,
				},
			})
		})
	})
}
