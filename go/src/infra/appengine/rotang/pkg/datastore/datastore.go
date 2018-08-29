// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package datastore implements the Storer interface using Cloud Datastore.
package datastore

import (
	"time"

	"infra/appengine/rotang"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"go.chromium.org/gae/service/datastore"
	"golang.org/x/net/context"
)

const (
	rotaKind   = "DsRotaConfig"
	memberKind = "DsMember"
	rootKind   = "DsRoot"
	root       = "root"
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

// _ make sure Store confirms with the Storer and TokenStore interfaces.
var (
	_ rotang.ConfigStorer = &Store{}
	_ rotang.MemberStorer = &Store{}
)

// Store represents a datatore entity.
type Store struct {
}

func rootKey(ctx context.Context) *datastore.Key {
	return datastore.NewKey(ctx, rootKind, root, 0, datastore.KeyForObj(ctx, &DsRoot{ID: root}))
}

// New creates a new Datastore backed store.
func New(ctx context.Context) (*Store, error) {
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
		return nil, err
	}
	return &Store{}, nil
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

	return datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		for _, m := range rotation.Members {
			if _, err := s.Member(ctx, m.Email); err != nil {
				return err
			}
		}

		if err := datastore.Get(ctx, &cfg); err != nil {
			if err == datastore.ErrNoSuchEntity {
				return datastore.Put(ctx, &DsRotaConfig{
					Key:     rootKey(ctx),
					ID:      rotation.Config.Name,
					Cfg:     rotation.Config,
					Members: rotation.Members,
				})
			}
		}
		return status.Errorf(codes.AlreadyExists, "rota already exists")
	}, nil)
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

	return datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		if err := datastore.Get(ctx, &cfg); err != nil {
			return err
		}
		return datastore.Put(ctx, &DsRotaConfig{
			Key:     rootKey(ctx),
			ID:      rotation.Config.Name,
			Cfg:     rotation.Config,
			Members: rotation.Members,
		})
	}, nil)

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
	return datastore.Delete(ctx, &DsRotaConfig{
		Key: rootKey(ctx),
		ID:  name,
	}, children)
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
