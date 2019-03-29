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
	"go.chromium.org/luci/common/errors"
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

	// IsDrained specifies if the assigner has been drained.
	//
	// If an assigner is drained, no tasks are scheduled and run for
	// the assigner.
	IsDrained bool

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

	return true
}

// UpdateAssigners update all the Assigner entities, on presumed valid configs.
//
// For removed configs, the Assigner entities are marked as removed.
// For new configs, new Assigner entities are created.
// For updated configs, the Assigner entities are updated, based on the updated
// content.
func UpdateAssigners(c context.Context, cfgs []*config.Assigner, rev string) error {
	aes, err := GetAllAssigners(c)
	if err != nil {
		return err
	}
	aeMap := make(map[string]*Assigner, len(aes))
	for _, ae := range aes {
		aeMap[ae.ID] = ae
	}

	merr := errors.MultiError(nil)
	// update or create new ones.
	for _, cfg := range cfgs {
		if ae, exist := aeMap[cfg.Id]; exist {
			delete(aeMap, cfg.Id)
			// optimization for common case when no updates are
			// necessary.
			if !ae.updateIfChanged(cfg, rev) {
				continue
			}
		}

		err := datastore.RunInTransaction(c, func(c context.Context) error {
			ae := Assigner{ID: cfg.Id}
			if err := datastore.Get(c, &ae); err != nil &&
				err != datastore.ErrNoSuchEntity {
				// likely transient flake
				return err
			}

			if ae.updateIfChanged(cfg, rev) {
				logging.Debugf(
					c, "Update/Insert Assigner %s (rev %s)",
					cfg.Id, rev,
				)
				return datastore.Put(c, &ae)
			}
			return nil
		}, &datastore.TransactionOptions{})
		if err != nil {
			merr = append(merr, err)
		}
	}

	// remove ones without configs.
	for id, ae := range aeMap {
		logging.Infof(c, "Delete Assigner %s (rev %s)", id, rev)
		if err := datastore.Delete(c, ae); err != nil {
			merr = append(merr, err)
		}
	}

	if merr != nil {
		return merr
	}
	return nil
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

// GenAssignerKey generates a datastore key for a given assigner object.
func GenAssignerKey(c context.Context, ae *Assigner) *datastore.Key {
	return datastore.KeyForObj(c, ae)
}
