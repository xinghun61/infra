// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gerrit

import (
	"fmt"
	"sort"
	"sync"
	"testing"
	"time"

	"github.com/golang/protobuf/proto"
	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"

	gr "golang.org/x/build/gerrit"
	"golang.org/x/net/context"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
	trit "infra/tricium/appengine/common/testing"
	"infra/tricium/appengine/common/track"
)

const (
	queryChangeLimit = 2
	host             = "https://chromium-review.googlesource.com"
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
	Projects map[string]*tricium.ProjectConfig
}

func (*mockConfigProvider) GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error) {
	return nil, nil // not used by the poller
}

func (*mockConfigProvider) GetProjectConfig(c context.Context, p string) (*tricium.ProjectConfig, error) {
	return nil, nil // not used by the poller
}

// GetAllProjectConfigs implements the ProviderAPI.
func (m *mockConfigProvider) GetAllProjectConfigs(c context.Context) (map[string]*tricium.ProjectConfig, error) {
	return m.Projects, nil
}

func numEnqueuedAnalyzeRequests(ctx context.Context) int {
	return len(tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue])
}

func TestPollBasicBehavior(t *testing.T) {

	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()

		now := time.Date(2017, 1, 1, 0, 0, 0, 0, time.UTC)
		ctx, tc := testclock.UseTime(ctx, now)
		ctx = auth.WithState(ctx, &authtest.FakeState{
			Identity: identity.AnonymousIdentity,
		})

		cp := &mockConfigProvider{
			Projects: map[string]*tricium.ProjectConfig{
				"playground": {
					Name: "playground",
					Repos: []*tricium.RepoDetails{
						{
							GitDetails: &tricium.GitRepoDetails{
								Repository: "https://repo-host.com/playground",
							},
							GerritDetails: &tricium.GerritDetails{
								Host:    host,
								Project: "project/tricium-gerrit",
							},
						},
					},
				},
				"infra": {
					Name: "infra",
					Repos: []*tricium.RepoDetails{
						{
							GitDetails: &tricium.GitRepoDetails{
								Repository: "https://repo-host.com/infra",
							},
							GerritDetails: &tricium.GerritDetails{
								Host:    host,
								Project: "infra/infra",
							},
						},
					},
				},
				"non-gerrit": {
					Name: "non-gerrit",
				},
			},
		}
		projects, err := cp.GetAllProjectConfigs(ctx)
		So(err, ShouldBeNil)

		var gerritProjects []*tricium.GerritDetails
		for _, pc := range projects {
			for _, repo := range pc.Repos {
				if gd := repo.GetGerritDetails(); gd != nil {
					gerritProjects = append(gerritProjects, gd)
				}
			}
		}
		So(len(gerritProjects), ShouldEqual, 2)

		Convey("First poll, no changes", func() {
			api := &mockPollRestAPI{}
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Creates tracking entries for Gerrit projects", func() {
				for _, gd := range gerritProjects {
					p := &Project{ID: gerritProjectID(gd.Host, gd.Project)}
					So(ds.Get(ctx, p), ShouldBeNil)
				}
			})
			Convey("Does not enqueue analyze requests", func() {
				So(numEnqueuedAnalyzeRequests(ctx), ShouldEqual, 0)
			})
		})

		Convey("Second poll, no changes", func() {
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
				So(numEnqueuedAnalyzeRequests(ctx), ShouldEqual, 0)
			})
		})

		Convey("First poll, with changes", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := clock.Now(ctx)
			// Fill up with one change per project.
			for _, gd := range gerritProjects {
				api.addChanges(gd.Host, gd.Project, []gr.ChangeInfo{
					{
						Project: gd.Project,
						Updated: gr.TimeStamp(lastChangeTs),
						Owner:   &gr.AccountInfo{Email: "user@example.com"},
					},
				})
			}
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Does not enqueue analyze requests", func() {
				So(numEnqueuedAnalyzeRequests(ctx), ShouldEqual, 0)
			})
		})

		Convey("Second poll, with new changes adding files", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := tc.Now().UTC()
			// Fill up with one change per project.
			for _, gd := range gerritProjects {
				files := map[string]*gr.FileInfo{
					"README.md": {Status: fileStatusAdded},
				}
				revisions := map[string]gr.RevisionInfo{
					"abcdef": {Files: files},
				}
				api.addChanges(gd.Host, gd.Project, []gr.ChangeInfo{
					{
						ID:              "project~branch~Ideadc0de",
						Project:         gd.Project,
						CurrentRevision: "abcdef",
						Updated:         gr.TimeStamp(lastChangeTs),
						Revisions:       revisions,
						Owner:           &gr.AccountInfo{Email: "user@example.com"},
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
				So(numEnqueuedAnalyzeRequests(ctx), ShouldEqual, len(gerritProjects))
				tasks := tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]
				projects := make([]string, len(tasks))
				for _, task := range tasks {
					//So(len(projects), ShouldEqual, i)
					ar := &tricium.AnalyzeRequest{}
					So(proto.Unmarshal(task.Payload, ar), ShouldBeNil)
					projects = append(projects, ar.Project)
				}
				// TODO(qyearsley): Find out why there are two empty analyze requests
				// with null projects added first.
				sort.Strings(projects)
				So(projects, ShouldResemble, []string{"", "", "infra", "playground"})

			})
			Convey("Adds change tracking entities", func() {
				for _, gd := range gerritProjects {
					So(ds.Get(ctx, &Change{
						ID:     "project~branch~Ideadc0de",
						Parent: ds.NewKey(ctx, "GerritProject", gerritProjectID(gd.Host, gd.Project), 0, nil),
					}), ShouldBeNil)
				}
			})
		})

		Convey("Poll with changes that include deleted and binary files", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := tc.Now().UTC()
			// Fill up with one change per project.
			for _, gd := range gerritProjects {
				files := map[string]*gr.FileInfo{
					"changed.txt": {Status: fileStatusModified},
					"deleted.txt": {Status: fileStatusDeleted},
					"binary.png":  {Status: fileStatusModified, Binary: true},
				}
				revisions := map[string]gr.RevisionInfo{
					"abcdef": {Files: files},
				}
				api.addChanges(gd.Host, gd.Project, []gr.ChangeInfo{
					{
						ID:              "project~branch~Ideadc0de",
						Project:         gd.Project,
						CurrentRevision: "abcdef",
						Updated:         gr.TimeStamp(lastChangeTs),
						Revisions:       revisions,
						Owner:           &gr.AccountInfo{Email: "user@example.com"},
					},
				})
			}
			So(poll(ctx, api, cp), ShouldBeNil)
			tc.Add(time.Second)
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Enqueued analyze requests do not include deleted files", func() {
				tasks := tq.GetTestable(ctx).GetScheduledTasks()[common.AnalyzeQueue]
				So(len(tasks), ShouldEqual, len(gerritProjects))
				for _, task := range tasks {
					ar := &tricium.AnalyzeRequest{}
					err := proto.Unmarshal(task.Payload, ar)
					So(err, ShouldBeNil)
					So(ar.Paths, ShouldResemble, []string{"changed.txt"})
				}
			})
		})

		Convey("Poll when there is a change with no files", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := tc.Now().UTC()
			// Fill up with one change per project.
			for _, gd := range gerritProjects {
				revisions := map[string]gr.RevisionInfo{
					"abcdef": {Files: make(map[string]*gr.FileInfo)},
				}
				api.addChanges(gd.Host, gd.Project, []gr.ChangeInfo{
					{
						ID:              "project~branch~Ideadc0de",
						Project:         gd.Project,
						CurrentRevision: "abcdef",
						Updated:         gr.TimeStamp(lastChangeTs),
						Revisions:       revisions,
						Owner:           &gr.AccountInfo{Email: "user@example.com"},
					},
				})
			}
			So(poll(ctx, api, cp), ShouldBeNil)
			tc.Add(time.Second)
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Does not enqueue analyze requests", func() {
				So(numEnqueuedAnalyzeRequests(ctx), ShouldEqual, 0)
			})
		})

		Convey("Poll with many changes, so paging is used", func() {
			api := &mockPollRestAPI{}
			// The first poll stores the timestamp.
			So(poll(ctx, api, cp), ShouldBeNil)
			tc.Add(time.Second)

			// Fill up each project with multiple changes.
			numChanges := 6
			revBase := "abcdef"
			branch := "master"
			changeIDFooter := "Ideadc0de"
			for _, gd := range gerritProjects {
				var changes []gr.ChangeInfo
				for i := 0; i < numChanges; i++ {
					tc.Add(time.Second)
					changeID := fmt.Sprintf("%s~%s~%s%d", gd.Project, branch, changeIDFooter, i)
					rev := fmt.Sprintf("%s%d", revBase, i)
					files := map[string]*gr.FileInfo{
						"README.md": {Status: fileStatusModified},
					}
					revisions := make(map[string]gr.RevisionInfo)
					revisions[rev] = gr.RevisionInfo{Files: files}
					changes = append(changes, gr.ChangeInfo{
						ID:              changeID,
						Project:         gd.Project,
						CurrentRevision: rev,
						Updated:         gr.TimeStamp(tc.Now().UTC()),
						Revisions:       revisions,
						Owner:           &gr.AccountInfo{Email: "user@example.com"},
					})
				}
				api.addChanges(gd.Host, gd.Project, changes)

			}
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Enqueues analyze requests", func() {
				So(numEnqueuedAnalyzeRequests(ctx), ShouldEqual, len(gerritProjects)*numChanges)
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
	})
}

func TestPollWhitelistBehavior(t *testing.T) {

	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()

		var (
			noWhitelistProject = "no-whitelist-project"
			whitelistProject   = "whitelist-group-project"
			whitelistGroup     = "whitelist-group-name"
		)

		now := time.Date(2017, 1, 1, 0, 0, 0, 0, time.UTC)
		ctx, tc := testclock.UseTime(ctx, now)
		ctx = auth.WithState(ctx, &authtest.FakeState{
			Identity: identity.AnonymousIdentity,
			FakeDB: authtest.FakeDB{
				"user:whitelisteduser@example.com": []string{whitelistGroup},
			},
		})

		cp := &mockConfigProvider{
			Projects: map[string]*tricium.ProjectConfig{
				noWhitelistProject: {
					Name: noWhitelistProject,
					Repos: []*tricium.RepoDetails{
						{
							GitDetails: &tricium.GitRepoDetails{
								Repository: "https://repo-host.com/no-whitelist",
							},
							GerritDetails: &tricium.GerritDetails{
								Host:    host,
								Project: noWhitelistProject,
							},
						},
					},
				},
				whitelistProject: {
					Name: whitelistProject,
					Repos: []*tricium.RepoDetails{
						{
							GitDetails: &tricium.GitRepoDetails{
								Repository: "https://repo-host.com/whitelist",
							},
							GerritDetails: &tricium.GerritDetails{
								Host:             host,
								Project:          whitelistProject,
								WhitelistedGroup: []string{whitelistGroup},
							},
						},
					},
				},
				"star-project": {
					Name: "star-project",
					Repos: []*tricium.RepoDetails{
						{
							GitDetails: &tricium.GitRepoDetails{
								Repository: "https://repo-host.com/star-project",
							},
							GerritDetails: &tricium.GerritDetails{
								Host:             host,
								Project:          "star-project",
								WhitelistedGroup: []string{"*"},
							},
						},
					},
				},
			},
		}

		projects, err := cp.GetAllProjectConfigs(ctx)
		So(err, ShouldBeNil)

		var gerritProjects []*tricium.GerritDetails
		for _, pc := range projects {
			for _, repo := range pc.Repos {
				if gd := repo.GetGerritDetails(); gd != nil {
					gerritProjects = append(gerritProjects, gd)
				}
			}
		}

		Convey("No whitelisted groups means all changes are analyzed", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := tc.Now().UTC()
			files := map[string]*gr.FileInfo{
				"README.md": {Status: fileStatusAdded},
			}
			revisions := map[string]gr.RevisionInfo{
				"abcdef": {Files: files},
			}
			api.addChanges(host, noWhitelistProject, []gr.ChangeInfo{
				{
					ID:              "project~branch~Ideadc0de",
					Project:         noWhitelistProject,
					CurrentRevision: "abcdef",
					Updated:         gr.TimeStamp(lastChangeTs),
					Revisions:       revisions,
					Owner:           &gr.AccountInfo{Email: "whitelisteduser@example.com"},
				},
			})
			So(poll(ctx, api, cp), ShouldBeNil)
			tc.Add(time.Second)
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Enqueues an analyze request", func() {
				So(numEnqueuedAnalyzeRequests(ctx), ShouldEqual, 1)
			})
		})

		Convey("Poll with a change by a whitelisted user", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := tc.Now().UTC()
			files := map[string]*gr.FileInfo{
				"README.md": {Status: fileStatusAdded},
			}
			revisions := map[string]gr.RevisionInfo{
				"abcdef": {Files: files},
			}
			api.addChanges(host, whitelistProject, []gr.ChangeInfo{
				{
					ID:              "project~branch~Ideadc0de",
					Project:         whitelistProject,
					CurrentRevision: "abcdef",
					Updated:         gr.TimeStamp(lastChangeTs),
					Revisions:       revisions,
					Owner:           &gr.AccountInfo{Email: "whitelisteduser@example.com"},
				},
			})
			So(poll(ctx, api, cp), ShouldBeNil)
			tc.Add(time.Second)
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Does not enqueue analyze requests", func() {
				So(numEnqueuedAnalyzeRequests(ctx), ShouldEqual, 1)
			})
		})

		Convey("Poll with a change by an unwhitelisted user", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := tc.Now().UTC()
			files := map[string]*gr.FileInfo{
				"README.md": {Status: fileStatusAdded},
			}
			revisions := map[string]gr.RevisionInfo{
				"abcdef": {Files: files},
			}
			api.addChanges(host, whitelistProject, []gr.ChangeInfo{
				{
					ID:              "project~branch~Ideadc0de",
					Project:         whitelistProject,
					CurrentRevision: "abcdef",
					Updated:         gr.TimeStamp(lastChangeTs),
					Revisions:       revisions,
					Owner:           &gr.AccountInfo{Email: "somebody-else@example.com"},
				},
			})
			So(poll(ctx, api, cp), ShouldBeNil)
			tc.Add(time.Second)
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Does not enqueue analyze requests", func() {
				So(numEnqueuedAnalyzeRequests(ctx), ShouldEqual, 0)
			})
		})

		Convey("Poll with a change where whitelist contains *", func() {
			api := &mockPollRestAPI{}
			lastChangeTs := tc.Now().UTC()
			files := map[string]*gr.FileInfo{
				"README.md": {Status: fileStatusAdded},
			}
			revisions := map[string]gr.RevisionInfo{
				"abcdef": {Files: files},
			}
			api.addChanges(host, "star-project", []gr.ChangeInfo{
				{
					ID:              "project~branch~Ideadc0de",
					Project:         "star-project",
					CurrentRevision: "abcdef",
					Updated:         gr.TimeStamp(lastChangeTs),
					Revisions:       revisions,
					Owner:           &gr.AccountInfo{Email: "somebody-else@example.com"},
				},
			})
			So(poll(ctx, api, cp), ShouldBeNil)
			tc.Add(time.Second)
			So(poll(ctx, api, cp), ShouldBeNil)
			Convey("Enqueues an analyze request", func() {
				So(numEnqueuedAnalyzeRequests(ctx), ShouldEqual, 1)
			})
		})
	})
}
