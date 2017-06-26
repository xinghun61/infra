// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"fmt"
	"testing"
	"time"

	ds "github.com/luci/gae/service/datastore"
	tq "github.com/luci/gae/service/taskqueue"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/clock/testclock"
	. "github.com/smartystreets/goconvey/convey"

	gr "golang.org/x/build/gerrit"
	"golang.org/x/net/context"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	trit "infra/tricium/appengine/common/testing"
	"infra/tricium/appengine/common/track"
)

const queryChangeLimit = 2

//mockPollRestAPI allows for modification of change state returned by QueryChanges.
type mockPollRestAPI struct {
	changes map[string][]gr.ChangeInfo
}

func (m *mockPollRestAPI) QueryChanges(c context.Context, host, project string, ts time.Time, offset int) ([]gr.ChangeInfo, bool, error) {
	if m.changes == nil {
		m.changes = make(map[string][]gr.ChangeInfo)
	}
	id := gerritProjectID(host, project)
	changes, _ := m.changes[id]
	more := false
	if len(changes) > queryChangeLimit {
		m.changes[id] = changes[queryChangeLimit:] // move the tail of changes not returned to the front
		changes = changes[0:queryChangeLimit]      // return the first chunk of changes
		more = true
	} else {
		m.changes[id] = make([]gr.ChangeInfo, 0) // replace with empty slice
	}
	return changes, more, nil
}

func (*mockPollRestAPI) PostReviewMessage(c context.Context, host, change, revision, msg string) error {
	// not used by the poller
	return nil
}

func (*mockPollRestAPI) PostRobotComments(c context.Context, host, change, revision string, runID int64, comments []*track.Comment) error {
	// not used by the poller
	return nil
}

func (m *mockPollRestAPI) addChanges(host, project string, c []gr.ChangeInfo) {
	if m.changes == nil {
		m.changes = make(map[string][]gr.ChangeInfo)
	}
	id := gerritProjectID(host, project)
	changes, _ := m.changes[id]
	changes = append(changes, c...)
	m.changes[id] = changes
}

type mockConfigProvider struct {
}

func (*mockConfigProvider) GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error) {
	return &tricium.ServiceConfig{
		Projects: []*tricium.ProjectDetails{
			{
				Name: "playground",
				GerritDetails: &tricium.GerritDetails{
					Host:    "https://chromium-review.googlesource.com",
					Project: "project/tricium-gerrit",
				},
			},
			{
				Name: "infra",
				GerritDetails: &tricium.GerritDetails{
					Host:    "https://chromium-review.googlesource.com",
					Project: "infra/infra",
				},
			},
			{
				Name: "non-gerrit",
			},
		},
	}, nil
}
func (*mockConfigProvider) GetProjectConfig(c context.Context, p string) (*tricium.ProjectConfig, error) {
	// not used by the poller
	return nil, nil
}

func TestPoll(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()

		now := time.Date(2017, 1, 1, 0, 0, 0, 0, time.UTC)
		ctx, tc := testclock.UseTime(ctx, now)

		cp := &mockConfigProvider{}
		sc, err := cp.GetServiceConfig(ctx)
		So(err, ShouldBeNil)

		var gerritProjects []*tricium.GerritDetails
		for _, pd := range sc.Projects {
			gd := pd.GetGerritDetails()
			if gd != nil {
				gerritProjects = append(gerritProjects, gd)
			}
		}

		Convey("First poll (no changes)", func() {
			api := &mockPollRestAPI{}
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Creates tracking entries for Gerrit projects", func() {
				for _, gd := range gerritProjects {
					p := &Project{ID: gerritProjectID(gd.Host, gd.Project)}
					So(ds.Get(ctx, p), ShouldBeNil)
				}
			})
			Convey("Enqueues no analyze request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]), ShouldEqual, 0)
			})
		})

		Convey("Second poll (no changes)", func() {
			api := &mockPollRestAPI{}
			So(poll(ctx, api, cp), ShouldBeNil)
			// Store lastPoll timestamps from first poll
			lastPolls := make(map[string]time.Time)
			for _, gd := range gerritProjects {
				p := &Project{ID: gerritProjectID(gd.Host, gd.Project)}
				So(ds.Get(ctx, p), ShouldBeNil)
				lastPolls[p.ID] = p.LastPoll
			}
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Does not update timestamp of last poll", func() {
				for _, gd := range gerritProjects {
					p := &Project{ID: gerritProjectID(gd.Host, gd.Project)}
					So(ds.Get(ctx, p), ShouldBeNil)
					t, _ := lastPolls[p.ID]
					So(t.Equal(p.LastPoll), ShouldBeTrue)
				}
			})
			Convey("Enqueues no analyze request", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]), ShouldEqual, 0)
			})
		})

		Convey("First poll (changes)", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := clock.Now(ctx)
			// Fill up with a change per project
			for _, gd := range gerritProjects {
				api.addChanges(gd.Host, gd.Project, []gr.ChangeInfo{
					{
						Project: gd.Project,
						Updated: gr.TimeStamp(lastChangeTs),
					},
				})
			}
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Does not enqueues analyze requests", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]), ShouldEqual, 0)
			})
		})

		Convey("Second poll (changes)", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := tc.Now().UTC()
			// Fill up with a change per project
			rev := "abcdefg"
			changeID := "1"
			file := "README.md"
			for _, gd := range gerritProjects {
				files := make(map[string]*gr.FileInfo)
				files[file] = &gr.FileInfo{Status: "A"}
				revisions := make(map[string]gr.RevisionInfo)
				revisions[rev] = gr.RevisionInfo{Files: files}
				api.addChanges(gd.Host, gd.Project, []gr.ChangeInfo{
					{
						Project:         gd.Project,
						ChangeID:        changeID,
						CurrentRevision: rev,
						Updated:         gr.TimeStamp(lastChangeTs),
						Revisions:       revisions,
					},
				})
			}
			So(poll(ctx, api, cp), ShouldBeNil)
			tc.Add(time.Second)
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Updates last poll timestamp to last change timestamp", func() {
				for _, gd := range gerritProjects {
					p := &Project{ID: gerritProjectID(gd.Host, gd.Project)}
					So(ds.Get(ctx, p), ShouldBeNil)
					So(lastChangeTs.Equal(p.LastPoll), ShouldBeTrue)
				}
			})
			Convey("Enqueues analyze requests", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]), ShouldEqual, len(gerritProjects))
			})
			Convey("Adds change tracking entities", func() {
				for _, gd := range gerritProjects {
					So(ds.Get(ctx, &Change{
						ID:     changeID,
						Parent: ds.NewKey(ctx, "GerritProject", gerritProjectID(gd.Host, gd.Project), 0, nil),
					}), ShouldBeNil)
				}
			})
		})

		Convey("Second poll (paged changes)", func() {
			api := &mockPollRestAPI{}
			So(poll(ctx, api, cp), ShouldBeNil) // first poll storing timestamp
			tc.Add(time.Second)
			// Fill up projects with changes
			numChanges := 6
			revBase := "abcdefg"
			changeIDBase := "1"
			file := "README.md"
			for _, gd := range gerritProjects {
				var changes []gr.ChangeInfo
				for i := 0; i < numChanges; i++ {
					tc.Add(time.Second)
					changeID := fmt.Sprintf("%s%s%d", changeIDBase, gd.Project, i)
					rev := fmt.Sprintf("%s%d", revBase, i)
					files := make(map[string]*gr.FileInfo)
					files[file] = &gr.FileInfo{Status: "M"}
					revisions := make(map[string]gr.RevisionInfo)
					revisions[rev] = gr.RevisionInfo{Files: files}
					changes = append(changes, gr.ChangeInfo{
						Project:         gd.Project,
						ChangeID:        changeID,
						CurrentRevision: rev,
						Updated:         gr.TimeStamp(tc.Now().UTC()),
						Revisions:       revisions,
					})
				}
				api.addChanges(gd.Host, gd.Project, changes)

			}
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Enqueues analyze requests", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]), ShouldEqual, len(gerritProjects)*numChanges)
			})
			Convey("Adds change tracking entities", func() {
				for _, gd := range gerritProjects {
					for i := 0; i < numChanges; i++ {
						So(ds.Get(ctx, &Change{
							ID:     fmt.Sprintf("%s%s%d", changeIDBase, gd.Project, i),
							Parent: ds.NewKey(ctx, "GerritProject", gerritProjectID(gd.Host, gd.Project), 0, nil),
						}), ShouldBeNil)
					}
				}
			})
		})
	})
}
