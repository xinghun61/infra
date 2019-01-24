package datastore

import (
	"context"
	"infra/appengine/rotang"
	"net/http"

	"go.chromium.org/gae/service/datastore"
	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	gcal "google.golang.org/api/calendar/v3"
)

var (
	_ rotang.TokenStorer = &Store{}
)

// DsToken is used to store tokens in Datastore.
type DsToken struct {
	Key    *datastore.Key `gae:"$parent"`
	ID     string         `gae:"$id"`
	Config string
	Token  oauth2.Token
}

// CreateToken creates a new token in Datastore.
func (t *Store) CreateToken(ctx context.Context, id, config string, token *oauth2.Token) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if id == "" {
		return status.Errorf(codes.InvalidArgument, "id must be set")
	}
	if token == nil {
		return status.Errorf(codes.InvalidArgument, "token must be set")
	}

	dsToken := &DsToken{
		Key:    rootKey(ctx),
		ID:     id,
		Config: config,
		Token:  *token,
	}

	return datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		if err := datastore.Get(ctx, dsToken); err != nil {
			if err != datastore.ErrNoSuchEntity {
				return err
			}
			if err := datastore.Put(ctx, dsToken); err != nil {
				return err
			}
			return nil
		}
		return status.Errorf(codes.AlreadyExists, "token already exists")
	}, nil)
}

func (t *Store) dsToken(ctx context.Context, id string) (*DsToken, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}

	entry := DsToken{
		Key: rootKey(ctx),
		ID:  id,
	}

	if err := datastore.Get(ctx, &entry); err != nil {
		return nil, err
	}

	return &entry, nil
}

// Token fetches the requested token from Datastore.
func (t *Store) Token(ctx context.Context, id string) (*oauth2.Token, error) {
	dst, err := t.dsToken(ctx, id)
	if err != nil {
		if err == datastore.ErrNoSuchEntity {
			return nil, status.Errorf(codes.NotFound, "token for id: %q not found", id)
		}
		return nil, err
	}

	return &dst.Token, nil
}

// Client fetches the requested http.Client from Datastore.
func (t *Store) Client(ctx context.Context, id string) (*http.Client, error) {
	dst, err := t.dsToken(ctx, id)
	if err != nil {
		if err == datastore.ErrNoSuchEntity {
			return nil, status.Errorf(codes.NotFound, "token for id: %q not found", id)
		}
		return nil, err
	}
	if dst.Config == "" {
		return nil, status.Errorf(codes.FailedPrecondition, "no config entry exist for id: %q", id)
	}
	config, err := google.ConfigFromJSON([]byte(dst.Config), gcal.CalendarScope)
	if err != nil {
		return nil, err
	}
	return config.Client(ctx, &dst.Token), nil
}

// DeleteToken deletes the specified token from tokenstore.
func (t *Store) DeleteToken(ctx context.Context, id string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	return datastore.Delete(ctx, &DsToken{
		Key: rootKey(ctx),
		ID:  id,
	})
}
