# Monorail Issue Tracker

## What is Monorail?

Monorail is the issue tracker used by Chromium-related projects on
<https://bugs.chromium.org>.

* Monorail is a port of the Google Code issue tracker to AppEngine. It provides
continuity for the chrome team with the least number of unknowns, while achieving
these goals:
  * Vastly simpler to develop and operate:
  * Runs on Google App Engine, data in Google Cloud SQL and GCS.
  * Built on simpler GAE APIs.
  * Pure python, greatly simplified code, supported by Chrome Operations team.
* Better product focus:
  * Focused on needs of larger teams: e.g., built-in support for user groups,
    custom fields, more control over issue visibility, better validation to
    improve issue data quality.
  * Closely aligned with the chrome development process and dedicated to the
    future needs of the chrome team.
* Scaleable by design:
  * Designed from the start to handle chrome's future issue tracking needs.
  * Efficient implementation of queries like issue ID and date ranges.
  * Improved security and spam defenses.
* Ease of transition:
  * Same data model as used by our existing issues for an exact import.
  * Our v1 API is very close to the old Google Code API.
  * Same ACLs and project administration controls.
  * Familiar UI, but streamlined.  One-to-one redirects from Google Code.

## Monorail key features

* Developed as open source.
* Flexible issue representation that allows for creation of one-off labels.
* Custom fields defined by project owners.
* Support for components.  Issues can be in multiple components.
* Filter rules are IF-THEN rules that automatically add labels or CC users.
* Fine-grained permission system allows control over visiblity and individual
  actions on individual issues.
* Saved queries per user and per project.
* Users can subscribe to their saved queries (not just labels) and get mail on updates.
* User groups are built into Monorail, so no update lag on built-in groups.
  We can also sync from Google Groups.
* Support for custom fields that are treated very much like built-in fields.
  Custom fields can be multi-valued.
* User-valued custom fields can be restricted to only allow qualified users that
  have a given permission.
* User-valued custom fields can trigger notifications to those users, and/or grant
  permissions to the named users.
* Notification emails include detailed footers that give an ordered list of the
  reasons why the email was sent to you, with specifics such as "You are the on the
  auto-cc list of Component C".
* ML-based spam detection applied before notifications are generated. Users can
  also flag spam.
* Limited-availability Endpoints API that works like the old Google Code API.
* Personal hotlists with ranked issues.

## Reporting problems with Monorail

Please file an issue at <https://bugs.chromium.org/p/monorail>.
