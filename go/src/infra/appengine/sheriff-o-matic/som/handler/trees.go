// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handler

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	"golang.org/x/net/context"

	"infra/appengine/sheriff-o-matic/som/model"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/appengine/gaeauth/server/gaesigner"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
)

// GetTrees retrieves all trees from the DataStore.
func GetTrees(c context.Context) ([]byte, error) {
	q := datastore.NewQuery("Tree")
	trees := []*model.Tree{}
	err := datastore.GetAll(c, q, &trees)
	if err != nil {
		return nil, err
	}
	bytes, err := json.Marshal(trees)
	if err != nil {
		return nil, err
	}
	return bytes, nil
}

// GetTreeLogoHandler returns a signed URL to an image asset hosted on GCS.
func GetTreeLogoHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	sa, err := info.ServiceAccount(c)
	if err != nil {
		logging.Errorf(c, "failed to get service account: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	getTreeLogo(ctx, sa, gaesigner.Signer{})
}

type signer interface {
	SignBytes(c context.Context, b []byte) (string, []byte, error)
}

func getTreeLogo(ctx *router.Context, sa string, sign signer) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params
	tree := p.ByName("tree")
	resource := fmt.Sprintf("/%s.appspot.com/logos/%s.png", info.AppID(c), tree)
	expStr := fmt.Sprintf("%d", time.Now().Add(10*time.Minute).Unix())
	sl := []string{
		"GET",
		"", // Optional MD5, which we don't have.
		"", // Content type, ommitted because it breaks the signature.
		expStr,
		resource,
	}
	unsigned := strings.Join(sl, "\n")
	_, b, err := sign.SignBytes(c, []byte(unsigned))
	if err != nil {
		logging.Errorf(c, "failed to sign bytes: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}
	sig := base64.StdEncoding.EncodeToString(b)
	params := url.Values{
		"GoogleAccessId": {sa},
		"Expires":        {expStr},
		"Signature":      {sig},
	}

	signedURL := fmt.Sprintf("https://storage.googleapis.com%s?%s", resource, params.Encode())
	http.Redirect(w, r, signedURL, http.StatusFound)
}
