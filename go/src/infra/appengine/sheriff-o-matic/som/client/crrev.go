package client

import (
	"encoding/json"
	"fmt"
	"io/ioutil"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/memcache"
)

type crRev simpleClient

// GetRedirect gets the redirect for a commit position.
func (cr *crRev) GetRedirect(c context.Context, pos string) (map[string]string, error) {
	itm := memcache.NewItem(c, fmt.Sprintf("crrev:%s", pos))
	err := memcache.Get(c, itm)

	if err == memcache.ErrCacheMiss {
		hc, err := getAsSelfOAuthClient(c)
		if err != nil {
			return nil, err
		}

		resp, err := hc.Get(fmt.Sprintf(cr.Host+"/_ah/api/crrev/v1/redirect/%s", pos))
		if err != nil {
			return nil, err
		}

		defer resp.Body.Close()
		body, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			return nil, err
		}
		itm.SetValue(body)
		if err = memcache.Set(c, itm); err != nil {
			return nil, fmt.Errorf("while setting memcache: %s", err)
		}
	} else if err != nil {
		return nil, fmt.Errorf("while getting from memcache: %s", err)
	}

	m := map[string]string{}
	err = json.Unmarshal(itm.Value(), &m)
	if err != nil {
		return nil, err
	}

	return m, nil
}

// WithCrRev registers a crrev client with the context.
func WithCrRev(c context.Context, baseURL string) context.Context {
	cr := &crRev{Host: baseURL, Client: nil}
	c = context.WithValue(c, crRevKey, cr)
	return c
}

// GetCrRev creturns the crrev client previously registered with the context,
// or panics.
func GetCrRev(c context.Context) *crRev {
	ret, ok := c.Value(crRevKey).(*crRev)
	if !ok {
		panic("No crrev client set in context")
	}
	return ret
}
