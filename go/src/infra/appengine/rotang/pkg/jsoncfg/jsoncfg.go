// Package jsoncfg handles the legacy json formatted rota configurations.
package jsoncfg

import (
	"encoding/json"
	"time"

	"infra/appengine/rotang"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const defaultTokenID = "test@admin"

var mtvMidnight = func() time.Time {
	t, err := time.Parse(time.RFC822, "02 Jan 06 00:00 PDT")
	if err != nil {
		panic(err)
	}
	return t
}()

// JSONMembers is used to convert rota members.
type JSONMembers struct {
	Members []rotang.Member `json:"person"`
}

// JSONRota is used to convert the legacy JSON based sheriff rotation configuration.
type JSONRota struct {
	Configuration JSONConfiguration `json:"rotation_config"`
	PSTRotation   JSONMembers       `json:"rotation_list_pacific"`
	EURotation    JSONMembers       `json:"rotation_list_default"`
	OtherRotation JSONMembers       `json:"rotation_list_other"`
}

// JSONMultiConfigRota is used to convert the legacy JSON based sheriff rotation configuration.
type JSONMultiConfigRota struct {
	Configuration []JSONConfiguration `json:"rotation_config"`
	PSTRotation   JSONMembers         `json:"rotation_list_pacific"`
	EURotation    JSONMembers         `json:"rotation_list_default"`
}

// JSONConfiguration contains the configuration part of the rotation.
type JSONConfiguration struct {
	Description          string   `json:"event_description"`
	Rotation             string   `json:"event_title"`
	Calendar             string   `json:"calendar_name"`
	EmailBody            string   `json:"reminder_email_body"`
	EmailSubject         string   `json:"reminder_email_subject"`
	Owners               []string `json:"owners"`
	EmailDaysInAdvance   int      `json:"reminder_email_advance_days"`
	ExpirationThreshold  int      `json:"expiration_threshold"`
	OncallersPerRotation int      `json:"people_per_rotation"`
	RotationLength       int      `json:"rotation_length"`
}

const (
	defaultDaysToSchedule = 10
	pacificTZ             = "US/Pacific"
	euTZ                  = "UTC"
	defaultShiftName      = "MTV all day"
)

func handleJSON(data []byte) (*JSONRota, error) {
	var jsonRota JSONRota
	if err := json.Unmarshal(data, &jsonRota); err != nil {
		var multiConf JSONMultiConfigRota
		// Turns out some of the configurations contains a list of configurations [ ] while most
		//  contain a single config. The Go JSON encoder gets a bit stressed out by this so here we
		//  retry the encode into a slice of configs in case the one with just one configuration fails.
		if err := json.Unmarshal(data, &multiConf); err != nil {
			return nil, err
		}
		if len(multiConf.Configuration) != 1 {
			return nil, status.Errorf(codes.Unimplemented, "support for multiple configurations not implemented")
		}
		jsonRota.Configuration = multiConf.Configuration[0]
		jsonRota.PSTRotation = multiConf.PSTRotation
		jsonRota.EURotation = multiConf.EURotation
	}
	return &jsonRota, nil
}

// BuildConfigurationFromJSON converts the Sheriff json configuration
//  to the native rota configuration.
func BuildConfigurationFromJSON(data []byte) (*rotang.Configuration, []rotang.Member, error) {
	jsonRota, err := handleJSON(data)
	if err != nil {
		return nil, nil, err
	}

	usLocation, err := time.LoadLocation(pacificTZ)
	if err != nil {
		return nil, nil, err
	}
	euLocation, err := time.LoadLocation(euTZ)
	if err != nil {
		return nil, nil, err
	}

	var (
		mbs          []rotang.Member
		shiftMembers []rotang.ShiftMember
	)

	for _, m := range jsonRota.PSTRotation.Members {
		mbs = append(mbs, rotang.Member{
			Name:  m.Name,
			Email: m.Email,
			TZ:    *usLocation,
		})
		shiftMembers = append(shiftMembers, rotang.ShiftMember{
			Email:     m.Email,
			ShiftName: defaultShiftName,
		})
	}
	for _, m := range append(jsonRota.EURotation.Members, jsonRota.OtherRotation.Members...) {
		mbs = append(mbs, rotang.Member{
			Name:  m.Name,
			Email: m.Email,
			TZ:    *euLocation,
		})
		shiftMembers = append(shiftMembers, rotang.ShiftMember{
			Email:     m.Email,
			ShiftName: defaultShiftName,
		})
	}

	return &rotang.Configuration{
		Config: rotang.Config{
			Name:        jsonRota.Configuration.Rotation,
			Description: jsonRota.Configuration.Description,
			Calendar:    jsonRota.Configuration.Calendar,
			TokenID:     defaultTokenID,
			Expiration:  jsonRota.Configuration.ExpirationThreshold,
			Owners:      jsonRota.Configuration.Owners,
			Email: rotang.Email{
				Subject:          jsonRota.Configuration.EmailSubject,
				Body:             jsonRota.Configuration.EmailBody,
				DaysBeforeNotify: jsonRota.Configuration.EmailDaysInAdvance,
			},
			DaysToSchedule: defaultDaysToSchedule,
			Shifts: rotang.ShiftConfig{
				StartTime:    mtvMidnight,
				ShiftMembers: jsonRota.Configuration.OncallersPerRotation,
				Length:       jsonRota.Configuration.RotationLength,
				Shifts: []rotang.Shift{
					{
						Name:     defaultShiftName,
						Duration: time.Duration(24 * time.Hour),
					},
				},
				Generator: "Legacy",
			},
		},
		Members: shiftMembers,
	}, mbs, nil
}
