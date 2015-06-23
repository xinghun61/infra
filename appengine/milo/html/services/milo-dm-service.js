/* milo-dm-service.js: Transforms Dungeon Master Json into Milo pages.
 *
 * The pipeline roughly goes like this:
 *    1. Acquire an attempt json from DM
 *       DM returns a list of attempts, but what we want is a traversable tree.
 *    2. treeify(): Create a tree of attempts, where each attempt has a "deps"
 *       entry that is a list of attempts that that attempt depends on.  The
 *       root attempt is the same as the one that's being queried.
 *    3. getPage(): Takes the attempt tree and create a Milo page.
 ***/

/*jshint globalstrict: true*/
/*jshint newcap: false*/
/*global Polymer*/
"use strict";

function getTopbar(attemptRoot) {
  /* Return a Milo item, or list of Milo items summerizing the results of a
   * DM attempt.
   ***/
  var result = attemptRoot.Failure ? "failed" : "succeeded";
  return [{mainText: ("This attempt " + result)}];
}

function getDep(dep) {
  /* Given either a DM attempt or attempt pointer, return a Milo item
   * params:
   *   dep: Can be a string or attempt object.
   *     String: A "Quest|Attempt" String
   *     Attempt: The dependent attempt object of the parent.
   *  returns:
   *     A Milo item representing an overview of the dependent attempt.
   ***/
  if (typeof dep == 'string' || dep instanceof String) {
    // Unresolved dep.
    return { mainText: dep };
  }
  var status = dep.result.Failure ? "failure" : "success";
  return {
    mainText: dep.id,
    isFailure: dep.result.Failure,
    status: status,
  };
}

function getDeps(attemptRoot) {
  /* Given a DM attempt, return a list of Milo items representing
   * first level dependencies.
   ***/
  var results = [];
  for (var i in attemptRoot.deps) {
    results.push(getDep(attemptRoot.deps[i]));
  }
  return results;
}

function getPage(attemptRoot, quest, attempt) {
  /* Given a DM attempt, return a full Milo page. */
  var topbar = [];
  var deps = [];
  var properties = [];
  if (attemptRoot) {
    topbar = getTopbar(attemptRoot);
    deps = getDeps(attemptRoot);
  }
  return {
    name: quest + ' | ' + attempt,
    topbar: topbar,
    steps: deps,
    nav: [
      {name: 'foo'},
      {name: 'bar'},
      {name: 'baz'}],
    properties: [],
    revisions:[]
  };
}

function makeAttemptTree(flat, attemptId) {
  /* Create an attempt tree based off a list of attempts.
   * params:
   *   flat: attempt ID: attempt object map.
   *     attempt ID is a string in the form of "%s|%s" % (Quest ID, Attempt #)
   *   attemptID: Specifies which attempt object should be placed at the root.
   * returns:
   *   The attempt object specified by attemptID, with an added "deps" property.
   *   deps is a list of attempt objects.
   ***/
  var luciAttempt = flat[attemptId];
  if (!luciAttempt) {
    return attemptId;
  }
  var attempt = {
    id: attemptId,
    state: luciAttempt.State,
    currentExecution: luciAttempt.CurrExecution,
    result: JSON.parse(luciAttempt.Result),
    deps: [],
  };
  for (var i in luciAttempt.FwdDeps) {
    var depQ = luciAttempt.FwdDeps[i];
    for (var j in depQ.AttemptIDs) {
      var depId = depQ.QuestID + "|" + depQ.AttemptIDs[j];
      attempt.deps.push(makeAttemptTree(flat, depId));
    }
  }
  return attempt;
}

function treeify(attemptJson, quest, attempt) {
  /* Turn a luci attempt response into an actual DAG
   * params:
   *   attemptJson: DM attempt json directly from DM.
   * returns:
   *   An single attempt, with an added "deps" property.
   ***/
  // First, flatten the object.
  if (!attemptJson) return {};
  var flat = {};
  for (var i in attemptJson.Quests) {
    var curr_quest = attemptJson.Quests[i];
    for (var j in curr_quest.Attempts) {
      var curr_attempt = curr_quest.Attempts[j];
      flat[curr_quest.ID+ "|" + curr_attempt.ID] = curr_attempt;
    }
  }

  var attemptId = quest + "|" + attempt;
  return makeAttemptTree(flat, attemptId);
}

Polymer("milo-dm-service", {
  created: function() {
    this.page = {};
    this.attemptRoot = {};
  },

  computed: {
    // Step 1: Turn a DM response into an attemptRoot
    // an attemptRoot is a single attempt entry, in the same format as returned
    // by the DM API, except with an extra "deps" property, containing all of
    // the dependencies of this attempt.
    attemptRoot: 'treeify(attemptJson, this.quest, this.attempt)',
    // Step 2: Take the attemptRoot and create the exported Milo page.
    page: 'getPage(attemptRoot, this.quest, this.attempt)'
  }
});
