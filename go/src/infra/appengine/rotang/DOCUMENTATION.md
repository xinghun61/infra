# Documentation

This document contains information on how to use the RotaNG web interface.

# Table of contents
- [Rotation Member](#rotation-member)
  - [Am I oncall](#am-i-oncall)
  - [Shift Swap](#shift-swap)
  - [OOO](#ooo)
- [Rotation Owner](#rotation-owner)
  - [Create new rotation](#create-new-rotation)
    - [Copy existing](#copy-existing)
    - [New from scratch](#new-from-scratch)
    - [From legacy JSON file](#new-from-json)
    - [Update from legacy JSON file](#update-from-legacy-json-file)
    - [Configuration Options](#configuration-options)
    - [External Rotations](#external-rotations)
  - [Manage Shifts](#manage-shifts)
    - [History](#history)
    - [Current](#current)
    - [Generate](#generate)
- [Test Email](#test-email)
- [Developer Information](./DEVINFO.md)
- [Migrate Information](./SWITCH.md)

## Rotation Member

### Am I oncall

The frontpage at (https://rota-ng.appspot.com) shows your next oncall shifts for your rotations.
Following the link show upcoming shifts.

### Shift swap

Following a rotation link from the frontpage will take you to the list of current shifts.

From that list you can add yourself to a shift, remove yourself from a shift (if it does not take the number of oncallers under the rotation limit),
and swap yourself in for someone  else. Filling in a comment is mandatory when changing the shift.

The common way to do a shift swap would be.
- Find someone else to take you shift.
- Ask that someone to go to (https://rota-ng.appspot.com) and switch themselves for you in the shift.

If you can't find a replacement, reach out to the rotation owner.

#### What about using the calendar to swap shifts

- RotaNG supports the legacy shift swaps using the shared calendar.
- It can take up to an hour before the calendar information is synced in to RotaNG.
- This is expected to be deprecated Q1 2019.
  Different to rotation.py RotaNG does not use Google Calendar as storage.
  Datastore is used to store all shifts and configurations, Calendar is just a UI
  to the database. Syncing Calendar -> RotaNG adds complexity and lag to the service.

### OOO
- Add your upcoming Out-of-Office dates to the (https://rota-ng.appspot.com) `OOO` section.

You'll not be considered for those dates when shifts are scheduled.
Already scheduled shifts will be unaffected , you'll have to swap  with someone for those.

Note: *For the OOO entries to be saved you need to click the `Update` button when finished*

## Rotation Owner

### Create new rotation

#### Copy existing

- Follow link [Manage Rotations](https://rota-ng.appspot.com/managerota) and click `Modify` for one of your existing rotations.
- Change the rotation name to the name of the new rotation.
- Modify and submit with the new changes.

#### New from scratch

- Follow link [Manage Rotations](https://rota-ng.appspot.com/managerota) and click `Create  new rotation`.

#### New from JSON

- Follow link [Upload Legacy JSON rota configuration](https://rota-ng.appspot.com/upload) and select the legacy JSON file.
- Submit.

#### Update from legacy JSON file

- Go to [Manage Rotations](https://rota-ng.appspot.com/managerota)
- Click `Delete` for the rotation to be updated.
- Confirm deletion.
- Follow link [Upload Legacy JSON rota configuration](https://rota-ng.appspot.com/upload) and select the legacy JSON file.
- Submit

#### Configuration Options


  * **Rotation Name**

    Used for calendar events.

    Changing this field on an existin rotation creates a copy.

  * **Description**

    Describes the rotation. Also used for the summary of calendar events.
    See the Email templates for more information about how to fill out this
    field.

  * **Calendar**

    This should contain the id of the team shared calendar.

    Eg. `google.com_d3itj7r696lolrs39d0to7rtjc@group.calendar.google.com`

    To give the rotation service the rights to read/modify the team calendar you need to share the calendar
    with the rota service account. `rota-ng@appspot.gserviceaccount.com`.

  * **Owners**

    A comma separated list of rotation owners.

    Note: *This will be changed to use mdb groups in the future.*

  * **Expiration**

    This specifies when to automatically schedule new shifts.
    Setting this to 0 gives no automatic shifts will be scheduled.

    Note: *Nothing will be scheduled before the rotation is enabled*

  * **Shifts To Schedule**

    Defines how many shifts to be scheduled when Expired.

  * **Email Subject Template**

    The subject of the emails sent from the rotation service to upcoming oncallers.

    This uses [Go templates](https://godoc.org/text/template) to generated the final message.

    The structures used to feed the template looks like this.

    ```
    type Info struct {
      RotaName    string
      ShiftConfig ShiftConfig
      ShiftEntry  ShiftEntry
      Member      Member
      MemberURL   string
    }

    type ShiftConfig struct {
      // StartTime represents the start-time of the first shift.
      // Only the Time of day is considered.
      // Defaults to 00:00 PDT.
      StartTime time.Time
      // Length sets the number of days a shift lasts.
      Length int
      // Skip defines a number of days with no oncalls.
      Skip int
      // Shifts represents the shifts over a 24hour period.
      Shifts []Shift
      // ShiftMembers specifides number of members per shift.
      ShiftMembers int
      // Generator used to schedule new shifts.
      Generator string
    }

    type ShiftEntry struct {
      // Name of the Shift this entry belongs to.
      Name string
      // OnCall are the members on-call for this shift.
      OnCall    []ShiftMember
      StartTime time.Time
      EndTime   time.Time
      // Comment is an optional comment where the rota algo
      // can add some extra information.
      Comment string
      // EvtID can be used to match an event to a calendar event.
      EvtID string
    }

    type Member struct {
      Name        string
      Email       string
      TZ          time.Location
      OOO         []OOO
      Preferences []Preference
    }
    ```

    This gives that you can have any information from the `Info` struct inserted in your message.

    Eg.

    ```
    Upcoming On-call shift for rotation: {{.RotaName}} {{.ShiftEntry.StartTime.In .Member.TZ}}  to  {{.ShiftEntry.EndTime.In .Member.TZ}}
    ```

    Will produce:

    ```
    Upcoming On-call shift for rotation: Name of rota 2006-04-05 17:00:00 -0700 PDT to 2006-04-06 17:00:00 -0700 PDT
    ```

    For a member with a US Pacific TZ.

    **Note**: The current %s format replacement will not work. You could replace the %s with {{.RotaName}} for something similar.

  * **Email Body Template**

    See Email Subject Template.

  * **Email Days Before Notify**

    Number of days before an on-call shift to send mails out.

    Note: *No mails will be produced until the rotation is enabled.*

  * **Email Notify Enable**

    Used to Enable/Disable sending mail notifications.

  * **Members**

    Manage members of the rotation.

  * **Shift StartTime**

      Specifies the start in MTV time of the first shift.

  * **Length**

      Number of days a shift spans.

  * **Skip**

    Skip in the shift schedule.
    Eg. if you rotation is weekdays only you'd set this to Length/Skip: 5/2

  * **ShiftMembers**

    Number of members to schedule per shift.

  * **Modifiers**

    Shift Modifiers are applied after the shift Generator is run. If set in the rotation configuration they'll be applied default to
    all generated shifts.

    They can also be temporarily enabled/disabled when managing shifts from the `Rotations -> Shifts` button.

    Currently two modifiers exists.

    * **WeekendSkip**

      This modifier moves generated shifts away from weekends (Saturday & Sunday).

      For example, a shift scheduled for Friday-Saturday will be split up into two shifts, one for Friday and one for Monday.
      A shift scheduled for Saturday-Sunday would be moved to Monday-Tuesday.

    * **SplitShift**

      This modifier splits the generated shifts into 1 day shifts.

      For example, a shift scheduled for Monday-Wednesday would be turned into three one day shifts: Monday, Tuesday and Wednesday.

      This lays the groundwork for single day swaps instead of having to swap a full shift.
      The UI will need to catch up to make this useful.

  * **Generator**

    What generator to use when scheduling new shifts.

    * **Legacy**

      Tries to emulate the legacy scheduler.

    * **Fair**

      Add weights to historic number of shifts done and how recent a member was on call.

    * **TZFair**

      Adds one member per TZ to the shift. Among the members of a particular timezone it behaves the same as Fair.
      Note that this overrides `ShiftMembers`, forcing it to be equal to the number of time-zones represented in the shift.

    * **Random**

      Randomly assigns members to shifts.

    * **Recent**

      The Recent generator only consider the last time a member was on-call.
      This gives the member with the last oncall shift will not be scheduled again until everyone with a less recent shift
      has been scheduled. Compared to the Fair generator the Recent generator does not take number of shifts into account.

    * **TZRecent**

      Adds one member per TZ to the shift. Among the members of a particular timezone it behaves the same as Recent.
      Note that this overrides `ShiftMembers`, forcing it to be equal to the number of time-zones represented in the shift.



  * **AllDayEvents**

    Enabling this option produces `AllDay` event in Google Calendar instead of the default DateTime events.

    **Note**: This option is only available for 24h shifts.


### External Rotations

RotaNG support External rotations by scraping a Google calendar. Matching calendar events are then converted to RotaNG shifts.
This gives that OnCall informatin can be given for both RotaNG native rotation and external rotations.

Shifts from External Rotations can not be changed from RotaNG, shift swaps, scheduling and shift management is disabled.

The proto is described [here](https://chromium.googlesource.com/infra/infra/+/master/go/src/infra/appengine/rotang/proto/rotangapi/rotangapi.proto), see `CreateExternalRequest`.

#### Create External Rotation

Creating an External Rotation is done through prpc.

Example text proto CCI_Trooper:

```
name: "CCI Trooper",
calendar: "google.com_3aov6uidfjscpj2hrpsd8i4e7o@group.calendar.google.com",
owners_emails: ["olakar@google.com"],
description: "CCI Trooper external",
match: "CCI-Trooper:",
```

Example usage:

```
cat CCI_Trooper | prpc call -format text rota-ng.appspot.com rotangapi.RotationAdmin.CreateExternal
```

#### Delete External Rotation

Example usage:

```
echo '{ "name": "CCI Trooper" }' | prpc call rota-ng.appspot.com rotangapi.RotationAdmin.DeleteExternal
```


### Manage shifts

- Follow link [Manage Rotations](https://rota-ng.appspot.com/managerota) and click `Shifts` for one of your existing rotations.

#### History

Toggles list of previous shifts.

#### Current

Shows upcoming shifts. As an owner you can modify shifts here. Rules for how many should be scheduled for a shift are overridden.

#### Generate

Schedules new shifts. Leaving the `StartTime` empty will continue scheduling from last current shift. If `ShiftsToSchedule` is left empty
the configuration setting will be used.


## Test Email

On the front page following the [Test Email](https://rota-ng.appspot.com/emailtest) link takes you to a list of all the
rotations you own and/or are a member of.

- Clicking the `Test` button expands the Email template.
- Clicking the `Send` button sends the generated email to the logged in user.
