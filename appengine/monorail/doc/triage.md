# Monorail Triage Guide (go/monorail-triage)

Monorail is a tool that is actively used and maintained by
the Chromium community.  It is important that we look at
issues reported by our users and take appropriate actions.

## Triage responsibilities

When you have a monorail triage shift, look at each issue in the
[untriaged queue](https://bugs.chromium.org/p/monorail/issues/list?can=2&q=-has%3Amilestone+-has%3Aowner)
and do the following:

* If it is an urgent issue that affects operation of the site, chat with jrobbins or
  escalate to the Chrome Operations team as a whole.
* If the issue is spam or off-topic, ban the user or set the issue state to Invalid.
  To ban: click the user's email address and press "Ban as spammer."
* If the issue clearly belongs in /p/chromium, move it there and then set status, pri, and type.
* If the issue is valid and requires action, set status to Accepted and the milestone to one described below.
* It if is not clear that this request should be acted on, leave the status as New and set the milestone to Later.
  We will look at it again if multiple users star the issue.

Also, take a look at the "Error reporting" section of the Google Cloud Console for our
production app to see if there are any new errors that are impacting users.  File Afterglow
issues to track these problems.

If you have questions, feel free to chat with jrobbins or other members of the monorail team.


## Triage SLA

* Try to look at incoming issues daily.
* If you have limited time, scan for urgent issues first.
* Try to have the queue empty on Monday mornings.
* If you cannot take your shift, trade with another monorail team member, or chat with jrobbins.


## Milestones

* Afterglow
  * Problems with existing functionality that our users depend on.
  * Requests for API whitelisting.
  * Operational changes that are needed to keep the site available (e.g., monitoring).
* Retrofit
  * Technology-driven changes needed for us to maintain the site over the long run.
* Goodies
  * Narrowly scoped enhancements requested by key customers.
  * Should not require major UI changes.
* Midterm
  * Changes to keep in mind for an upcoming UI redesign.
* Later
  * Suggestions that we would probably not act on unless there is demonstrated user demand.
