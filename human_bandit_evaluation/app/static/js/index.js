// Some Constants
var baseUrl = window.location.origin;
var MINIMUM_RESPONSE_TIME = 1.0; // 10 seconds.
var start_timestamp = moment().valueOf() / 1000.0;

// Submission variable to prevent multiple submissions.
var submission_valid = true;

// Display Message Modal
var display_message_modal = function (errorMessage) {
    $("#message-modal .content").empty();
    $("#message-modal .content").append($("<p>").text(errorMessage));
    $("#message-modal").modal("show");
}

var validate_user_response = function() {
    var user_slider_response_value = document.getElementById("user_slider_response_value");
    return user_slider_response_value.innerHTML != "<em>none</em>";
}

var validate_user_selection = function() {
    return ($(".category").length == 0) ||
	   ($(".category").filter('.active-button').length == 1);
}

var validate_user_selection2 = function() {
    return ($(".category2").length == 0) ||
	   ($(".category2").filter('.active-button').length == 1);
}

var validate_user_attention = function() {
    if ($(".attention_check").length == 0) { return true; }
    console.log($(".attention_check").length);
    var attention_checks = document.getElementsByClassName("attention_check");
    var is_valid = true;
    for (let i = 0; i < attention_checks.length; i++) {
      var attention_check = attention_checks[i];
      is_valid = is_valid && (attention_check.value.length > 0);
    }
    return is_valid;
}

var validate_submission_time = function(submit_time) {
    return (submit_time - start_timestamp) >= MINIMUM_RESPONSE_TIME;
}

var submit_task_session = function () {
    var curr_img = document.getElementById("content_object");
    var user_response = document.getElementById("user_response");
    var user_slider_response_value = document.getElementById("user_slider_response_value");
    var task_id = document.getElementById("session").textContent.split(/[ ,]+/)[2];
    var attention_checks = document.getElementsByClassName("attention_check");
    var attention_check_labels = $('label[for="question"]');
    var submit_time = moment().valueOf() / 1000.0;
    var attention_check_outputs = [];
    // Validate user inputs.
    var validation_error = !validate_user_response() ||
                           !validate_user_selection() ||
                           !validate_user_attention();
    $(".hidden-user-response-error-msg")[0].innerHTML = "";
    $(".hidden-submit-button-error-msg")[0].innerHTML = "";
    if ($(".hidden-category-error-msg").length > 0) {
    	$(".hidden-category-error-msg")[0].innerHTML = "";
    }
    if ($(".hidden-attention-error-msg").length > 0) {
    	$(".hidden-attention-error-msg")[0].innerHTML = "";
    }
    if (!validate_user_response()) {
        $(".hidden-user-response-error-msg")[0].innerHTML = "You must provide a score between 1 and 9.";
        // console.log("You must provide a score between 1 and 9.");
    }
    if (!validate_user_selection()) {
        $(".hidden-category-error-msg")[0].innerHTML = "You must select a category.";
        // console.log("You must select a category.");
    }
    if (!validate_user_attention()) {
        $(".hidden-attention-error-msg")[0].innerHTML = "You must provide an answer to the attention check.";
        // console.log("You must provide an answer to the attention check.");
    } else {
        attention_check_outputs = [];
        for (var i = 0; i < attention_checks.length; i++) {
            attention_check_outputs.push({'question': attention_check_labels[i].innerHTML,
                                          'user_response': attention_checks[i].value});
        }
    }
    if (validation_error) {
        return;
    }
    // Validate submit button time after all correct answers have been entered.
    if (!validate_submission_time(submit_time)) {
        $(".hidden-submit-button-error-msg")[0].innerHTML = "The task can be submitted once 10 seconds have elapsed.";
        // console.log("The task can be submitted once 10 seconds have elapsed.");
        return;
    }
    var data = {
        task_id: task_id,
        start_time: start_timestamp,
        finish_time: submit_time,
        submit_time: submit_time,
        feedback: Math.round(user_response.value / 10.0),
        image_path: curr_img.src,
        user_selected_category: fetch_category(),
        attention_checks: attention_check_outputs,
    };
    var submitUrl = baseUrl + "/submit";
    $.post(submitUrl, data, function (res) {
	if (res['next_image_path'] == '') {
	    window.location.replace("/end_of_study");
	} else if (res['refresh_page']) {
	    window.location.replace("/");
	}
    	var img = document.getElementById("content_object");
	img.onload = function() {
	    img.onload = function() {
	        $("#session").text('Session Task ' + res['task_id']);
                $(".category").toggleClass('active-button', false);
                $(".category").toggleClass('inactive-button', true);
	        user_response.value = "";
            user_response.style.setProperty('--SliderColor', '#d3d3d3');
	        user_slider_response_value.innerHTML = "<em>none</em>";
                user_response.classList.remove('selected-slider');
                user_response.classList.add('unselected-slider');
            console.log(res);
            // Update attention check(s).
            for (var i = 0; i < attention_checks.length; i++) {
                attention_checks[i].value = "";
                attention_check_labels[i].innerHTML = res['attention_checks'][i]['question'];
            }
            // Reset start timestamp.
            start_timestamp = moment().valueOf() / 1000.0
            // Make adjustments to category buttons, such as reordering or removing
            // buttons for the last entry.
            if ('next_categories' in res) {
                var category_to_button = {};
                var category_buttons =  $(".category");
                var new_buttons_html = "";
		console.log(category_buttons);
                for (var i = 0; i < category_buttons.length; i++) {
                    category_to_button[category_buttons[i].id] = category_buttons[i];
		}
		console.log(category_to_button);
                for (var i = 0; i < res['next_categories'].length; i++) {
		    var category = res['next_categories'][i];
	            console.log(category);
                    new_buttons_html += category_to_button[category].outerHTML;
		}
                document.getElementById('category-buttons-container').innerHTML = new_buttons_html;
                $(".category").on('click', function () {
                    select_category(this);
                });
	    }
            if (res['last_task']) {
                var category_buttons = document.getElementById("category-buttons");
	            if (category_buttons) {
                        category_buttons.parentNode.removeChild(category_buttons);
	            }
	        }
	    }
	    img.src = res['next_image_path']
	}
	img.src = "static/images/loading.gif"
    }).fail(function (e) {
        var errorMessage = "Error encountered while ending session!";
        display_message_modal(errorMessage);
    });
}

var submit_survey_session = function () {
    var curr_img = document.getElementById("content_object");
    var task_id = document.getElementById("session").textContent.split(/[ ,]+/)[2];
    var submit_time = moment().valueOf() / 1000.0;
    var user_response = [];
    // Validate user inputs.
    var validation_error = !validate_user_selection() ||
			   !validate_user_selection2();
    if ($(".hidden-category-error-msg").length > 0) {
      $(".hidden-category-error-msg")[0].innerHTML = "";
    }
    if ($(".hidden-category2-error-msg").length > 0) {
      $(".hidden-category2-error-msg")[0].innerHTML = "";
    }
    if (!validate_user_selection()) {
        $(".hidden-category-error-msg")[0].innerHTML = "You must select an answer for the first question.";
    }
    if (!validate_user_selection2()) {
        $(".hidden-category2-error-msg")[0].innerHTML = "You must select an answer for the second question.";
    }
    if (validation_error) {
	// Allow for next submission since validation failed.
	submission_valid = true;
        return;
    }
    var survey_responses = document.getElementsByClassName("survey_question");
    if (survey_responses.length > 0) {
        var user_responses = [fetch_category(), fetch_category2()];
        for (var i = 0; i < survey_responses.length; i++) {
          // var survey_response_labels_i = $('label[for="survey_question' + (i+1) + '"]')[0];
          var survey_response_question_i = document.getElementById("survey_question" + (i+1));
	  console.log(survey_response_question_i);
	  console.log(user_responses[i]);
	  user_response.push({'question': survey_response_question_i.title,
                              'answer': user_responses[i]});
	}
    } else {
        user_response = fetch_category();
    }

    var data = {
        task_id: task_id,
        start_time: start_timestamp,
        finish_time: submit_time,
        submit_time: submit_time,
        user_response: user_response,
    };
    var submitUrl = baseUrl + "/survey";
    $.post(submitUrl, data, function (res) {
	window.location.replace("/survey")
    }).fail(function (e) {
        var errorMessage = "Error encountered while ending session!";
        display_message_modal(errorMessage);
    });
}

var submit_end_of_study_session = function () {
    window.location.replace("/survey")
}


var select_category = function (el) {
    if (el.classList.contains('inactive-button')) {
      $(".category").toggleClass('active-button', false);
      $(".category").toggleClass('inactive-button', true);
      el.classList.remove('inactive-button');
      el.classList.add('active-button');
    } else if (el.classList.contains('active-button')) {
      el.classList.remove('active-button');
      el.classList.add('inactive-button');
    }
}

var select_category2 = function (el) {
    if (el.classList.contains('inactive-button')) {
      $(".category2").toggleClass('active-button', false);
      $(".category2").toggleClass('inactive-button', true);
      el.classList.remove('inactive-button');
      el.classList.add('active-button');
    } else if (el.classList.contains('active-button')) {
      el.classList.remove('active-button');
      el.classList.add('inactive-button');
    }
}

var fetch_category = function () {
    active_category = $(".category").filter('.active-button');
    console.log(active_category);
    if (active_category.length == 0) {
        return null;
    } else {
	return active_category[0].id;
    }
}

var fetch_category2 = function () {
    active_category = $(".category2").filter('.active-button');
    console.log(active_category);
    if (active_category.length == 0) {
        return null;
    } else {
	return active_category[0].id;
    }
}

$(document).ready(function () {
    console.log("Document ready.");

    // Activate dropdown menu
    $('.ui.dropdown').dropdown();

    // Display Answer Modal
    $("#answer").on('click', function () {
        $("#answer-modal").modal("show");
    });

    // Next Step button
    $("#next").on('click', function () {
        move_next();
    });

    // Next Image button
    $("#next_img").on('click', function () {
        move_next_image();
    });

    // Category buttons
    $(".category").on('click', function () {
        select_category(this);
    });
    $(".category2").on('click', function () {
        select_category2(this);
    });

    $("#submit").on('click', function () {
	submit_task_session();
    });

    $("#submit-survey").on('click', function () {
	submit_survey_session();
    });

    $("#submit-end-of-study").on('click', function () {
	submit_end_of_study_session();
    });

    if ($("#user_slider_response_value").length > 0) {
        var user_response_slider = document.getElementById('user_response');
        var user_response_value = document.getElementById('user_slider_response_value');
        user_response_slider.classList.add('unselected-slider');
	user_response_slider.oninput = function() {
            // Round the slider value to the nearest integer.
            user_response_value.innerHTML = Math.round(user_response_slider.value / 10);
            user_response_slider.classList.remove('unselected-slider');
            user_response_slider.classList.add('selected-slider');
            user_response_slider.style.setProperty('--SliderColor', '#3198e5');
        }
	user_response_slider.onclick = function() {
            // Round the slider value to the nearest integer.
            user_response_value.innerHTML = Math.round(user_response_slider.value / 10);
            user_response_slider.classList.remove('unselected-slider');
            user_response_slider.classList.add('selected-slider');
            user_response_slider.style.setProperty('--SliderColor', '#3198e5');
        }
    }
})
