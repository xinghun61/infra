package who

import (
	"encoding/json"
	"fmt"
	"html/template"
	"net/http"
	"sort"
	"strings"
	"time"

	"golang.org/x/net/context"

	"infra/monorail"

	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/common/auth/identity"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"

	gerrit "github.com/andygrunwald/go-gerrit"
)

const (
	authGroup = "chromium-who-access"
)

var (
	mainPage         = template.Must(template.ParseFiles("./index.html"))
	accessDeniedPage = template.Must(template.ParseFiles("./access-denied.html"))
)

func base(includeCookie bool) router.MiddlewareChain {
	a := auth.Authenticator{
		Methods: []auth.Method{
			&server.OAuth2Method{Scopes: []string{server.EmailScope}},
			&server.InboundAppIDAuthMethod{},
		},
	}
	if includeCookie {
		a.Methods = append(a.Methods, server.CookieAuth)
	}
	return standard.Base().Extend(a.GetMiddleware())
}

var errStatus = func(c context.Context, w http.ResponseWriter, status int, msg string) {
	logging.Errorf(c, "Status %d msg %s", status, msg)
	w.WriteHeader(status)
	w.Write([]byte(msg))
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

func indexPage(ctx *router.Context) {
	c, w, r, _ := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

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

	data := map[string]string{
		"User":      user.Email(),
		"LogoutUrl": logoutURL,
	}

	if !isGoogler {
		err = accessDeniedPage.Execute(w, data)
		if err != nil {
			logging.Errorf(c, "while rendering index: %s", err)
		}
		return
	}

	err = mainPage.Execute(w, data)
	if err != nil {
		logging.Errorf(c, "while rendering index: %s", err)
	}
}

// Bug is a dummy struct. Put whatever you want in here, I'll hook it up
// to the actual api in a follow-up CL.
type Bug struct {
	ID, Title, Status string
	LastUpdate        time.Time
}

// Change is a dummy struct. Put whatever you want in here, I'll hook it up
// to the actual api in a follow-up CL.
type Change struct {
	ID, Title, Status string
	LastUpdate        time.Time
}

// DayDetails is a list of activity for a user on a given day.
type DayDetails struct {
	Username string
	Bugs     []Bug
	Changes  []Change
}

// ActivityCounts contains counts for user activities on a given day.
type ActivityCounts struct {
	Changes, Bugs int
	Day           time.Time
}

// ActivityHistory holds daily activity counts for a user over some data range.
type ActivityHistory struct {
	Activities []ActivityCounts
}

func historyHandler(ctx *router.Context) {
	c, w, _, _ := ctx.Context, ctx.Writer, ctx.Request, ctx.Params
	encoder := json.NewEncoder(w)

	h := ActivityHistory{
		Activities: []ActivityCounts{},
	}

	user := auth.CurrentIdentity(c)
	email := getAlternateEmail(user.Email())
	q := fmt.Sprintf("owner:%s OR owner:%s", user.Email(), email)
	logging.Errorf(c, "query: %v", q)

	bugs, err := getBugsFromMonorail(c, q, monorail.IssuesListRequest_OPEN)
	if err != nil {
		logging.Errorf(c, "error getting bugs: %v", err)
		return
	}

	byDay := map[time.Time][]ActivityCounts{}

	for _, bug := range bugs.Items {
		updated, err := time.Parse("2006-01-02T15:04:05", bug.Updated)
		if err != nil {
			logging.Errorf(c, "error parsing time: %s %v", bug.Updated, err)
			continue
		}
		day := updated.Truncate(24 * time.Hour)
		if _, ok := byDay[day]; !ok {
			byDay[day] = []ActivityCounts{}
		}
		byDay[day] = append(byDay[day], ActivityCounts{
			Bugs: 1,
		})
	}

	// Next, get changes.
	client, err := getGerritClient(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	changeInfo, _, err := client.Changes.QueryChanges(&gerrit.QueryChangeOptions{
		QueryOptions: gerrit.QueryOptions{
			Query: []string{fmt.Sprintf("owner:%s", user.Email())},
		},
	})
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	for _, change := range *changeInfo {
		updated, err := time.Parse("2006-01-02 15:04:05.000000000", change.Updated)
		if err != nil {
			logging.Errorf(c, "error parsing time: %s %v", change.Updated, err)
			continue
		}
		day := updated.Truncate(24 * time.Hour)
		if _, ok := byDay[day]; !ok {
			byDay[day] = []ActivityCounts{}
		}
		byDay[day] = append(byDay[day], ActivityCounts{
			Changes: 1,
		})
	}

	// Next, reduce

	for day, activityCounts := range byDay {
		ac := ActivityCounts{Day: day}
		for _, c := range activityCounts {
			ac.Bugs = ac.Bugs + c.Bugs
			ac.Changes = ac.Changes + c.Changes
		}

		h.Activities = append(h.Activities, ac)
	}

	sort.Sort(byUpdated(h.Activities))

	if err := encoder.Encode(h); err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error json encoding: %v", err))
	}
}

type byUpdated []ActivityCounts

func (a byUpdated) Len() int           { return len(a) }
func (a byUpdated) Swap(i, j int)      { a[i], a[j] = a[j], a[i] }
func (a byUpdated) Less(i, j int) bool { return a[i].Day.After(a[j].Day) }

func detailHandler(ctx *router.Context) {
	c, w, _, _ := ctx.Context, ctx.Writer, ctx.Request, ctx.Params
	encoder := json.NewEncoder(w)

	if err := encoder.Encode(DayDetails{
		Bugs: []Bug{
			{"1", "dummy bug", "Open", time.Now()},
			{"2", "another dummy bug", "Open", time.Now()},
		},
		Changes: []Change{
			{"1", "dummy change", "Open", time.Now()},
			{"2", "another dummy change", "Open", time.Now()},
		},
	}); err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error json encoding: %v", err))
	}
}

// getAsSelfOAuthClient returns a client capable of making HTTP requests authenticated
// with OAuth access token for userinfo.email scope.
func getAsSelfOAuthClient(c context.Context) (*http.Client, error) {
	// Note: "https://www.googleapis.com/auth/userinfo.email" is the default
	// scope used by GetRPCTransport(AsSelf). Use auth.WithScopes(...) option to
	// override.
	t, err := auth.GetRPCTransport(c, auth.AsSelf)
	if err != nil {
		return nil, err
	}
	return &http.Client{Transport: t}, nil
}

// A bit of a hack to let us mock getBugsFromMonorail.
var getBugsFromMonorail = func(c context.Context, q string,
	can monorail.IssuesListRequest_CannedQuery) (*monorail.IssuesListResponse, error) {
	// Get authenticated monorail client.
	c, cancel := context.WithDeadline(c, time.Now().Add(time.Second*30))
	defer cancel()

	logging.Infof(c, "about to get mr client")
	client, err := getAsSelfOAuthClient(c)

	if err != nil {
		panic("No OAuth client in context")
	}

	mr := monorail.NewEndpointsClient(client, "https://monorail-prod.appspot.com/_ah/api/monorail/v1/")
	logging.Infof(c, "mr client: %v", mr)

	// TODO(martiniss): make this look up request info based on Tree datastore
	// object
	req := &monorail.IssuesListRequest{
		ProjectId: "chromium",
		Q:         q,
	}

	req.Can = can

	before := time.Now()

	res, err := mr.IssuesList(c, req)
	if err != nil {
		logging.Errorf(c, "error getting issuelist: %v", err)
		return nil, err
	}

	logging.Debugf(c, "Fetch to monorail took %v. Got %d bugs.", time.Now().Sub(before), res.TotalResults)
	return res, nil
}

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

func getGerritClient(c context.Context) (*gerrit.Client, error) {
	// Use the default.
	instanceURL := "https://chromium-review.googlesource.com"
	logging.Infof(c, "using gerrit instance %q", instanceURL)

	tr, err := auth.GetRPCTransport(c, auth.AsSelf,
		auth.WithScopes("https://www.googleapis.com/auth/gerritcodereview"))
	if err != nil {
		return nil, err
	}

	httpc := &http.Client{Transport: tr}
	client, err := gerrit.NewClient(instanceURL, httpc)
	if err != nil {
		return nil, err
	}

	// This is a workaround to force the client lib to prepend /a to paths.
	client.Authentication.SetCookieAuth("not-used", "not-used")

	return client, nil
}

func init() {
	r := router.New()
	basemw := base(true)
	protected := basemw.Extend(requireGoogler)
	standard.InstallHandlers(r)

	r.GET("/", basemw, indexPage)
	r.GET("/_/history", protected, historyHandler)
	r.GET("/_/detail", protected, detailHandler)

	http.DefaultServeMux.Handle("/_/", r)
	http.DefaultServeMux.Handle("/_ah/", r)
	http.DefaultServeMux.Handle("/auth/", r)
	http.DefaultServeMux.Handle("/admin/", r)
	http.DefaultServeMux.Handle("/", r)
}
