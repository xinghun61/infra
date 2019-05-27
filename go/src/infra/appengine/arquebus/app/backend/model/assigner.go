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

package model

import (
	"context"
	"time"

	"github.com/golang/protobuf/proto"
	"github.com/golang/protobuf/ptypes"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"

	"infra/appengine/arquebus/app/config"
)

const (
	// The interval of schedule-assigners cron job.
	scheduleAssignerCronInterval = time.Second * 60
)

// Assigner is a job object that periodically runs to perform issue update
// operations.
type Assigner struct {
	_kind  string                `gae:"$kind,Assigner"`
	_extra datastore.PropertyMap `gae:"-,extra"`

	// ID is a globally unique identifier of the assigner.
	ID string `gae:"$id,"`

	// Owners contain an email list of the owners.
	Owners []string `gae:",noindex"`

	// IssueQuery defines a search query to be sent to Monorail for issue
	// searches.
	IssueQuery config.IssueQuery `gae:",noindex"`

	// Interval specifies the delay between each individual runs of the
	// assigner.
	Interval time.Duration `gae:",noindex"`

	// AssigneesRaw is a blob with serialized config.UserSource.
	AssigneesRaw [][]byte `gae:",noindex" json:"-"`

	// CCsRaw is a blob with serialized config.UserSource.
	CCsRaw [][]byte `gae:",noindex" json:"-"`

	Description string `gae:",noindex"`
	Comment     string `gae:",noindex"`

	// IsDryRun specifies if the assigner should process tasks without
	// issue update operations.
	IsDryRun bool

	// IsDrained specifies if the assigner has been drained.
	//
	// If an assigner is drained, no tasks are scheduled and run for
	// the assigner.
	IsDrained bool

	// LatestSchedule is the latest timestamp that the Assigner has been
	// scheduled for.
	LatestSchedule time.Time `gae:",noindex"`

	// ConfigRevision specifies the revision of a luci config with which
	// a given assigner entity was last updated.
	//
	// If an Assigner config is removed, this is the revision of the first
	// config push without the removed Assigner config.
	ConfigRevision string `gae:",noindex"`
}

// updateIfChanged updates the Assigner entity, based on the valid config.
//
// This Returns whether the content has been updated.
func (a *Assigner) updateIfChanged(c context.Context, cfg *config.Assigner, rev string) bool {
	// skip updating if the revision is the same.
	if a.ConfigRevision == rev {
		return false
	}

	a.Owners = cfg.Owners
	a.IssueQuery = *cfg.IssueQuery
	a.Description = cfg.Description
	a.Comment = cfg.Comment
	a.IsDryRun = cfg.DryRun
	a.ConfigRevision = rev

	interval, _ := ptypes.Duration(cfg.Interval)
	a.Interval = interval
	a.AssigneesRaw = make([][]byte, len(cfg.Assignees))
	for i, assignee := range cfg.Assignees {
		a.AssigneesRaw[i], _ = proto.Marshal(assignee)
	}
	a.CCsRaw = make([][]byte, len(cfg.Ccs))
	for i, cc := range cfg.Ccs {
		a.CCsRaw[i], _ = proto.Marshal(cc)
	}

	return true
}

// Assignees returns a list of UserSource to look for issue assignees from.
func (a *Assigner) Assignees() ([]config.UserSource, error) {
	results := make([]config.UserSource, len(a.AssigneesRaw))
	for i, raw := range a.AssigneesRaw {
		if err := proto.Unmarshal(raw, &results[i]); err != nil {
			return nil, err
		}
	}
	return results, nil
}

// CCs returns a list of UserSource to look for whom to cc issues from.
func (a *Assigner) CCs() ([]config.UserSource, error) {
	results := make([]config.UserSource, len(a.CCsRaw))
	for i, raw := range a.CCsRaw {
		if err := proto.Unmarshal(raw, &results[i]); err != nil {
			return nil, err
		}
	}
	return results, nil
}

// UpdateAssigners update all the Assigner entities, on presumed valid
// configs.
//
// For removed configs, the Assigner entities are marked as removed.
// For new configs, new Assigner entities are created.
// For updated configs, the Assigner entities are updated,
// based on the updated content.
func UpdateAssigners(c context.Context, cfgs []*config.Assigner, rev string) error {
	assigners, err := GetAllAssigners(c)
	if err != nil {
		return err
	}
	aeMap := make(map[string]*Assigner, len(assigners))
	for _, assigner := range assigners {
		aeMap[assigner.ID] = assigner
	}

	merr := errors.MultiError(nil)
	// update or create new ones.
	for _, cfg := range cfgs {
		if assigner, exist := aeMap[cfg.Id]; exist {
			delete(aeMap, cfg.Id)
			// optimization for common case when no updates are
			// necessary.
			if !assigner.updateIfChanged(c, cfg, rev) {
				continue
			}
		}

		err := datastore.RunInTransaction(c, func(c context.Context) error {
			assigner := Assigner{ID: cfg.Id}
			if err := datastore.Get(c, &assigner); err != nil &&
				err != datastore.ErrNoSuchEntity {
				// likely transient flake
				return err
			}

			if assigner.updateIfChanged(c, cfg, rev) {
				logging.Debugf(
					c, "Update/Insert Assigner %s (rev %s)",
					cfg.Id, rev,
				)
				return datastore.Put(c, &assigner)
			}
			return nil
		}, &datastore.TransactionOptions{})
		if err != nil {
			merr = append(merr, err)
		}
	}

	// remove ones without configs.
	for id, assigner := range aeMap {
		logging.Infof(c, "Delete Assigner %s (rev %s)", id, rev)
		if err := datastore.Delete(c, assigner); err != nil {
			merr = append(merr, err)
		}
	}

	if merr != nil {
		return merr
	}
	return nil
}

// GetAssigner returns the Assigner entity matching with a given id.
func GetAssigner(c context.Context, assignerID string) (*Assigner, error) {
	assigner := &Assigner{ID: assignerID}
	if err := datastore.Get(c, assigner); err != nil {
		return nil, err
	}
	return assigner, nil
}

// GetAllAssigners returns all the assigner entities.
func GetAllAssigners(c context.Context) ([]*Assigner, error) {
	var assigners []*Assigner
	q := datastore.NewQuery("Assigner")
	if err := datastore.GetAll(c, q, &assigners); err != nil {
		return nil, err
	}
	return assigners, nil
}

// GenAssignerKey generates a datastore key for a given assigner object.
func GenAssignerKey(c context.Context, assigner *Assigner) *datastore.Key {
	return datastore.KeyForObj(c, assigner)
}

// EnsureScheduledTasks ensures that the Assigner has at least one Scheduled
// Task for upcoming runs.
//
// This function must be invoked within a transaction.
func EnsureScheduledTasks(c context.Context, assignerID string) ([]*Task, error) {
	if datastore.CurrentTransaction(c) == nil {
		panic("EnsureScheduledTasks was invoked out of a transaction.")
	}

	assigner, err := GetAssigner(c, assignerID)
	if err != nil {
		return nil, err
	}
	now := clock.Now(c).UTC()
	if assigner.IsDrained || assigner.LatestSchedule.After(now) {
		// no further schedules need to be created.
		return nil, nil
	}

	var tasks []*Task
	nextETA, scheduleUpTo := findNextETA(now, assigner)
	for ; !nextETA.After(scheduleUpTo); nextETA = nextETA.Add(assigner.Interval) {
		assigner.LatestSchedule = nextETA
		newTask := &Task{
			AssignerKey:   GenAssignerKey(c, assigner),
			ExpectedStart: nextETA,
			Status:        TaskStatus_Scheduled,
		}
		// Just to show a log entry for a newly created task in UI.
		newTask.WriteLog(c, "Task created for assigner %s", assignerID)
		tasks = append(tasks, newTask)
	}

	if err := datastore.Put(c, assigner); err != nil {
		return nil, err
	}
	if err := datastore.Put(c, tasks); err != nil {
		return nil, err
	}
	return tasks, nil
}

func findNextETA(now time.Time, assigner *Assigner) (nextETA time.Time, scheduleUpTo time.Time) {
	nextETA = assigner.LatestSchedule.Add(assigner.Interval)
	if nextETA.Before(now) {
		// Perhaps, the assigner was drained in the past.
		//
		// Note that nextETA should be in the future. Otherwise, the task will
		// likely be stale and cancelled when it is handed to the Task executor.
		nextETA = now.Add(assigner.Interval)
	}

	scheduleUpTo = now.Add(scheduleAssignerCronInterval)
	if nextETA.After(scheduleUpTo) {
		// It means that assigner.Interval is longer than the cron interval.
		// To ensure that there is at least one Task scheduled always,
		// set the cut-off time with the nextETA.
		scheduleUpTo = nextETA
	}

	return nextETA, scheduleUpTo
}
