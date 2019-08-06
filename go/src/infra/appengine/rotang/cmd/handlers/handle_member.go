package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"infra/appengine/rotang"
	"net/http"
	"time"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// JSONMember adds a TZString field to the rotang.Member structure.
// This is needed due to time.Location not having an encoding to JSON.
type JSONMember struct {
	rotang.Member
	TZString string
}

// MemberInfo is used by the shift-member element to get
// relevant member information.
type MemberInfo struct {
	Member JSONMember
	Shifts []RotaShift
}

// RotaShift contains a rota name and relevant shift
// information for the shift-member element.
type RotaShift struct {
	Name    string
	Entries []rotang.ShiftEntry
}

// HandleMember handles shift-member.
func (h *State) HandleMember(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	usr := auth.CurrentUser(ctx.Context)
	if usr == nil || usr.Email == "" {
		url, err := auth.LoginURL(ctx.Context, ctx.Params.ByName("path"))
		if err != nil {
			http.Error(ctx.Writer, "not logged in", http.StatusForbidden)
			return
		}
		http.Redirect(ctx.Writer, ctx.Request, url, http.StatusFound)
		return
	}

	m, err := h.memberStore(ctx.Context).Member(ctx.Context, usr.Email)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	switch ctx.Request.Method {
	case "POST":
		if err := h.memberPOST(ctx, &JSONMember{
			Member:   *m,
			TZString: m.TZ.String(),
		}); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
	case "GET":
		if err := h.memberGET(ctx, m); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
	default:
		http.Error(ctx.Writer, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
}

func (h *State) memberPOST(ctx *router.Context, user *JSONMember) error {
	// Decode JSONMember from the post request body.
	var jsonMember JSONMember
	if err := json.NewDecoder(ctx.Request.Body).Decode(&jsonMember); err != nil {
		return err
	}
	logging.Infof(ctx.Context, "member: %v", jsonMember)

	// A Member's information may only be changed by that member or an admin.
	if jsonMember.Email != user.Email && !isAdmin(ctx) {
		return status.Errorf(codes.PermissionDenied, "only changes to your own user allowed")
	}

	// Assert OOO dates have comments.
	for i := range jsonMember.OOO {
		if jsonMember.OOO[i].Comment == "" {
			return status.Errorf(codes.InvalidArgument, "comment needs to be set")
		}
		logging.Infof(ctx.Context, "member.OOO[i}", jsonMember.OOO[i])
	}

	// Load TZString. Fall back to the user's TZString.
	loc, err := time.LoadLocation(jsonMember.TZString)
	if err != nil {
		loc, err = time.LoadLocation(user.TZString)
		if err != nil {
			return err
		}
	}

	member := rotang.Member{
		Name:        jsonMember.Name,
		Email:       jsonMember.Email,
		TZ:          *loc,
		OOO:         jsonMember.OOO,
		Preferences: jsonMember.Preferences,
	}

	return h.memberStore(ctx.Context).UpdateMember(ctx.Context, &member)
}

func (h *State) memberGET(ctx *router.Context, user *rotang.Member) error {
	member := user

	// Admins may request data for any member.
	// They could use the cloud console instead, but this allows scripting in a
	// way that the console does not.
	if isAdmin(ctx) {
		emails, ok := ctx.Request.URL.Query()["email"]
		if ok && len(emails) == 1 {
			m, err := h.memberStore(ctx.Context).Member(ctx.Context, emails[0])
			if err == nil {
				member = m
			}
		}
	}

	rotas, err := h.configStore(ctx.Context).MemberOf(ctx.Context, member.Email)
	if err != nil {
		return err
	}

	now := clock.Now(ctx.Context)

	shiftStore := h.shiftStore(ctx.Context)
	res := MemberInfo{
		Member: JSONMember{
			Member:   *member,
			TZString: member.TZ.String(),
		},
	}
	for _, r := range rotas {
		shifts, err := shiftStore.AllShifts(ctx.Context, r)
		if err != nil && status.Code(err) != codes.NotFound {
			return err
		}
		var entries []rotang.ShiftEntry
		for _, s := range shifts {
			if s.EndTime.After(now) {
				for _, o := range s.OnCall {
					if o.Email == member.Email {
						entries = append(entries, s)
					}
				}
			}
		}
		if len(entries) > 0 {
			res.Shifts = append(res.Shifts, RotaShift{
				Name:    r,
				Entries: entries,
			})
		}
	}

	var buf bytes.Buffer
	if err = json.NewEncoder(&buf).Encode(&res); err != nil {
		return err
	}
	_, err = fmt.Fprintln(ctx.Writer, buf.String())
	return err
}
