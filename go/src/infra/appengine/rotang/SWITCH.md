# Switch to RotaNG.

This document describes the steps needed to switch over from the cron/python based rotation generator
to the new RotaNG service.

See [Design Doc](https://docs.google.com/document/d/1WdvMckyfzfx9anU1hLHJ16EuvXv4Keo8aUmSTQRuNp4/edit) for further information.


## Switch a rotation to the RotaNG service.

### Create/Import a Rotation

  Browse to (https://rota-ng-staging.googleplex.com/).

  From here you have a few options on how to create a rotation.

 - **It's already in there!**.

    - If when following the `Manage rotations` link you can see your rotation it was already imported.

      Continue to next step.

 - If your rotation does show up when following the `List configurations in backend store` but not
      in `Manage rotations` it's probably b/c you're not part of the *owners* of the rotation.

      Drop a mail to **olakar@chromium.org** to have this sorted.

 - Your rotation is not in `List configurations in backend store`.

    - ***Either*** Create a new rotation from scratch.
        
        Choose `Create new rotation` from the `Manage rotation page`.
        
    - **Or** Import rotation from a configuration file. 
      
      Follow the link `Upload Legacy JSON rota configuration` to upload and convert.

### Configure a Rotation

  - If your rotation already existed press the `modify` button.

  You should now be looking at a form with the following fields.

  * **Rotation Name**

    If you're modifying a rotation this field can not be changed due to it being
    used as the key in the backend storage.
    To rename a rotation you need to delete the rotation and create a new one with
    the desired name.

    This field is also used when creating calendar entries.

  * **Description**

    Describes the rotation. Also used for the summary of calendar events.
    See the Email templates for more information about how to fill out this
    field.

  * **Calendar**

    This should contain the id of the team shared calendar.

    Eg. `google.com_d3itj7r696lolrs39d0to7rtjc@group.calendar.google.com`

    To give the rotation service the rights to read/modify the team calendar you need to share the calendar
    with the rota service account. `rota-ng-staging.google.com@appspot.gserviceaccount.com`.

    ![CalShare](http://www.google.com/url?sa=D&q=https%3A%2F%2Fcalendar.google.com%2Fcalendar%2Fr%2Fsettings%2Fcalendar%2FZ29vZ2xlLmNvbV9kM2l0ajdyNjk2bG9scnMzOWQwdG83cnRqY0Bncm91cC5jYWxlbmRhci5nb29nbGUuY29t)

  * **Owners**

    A comma separated list of rotation owners.

    Note: *This will be changed to use mdb groups shortly*

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
    Upcoming On-call shift for rotation: \{\{.RotaName\}\} \{\{.ShiftEntry.StartTime.In .Member.TZ\}\} to \{\{.ShiftEntry.EndTime.In .Member.TZ\}\}
    ```

    Will produce:

    ```
    Upcoming On-call shift for rotation: Name of rota 2006-04-05 17:00:00 -0700 PDT to 2006-04-06 17:00:00 -0700 PDT
    ```

    For a member with a US Pacific TZ.

    **Note**: The current %s format replacement will not work. You could replace the %s with \{\{.RotaName\}\} for something similar.

  * **Email Body Template**

    See Email Subject Template.

  * **Email Days Before Notify**

    Number of days before an on-call shift to send mails out.

    Note: *No mails will be produced until the rotation is enabled.*

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

  * **Generator**

    Specifies what Generator to use when scheduling shifts
    * Fair

        Takes previous shifts into account when scheduling shifts.
        If there are no previous shifts it'll fall back to random.
    * Random
    * Legacy

       Tries to emulate the current scheduler.

  * **Shifts**

    The service supports split shifts so you can have follow the sun kind of configurations with MTV -> SYD -> EU.

    This would be configured as 3 shifts.

    ```
    Name: MTV OnCall  Duration: 8
    Name: SYD OnCall  Duration: 8
    Name: EU OnCall   Duration: 8
    ```

    When scheduling the RotaMembers `ShiftsName` would be used to figure out which users to put into which shift.

    It's also OK to have empty splits Eg.

    ```
    Name: MTV Office      Duration: 6
    Name: MTV->SYD no-one Duration: 2
    Name: SYD Office      Duration: 6
    Name: SYD->EU no-one  Duration: 2
    Name: EU Office       Duration: 6
    Name: EU->MTV no-one  Duration: 2
    ```

    The calendar entries created will have the Shift name added to the description.

    Note: *The sum of the shift durations should always be 24*

### Import shifts from current calendar.

  With `rota-ng-staging.google.com@appspot.gserviceaccount.com` permissions added to the shared calendar we can import the current rotations.

  * Go back to the Shift Management page.
  * Press the `import` button.
  * You should now see a list of current shifts.
  * If all looks good click `Submit Shifts` to have them imported.

### Mange shifts

  * Go back to the Shift Management page.
  * Click the `Shifts` button.

  * **Shift History**
    * Shows the shift history.
  * **Current Shifts**

    Contains current shifts. From here you can modify who's oncall for the different shifts.

    Note: *The down arrow will remove all shifts from the pressed one.*
    Note: Nothing is saved to backend storage until you click `Update Shifts`
  * **Generate Shifts**

    As default `Generate` will generate new shifts after the last shift in store using the configuration values for number of shifts and the Fair generator.

    Note: *When setting the StartDate and having `skip` configured , make sure the date is on a Monday*
    Note: *Nothing is saved until you press `Submit`*

4. Start using the new service.

  To switch over to the new service you do the following.
  - Remove the legacy json configuration.

    Without this step the oncallers will get duplicate emails for upcoming shifts.


  - `Enable` the rotation in the `Manage` rotations section.

## FAQ

* The interface looks like something from the early 90s ..

  Yes this was probably the last time I touched HTML so I've had quite a bit of rust to remove off of my frontend skillz.
  This is rapidly getting improved though with the help of the ChOps Frontend team.

* What about go/chromecals allshifts.txt etc.

  I'm currently working on getting all the users of those sources switched over to the new service. [b/889221](https://bugs.chromium.org/p/chromium/issues/detail?id=889221)

* Bugs

  File bugs in [component:Infra>Sheriffing>Rotations](https://bugs.chromium.org/p/chromium/issues/list?q=component:Infra%3ESheriffing%3ERotations) and assign to: *olakar@chromium.org*
