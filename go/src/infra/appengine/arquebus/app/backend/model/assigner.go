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

	"github.com/golang/protobuf/ptypes"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"

	"infra/appengine/arquebus/app/config"
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

	// Rotations specify a list of rotation names to find assignees.
	//
	// The rotation names must be a valid rotation name in RotaNG.
	Rotations []string `gae:",noindex"`

	Description string `gae:",noindex"`

	// IsDryRun specifies if the assigner should process tasks without
	// issue update operations.
	IsDryRun bool

	// Status specifies the status of the assigner. e.g., drained or running
	Status AssignerStatus

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
func (a *Assigner) updateIfChanged(cfg *config.Assigner, rev string) bool {
	// skip updating if the revision is the same.
	if a.ConfigRevision == rev {
		return false
	}

	a.Owners = cfg.Owners
	a.IssueQuery = *cfg.IssueQuery
	interval, _ := ptypes.Duration(cfg.Interval)
	a.Interval = interval
	a.Rotations = cfg.Rotations
	a.Description = cfg.Description
	a.IsDryRun = cfg.DryRun
	a.ConfigRevision = rev

	// If the Assigner config exists, the status should be either
	// Running or Drained.
	if a.Status != AssignerStatus_DRAINED {
		a.Status = AssignerStatus_RUNNING
	}

	return true
}

// UpdateAssigners update all the Assigner entities, on presumed valid configs.
//
// For removed configs, the Assigner entities are marked as removed.
// For new configs, new Assigner entities are created.
// For updated configs, the Assigner entities are updated, based on the updated
// content.
func UpdateAssigners(c context.Context, cfgs []*config.Assigner, rev string) error {
	cfgMap := make(map[string]*config.Assigner, len(cfgs))
	for _, ac := range cfgs {
		cfgMap[ac.Id] = ac
	}

	aes, err := GetAllAssigners(c)
	if err != nil {
		return nil
	}

	aesToSave := make([]*Assigner, 0, len(aes)+len(cfgMap))
	for _, ae := range aes {
		if ac, ok := cfgMap[ae.ID]; ok == true {
			delete(cfgMap, ae.ID)

			// Update only if config has been changed.
			if ae.updateIfChanged(ac, rev) {
				aesToSave = append(aesToSave, ae)
				logging.Debugf(
					c, "Update Assigner %s (rev %s)",
					ae.ID, rev,
				)
			}
		} else {
			// The config for the assigner has been removed.
			ae.Status = AssignerStatus_REMOVED
			ae.ConfigRevision = rev
			aesToSave = append(aesToSave, ae)
			logging.Infof(
				c, "Remove Assigner %s (rev %s)", ae.ID, rev,
			)
		}
	}

	// Create Assigners for new configs.
	for _, ac := range cfgMap {
		// Just to ensure that this wasn't missed by GetAllAssigners()
		// due to delays in index updates.
		ae, err := GetAssigner(c, ac.Id)
		if err != nil {
			if err != datastore.ErrNoSuchEntity {
				return err
			}
			ae = &Assigner{ID: ac.Id}
		}

		if ae.updateIfChanged(ac, rev) {
			aesToSave = append(aesToSave, ae)
			logging.Infof(c, "Add Assigner %s (rev %s)", ae.ID, rev)
		}
	}

	return datastore.Put(c, aesToSave)
}

// GetAssigner returns the Assigner entity matching with a given id.
func GetAssigner(c context.Context, aid string) (*Assigner, error) {
	ae := &Assigner{ID: aid}
	if err := datastore.Get(c, ae); err != nil {
		return nil, err
	}
	return ae, nil
}

// GetAllAssigners returns all the assigner entities.
func GetAllAssigners(c context.Context) ([]*Assigner, error) {
	var aes []*Assigner
	q := datastore.NewQuery("Assigner")
	if err := datastore.GetAll(c, q, &aes); err != nil {
		return nil, err
	}
	return aes, nil
}

// GetLiveAssigners returns all that are not marked as removed.
func GetLiveAssigners(c context.Context) ([]*Assigner, error) {
	all, err := GetAllAssigners(c)
	if err != nil {
		return nil, err
	}
	live := make([]*Assigner, 0, len(all))
	for _, ae := range all {
		if ae.Status != AssignerStatus_REMOVED {
			live = append(live, ae)
		}
	}

	return live, nil
}

// GenAssignerKey generates a datastore key for a given assigner object.
func GenAssignerKey(c context.Context, ae *Assigner) *datastore.Key {
	return datastore.KeyForObj(c, ae)
}
