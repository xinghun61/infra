// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/golang/protobuf/proto"
	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"

	gr "golang.org/x/build/gerrit"
	"golang.org/x/net/context"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	trit "infra/tricium/appengine/common/testing"
	"infra/tricium/appengine/common/track"
)

const (
	queryChangeLimit   = 2
	noWhitelistProject = "no-whitelist-project"
	host               = "https://chromium-review.googlesource.com"
)

// mockPollRestAPI allows for modification of change state returned by QueryChanges.
type mockPollRestAPI struct {
	sync.Mutex
	changes map[string][]gr.ChangeInfo
}

func (m *mockPollRestAPI) QueryChanges(c context.Context, host, project string, ts time.Time, offset int) ([]gr.ChangeInfo, bool, error) {
	m.Lock()
	defer m.Unlock()

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

func (*mockPollRestAPI) PostRobotComments(c context.Context, host, change, revision string, runID int64, comments []*track.Comment) error {
	// not used by the poller
	return nil
}

func (m *mockPollRestAPI) addChanges(host, project string, c []gr.ChangeInfo) {
	m.Lock()
	defer m.Unlock()

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
					Host:             host,
					Project:          "project/tricium-gerrit",
					WhitelistedGroup: []string{"*"},
				},
			},
			{
				Name: "infra",
				GerritDetails: &tricium.GerritDetails{
					Host:             host,
					Project:          "infra/infra",
					WhitelistedGroup: []string{"*"},
				},
			},
			{
				Name: "non-gerrit",
			},
			{
				Name: noWhitelistProject,
				GerritDetails: &tricium.GerritDetails{
					Host:    host,
					Project: noWhitelistProject,
				},
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
			Convey("Does not enqueue analyze requests", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]), ShouldEqual, 0)
			})
		})

		Convey("Second poll (no changes)", func() {
			api := &mockPollRestAPI{}
			So(poll(ctx, api, cp), ShouldBeNil)
			// Store last poll timestamps from first poll.
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
			Convey("Does not enqueue analyze requests", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]), ShouldEqual, 0)
			})
		})

		Convey("First poll (with changes)", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := clock.Now(ctx)
			owner := &gr.AccountInfo{Email: "emso@chromium.org"}
			// Fill up with one change per project.
			for _, gd := range gerritProjects {
				api.addChanges(gd.Host, gd.Project, []gr.ChangeInfo{
					{
						Project: gd.Project,
						Updated: gr.TimeStamp(lastChangeTs),
						Owner:   owner,
					},
				})
			}
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Does not enqueue analyze requests", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]), ShouldEqual, 0)
			})
		})

		Convey("Second poll (with new changes adding files)", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := tc.Now().UTC()
			// Fill up with one change per project.
			rev := "abcdefg"
			changeID := "project~branch~Ideadc0de"
			file := "README.md"
			owner := &gr.AccountInfo{Email: "emso@chromium.org"}
			for _, gd := range gerritProjects {
				files := make(map[string]*gr.FileInfo)
				files[file] = &gr.FileInfo{Status: fileStatusAdded}
				revisions := make(map[string]gr.RevisionInfo)
				revisions[rev] = gr.RevisionInfo{Files: files}
				api.addChanges(gd.Host, gd.Project, []gr.ChangeInfo{
					{
						ID:              changeID,
						Project:         gd.Project,
						CurrentRevision: rev,
						Updated:         gr.TimeStamp(lastChangeTs),
						Revisions:       revisions,
						Owner:           owner,
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
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]), ShouldEqual, len(gerritProjects)-1)
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

		Convey("Deleted files are not included in analyze request", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := tc.Now().UTC()
			// Fill up with a change per project
			rev := "abcdefg"
			changeID := "project~branch~Ideadc0de"
			changedFile := "changed-file.bar"
			deletedFile := "deprecated.foo"
			owner := &gr.AccountInfo{
				Email: "emso@chromium.org",
			}
			for _, gd := range gerritProjects {
				files := make(map[string]*gr.FileInfo)
				files[changedFile] = &gr.FileInfo{Status: fileStatusModified}
				files[deletedFile] = &gr.FileInfo{Status: fileStatusDeleted}
				revisions := make(map[string]gr.RevisionInfo)
				revisions[rev] = gr.RevisionInfo{Files: files}
				api.addChanges(gd.Host, gd.Project, []gr.ChangeInfo{
					{
						ID:              changeID,
						Project:         gd.Project,
						CurrentRevision: rev,
						Updated:         gr.TimeStamp(lastChangeTs),
						Revisions:       revisions,
						Owner:           owner,
					},
				})
			}
			So(poll(ctx, api, cp), ShouldBeNil)
			tc.Add(time.Second)
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Enqueues analyze requests with no deleted files", func() {
				tasks := tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]
				So(len(tasks), ShouldEqual, len(gerritProjects)-1)
				for _, task := range tasks {
					ar := &tricium.AnalyzeRequest{}
					err := proto.Unmarshal(task.Payload, ar)
					So(err, ShouldBeNil)
					So(ar.Paths, ShouldResemble, []string{changedFile})
				}
			})
		})

		Convey("Poll when there is a change with no files", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := tc.Now().UTC()
			// Fill up with a change per project
			rev := "abcdefg"
			changeID := "project~branch~Ideadc0de"
			owner := &gr.AccountInfo{
				Email: "emso@chromium.org",
			}
			for _, gd := range gerritProjects {
				files := make(map[string]*gr.FileInfo)
				revisions := make(map[string]gr.RevisionInfo)
				revisions[rev] = gr.RevisionInfo{Files: files}
				api.addChanges(gd.Host, gd.Project, []gr.ChangeInfo{
					{
						ID:              changeID,
						Project:         gd.Project,
						CurrentRevision: rev,
						Updated:         gr.TimeStamp(lastChangeTs),
						Revisions:       revisions,
						Owner:           owner,
					},
				})
			}
			So(poll(ctx, api, cp), ShouldBeNil)
			tc.Add(time.Second)
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Does not enqueue analyze requests", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]), ShouldEqual, 0)
			})
		})

		Convey("Second poll (paged changes)", func() {
			api := &mockPollRestAPI{}
			// The first poll stores timestamp.
			So(poll(ctx, api, cp), ShouldBeNil)
			tc.Add(time.Second)

			// Fill up each project with multiple changes.
			numChanges := 6
			revBase := "abcdefg"
			branch := "master"
			changeIDFooter := "Ideadc0de"
			file := "README.md"
			owner := &gr.AccountInfo{Email: "emso@chromium.org"}
			for _, gd := range gerritProjects {
				var changes []gr.ChangeInfo
				for i := 0; i < numChanges; i++ {
					tc.Add(time.Second)
					changeID := fmt.Sprintf("%s~%s~%s%d", gd.Project, branch, changeIDFooter, i)
					rev := fmt.Sprintf("%s%d", revBase, i)
					files := make(map[string]*gr.FileInfo)
					files[file] = &gr.FileInfo{Status: fileStatusModified}
					revisions := make(map[string]gr.RevisionInfo)
					revisions[rev] = gr.RevisionInfo{Files: files}
					changes = append(changes, gr.ChangeInfo{
						ID:              changeID,
						Project:         gd.Project,
						CurrentRevision: rev,
						Updated:         gr.TimeStamp(tc.Now().UTC()),
						Revisions:       revisions,
						Owner:           owner,
					})
				}
				api.addChanges(gd.Host, gd.Project, changes)

			}
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Enqueues analyze requests", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]), ShouldEqual, (len(gerritProjects)-1)*numChanges)
			})
			Convey("Adds change tracking entities", func() {
				for _, gd := range gerritProjects {
					for i := 0; i < numChanges; i++ {
						So(ds.Get(ctx, &Change{
							ID:     fmt.Sprintf("%s~%s~%s%d", gd.Project, branch, changeIDFooter, i),
							Parent: ds.NewKey(ctx, "GerritProject", gerritProjectID(gd.Host, gd.Project), 0, nil),
						}), ShouldBeNil)
					}
				}
			})
		})

		Convey("Second poll (changes, no whitelist)", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := tc.Now().UTC()
			// Fill up with a change in project with no whitelist.
			rev := "abcdefg"
			changeID := "project~branch~Ideadc0de"
			file := "README.md"
			owner := &gr.AccountInfo{Email: "emso@chromium.org"}
			files := make(map[string]*gr.FileInfo)
			files[file] = &gr.FileInfo{Status: fileStatusAdded}
			revisions := make(map[string]gr.RevisionInfo)
			revisions[rev] = gr.RevisionInfo{Files: files}
			api.addChanges(host, noWhitelistProject, []gr.ChangeInfo{
				{
					ID:              changeID,
					Project:         noWhitelistProject,
					CurrentRevision: rev,
					Updated:         gr.TimeStamp(lastChangeTs),
					Revisions:       revisions,
					Owner:           owner,
				},
			})
			So(poll(ctx, api, cp), ShouldBeNil)
			tc.Add(time.Second)
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Updates last poll timestamp to last change timestamp", func() {
				p := &Project{ID: gerritProjectID(host, noWhitelistProject)}
				So(ds.Get(ctx, p), ShouldBeNil)
				So(lastChangeTs.Equal(p.LastPoll), ShouldBeTrue)
			})
			Convey("Does not enqueue analyze requests", func() {
				So(len(tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]), ShouldEqual, 0)
			})
		})

	})
}
