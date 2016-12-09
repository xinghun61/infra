package som

import (
	"encoding/base64"
	"fmt"
	"io/ioutil"
	"net/http"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/memcache"
	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/appengine/gaeauth/client"
	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/logging"
)

var (
	gitilesScope       = "https://www.googleapis.com/auth/gerritcodereview"
	gitilesCachePrefix = "gitiles:"
)

func getGitilesCached(c context.Context, URL string) ([]byte, error) {
	item, err := memcache.GetKey(c, gitilesCachePrefix+URL)
	if err != nil && err != memcache.ErrCacheMiss {
		return nil, err
	}

	var b []byte
	if err == memcache.ErrCacheMiss {
		b, err = getGitiles(c, URL)
		if err != nil {
			return nil, err
		}

		item = memcache.NewItem(c, gitilesCachePrefix+URL).SetValue(b).SetExpiration(5 * time.Minute)
		err = memcache.Set(c, item)
	}

	if err != nil {
		return nil, err
	}

	return item.Value(), nil
}

// TODO(seanmccullough): refactor this into one of our shared packages.
func getGitiles(c context.Context, URL string) ([]byte, error) {
	token, err := client.GetAccessToken(c, []string{gitilesScope})
	if err != nil {
		logging.Errorf(c, "getting access token: %v", err)
		return nil, err
	}

	trans := auth.NewModifyingTransport(urlfetch.Get(c), func(req *http.Request) error {
		req.Header.Add("Authorization", fmt.Sprintf("Bearer %s", token.AccessToken))
		return nil
	})

	client := &http.Client{Transport: trans}

	resp, err := client.Get(URL)
	if err != nil {
		logging.Errorf(c, "getting URL: %v", err)
		return nil, err
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP status code %d from %s", resp.StatusCode, resp.Request.URL)
	}

	defer resp.Body.Close()

	// This is currently only used for fetching gitiles files with ?format=text,
	// which will returq the body base64 encoded. Response headers don't indicate
	// this encoding (sigh) so we may need to some extra logic here to make this
	// decoding conditional on some other heuristic, like request parameters.
	reader := base64.NewDecoder(base64.StdEncoding, resp.Body)
	b, err := ioutil.ReadAll(reader)
	if err != nil {
		return nil, err
	}
	return b, nil
}
