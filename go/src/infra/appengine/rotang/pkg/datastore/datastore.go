// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package datastore implements the Storer interface using Cloud Datastore.
package datastore

import (
	"sort"
	"sync"
	"time"

	"infra/appengine/rotang"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
)

const (
	rotaKind   = "DsRotaConfig"
	memberKind = "DsMember"
	rootKind   = "DsRoot"
	root       = "root"
	changeKind = "DsConfigChange"
)

// DsRoot identifies the root of the Rota datastore.
type DsRoot struct {
	ID string `gae:"$id"`
}

// DsRotaConfig is used to store a RotaConfiguration in Datastore.
type DsRotaConfig struct {
	Key     *datastore.Key `gae:"$parent"`
	ID      string         `gae:"$id"`
	Cfg     rotang.Config
	Members []rotang.ShiftMember
}

// DsMember is used to store a rotang.Member in Datastore.
type DsMember struct {
	Key    *datastore.Key `gae:"$parent"`
	Email  string         `gae:"$id"`
	Member rotang.Member
	TZ     string
}

// DsConfigChange is used to store rotang.ConfigChange in Datastore.
type DsConfigChange struct {
	Key     *datastore.Key `gae:"$parent"`
	ID      int64          `gae:"$id"`
	At      time.Time
	Rota    string
	Type    rotang.ChangeType
	Who     string
	Cfg     rotang.Config
	Members []rotang.ShiftMember
}

// _ make sure Store confirms with the ConfigStorer and MemberStorer interfaces.
var (
	_ rotang.ConfigStorer = &Store{}
	_ rotang.MemberStorer = &Store{}
)

// Store represents a datastore entity.
type Store struct {
	user string
}

func rootKey(ctx context.Context) *datastore.Key {
	return datastore.NewKey(ctx, rootKind, root, 0, datastore.KeyForObj(ctx, &DsRoot{ID: root}))
}

var once sync.Once

// New creates a new Datastore backed store.
func New(ctx context.Context) *Store {
	once.Do(func() {
		root := &DsRoot{
			ID: root,
		}
		if err := datastore.RunInTransaction(ctx, func(ctx context.Context) error {
			if err := datastore.Get(ctx, root); err != nil {
				if err == datastore.ErrNoSuchEntity {
					return datastore.Put(ctx, root)
				}
				return err
			}
			return nil
		}, nil); err != nil {
			panic(err)
		}
	})
	return &Store{
		user: auth.CurrentUser(ctx).Email,
	}
}

// ChangeHistory returns the configuration change history for the specified rotation.
func (s *Store) ChangeHistory(ctx context.Context, from, to time.Time, rota string) ([]rotang.ConfigChange, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	from, to = from.UTC(), to.UTC()

	query := datastore.NewQuery(changeKind)

	var dsChanges []DsConfigChange
	switch {
	case to.IsZero() && from.IsZero():
		if err := datastore.GetAll(ctx, query, &dsChanges); err != nil {
			return nil, err
		}
	case from.IsZero():
		if err := datastore.GetAll(ctx, query.Lte("At", to), &dsChanges); err != nil {
			return nil, err
		}
	case to.IsZero():
		if err := datastore.GetAll(ctx, query.Gte("At", from), &dsChanges); err != nil {
			return nil, err
		}
	default:
		var tmpEntries []DsConfigChange
		if err := datastore.GetAll(ctx, query.Gte("At", from), &tmpEntries); err != nil {
			return nil, err
		}
		sort.Slice(tmpEntries, func(i, j int) bool {
			return tmpEntries[i].At.Before(tmpEntries[j].At)
		})
		for _, e := range tmpEntries {
			if e.At.After(to) {
				continue
			}
			dsChanges = append(dsChanges, e)
		}
	}

	var res []rotang.ConfigChange
	for _, c := range dsChanges {
		res = append(res, rotang.ConfigChange{
			At:   c.At,
			Rota: c.Rota,
			Type: c.Type,
			Who:  c.Who,
			Cfg: rotang.Configuration{
				Config:  c.Cfg,
				Members: c.Members,
			},
		})
	}
	return res, nil
}

func (s *Store) storeChange(ctx context.Context, at time.Time, tp rotang.ChangeType, cfg *rotang.Configuration) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if cfg == nil {
		return status.Errorf(codes.InvalidArgument, "cfg can can not be nil")
	}
	now := clock.Now(ctx).UTC()
	if tp == rotang.Delete {
		return datastore.Put(ctx, &DsConfigChange{
			Key:  rootKey(ctx),
			ID:   now.Unix(),
			At:   now,
			Rota: cfg.Config.Name,
			Type: tp,
			Who:  s.user,
		})
	}
	return datastore.Put(ctx, &DsConfigChange{
		Key:     rootKey(ctx),
		ID:      now.Unix(),
		At:      clock.Now(ctx).UTC(),
		Rota:    cfg.Config.Name,
		Type:    tp,
		Who:     s.user,
		Cfg:     cfg.Config,
		Members: cfg.Members,
	})
}

// Member fetches the matching Member from datastore.
func (s *Store) Member(ctx context.Context, email string) (*rotang.Member, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}

	if email == "" {
		return nil, status.Errorf(codes.InvalidArgument, "email needs to be set")
	}
	dsMember := &DsMember{
		Key:   rootKey(ctx),
		Email: email,
	}
	if err := datastore.Get(ctx, dsMember); err != nil {
		if err == datastore.ErrNoSuchEntity {
			return nil, status.Errorf(codes.NotFound, "member not found")
		}
		return nil, err
	}
	m, err := convertMembers([]DsMember{
		*dsMember,
	})
	if err != nil {
		return nil, err
	}
	if len(m) != 1 {
		return nil, status.Errorf(codes.NotFound, "wrong number of members returned from datastore")
	}
	member := m[0]
	return &member, nil
}

// AllMembers fetches all members from datastore.
func (s *Store) AllMembers(ctx context.Context) ([]rotang.Member, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	memberQuery := datastore.NewQuery(memberKind).Ancestor(rootKey(ctx))
	var dsMembers []DsMember
	if err := datastore.GetAll(ctx, memberQuery, &dsMembers); err != nil {
		return nil, err
	}
	if len(dsMembers) == 0 {
		return nil, status.Error(codes.NotFound, "no members in the pool")
	}
	return convertMembers(dsMembers)
}

// CreateMember stores a new member in datastore.
func (s *Store) CreateMember(ctx context.Context, member *rotang.Member) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if member.Email == "" {
		return status.Errorf(codes.InvalidArgument, "Email must be set")
	}
	dsMember := DsMember{
		Key:    rootKey(ctx),
		Email:  member.Email,
		Member: *member,
		TZ:     member.TZ.String(),
	}

	return datastore.RunInTransaction(ctx, func(ctx context.Context) error {

		if err := datastore.Get(ctx, &dsMember); err != datastore.ErrNoSuchEntity {
			if err != nil {
				return err
			}
			return status.Errorf(codes.AlreadyExists, "member key: %q already exist", member.Email)
		}
		return datastore.Put(ctx, &dsMember)
	}, nil)
}

// DeleteMember deletes a member from datastore.
func (s *Store) DeleteMember(ctx context.Context, email string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	return datastore.Delete(ctx, &DsMember{
		Key:   rootKey(ctx),
		Email: email,
	})
}

// UpdateMember updates an existing member.
func (s *Store) UpdateMember(ctx context.Context, member *rotang.Member) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if member.Email == "" {
		return status.Errorf(codes.InvalidArgument, "member Email must be set")
	}
	dsMember := DsMember{
		Key:   rootKey(ctx),
		Email: member.Email,
	}
	// Datastore needs times set to UTC.
	for i := range member.OOO {
		member.OOO[i].Start = member.OOO[i].Start.UTC()
	}
	return datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		if err := datastore.Get(ctx, &dsMember); err != nil {
			if err == datastore.ErrNoSuchEntity {
				return status.Errorf(codes.NotFound, "member: %q not found", dsMember.Email)
			}
			return err
		}
		return datastore.Put(ctx, &DsMember{
			Key:    rootKey(ctx),
			Email:  member.Email,
			Member: *member,
			TZ:     member.TZ.String(),
		})
	}, nil)
}

func convertMembers(dsMembers []DsMember) ([]rotang.Member, error) {
	var members []rotang.Member
	for _, m := range dsMembers {
		loc, err := time.LoadLocation(m.TZ)
		if err != nil {
			return nil, err
		}
		m.Member.TZ = *loc
		members = append(members, m.Member)
	}
	return members, nil
}

// CreateRotaConfig stores a rotang.Configuration in Datastore.
func (s *Store) CreateRotaConfig(ctx context.Context, rotation *rotang.Configuration) error {
	// The datastore doesn't seem to check the context so might as well do it here.
	if err := ctx.Err(); err != nil {
		return err
	}

	if rotation == nil {
		return status.Errorf(codes.InvalidArgument, "rotation can not be nil")
	}

	rotation.Config.Shifts.StartTime = rotation.Config.Shifts.StartTime.UTC()

	cfg := DsRotaConfig{
		Key:     rootKey(ctx),
		ID:      rotation.Config.Name,
		Cfg:     rotation.Config,
		Members: rotation.Members,
	}

	if err := datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		for _, m := range rotation.Members {
			if _, err := s.Member(ctx, m.Email); err != nil {
				return err
			}
		}

		if err := datastore.Get(ctx, &cfg); err != nil {
			if err == datastore.ErrNoSuchEntity {
				if err := datastore.Put(ctx, &cfg); err != nil {
					return err
				}
				return nil
			}
		}
		return status.Errorf(codes.AlreadyExists, "rota already exists")
	}, nil); err != nil {
		return err
	}
	if err := s.storeChange(ctx, clock.Now(ctx), rotang.Create, rotation); err != nil {
		logging.Warningf(ctx, "Storing ChangeHistory for: %q failed: %v", rotation.Config.Name, err)
	}
	return nil
}

// UpdateRotaConfig updates an existing Configuration entry.
func (s *Store) UpdateRotaConfig(ctx context.Context, rotation *rotang.Configuration) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	rotation.Config.Shifts.StartTime = rotation.Config.Shifts.StartTime.UTC()

	cfg := DsRotaConfig{
		Key: rootKey(ctx),
		ID:  rotation.Config.Name,
	}

	if err := datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		if err := datastore.Get(ctx, &cfg); err != nil {
			return err
		}
		if err := datastore.Put(ctx, &DsRotaConfig{
			Key:     rootKey(ctx),
			ID:      rotation.Config.Name,
			Cfg:     rotation.Config,
			Members: rotation.Members,
		}); err != nil {
			return err
		}
		return nil
	}, nil); err != nil {
		return err
	}
	if err := s.storeChange(ctx, clock.Now(ctx), rotang.Update, rotation); err != nil {
		logging.Warningf(ctx, "Storing ChangeHistory for: %q failed: %v", rotation.Config.Name, err)
	}
	return nil
}

// MemberOf returns the rotas the specified email is a member of.
func (s *Store) MemberOf(ctx context.Context, email string) ([]string, error) {
	cs, err := s.RotaConfig(ctx, "")
	if err != nil {
		return nil, err
	}
	var res []string
	for _, cfg := range cs {
		for _, m := range cfg.Members {
			if m.Email == email {
				res = append(res, cfg.Config.Name)
				break
			}
		}
	}
	return res, nil
}

// RotaConfig fetches the Rota specified in `name`. If name is left empty all the rotas in store is returned.
func (s *Store) RotaConfig(ctx context.Context, name string) ([]*rotang.Configuration, error) {
	// The datastore doesn't seem to check the context so migh as well do it here.
	if err := ctx.Err(); err != nil {
		return nil, err
	}

	var rotas []DsRotaConfig
	if name == "" {
		rotas = []DsRotaConfig{}
		query := datastore.NewQuery(rotaKind)
		if err := datastore.GetAll(ctx, query, &rotas); err != nil {
			return nil, err
		}
		if len(rotas) < 1 {
			return nil, status.Errorf(codes.NotFound, "no rotas found in Datastore")
		}
	}
	if len(rotas) < 1 {
		r := DsRotaConfig{
			Key: rootKey(ctx),
			ID:  name,
		}
		if err := datastore.Get(ctx, &r); err != nil {
			if err == datastore.ErrNoSuchEntity {
				return nil, status.Errorf(codes.NotFound, "rota: %q not found", name)
			}
			return nil, err
		}
		rotas = append(rotas, r)
	}

	var res []*rotang.Configuration
	for _, rotaCfg := range rotas {
		res = append(res, &rotang.Configuration{
			Config:  rotaCfg.Cfg,
			Members: rotaCfg.Members,
		})
	}
	return res, nil
}

// DeleteRotaConfig deletes the named rota.
func (s *Store) DeleteRotaConfig(ctx context.Context, name string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	key, err := datastore.KeyForObjErr(ctx, &DsRotaConfig{
		Key: rootKey(ctx),
		ID:  name,
	})
	if err != nil {
		return err
	}
	var children []DsMember
	if err := datastore.GetAll(ctx, datastore.NewQuery(memberKind).Ancestor(key), &children); err != nil {
		return err
	}
	if err := datastore.Delete(ctx, &DsRotaConfig{
		Key: rootKey(ctx),
		ID:  name,
	}, children); err != nil {
		return err
	}
	if err := s.storeChange(ctx, clock.Now(ctx), rotang.Delete, &rotang.Configuration{
		Config: rotang.Config{
			Name: name,
		},
	}); err != nil {
		logging.Warningf(ctx, "Storing ChangeHistory for: %q failed: %v", name, err)
	}
	return nil
}

// EnableRota enables jobs to consider the specified rotation.
func (s *Store) EnableRota(ctx context.Context, name string) error {
	return s.changeRotaState(ctx, name, true)
}

// DisableRota disables jobs for the specified rotation.
func (s *Store) DisableRota(ctx context.Context, name string) error {
	return s.changeRotaState(ctx, name, false)
}

// RotaEnabled returns the state of the specified rota.
func (s *Store) RotaEnabled(ctx context.Context, name string) (bool, error) {
	if err := ctx.Err(); err != nil {
		return false, err
	}

	cfg, err := s.RotaConfig(ctx, name)
	if err != nil {
		return false, err
	}

	if len(cfg) != 1 {
		return false, status.Errorf(codes.Internal, "unexpected number of configurations returned")
	}
	return cfg[0].Config.Enabled, nil

}

func (s *Store) changeRotaState(ctx context.Context, name string, state bool) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	cfg, err := s.RotaConfig(ctx, name)
	if err != nil {
		return err
	}
	if len(cfg) != 1 {
		return status.Errorf(codes.Internal, "unexpected number of configurations returned")
	}
	if cfg[0].Config.External {
		return status.Errorf(codes.InvalidArgument, "can't enable external rotation")
	}
	cfg[0].Config.Enabled = state
	return s.UpdateRotaConfig(ctx, cfg[0])
}

// AddRotaMember adds a members to the specified rota.
func (s *Store) AddRotaMember(ctx context.Context, rota string, member *rotang.ShiftMember) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	if _, err := s.Member(ctx, member.Email); err != nil {
		return err
	}

	cfg := DsRotaConfig{
		Key: rootKey(ctx),
		ID:  rota,
	}

	return datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		if err := datastore.Get(ctx, &cfg); err != nil {
			return err
		}
		for _, m := range cfg.Members {
			if m.Email == member.Email {
				return status.Errorf(codes.AlreadyExists, "member already exists")
			}
		}
		cfg.Members = append(cfg.Members, *member)

		return datastore.Put(ctx, &cfg)
	}, nil)
}

// DeleteRotaMember deletes a member in a rotang.
func (s *Store) DeleteRotaMember(ctx context.Context, rota, email string) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	if rota == "" || email == "" {
		return status.Errorf(codes.InvalidArgument, "rota and email must be set")
	}

	return datastore.RunInTransaction(ctx, func(ctx context.Context) error {

		cfg := DsRotaConfig{
			Key: rootKey(ctx),
			ID:  rota,
		}
		if err := datastore.Get(ctx, &cfg); err != nil {
			return err
		}
		for i, m := range cfg.Members {
			if m.Email == email {
				cfg.Members = append(cfg.Members[:i], cfg.Members[i+1:]...)
				return datastore.Put(ctx, &cfg)
			}

		}
		return status.Errorf(codes.NotFound, "member not found")
	}, nil)
}

// TestTable is used to setup a consistent table for testing.
func TestTable(ctx context.Context) {
	tt := datastore.GetTestable(ctx)
	tt.Consistent(true)
	tt.AutoIndex(true)
}
