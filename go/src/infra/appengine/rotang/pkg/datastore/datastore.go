// Package datastore implements the Storer interface using Cloud Datastore.
package datastore

import (
	"context"
	"time"

	"infra/appengine/rotang/pkg/rotang"

	"golang.org/x/oauth2"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"go.chromium.org/gae/service/datastore"
)

const (
	rotaKind       = "DsRotaConfig"
	memberKind     = "DsMember"
	shiftKind      = "DsShifts"
	shiftEntryKind = "DsShiftEntry"
	memberOOOKind  = "DsOOOMember"
)

// DsRotaConfig is used to store a RotaConfiguration in Datastore.
type DsRotaConfig struct {
	ID  string `gae:"$id"`
	Cfg rotang.Config
}

// DsMember is used to store a rotang.Member in Datastore.
type DsMember struct {
	Key    *datastore.Key `gae:"$parent"`
	Email  string         `gae:"$id"`
	Member rotang.Member
	TZ     string
}

// DsToken is used to store oauth2 tokens in Datastore.
type DsToken struct {
	Email string `gae:"$id"`
	Token oauth2.Token
}

// DsShifts is used to store rotang.Shifs in Datastore.
type DsShifts struct {
	Name string `gae:"$id"`
}

// DsOOOMember is used to store OOO information in Datastore.
type DsOOOMember struct {
	Idx    int
	Key    *datastore.Key `gae:"$parent"`
	Email  string         `gae:"$id"`
	Member rotang.Member
	TZ     string
}

// DsShiftEntry is the Datastore representation of rotang.ShiftEntry.
type DsShiftEntry struct {
	Key       *datastore.Key `gae:"$parent"`
	Name      string
	ID        string `gae:"$id"`
	StartTime time.Time
	EndTime   time.Time
	Comment   string
}

// _ make sure Store confirms with the Storer and TokenStore interfaces.
var (
	_ rotang.ConfigStorer = &Store{}
)

// Store represents a datatore entity.
type Store struct {
}

// New creates a new Datastore backed store.
func New() *Store {
	return &Store{}
}

// StoreRotaConfig stores a rotang.Configuration in Datastore.
func (s *Store) StoreRotaConfig(ctx context.Context, rotation *rotang.Configuration) error {
	// The datastore doesn't seem to check the context so might as well do it here.
	if err := ctx.Err(); err != nil {
		return err
	}
	rotation.Config.Shifts.StartTime = rotation.Config.Shifts.StartTime.UTC()
	// The datastore Flattening can't handle slices of structs inside of structs.
	// To handle this the members are put in separate with the configuration as the parent.
	rotaCfg := DsRotaConfig{
		ID:  rotation.Config.Name,
		Cfg: rotation.Config,
	}
	var dsMembers []DsMember
	for _, member := range rotation.Rotation.Members {
		dsMembers = append(dsMembers, DsMember{
			Key:    datastore.NewKey(ctx, rotaKind, rotaCfg.ID, 0, nil),
			Email:  member.Email,
			Member: member,
			TZ:     member.TZ.String(),
		})
	}
	return datastore.Put(ctx, &rotaCfg, dsMembers)
}

// FetchRotaConfig fetches the Rota specified in `name`. If name is left empty all the rotas in store is returned.
func (s *Store) FetchRotaConfig(ctx context.Context, name string) ([]*rotang.Configuration, error) {
	// The datastore doesn't seem to check the context so might as well do it here.
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
			ID: name,
		}
		if err := datastore.Get(ctx, &r); err != nil {
			return nil, err
		}
		rotas = append(rotas, r)
	}

	var res []*rotang.Configuration
	for _, rotaCfg := range rotas {

		queryMembers := datastore.NewQuery(memberKind).Ancestor(datastore.KeyForObj(ctx, &rotaCfg))

		var dsMembers []DsMember
		if err := datastore.GetAll(ctx, queryMembers, &dsMembers); err != nil {
			return nil, err
		}

		var rotaMembers []rotang.Member
		for _, member := range dsMembers {
			loc, err := time.LoadLocation(member.TZ)
			if err != nil {
				return nil, err
			}
			member.Member.TZ = *loc
			rotaMembers = append(rotaMembers, member.Member)
		}
		res = append(res, &rotang.Configuration{
			Config: rotaCfg.Cfg,
			Rotation: rotang.Members{
				Members: rotaMembers,
			},
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
		ID: name,
	})
	if err != nil {
		return err
	}
	var children []DsMember
	if err := datastore.GetAll(ctx, datastore.NewQuery(memberKind).Ancestor(key), &children); err != nil {
		return err
	}
	return datastore.Delete(ctx, &DsRotaConfig{
		ID: name,
	}, children)
}

// AddMember adds a members to the specified rotang.
func (s *Store) AddMember(ctx context.Context, rota string, member rotang.Member) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	if err := datastore.Get(ctx, &DsRotaConfig{
		ID: rota,
	}); err != nil {
		return err
	}
	return datastore.Put(ctx, &DsMember{
		Key:    datastore.NewKey(ctx, rotaKind, rota, 0, nil),
		Email:  member.Email,
		TZ:     member.TZ.String(),
		Member: member,
	})
}

// DeleteMember deletes a member in a rotang.
func (s *Store) DeleteMember(ctx context.Context, rota, email string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	return datastore.Delete(ctx, &DsMember{
		Key:   datastore.NewKey(ctx, rotaKind, rota, 0, nil),
		Email: email,
	})
}

// TestTable is used to setup a consistent table for testing.
func TestTable(ctx context.Context) {
	tt := datastore.GetTestable(ctx)
	tt.Consistent(true)
	tt.AutoIndex(true)
}
