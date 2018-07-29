//
// Copyright (c) 2012-2014 Stephen P. Smith
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

//declare globals
var timeElapsed, tempDataArray, heatDataArray, setpointDataArray, dutyCycle, options_temp, options_heat, plot, gaugeDisplay, newGaugeDisplay;
var capture_on = 1;
var numTempSensors, tempUnits, temp, setpoint;

// Column highlighting
$('input[name=profilelock]').on('click', function() {
    var $currentTable = $(this).closest('table');
    var index = $(this).parent().index();
    $currentTable.find('td').removeClass('col-highlight');
    $currentTable.find('input[type=number]').removeAttr("disabled");
    $currentTable.find('tr').each(function() {
        if($(this).hasClass("lockable")){
            var $mytd = $(this).find('td').eq(index-1)
            $mytd.addClass('col-highlight');
            $mytd.find('input[type=number]').each(function() { $(this).attr("disabled","disabled"); });
        }
    });
});

// MAFS!!
$('input.profile').on('change paste keyup', function() {
    var myIndex = $(this).closest('td').index()-1;
    var $myRow = $(this).closest('tr');
    var lockedCol = $myRow.find('input[disabled=disabled]').closest('td').index() - 1;
    var rowNum = $myRow.index();
    var inArr = [];
    var tempDiff = -1;
    var oldTemp = -1;

    // We have 5 rows and only care about calculating for three
    if(rowNum <= 1 ){
        alert("no previous row");
        return;
    }
    else {
        var oldTemp = $('#profileTable').find('tr').eq(rowNum).find('td').eq(-1).find('input[type=number]').val();
        if (oldTemp == ''){
            return;
        }
    }

    // Well, shit. We have to calculate our row AND every row after ours.
    // temp/time = ramp
    // ramp*time = temp
    // temp/ramp = time
    var valCount = 0;
    $myRow.find('input').each(function(column, inVal) {
        inArr.push($(inVal).val()); 
        if($(inVal).val() != ''){
            valCount++;
        }
    });

    // need at least two values to calculate
    if (valCount <= 1){
        //alert('Not enough values to calculate');
        return;
    }

    var [ramp,time,temp] = inArr;
    if(valCount == 3){
        // This is the only time it's important to know which one is locked
        if(lockedCol == 0){
            ramp = (temp - oldTemp) / time;
        }
        else if (lockedCol = 1){
            time = (temp - oldTemp) / ramp;
        }
        else{
            temp = ramp * time;
        }
    }
    else{
        if(ramp == ''){
            ramp = (temp - oldTemp) / time;
        }
        else if(temp == ''){
            temp = ramp * time;
        }
        else{
            time = (temp - oldTemp) / ramp;
        }
    }

    $inputs = $myRow.find('input[type=number]');
    var rampIn = $myRow.find('input[type=number]')[0];
    var timeIn = $myRow.find('input[type=number]')[1];
    var tempIn = $myRow.find('input[type=number]')[2];

    rampIn.value = ramp;
    timeIn.value = time;
    tempIn.value = temp;
/*
    alert(inArr);
    alert(inArr[0]);
    alert(inArr[1]);
    alert(inArr[2]);
*/
    
});

$('.selectRow').click(function() {
	$('.selectRow').removeClass("row-highlight");
 // removes all the highlights from the table
	$(this).addClass('row-highlight');
});

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
		url : "/getstatus/1",
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

			numTempSensors = parseInt(data.numTempSensors);

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

			jQuery('#tempResponse').html(data.temp);
			jQuery('#modeResponse').html(data.mode);
			jQuery('#setpointResponse').html(data.set_point);
			jQuery('#dutycycleResponse').html(data.gasOutput.toFixed(2));
			jQuery('#cycletimeResponse').html(data.sampleTime);
			jQuery('#k_paramResponse').html(data.k_param);
			jQuery('#i_paramResponse').html(data.i_param);
			jQuery('#d_paramResponse').html(data.d_param);

			//gaugeDisplay.setValue(parseFloat(data.temp));

			storeData(0, data);

			if (capture_on == 1) {
				if ($('#1Row').hasClass('row-highlight') == true) {
					plotData(0, data);
				}
				setTimeout('waitForMsg()', 1);
				//in millisec
			}
		}
	});
	if (numTempSensors >= 2) {
		jQuery.ajax({
			type : "GET",
			url : "/getstatus/2",
			dataType : "json",
			async : true,
			cache : false,
			timeout : 50000,

			success : function(data) {

				jQuery('#dutyCycleUnits2').html("%");

				if (data.tempUnits == "F") {
					jQuery('#tempResponseUnits2').html("&#176F");
					jQuery('#setpointResponseUnits2').html("&#176F");
					jQuery('#setpointInputUnits2').html("&#176F");
				} else {
					jQuery('#tempResponseUnits2').html("&#176C");
					jQuery('#setpointResponseUnits2').html("&#176C");
					jQuery('#setpointInputUnits2').html("&#176C");
				}

				jQuery('#tempResponse2').html(data.temp);
				jQuery('#modeResponse2').html(data.mode);
				jQuery('#setpointResponse2').html(data.set_point);
				jQuery('#dutycycleResponse2').html(data.gasOutput.toFixed(2));
				jQuery('#cycletimeResponse2').html(data.sampleTime);
				jQuery('#k_paramResponse2').html(data.k_param);
				jQuery('#i_paramResponse2').html(data.i_param);
				jQuery('#d_paramResponse2').html(data.d_param);
				jQuery('#d_paramResponse2').html(data.d_param);

				storeData(1, data);

				if (capture_on == 1) {
					if ($('#secondRow').hasClass('row-highlight') == true) {
						plotData(1, data);
					}
				}
			}
		});
	}
	if (numTempSensors >= 3) {
		jQuery.ajax({
			type : "GET",
			url : "/getstatus/3",
			dataType : "json",
			async : true,
			cache : false,
			timeout : 50000,

			success : function(data) {

				jQuery('#dutyCycleUnits3').html("%");

				if (data.tempUnits == "F") {
					jQuery('#tempResponseUnits3').html("&#176F");
					jQuery('#setpointResponseUnits3').html("&#176F");
					jQuery('#setpointInputUnits3').html("&#176F");
				} else {
					jQuery('#tempResponseUnits3').html("&#176C");
					jQuery('#setpointResponseUnits3').html("&#176C");
					jQuery('#setpointInputUnits3').html("&#176C");
				}

				jQuery('#tempResponse3').html(data.temp);
				jQuery('#modeResponse3').html(data.mode);
				jQuery('#setpointResponse3').html(data.set_point);
				jQuery('#dutycycleResponse3').html(data.gasOutput.toFixed(2));
				jQuery('#cycletimeResponse3').html(data.sampleTime);
				jQuery('#k_paramResponse3').html(data.k_param);
				jQuery('#i_paramResponse3').html(data.i_param);
				jQuery('#d_paramResponse3').html(data.d_param);

				storeData(2, data);

				if (capture_on == 1) {
					if ($('#thirdRow').hasClass('row-highlight') == true) {
						plotData(2, data);
					}
				}
			}
		});
	}

};

jQuery(document).ready(function() {

    // one-time on load, lock the time column
    jQuery('#timelock').attr("checked",true);
    var currentTable = $('#profileTable');
    var index = $('th[name=timecol]').index();
    currentTable.find('td').removeClass('col-highlight');
    currentTable.find('input[type=number]').removeAttr("disabled");
    currentTable.find('tr').each(function() {
        if($(this).hasClass("lockable")){
            var $mytd = $(this).find('td').eq(index-1)
            $mytd.addClass('col-highlight');
            $mytd.find('input[type=number]').each(function() { $(this).attr("disabled","disabled"); });
        }
    });

    
	jQuery('#stop').click(function() {
		capture_on = 0;
	});
	jQuery('#restart').click(function() {
		capture_on = 1;
		tempDataArray = [[], [], []];
		heatDataArray = [[], [], []];
		timeElapsed = [0, 0, 0];
		waitForMsg();
	});
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

	jQuery('#roastingProfileForm').submit(function() {
		formdata = jQuery(this).serialize();
        // See if all of our values are filled in
        var pairs = formdata.split('&');
        pairs.some(function(pair){
            val = pair.split('=')[1]; 
            if (val == ''){
                window.alert('All profile values are required');
                return true;
            } 
        });
        jQuery.ajax({
            type : "POST",
            url : "/postprofile",
            data : formdata,
            success : function(data) {
            },
        });

		return false;
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
		if (($('#secondRow').hasClass('row-highlight') == true) && (numTempSensors >= 2)) {

			jQuery.ajax({
				type : "POST",
				url : "/postparams/2",
				data : formdata,
				success : function(data) {
				},
			});
		}
		if (($('#thirdRow').hasClass('row-highlight') == true) && (numTempSensors >= 3)) {

			jQuery.ajax({
				type : "POST",
				url : "/postparams/3",
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

	//draw gauge
	//var options_gauge = {
	//	majorTickLabel : true,
	//	value : 60,
	//	label : 'Temp',
	//	unitsLabel : '' + String.fromCharCode(186),
	//	min : 60,
	//	max : 220,
	//	majorTicks : 9,
	//	minorTicks : 9, // small ticks inside each major tick
	//	greenFrom : 60,
	//	greenTo : 95,
	//	yellowFrom : 95,
	//	yellowTo : 150,
	//	redFrom : 150,
	//	redTo : 200
	//};

	//gaugeDisplay = new Gauge(document.getElementById('tempGauge'), options_gauge);

	// line plot Settings
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

	waitForMsg();

});
