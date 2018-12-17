//
// Copyright (c) 2012-2014 Stephen P. Smith
// Copyright (c) 2017-2018 Mark Juric
//
// Permission is hereby granted, free of charge, to any person obtaining
// a copy of this software and associated documentation files
// (the "Software"), to deal in the Software without restriction,
// including without limitation the rights to use, copy, modify,
// merge, publish, distribute, sublicense, and/or sell copies of the Software,
// and to permit persons to whom the Software is furnished to do so,
// subject to the following conditions:

// The above copyright notice and this permission notice shall be included
// in all copies or substantial portions of the Software.

// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
// OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
// WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
// IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

var timeElapsed, tempDataArray, heatDataArray, setpointDataArray, dutyCycle, options_temp, options_heat, plot;
var capture_on = 0;
var tempUnits, temp, setpoint;
// Roaster animation vars
var elem, output, tilt, isCCW; // DOM objects
var rHeight, rx, rRect, rCircle, rCross, rCrosses;
var rPercentFull, rCurrentTilt, rAngleProbeOne;
var two;

// Column highlighting
$('input[name=profilelock]').on('click', function() {
    var $currentTable = $(this).closest('table');
    var index = $(this).parent().index();
    $currentTable.find('td').removeClass('col-highlight');
    $currentTable.find('input[type=number]').removeAttr("disabled");
    $currentTable.find('tr').each(function() {
        if($(this).hasClass("lockable")){
            var $mytd = $(this).find('td').eq(index-1);
            $mytd.addClass('col-highlight');
            $mytd.find('input[type=number]').each(function() { $(this).attr("disabled","disabled"); });
        }
    });
});

// MAFS!!
// Calculate the profile table
$('input.profile').on('change paste keyup', function() {
    validateProfile();
});


// Highilight a row
$('.selectRow').click(function() {
	$('.selectRow').removeClass("row-highlight");
 // removes all the highlights from the table
	$(this).addClass('row-highlight');
});

(function ($) {
  $.fn.serializeDisabled = function () {
    var obj = {};

    $(':disabled[name]', this).each(function () { 
        obj[this.name] = $(this).val(); 
    });
    return $.param(obj);
  }
})(jQuery);

function validateProfile(){
    var tableValues = new Array();
    var lockedCol = $('#profileTable').find('input[disabled=disabled]').closest('td').index() - 1;
    var myRow = $(this).closest('tr').index() - 1;
    var myCol = $(this).closest('td').index() - 1;
    var profileBuilder = new Array(4);

    $('#profileTable tr').each(function(row, tr){
        // ramp, time, temp
        if(row == 2){
            tableValues[row] = ['','', $(tr).find('td:eq(2)').find('input').val()];
        }
        else{
            tableValues[row] = [
                $(tr).find('td:eq(0)').find('input').val(),                        
                $(tr).find('td:eq(1)').find('input').val(),                        
                $(tr).find('td:eq(2)').find('input').val()
                ];
        }
    });
    // First row is headers, second is radio buttons
    tableValues.shift();
    tableValues.shift();
    
    var submitReady = true;
    for(var i = 1; i < tableValues.length; i++){
        var oldTemp = tableValues[i-1][2];
        // Only calculate if there's an old temperature
        if(oldTemp != ''){ 
            var full = 0;
            var empty = lockedCol;
            for(var j = 0; j < 3; j++){
                if(tableValues[i][j] != ''){
                    full += 1;
                }
                else{
                    submitReady = false;
                    empty = j;
                }
            }

            if(full < 3 && i == myRow && empty == myCol){
                // Don't do anything if we've just cleared out our input field
                full = 0;
            }
            if (full >= 2){
                // If we have 2, we calculate the one that's empty
                if(empty == 0){
                    tableValues[i][0] = (tableValues[i][2] - oldTemp) / tableValues[i][1];
                }
                if(empty == 1){
                    tableValues[i][1] = (tableValues[i][2] - oldTemp) / tableValues[i][0];
                }
                if(empty == 2){
                    tableValues[i][2] = tableValues[i][0] * tableValues[i][1];
                }
            }
            // Otherwise we fall through. Need at least two values to calculate
        }
    }

    $('#profileTable input[type=number]').each(function(count,input){
        if(count == 0){
            input.value = tableValues[0][2];
        }
        else{
            input.value = tableValues[Math.floor((count+2)/3)][(count+2) % 3];
        }
    });

    var totalTime = 0;
    for(var i=1;i<tableValues.length; i++){
        profileBuilder[i-1] = parseFloat(tableValues[i][1]);
        if(profileBuilder[i-1] == profileBuilder[i-1]){
            totalTime += profileBuilder[i-1];
        }
        else{
            profileBuilder[i-1] = '';
        }
    }
    profileBuilder[3] = "@" + tableValues[3][2] + "&degF";
    $("#profileOutput").html(profileBuilder.slice(0,3).join("/")+profileBuilder[3]); 
    $("#totaltime").html(totalTime);
    if(submitReady){
        $('#saveprofile').prop('disabled',false);
        init();
    }
    else{
        $('#saveprofile').prop('disabled',true);
    }
}

// Callback for profile load button
function loadProfile(){
    var profile = fr.result
    vals = jQuery.parseJSON(profile);
    $('#ambientFinaltemp').val(vals["ambient"]["finaltemp"]);
    $('#dryingRamp').val(vals["drying"]["ramp"]);
    $('#dryingTime').val(vals["drying"]["time"]);
    $('#dryingFinaltemp').val(vals["drying"]["finaltemp"]);
    $('#developmentRamp').val(vals["development"]["ramp"]);
    $('#developmentTime').val(vals["development"]["time"]);
    $('#developmentFinaltemp').val(vals["development"]["finaltemp"]);
    $('#finishRamp').val(vals["finish"]["ramp"]);
    $('#finishTime').val(vals["finish"]["time"]);
    $('#finishFinaltemp').val(vals["finish"]["finaltemp"]);
    // validate that it's a good profile.
    validateProfile();
    // Likely do some modifications here so load it back in
    vals["ambient"]["finaltemp"] = $('#ambientFinaltemp').val();
    vals["drying"]["ramp"] = $('#dryingRamp').val();
    vals["drying"]["time"] = $('#dryingTime').val();
    vals["drying"]["finaltemp"] = $('#dryingFinaltemp').val();
    vals["development"]["ramp"] = $('#developmentRamp').val();
    vals["development"]["time"] = $('#developmentTime').val();
    vals["development"]["finaltemp"] = $('#developmentFinaltemp').val();
    vals["finish"]["ramp"] = $('#finishRamp').val();
    vals["finish"]["time"]= $('#finishTime').val();
    vals["finish"]["finaltemp"] = $('#finishFinaltemp').val();

    // upload 
    jQuery.ajax({
        type: 'POST',
        url : "/postprofile",
        data: JSON.stringify(vals),
        contentType: 'application/json',
        dataType: 'json',
        success:function(data){
        },
    });
}

function findLS(selected_start, selected_end, in_pointArray) {

	var i;
	var values_x = [];
	var values_y = [];
	var in_pointArrayLength = in_pointArray.length;

	for ( i = 0; i < in_pointArrayLength; i++) {
		values_x.push(in_pointArray[i][0]);
		values_y.push(in_pointArray[i][1]);
	}

	var values_length = values_x.length;

	if (values_length != values_y.length) {
		throw new Error('x and y are not same size.');
	}

	if ((selected_start == 0) || (selected_end == 0)) {
		alert("Make a Selection");
	}
	// find indices	of selection
	var selection_start_index;
	var selection_end_index;
	var found_start = false;
	for ( i = 0; i < values_length; i++) {
		if ((values_x[i] >= selected_start) && (found_start == false)) {
			selection_start_index = i;
			found_start = true;
		}
		if (values_x[i] <= selected_end) {
			selection_end_index = i;
		}
	}

	var sum_x = 0;
	var sum_y = 0;
	var sum_xy = 0;
	var sum_xx = 0;
	var count = 0;
	var x = 0;
	var y = 0;
	/*
	 * Calculate the sum for each of the parts from imax to end
	 */
	for ( i = selection_start_index; i <= selection_end_index; i++) {
		x = values_x[i];
		y = values_y[i];
		sum_x += x;
		sum_y += y;
		sum_xx += x * x;
		sum_xy += x * y;
		count++;
	}

	/*
	 * Calculate m and b for the formula:
	 * y = x * m + b
	 */
	var m = (count * sum_xy - sum_x * sum_y) / (count * sum_xx - sum_x * sum_x);
	var b = (sum_y / count) - (m * sum_x) / count;

	var out_pointArray = [];

	for ( i = selection_start_index; i <= selection_end_index; i++) {
		x = values_x[i];
		y = m * x + b;
		out_pointArray.push([x, y]);
	}

	return [out_pointArray, m, b];
}

function showTooltip(x, y, contents) {
	jQuery('<div id="tooltip">' + contents + '</div>').css({
		position : 'absolute',
		display : 'none',
		top : y + 5,
		left : x + 5,
		border : '1px solid #fdd',
		padding : '2px',
		'background-color' : '#fee',
		opacity : 0.80
	}).appendTo("body").fadeIn(200);
}

function storeData(index, data) {
	if (data.mode == "auto") {
		//setpoint_C = (5.0/9.0)*(parseFloat(data.set_point) - 32);
		setpointDataArray[index].push([timeElapsed[index], parseFloat(data.set_point)]);
	} else {
		setpointDataArray[index] = [];
	}

	tempDataArray[index].push([timeElapsed[index], parseFloat(data.temp)]);
	heatDataArray[index].push([timeElapsed[index], parseFloat(data.gasOutput)]);

	//tempDataArray[0].push([i,parseFloat(data.temp)]);
	//heatDataArray[0].push([i,parseFloat(data.gasOutput)]);

	while (tempDataArray[index].length > jQuery('#windowSizeText').val()) {
		tempDataArray[index].shift();
	}

	while (heatDataArray[index].length > jQuery('#windowSizeText').val()) {
		heatDataArray[index].shift();
	}

	timeElapsed[index] += parseFloat(data.elapsed);

	jQuery('#windowSizeText').change(function() {
		tempDataArray[index] = [];
		heatDataArray[index] = [];
		timeElapsed[index] = 0;
	});
}

function plotData(index, data) {

	if (data.mode == "auto") {
		plot = jQuery.plot($("#tempplot"), [tempDataArray[index], setpointDataArray[index]], options_temp);
	} else {
		plot = jQuery.plot($("#tempplot"), [tempDataArray[index]], options_temp);
	}
	plot = jQuery.plot($("#heatplot"), [heatDataArray[index]], options_heat);
	//plot.setData([dataarray]);
	//plot.draw();
}

//long polling - wait for message
function waitForMsg() {

	var className;

	jQuery.ajax({
		type : "GET",
		url : "/getstatus",
		dataType : "json",
		async : true,
		cache : false,
		timeout : 50000,

		success : function(data) {

			//alert(data.mode);
			//temp_F = (9.0/5.0)*parseFloat(data.temp) + 32;
			//temp_F = temp_F.toFixed(2);
			//temp_C = (5.0/9.0)*(parseFloat(data.temp) - 32);
			//temp_C = temp_C.toFixed(2);

			jQuery('#dutyCycleUnits').html("%");
			if (data.tempUnits == "F") {
				jQuery('#tempResponseUnits').html("&#176F");
				jQuery('#setpointResponseUnits').html("&#176F");
				jQuery('#setpointInputUnits').html("&#176F");
			} else {
				jQuery('#tempResponseUnits').html("&#176C");
				jQuery('#setpointResponseUnits').html("&#176C");
				jQuery('#setpointInputUnits').html("&#176C");
			}

            for(i=1;i<=data.tempSensors.length;i++){
                jQuery('#tempResponse'+i).html(data.tempSensors[i-1][2]);
            }
			jQuery('#modeResponse').html(data.mode);
			jQuery('#setpointResponse').html(data.set_point);
			jQuery('#dutycycleResponse').html(data.gasOutput.toFixed(2));
			jQuery('#cycletimeResponse').html(data.sampleTime);
			jQuery('#k_paramResponse').html(data.k_param);
			jQuery('#i_paramResponse').html(data.i_param);
			jQuery('#d_paramResponse').html(data.d_param);

            // What is the angle of probe 1?
            rAngleProbeOne = data.roasterRotation;

			storeData(0, data);
			if (capture_on == 1) {
				if ($('#1Row').hasClass('row-highlight') == true) {
					plotData(0, data);
				}
				//in millisec
                setTimeout('waitForMsg()', 1);
			}
            else {
                // Don't bombard us if we're not capturing
                setTimeout('waitForMsg()', 1);
            }
		}
	});
};


function drawProbes(two, total_height, probes) {
  var width = 2;
  var height =  total_height/2/2;
  var p = [4];
  var group = two.makeGroup();
  if(probes[0]){
    p[0] = two.makeRectangle(0, height/2, width, height);
    p[0].stroke = 'rgb(66,133,244)';
    group.add(p[0]);
  }
  if(probes[1]){
    p[1] = two.makeRectangle(0, -height/2, width, height);
    p[1].stroke = 'rgb(15, 157, 88)';
    group.add(p[1]);
  }
  if(probes[2]){
    p[2] = two.makeRectangle(-height/2, 0, height, width);
    p[2].stroke = 'rgb(244, 160, 0)';
    group.add(p[2]);
  }
  if(probes[3]){
    p[3] = two.makeRectangle(height/2, 0, height, width);
    p[3].stroke = 'rgb(219, 68, 5)';
    group.add(p[3]);
  }
  return group;
}


jQuery(document).ready(function() {
    // Roaster animation setup
    rHeight = 200;
    rPercentFull = 50;
    rCurrentTilt = 0;

    // Find our DOM objects
    elem = document.getElementById('draw-animation');
    rx = elem.offsetWidth/2;
    ry = rHeight / 2; 
    output = document.getElementById('output');
    tilt = document.getElementById("spillangle").value;

    // Create our Two.js object
    two = new Two({
      autostart: true,
      width: rx * 2,
      height: ry * 2,
    }).appendTo(elem);

    rRect = two.makeRectangle(rx, ry, rHeight , rHeight);
    rCircle = two.makeCircle(rx, ry, rHeight/2);
    rCircle.noStroke().fill = 'chocolate';
    var rContainer = two.makeGroup(rCircle);

    rCross = drawProbes(two, rHeight, [true,true,true,true]);
    rCross.linewidth = 5;
    rCross.translation.set(rx, ry);
    rCrosses = two.makeGroup(rCross);
    rContainer.mask = rRect;

    // Bind our update trigger
    two.bind('update', function(frameCount) {
      var tick = 100;
      var rPercentFull = document.getElementById("fullpercent").value;
      var pfull_mult = (rHeight * (rPercentFull * 0.01));
      var qturn = 90 * Math.PI /180;
      var rot = frameCount / tick;
      var rDirection = $('#direction').is(":checked");
      if (rDirection){
        rCross.rotation -= 0.01;
      }
      else{
        rCross.rotation += 0.01;
      }
      tilt = document.getElementById("spillangle").value;

      //rCross.rotation = rot+qturn;

      if(Math.round(rCurrentTilt*100)/100 != Math.round(tilt*100)/100){
        rRect.rotation = rCurrentTilt+qturn;
        rRect.translation.x = (rHeight - pfull_mult) * Math.cos(rCurrentTilt+qturn) + rx;
        rRect.translation.y = (rHeight - pfull_mult) * Math.sin(rCurrentTilt+qturn) + ry;
        if(rCurrentTilt < tilt){
          rCurrentTilt += 1/tick;
        }
        else {
          rCurrentTilt -= 1/tick;
        }
      }
      else{
        rRect.translation.x = (rHeight - pfull_mult) * Math.cos(rRect.rotation) + rx;
        rRect.translation.y = (rHeight - pfull_mult) * Math.sin(rRect.rotation) + ry;
      }
      //output.innerHTML = "rot: " + rot + "<p>frameCount/tick: " + frameCount/tick + "<p>frameCount/tick * -1: " + (frameCount / tick) * -1
    });

    // one-time on load, lock the time column
    jQuery('#ramplock').attr("checked",true);
    var currentTable = $('#profileTable');
    var index = $('th[id=rampcol]').index();
    currentTable.find('td').removeClass('col-highlight');
    currentTable.find('input[type=number]').removeAttr("disabled");
    currentTable.find('tr').each(function() {
        if($(this).hasClass("lockable")){
            var $mytd = $(this).find('td').eq(index-1)
            $mytd.addClass('col-highlight');
            $mytd.find('input[type=number]').each(function() { $(this).attr("disabled","disabled"); });
        }
    });

    // Also lock the profile save button
    // FEATURE: check to make sure the table is populated. We may want to upload profiles from a file
    $('#saveprofile').prop('disabled',true);

    // Deal with our load profile
    $('input:file[id=loadprofile]').on("change", function() {
        $('button:submit[id=uploadprofile]').prop('disabled', !$(this).val()); 
    });

    
	jQuery('#stop').click(function() {
		capture_on = 0;
        $('#start').removeAttr("disabled");
        $('#stop').attr("disabled","disabled");
	});
	jQuery('#start').click(function() {
		capture_on = 1;
        $('#start').attr("disabled","disabled");
        $('#stop').removeAttr("disabled");
		tempDataArray = [[], [], []];
		heatDataArray = [[], [], []];
		timeElapsed = [0, 0, 0];
		waitForMsg();
	});

    // And make sure they're set right on load
    $('#start').removeAttr("disabled");
    $('#stop').attr("disabled","disabled");
    init();

	jQuery("#tempplot").bind("plotselected", function(event, ranges) {
		var selected_start = ranges.xaxis.from;
		var selected_end = ranges.xaxis.to;
		var k_param, i_param, d_param, normalizedSlope, pointArray, m, b, deadTime; 
        var dryingRamp, dryingFinaltemp, dryingTime;
        var developmentRamp, developmentFinaltemp, developmentTime;
        var finishRamp, finishFinaltemp, finishTime;
		var LS = findLS(selected_start, selected_end, tempDataArray[0]);
		pointArray = LS[0]; m = LS[1]; b = LS[2];
		deadTime = pointArray[0][0];
		normalizedSlope = m / jQuery('input:text[name=dutycycle]').val();
		jQuery('#deadTime').html(deadTime);
		jQuery('#normSlope').html(normalizedSlope);
		plot = jQuery.plot($("#tempplot"), [tempDataArray[0], pointArray], options_temp);
		k_param = 1.2 / (deadTime * normalizedSlope);
		i_param = 2.0 * deadTime;
		d_param = 0.5 * deadTime;
		jQuery('#Kc_tune').html(k_param.toFixed(2).toString());
		jQuery('#I_tune').html(i_param.toFixed(2).toString());
		jQuery('#D_tune').html(d_param.toFixed(2).toString());
	});

	var previousPoint = null;
	jQuery("#tempplot").bind("plothover", function(event, pos, item) {
		if (item) {
			if (previousPoint != item.dataIndex) {
				previousPoint = item.dataIndex;

				jQuery("#tooltip").remove();
				var x = item.datapoint[0].toFixed(2), y = item.datapoint[1].toFixed(2);

				showTooltip(item.pageX, item.pageY, "(" + x + ", " + y + ")");
			}
		} else {
			jQuery("#tooltip").remove();
			previousPoint = null;
		}

	});

    // Save a roasting profile
	jQuery('#roastingProfileForm').submit(function(e) {
        e.preventDefault();
/*
		formdata = jQuery(this).serialize();
        formdata = formdata + '&' + jQuery(this).serializeDisabled();
        jQuery.ajax({
            type : "POST",
            url : "/postprofile",
            data : formdata,
            success : function(data) {
            },
        });
*/

		return false;
	});
	jQuery('#saveprofile').on('click',function() {
		form = $('#saveprofile').closest('form');
        formdata = form.serialize();
        formdata = formdata + '&' + form.serializeDisabled();
/*        svg = document.getElementById('profilesvg');

        profileCircles = [[,],[,],[,],[,]];
        profilePaths = [[,,,],[,,,],[,,,]];

        $circleArray = $('circle'); //get all circles
        $circleArray.each(function(idx, el){//go through each circle
            x_val = $(el).attr('cx');//get cx
            y_val = $(el).attr('cy');//get cy
            profileCircles[idx] = [x_val,y_val];
        });

        $svg = $('path[id=profilepath]');
        $svg.each(function(idx, el){//go through each path
            d  = $(el).attr('d');
            if(d){
                data =  d.split(' ');    //get data
                profilePaths[idx] = [data[4],data[5],data[6],data[7]];
            }
        });
        
        // Need a better array than this
        circleJSON = JSON.stringify(profileCircles);
        pathsJSON = JSON.stringify(profilePaths);
        formdata = formdata + '&' + circleJSON + '&' + pathsJSON; */
        jQuery.ajax({
            type : "POST",
            url : "/postprofile",
            data : formdata,
            success : function(data) {
            },
        });

		return false;
	});

    // Upload a roasting rofile
    jQuery('#uploadprofile').on('click', function(){
        var f = $('input[type=file]')[0].files[0];
        fr = new FileReader();
        fr.onload = loadProfile;
        fr.readAsText(f);
    });


	jQuery('#controlPanelForm').submit(function() {

		formdata = jQuery(this).serialize();

		if ($('#1Row').hasClass('row-highlight') == true) {

			jQuery.ajax({
				type : "POST",
				url : "/postparams/1",
				data : formdata,
				success : function(data) {
				},
			});
		}

		//reset plot
		if (jQuery('#off').is(':checked') == false) {
			tempDataArray = [[], [], []];
			heatDataArray = [[], [], []];
			setpointDataArray = [[], [], []];
			timeElapsed = [0, 0, 0];
		}

		return false;
	});

	i = 0;
	tempDataArray = [[], [], []];
	heatDataArray = [[], [], []];
	setpointDataArray = [[], [], []];
	timeElapsed = [0, 0, 0];

	options_temp = {
		series : {
			lines : {
				show : true
			},
			//points: {show: true},
			shadowSize : 0
		},
		yaxis : {
			min : null,
			max : null
		},
		xaxis : {
			show : true
		},
		grid : {
			hoverable : true
			//  clickable: true
		},
		selection : {
			mode : "x"
		}
	};

	options_heat = {
		series : {
			lines : {
				show : true
			},
			//points: {show: true},
			shadowSize : 0
		},
		yaxis : {
			min : 0,
			max : 100
		},
		xaxis : {
			show : true
		},
		selection : {
			mode : "x"
		}
	};

    plotData(0, []);
	waitForMsg();

});
