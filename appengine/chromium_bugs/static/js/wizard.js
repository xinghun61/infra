/** Functions for the new issue wizard. 
 */

function $(id) {
    return document.getElementById(id);
}


var debug = $("debug");


function guessChannel(json_data) {
    if (json_data && json_data['channel']) {
	$("channel").value = json_data['channel'];
    }
}


function getFlashVersion() {
    if (FlashDetect) {
	var flash_version = FlashDetect.raw;
	$("flashversion").value = flash_version;
    }
}


function goStep(step_num, opt_focus_id) {
    window.history.pushState(step_num, "Step " + step_num);
    showStep(step_num, opt_focus_id);
}

function showStep(step_num, opt_focus_id) {
    if (!step_num) step_num = 1;
    for (var i = 1; i <= 4; ++i) {
	var step = $("step" + i);
	if (step) {
	    step.className = "";
	}
    }
    $("step" + step_num).className = "activestep";

    if (opt_focus_id) {
	$(opt_focus_id).focus();
    }
}

function selectComp(component_name) {
    $("next2").disabled = "";
    $("component_name").innerHTML = component_name;
    getDetailPanel(component_name);
}

function getDetailPanel(component_name) {
    $("detail_area").innerHTML = "Loading...";
    $("actual_instructions").innerHTML = "";
    $("actual_password_warning").innerHTML = $("default_password_warning").innerHTML;
    var component_page_name = component_name.replace(/\W/g, "").toLowerCase();
    var xmlhttp = new XMLHttpRequest();
    xmlhttp.onreadystatechange=function() {
	if (xmlhttp.readyState==4 && xmlhttp.status==200) {
	    $("detail_area").innerHTML = xmlhttp.responseText;
	    if ($("put_in_actual_instructions")) {
		$("actual_instructions").innerHTML = $("put_in_actual_instructions").innerHTML;
	    }
	    if ($("put_in_actual_password_warning")) {
		$("actual_password_warning").innerHTML = $("put_in_actual_password_warning").innerHTML;
	    }
	}
    }
    xmlhttp.open("GET", "ajah/" + component_page_name + ".html?cd=" + Math.random(), true);
    xmlhttp.send();
}

var ATTACHPROMPT_ID = 'attachprompt';
var ATTACHAFILE_ID = 'attachafile';
var ATTACHMAXSIZE_ID = 'attachmaxsize';
var nextFileID = 1;

/**
  * Function to dynamically create a new attachment upload field add
  * insert it into the page DOM.
  * @param {string} id The id of the parent HTML element.
  */
 function addAttachmentFields(id) {
   if (nextFileID >= 16) {
     return;
   }
   var el = $('attachmentarea');
   el.style.marginTop = '4px';
   var div = document.createElement('div');
   div.innerHTML = '<input type="file" name="file' + nextFileID +
                   '" size=35 style="width:auto;margin-left:17px">&nbsp;' +
                   '<a style="font-size:x-small" href="#" ' +
                   'onclick="this.parentNode.parentNode.removeChild(' +
                   'this.parentNode); return false">Remove</a> ';
   el.appendChild(div);
   ++nextFileID;
   if (nextFileID < 16) {
     $(ATTACHAFILE_ID).innerHTML = 'Attach another file'; // TODO: i18n
   } else {
     $(ATTACHPROMPT_ID).style.display = 'none';
   }
   $(ATTACHMAXSIZE_ID).style.display = '';
 }


var originalDescriptionParts = [
    "Example URL:\n$SPECIFIC_URL",
    "Steps to reproduce the problem:\n$REPRO_STEPS",
    "What is the expected behavior?\n$EXPECTED",
    "What went wrong?\n$ACTUAL",
    "Does it occur on multiple sites: $MULTIPLE_SITES",
    "Crashed report ID: $CRASH_REPORT_ID",
    "How much crashed? $CRASH_SCOPE",
    "Is it a problem playing media? $MEDIA",
    "WebStore page: $WEBSTORE_URL",
    "Is it a problem with a plugin? $PLUGIN $WHICH_PLUGIN",
    "about:sync contents: $ABOUT_SYNC",
    "Did this work before? $WORKED_BEFORE $WHEN_WORKED",
    "Is it a problem with Flash or HTML5? $FLASH_OR_HTML5",
    "Does this work in other browsers? $WORKS_OTHERS $WORKS_WHICH",
    ("Chrome version: $CHROMEVERSION  Channel: $CHANNEL\n" +
     "OS Version: $OSVERSION\n"  +
     "Flash Version: $FLASHVERSION"),
    "$OTHER_COMMENTS"
    ];
var descriptionParts = originalDescriptionParts.slice(0);  // Copy the whole array.

/** Expand one part of the description.
 *  Each value is only replaced once in the template.
 */
function expandDescriptionPart(descriptionPart) {
    var expandedPart = descriptionPart;
    inputElements = $("input_form").elements;
    for (var i = 0; i < inputElements.length; ++i) {
	var fieldName = inputElements[i].name;
	if (fieldName) {
	    var varName = "$" + fieldName.toUpperCase();
	    var newValue = "";
	    if (inputElements[i].value) {
		newValue = inputElements[i].value;
	    }
	    expandedPart = expandedPart.replace(varName, newValue);
	}
    }
    return expandedPart;
}

/** Expand the template string by replacing $VARIABLE references with
 *  the appropriate form field values.  Form field values should be in
 *  the format desired already (override preformatValues() if needed).
 *
 *  The template string is initialized to a default value above, but
 *  it can be overridden in any of the AJAH files for the final step.
 */
function expandDescriptionTemplate() {
    var expanded = "";
    for (var i = 0; i < descriptionParts.length; ++i) {
	var expandedPart = expandDescriptionPart(descriptionParts[i]);
	// Only display parts that have some valid expansion.
	if (expandedPart != descriptionParts[i]) {
	    expanded += expandedPart + "\n\n";
	}
    }

    var platform = $('platform').value;
    if (platform != "OS-iOS" && platform != "OS-Android") {
	var ua_text = "UserAgent: " + navigator.userAgent + "\n";
	var plat_text = "\n";
	var platformline = $('aboutplatformline').value;
	if (platformline) {
	    plat_text = "Platform: " + platformline + "\n";
	}

	expanded = ua_text + plat_text + "\n" + expanded;
    }

    // Trim off any excessive blank lines or whitespace.
    expanded = expanded.replace(/\n\s*\n/g, "\n\n");
    expanded = expanded.replace(/^\s+/, "");
    expanded = expanded.replace(/\s+$/, "");

    return expanded;
}


function preformatValues() {
    // For content.html
    if (document.forms[0].multiple_sites) {
	var affectsMultipleSites = (document.forms[0].multiple_sites.value == "Yes");
	if (affectsMultipleSites) {
	    document.forms[0].label1.value = "Cr-Blink";
	    document.forms[0].label9.value = "Type-Bug";
	} else {
	    document.forms[0].label1.value = "";
	    document.forms[0].label9.value = "Type-Compat";
	}
    }

    // For appsextensionswebstore.html
    if (document.forms[0].software_kind) {
	var kind = document.forms[0].software_kind;
	var label1 = document.forms[0].label1;
	if (kind.value == "Extension") {
	    label1.value = "Cr-Platform-Extensions";
	} else if (kind.value == "Theme") {
	    label1.value = "Cr-UI-Browser-Themes";
	}
    }

    // For other.html
    if (document.forms[0].other_type) {
	var other_type = document.forms[0].other_type;
	var label1 = document.forms[0].label1;
	var label9 = document.forms[0].label9;
	if (other_type.value == "N/A") {
	    label9.value = "Type-Bug";
	} else if (other_type.value == "feature") {
	    label9.value = "Type-Feature";
	} else if (other_type.value == "regression") {
	    label9.value = "Type-Bug-Regression";
	} else if (other_type.value == "bug") {
	    label9.value = "Type-Bug";
	} else if (other_type.value == "localization") {
	    label1.value = "Cr-UI-I18N";
	}
    }

}

CR_PREFIX = 'Cr-';

/** Examine the fields that the user entered and copy them into the
 *  id="post_*" form fields that are posted to the actual issue tracker
 *  form handler.
 */
function stuffDataAndSubmit() {
    // If there were no problems detected, go ahead and start the wizard.
    $("post_summary").value = document.forms[0].elements["summary"].value;
    preformatValues();
    $("post_comment").value = expandDescriptionTemplate();

    
    for (var labelNum = 1; labelNum < 10; labelNum++) {
	var el = document.forms[0].elements["label" + labelNum];
	if (el) {
	    $("post_label" + labelNum).value = el.value;
	}
    }

    $("post_label_os").value = document.forms[0].platform.value;

    var uas = navigator.userAgent;
    if (uas.indexOf('; Win64; x64') >= 0) {
      $("post_label_bitness").value = 'Arch-x86_64';
    }

    while ($('attachmentarea').hasChildNodes()) {
	$('submit_attachmentarea').appendChild($('attachmentarea').firstChild);
    }

    // If the wizard is not posting to codesite this time, convert label1
    // to a component value.
    // TODO(jrobbins): after chromium is migrated to monorail, simplify
    // this logic and use a components field all the time instad of label1.
    $("post_components").value = "";
    var isMonorail = !location.search.includes('code.google.com');
    var compLabelEl = document.forms[0].label1;
    if (isMonorail && compLabelEl && compLabelEl.value.startsWith(CR_PREFIX)) {
	var compValue = compLabelEl.value;
	compValue = compValue.substring(CR_PREFIX.length);
	compValue = compValue.replace(/-/g, '>');
	$("post_components").value = compValue;
	$("post_label1").value = "";
    }

    $("submit_form").submit();
}


function exposeQuestion(actualValue, conditionalQuestionID, exposeValues) {
    var questionEl = $("q_"+ conditionalQuestionID);
    var answerEl = $("a_"+ conditionalQuestionID);
    if (exposeValues.indexOf(actualValue) != -1) {
	questionEl.style.display = "block";
	answerEl.style.display = "block";
    } else {
	questionEl.style.display = "";
	answerEl.style.display = "";
	answerEl.value = "";
    }
}


function exposePlatformLine() {
    var platformValue = $('platform').value;
    var platformRowEl = $('platformrow');
    platformRowEl.style.display = (platformValue == "OS-Chrome") ? '' : 'none';
}

function checkSubmit() {
    var disabled = false;
    var formElements = document.forms[0].elements;
    for (var i = 0; i < formElements.length; ++i) {
	var el = formElements[i];
	if (el.value != "") continue;
	var dd = el.parentNode;
	while (dd && dd.nodeName != "DD") {
	    dd = dd.parentNode;
	}
	if (dd && dd.className.indexOf("required") != -1) {
	    disabled = true;
	}
    }
    $("submit_button").disabled = (disabled ? "disabled" : "");
}

getFlashVersion();
exposePlatformLine();
window.setInterval(checkSubmit, 700);


