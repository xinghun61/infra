package datastore

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/luci/server/router"
	"golang.org/x/oauth2"
)

func TestTokenCreate(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name     string
		fail     bool
		ctx      context.Context
		config   string
		token    *oauth2.Token
		id       string
		existing []DsToken
	}{{
		name: "Canceled context",
		fail: true,
		ctx:  ctxCancel,
	}, {
		name: "No ID",
		fail: true,
		ctx:  ctx,
	}, {
		name: "Already Exists",
		fail: true,
		ctx:  ctx,
		existing: []DsToken{{
			ID:    "test ID",
			Token: oauth2.Token{},
		},
		},
		id:    "test ID",
		token: &oauth2.Token{},
	}, {
		name: "No token",
		fail: true,
		ctx:  ctx,
		existing: []DsToken{{
			ID:    "test ID",
			Token: oauth2.Token{},
		},
		},
		id: "test ID",
	}, {
		name:  "Success",
		ctx:   ctx,
		id:    "New Token",
		token: &oauth2.Token{},
	},
	}

	tokenStore := &Store{}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, e := range tst.existing {
				if err := tokenStore.CreateToken(ctx, e.ID, e.Config, &e.Token); err != nil {
					t.Fatalf("%s: CreateToken(ctx, %q, %q, _) failed: %v", tst.name, e.ID, e.Config, err)
				}
				defer tokenStore.DeleteToken(ctx, e.ID)
			}
			err := tokenStore.CreateToken(tst.ctx, tst.id, tst.config, tst.token)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: CreateToken(ctx, %q, %q, _) = %t, want: %t, err: %v", tst.name, tst.id, tst.config, got, want, err)
			}
		})
	}
}

func TestToken(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name     string
		fail     bool
		ctx      context.Context
		token    *oauth2.Token
		id       string
		existing []DsToken
	}{{
		name: "Canceled context",
		fail: true,
		ctx:  ctxCancel,
	}, {
		name: "No ID",
		fail: true,
		ctx:  ctx,
	}, {
		name: "Success",
		ctx:  ctx,
		id:   "Test Token",
		existing: []DsToken{
			{
				ID: "Test Token",
				Token: oauth2.Token{
					AccessToken:  "testAccess",
					TokenType:    "testToken",
					RefreshToken: "testRefresh",
					Expiry:       midnight,
				},
			},
		},
		token: &oauth2.Token{
			AccessToken:  "testAccess",
			TokenType:    "testToken",
			RefreshToken: "testRefresh",
			Expiry:       midnight,
		},
	},
	}

	tokenStore := &Store{}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, e := range tst.existing {
				if err := tokenStore.CreateToken(ctx, e.ID, e.Config, &e.Token); err != nil {
					t.Fatalf("%s: CreateToken(ctx, %q, %q, _) failed: %v", tst.name, e.ID, e.Config, err)
				}
				defer tokenStore.DeleteToken(ctx, e.ID)
			}
			token, err := tokenStore.Token(tst.ctx, tst.id)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: Token(ctx, %q) = %t, want: %t, err: %v", tst.name, tst.id, got, want, err)
			}
			if err != nil {
				return
			}
			if diff := pretty.Compare(tst.token, token); diff != "" {
				t.Fatalf("%s: Token(ctx, %q) differ -want +got, %s", tst.name, tst.id, diff)
			}
		})
	}
}

func TestTokenClient(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name     string
		fail     bool
		ctx      *router.Context
		token    *oauth2.Token
		client   *http.Client
		id       string
		existing []DsToken
	}{{
		name: "Canceled context",
		fail: true,
		ctx: &router.Context{
			Request: httptest.NewRequest("GET", "/", nil),
			Context: ctxCancel,
		},
	}, {
		name: "No ID",
		fail: true,
		ctx: &router.Context{
			Request: httptest.NewRequest("GET", "/", nil),
			Context: ctx,
		},
	}, {
		name: "No config entry",
		fail: true,
		ctx: &router.Context{
			Request: httptest.NewRequest("GET", "/", nil),
			Context: ctx,
		},
		id: "Test Token",
		existing: []DsToken{
			{
				ID: "Test Token",
				Token: oauth2.Token{
					AccessToken:  "testAccess",
					TokenType:    "testToken",
					RefreshToken: "testRefresh",
					Expiry:       midnight,
				},
			},
		},
		token: &oauth2.Token{
			AccessToken:  "testAccess",
			TokenType:    "testToken",
			RefreshToken: "testRefresh",
			Expiry:       midnight,
		},
	}, {
		name: "Broken config",
		fail: true,
		ctx: &router.Context{
			Request: httptest.NewRequest("GET", "/", nil),
			Context: ctx,
		},
		id: "Test Token",
		existing: []DsToken{
			{
				ID: "Test Token",
				Token: oauth2.Token{
					AccessToken:  "testAccess",
					TokenType:    "testToken",
					RefreshToken: "testRefresh",
					Expiry:       midnight,
				},
				Config: "Should not parse",
			},
		},
		token: &oauth2.Token{
			AccessToken:  "testAccess",
			TokenType:    "testToken",
			RefreshToken: "testRefresh",
			Expiry:       midnight,
		},
	}, {
		name: "Success",
		ctx: &router.Context{
			Request: httptest.NewRequest("GET", "/", nil),
			Context: ctx,
		},
		id: "Test Token",
		existing: []DsToken{
			{
				ID: "Test Token",
				Token: oauth2.Token{
					AccessToken:  "testAccess",
					TokenType:    "testToken",
					RefreshToken: "testRefresh",
					Expiry:       midnight,
				},
				Config: `{"web":
					{"client_id":"non-exist",
						"project_id":"test_id",
						"auth_uri":"https://accounts.google.com/o/oauth2/auth",
						"token_uri":"https://accounts.google.com/o/oauth2/token",
						"auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",
						"client_secret":"superSecret",
						"redirect_uris":["http://localhost:8080/oauth2callback","https://leCallback/oauth2callback","http://leCallback/oauth2callback"]}}`,
			},
		},
		token: &oauth2.Token{
			AccessToken:  "testAccess",
			TokenType:    "testToken",
			RefreshToken: "testRefresh",
			Expiry:       midnight,
		},
	},
	}

	tokenStore := &Store{}

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			for _, e := range tst.existing {
				if err := tokenStore.CreateToken(ctx, e.ID, e.Config, &e.Token); err != nil {
					t.Fatalf("%s: CreateToken(ctx, %q, %q, _) failed: %v", tst.name, e.ID, e.Config, err)
				}
				defer tokenStore.DeleteToken(ctx, e.ID)
			}
			_, err := tokenStore.Client(tst.ctx, tst.id)
			if got, want := (err != nil), tst.fail; got != want {
				t.Fatalf("%s: Client(ctx, %q) = %t, want: %t, err: %v", tst.name, tst.id, got, want, err)
			}
		})
	}
}
