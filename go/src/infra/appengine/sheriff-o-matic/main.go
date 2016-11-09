// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package som implements HTTP server that handles requests to default module.
package som

import (
	"bytes"
	"crypto/sha1"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"html/template"
	"io/ioutil"
	"net/http"
	"net/url"
	"strings"
	"time"

	"infra/monitoring/messages"
	"infra/monorail"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/info"
	"github.com/luci/gae/service/memcache"
	"github.com/luci/luci-go/appengine/gaeauth/server"
	"github.com/luci/luci-go/appengine/gaeauth/server/gaesigner"
	"github.com/luci/luci-go/appengine/gaemiddleware"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/identity"
	"github.com/luci/luci-go/server/auth/xsrf"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/settings"
)

const (
	authGroup           = "sheriff-o-matic-access"
	bugQueueCacheFormat = "bugqueue-%s"
	settingsKey         = "tree"
	// annotations will expire after this amount of time
	annotationExpiration  = time.Hour * 24 * 10
	productionAnalyticsID = "UA-55762617-1"
	stagingAnalyticsID    = "UA-55762617-22"
)

var (
	mainPage         = template.Must(template.ParseFiles("./index.html"))
	accessDeniedPage = template.Must(template.ParseFiles("./access-denied.html"))
	monorailEndpoint = "https://monorail-prod.appspot.com/_ah/api/monorail/v1/"
	jsErrors         = metric.NewCounter("frontend/js_errors",
		"Number of uncaught javascript errors.", nil)
)

var errStatus = func(c context.Context, w http.ResponseWriter, status int, msg string) {
	logging.Errorf(c, "Status %d msg %s", status, msg)
	w.WriteHeader(status)
	w.Write([]byte(msg))
}

// TrooperAlert ... Extended alert struct type for use in the trooper tab.
type TrooperAlert struct {
	messages.Alert
	Tree string `json:"tree"`
}

//// Handlers.
func indexPage(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params
	if p.ByName("path") == "" {
		http.Redirect(w, r, "/chromium", http.StatusFound)
		return
	}

	user := auth.CurrentIdentity(c)

	if user.Kind() == identity.Anonymous {
		url, err := auth.LoginURL(c, "/")
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf(
				"You must login. Additionally, an error was encountered while serving this request: %s", err.Error()))
		} else {
			http.Redirect(w, r, url, http.StatusFound)
		}

		return
	}

	isGoogler, err := auth.IsMember(c, authGroup)

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	logoutURL, err := auth.LogoutURL(c, "/")

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	if !isGoogler {
		err = accessDeniedPage.Execute(w, map[string]interface{}{
			"Group":     authGroup,
			"LogoutURL": logoutURL,
		})
		if err != nil {
			logging.Errorf(c, "while rendering index: %s", err)
		}
		return
	}

	tok, err := xsrf.Token(c)
	if err != nil {
		logging.Errorf(c, "while getting xrsf token: %s", err)
	}

	AnalyticsID := stagingAnalyticsID
	if !strings.HasSuffix(info.AppID(c), "-staging") {
		logging.Debugf(c, "Using production GA ID for app %s", info.AppID(c))
		AnalyticsID = productionAnalyticsID
	}

	data := map[string]interface{}{
		"User":           user.Email(),
		"LogoutUrl":      logoutURL,
		"IsDevAppServer": info.IsDevAppServer(c),
		"XsrfToken":      tok,
		"AnalyticsID":    AnalyticsID,
	}

	err = mainPage.Execute(w, data)
	if err != nil {
		logging.Errorf(c, "while rendering index: %s", err)
	}
}

func getTreesHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	q := datastore.NewQuery("Tree")
	results := []*Tree{}
	err := datastore.GetAll(c, q, &results)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	txt, err := json.Marshal(results)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(txt)
}

func getTrooperAlerts(c context.Context) ([]byte, error) {
	q := datastore.NewQuery("Tree")
	trees := []*Tree{}
	datastore.GetAll(c, q, &trees)

	result := make(map[string]interface{})
	alerts := []*TrooperAlert{}

	for _, t := range trees {
		q := datastore.NewQuery("AlertsJSON")
		q = q.Ancestor(datastore.MakeKey(c, "Tree", t.Name))
		q = q.Order("-Date")
		q = q.Limit(1)

		alertsJSON := []*AlertsJSON{}
		err := datastore.GetAll(c, q, &alertsJSON)
		if err != nil {
			return nil, err
		}

		if len(alertsJSON) > 0 {
			data := alertsJSON[0].Contents

			alertsSummary := &messages.AlertsSummary{}

			result["timestamp"] = alertsSummary.Timestamp
			result["revision_summaries"] = alertsSummary.RevisionSummaries
			result["date"] = alertsJSON[0].Date

			err = json.Unmarshal(data, alertsSummary)
			if err != nil {
				return nil, err
			}

			for _, a := range alertsSummary.Alerts {
				if a.Type == messages.AlertInfraFailure {
					newAlert := &TrooperAlert{a, t.Name}
					alerts = append(alerts, newAlert)
				}
			}
		}
	}

	result["alerts"] = alerts

	out, err := json.Marshal(result)

	if err != nil {
		return nil, err
	}

	return out, nil
}

func getAlertsHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	tree := p.ByName("tree")

	if tree == "trooper" {
		data, err := getTrooperAlerts(c)
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, err.Error())
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.Write(data)
		return
	}

	results := []*AlertsJSON{}
	q := datastore.NewQuery("AlertsJSON")
	q = q.Ancestor(datastore.MakeKey(c, "Tree", tree))
	q = q.Order("-Date")
	q = q.Limit(1)

	err := datastore.GetAll(c, q, &results)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	if len(results) == 0 {
		logging.Warningf(c, "No alerts found for tree %s", tree)
		errStatus(c, w, http.StatusNotFound, fmt.Sprintf("Tree \"%s\" not found", tree))
		return
	}

	alertsJSON := results[0]
	w.Header().Set("Content-Type", "application/json")
	w.Write(alertsJSON.Contents)
}

func postAlertsHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	tree := p.ByName("tree")

	alerts := AlertsJSON{
		Tree: datastore.MakeKey(c, "Tree", tree),
		Date: clock.Now(c),
	}
	data, err := ioutil.ReadAll(r.Body)
	if err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	if err := r.Body.Close(); err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	// Do a sanity check.
	alertsSummary := &messages.AlertsSummary{}
	err = json.Unmarshal(data, alertsSummary)
	if err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	if alertsSummary.Timestamp == 0 {
		errStatus(c, w, http.StatusBadRequest,
			"Couldn't decode into AlertsSummary or did not include a timestamp.")
		return
	}

	// Now actually do decoding necessary for storage.
	out := make(map[string]interface{})
	err = json.Unmarshal(data, &out)

	if err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	out["date"] = alerts.Date.String()
	data, err = json.Marshal(out)

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	alerts.Contents = data
	err = datastore.Put(c, &alerts)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}
}

func getAnnotationsHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	q := datastore.NewQuery("Annotation")
	results := []*Annotation{}
	datastore.GetAll(c, q, &results)

	data, err := json.Marshal(results)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}

type postRequest struct {
	XSRFToken string           `json:"xsrf_token"`
	Data      *json.RawMessage `json:"data"`
}

func postAnnotationsHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	annKey := p.ByName("annKey")
	action := p.ByName("action")

	if !(action == "add" || action == "remove") {
		errStatus(c, w, http.StatusNotFound, "Invalid action")
		return
	}

	req := &postRequest{}
	err := json.NewDecoder(r.Body).Decode(req)
	if err != nil {
		errStatus(c, w, http.StatusBadRequest, fmt.Sprintf("while decoding request: %s", err))
		return
	}

	if err := xsrf.Check(c, req.XSRFToken); err != nil {
		errStatus(c, w, http.StatusForbidden, err.Error())
		return
	}

	annotation := &Annotation{
		KeyDigest: fmt.Sprintf("%x", sha1.Sum([]byte(annKey))),
		Key:       annKey,
	}

	err = datastore.Get(c, annotation)
	if action == "remove" && err != nil {
		logging.Errorf(c, "while getting %s: %s", annKey, err)
		errStatus(c, w, http.StatusNotFound, fmt.Sprintf("Annotation %s not found", annKey))
		return
	}
	// The annotation probably doesn't exist if we're adding something

	data := bytes.NewReader([]byte(*req.Data))
	if action == "add" {
		err = annotation.add(c, data)
	} else if action == "remove" {
		err = annotation.remove(c, data)
	}

	if err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	err = r.Body.Close()
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	err = datastore.Put(c, annotation)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	resp, err := json.Marshal(annotation)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(resp)
}

func flushOldAnnotationsHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	numDeleted, err := flushOldAnnotations(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	s := fmt.Sprintf("deleted %d annotations", numDeleted)
	logging.Debugf(c, s)
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(s))
}

func flushOldAnnotations(c context.Context) (int, error) {
	q := datastore.NewQuery("Annotation")
	q = q.Lt("ModificationTime", clock.Get(c).Now().Add(-annotationExpiration))
	q = q.KeysOnly(true)

	results := []*Annotation{}
	err := datastore.GetAll(c, q, &results)
	if err != nil {
		return 0, fmt.Errorf("while fetching annotations to delete: %s", err)
	}

	for _, ann := range results {
		logging.Debugf(c, "Deleting %#v\n", ann)
	}

	err = datastore.Delete(c, results)
	if err != nil {
		return 0, fmt.Errorf("while deleting annotations: %s", err)
	}

	return len(results), nil
}

func getBugQueueHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	label := p.ByName("label")

	key := fmt.Sprintf(bugQueueCacheFormat, label)

	item, err := memcache.GetKey(c, key)

	if err == memcache.ErrCacheMiss {
		logging.Debugf(c, "No bug queue data for %s in memcache, refreshing...", label)
		item, err = refreshBugQueue(c, label)
	}

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(item.Value())
}

func refreshBugQueue(c context.Context, label string) (memcache.Item, error) {
	// Get authenticated monorail client.
	client, err := getOAuthClient(c)

	if err != nil {
		return nil, err
	}

	mr := monorail.NewEndpointsClient(client, monorailEndpoint)

	q := fmt.Sprintf("label:%s", label)
	if label == "infra-troopers" {
		user := auth.CurrentIdentity(c)
		email := getAlternateEmail(user.Email())
		q = fmt.Sprintf(`Infra=Troopers -has:owner OR owner:%s Infra=Troopers
			OR owner:%s Infra=Troopers`, user.Email(), email)
	}

	// TODO(martiniss): make this look up request info based on Tree datastore
	// object
	req := &monorail.IssuesListRequest{
		ProjectId: "chromium",
		Can:       monorail.IssuesListRequest_OPEN,
		Q:         q,
	}

	before := clock.Now(c)

	res, err := mr.IssuesList(c, req)
	if err != nil {
		return nil, err
	}

	logging.Debugf(c, "Fetch to monorail took %v. Got %d bugs.", clock.Now(c).Sub(before), res.TotalResults)

	bytes, err := json.Marshal(res)
	if err != nil {
		return nil, err
	}

	key := fmt.Sprintf(bugQueueCacheFormat, label)

	item := memcache.NewItem(c, key).SetValue(bytes)

	err = memcache.Set(c, item)

	if err != nil {
		return nil, err
	}

	return item, nil
}

func refreshBugQueueHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params
	label := p.ByName("label")
	item, err := refreshBugQueue(c, label)

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(item.Value())
}

// Switches chromium.org emails for google.com emails and vice versa.
// Note that chromium.org emails may be different from google.com emails.
func getAlternateEmail(email string) string {
	s := strings.Split(email, "@")
	if len(s) != 2 {
		return email
	}

	user, domain := s[0], s[1]
	if domain == "chromium.org" {
		return fmt.Sprintf("%s@google.com", user)
	}
	return fmt.Sprintf("%s@chromium.org", user)
}

func getCrRevJSON(c context.Context, pos string) (map[string]string, error) {
	hc, err := getOAuthClient(c)
	if err != nil {
		return nil, err
	}

	resp, err := hc.Get(fmt.Sprintf("https://cr-rev.appspot.com/_ah/api/crrev/v1/redirect/%s", pos))
	if err != nil {
		return nil, err
	}

	defer resp.Body.Close()
	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	m := map[string]string{}
	err = json.Unmarshal(body, &m)
	if err != nil {
		return nil, err
	}

	return m, nil
}

func getRevRangeHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	start := p.ByName("start")
	end := p.ByName("end")
	if start == "" || end == "" {
		errStatus(c, w, http.StatusBadRequest, "Start and end parameters must be set.")
		return
	}

	startRev, err := getCrRevJSON(c, start)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	endRev, err := getCrRevJSON(c, end)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	// TODO(seanmccullough): some sanity checking of the rev json (same repo etc)

	gitilesURL := fmt.Sprintf("https://chromium.googlesource.com/chromium/src/+log/%s^..%s?format=JSON",
		startRev["git_sha"], endRev["git_sha"])

	http.Redirect(w, r, gitilesURL, 301)
}

type eCatcherReq struct {
	Errors    map[string]int64 `json:"errors"`
	XSRFToken string           `json:"xsrf_token"`
}

func postClientMonHandler(ctx *router.Context) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request

	req := &eCatcherReq{}
	if err := json.NewDecoder(r.Body).Decode(req); err != nil {
		errStatus(c, w, http.StatusBadRequest, err.Error())
		return
	}

	if err := xsrf.Check(c, req.XSRFToken); err != nil {
		errStatus(c, w, http.StatusForbidden, err.Error())
		return
	}

	for _, errCount := range req.Errors {
		jsErrors.Add(c, errCount)
	}
	logging.Errorf(c, "clientmon report: %v", req.Errors)
}

func getTreeLogoHandler(ctx *router.Context) {
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

// getOAuthClient returns a client capable of making HTTP requests authenticated
// with OAuth access token for userinfo.email scope.
var getOAuthClient = func(c context.Context) (*http.Client, error) {
	// Note: "https://www.googleapis.com/auth/userinfo.email" is the default
	// scope used by GetRPCTransport(AsSelf). Use auth.WithScopes(...) option to
	// override.
	t, err := auth.GetRPCTransport(c, auth.AsSelf)
	if err != nil {
		return nil, err
	}
	return &http.Client{Transport: t}, nil
}

// base is the root of the middleware chain.
func base(includeCookie bool) router.MiddlewareChain {
	methods := []auth.Method{
		&server.OAuth2Method{Scopes: []string{server.EmailScope}},
		&server.InboundAppIDAuthMethod{},
	}
	if includeCookie {
		methods = append(methods, server.CookieAuth)
	}

	return gaemiddleware.BaseProd().Extend(
		auth.Use(methods),
		auth.Authenticate,
	)
}

func requireGoogler(c *router.Context, next router.Handler) {
	isGoogler, err := auth.IsMember(c.Context, authGroup)
	switch {
	case err != nil:
		errStatus(c.Context, c.Writer, http.StatusInternalServerError, err.Error())
	case !isGoogler:
		errStatus(c.Context, c.Writer, http.StatusForbidden, "Access denied")
	default:
		next(c)
	}
}

func noopHandler(ctx *router.Context) {
	return
}

//// Routes.
func init() {

	settings.RegisterUIPage(settingsKey, settingsUIPage{})

	r := router.New()
	basemw := base(true)

	protected := basemw.Extend(requireGoogler)

	gaemiddleware.InstallHandlers(r, gaemiddleware.BaseProd())
	r.GET("/api/v1/trees/", protected, getTreesHandler)
	r.GET("/api/v1/alerts/:tree", protected, getAlertsHandler)
	r.GET("/api/v1/pubsubalerts/:tree", protected, getPubSubAlertsHandler)

	// Disallow cookies because this handler should not be accessible by regular
	// users.
	r.POST("/api/v1/alerts/:tree", base(false), postAlertsHandler)
	r.GET("/api/v1/annotations/", protected, getAnnotationsHandler)
	r.POST("/api/v1/annotations/:annKey/:action", protected, postAnnotationsHandler)
	r.GET("/api/v1/bugqueue/:label", protected, getBugQueueHandler)
	r.GET("/api/v1/revrange/:start/:end", basemw, getRevRangeHandler)
	r.GET("/logos/:tree", protected, getTreeLogoHandler)
	r.GET("/_cron/refresh/bugqueue/:label", basemw, refreshBugQueueHandler)
	r.GET("/_cron/annotations/flush_old/", basemw, flushOldAnnotationsHandler)
	r.POST("/_/clientmon", basemw, postClientMonHandler)
	r.POST("/_ah/push-handlers/milo", basemw, postMiloPubSubHandler)

	// Ingore reqeuests from builder-alerts rather than 404.
	r.GET("/alerts", gaemiddleware.BaseProd(), noopHandler)
	r.POST("/alerts", gaemiddleware.BaseProd(), noopHandler)

	rootRouter := router.New()
	rootRouter.GET("/*path", basemw, indexPage)

	http.DefaultServeMux.Handle("/_cron/", r)
	http.DefaultServeMux.Handle("/api/", r)
	http.DefaultServeMux.Handle("/admin/", r)
	http.DefaultServeMux.Handle("/auth/", r)
	http.DefaultServeMux.Handle("/_ah/", r)
	http.DefaultServeMux.Handle("/internal/", r)
	http.DefaultServeMux.Handle("/_/", r)
	http.DefaultServeMux.Handle("/logos/", r)
	http.DefaultServeMux.Handle("/alerts", r)

	http.DefaultServeMux.Handle("/", rootRouter)
}
