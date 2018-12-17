/* bezier-spline.js
 *
 * computes cubic bezier coefficients to generate a smooth
 * line through specified points. couples with SVG graphics 
 * for interactive processing.
 *
 * For more info see:
 * http://www.particleincell.com/2012/bezier-splines/ 
 *
 * Lubos Brieda, Particle In Cell Consulting LLC, 2012
 * you may freely use this algorithm in your codes however where feasible
 * please include a link/reference to the source article
 */ 

var svg;
var S=new Array() /*splines*/
var V=new Array() /*vertices*/
var controlPoints=new Array() /* control points */
var C   /*current object*/
var x0,y0 /*svg offset*/
var svgWidth = 730;
var svgHeight = 280;
var plotWidth = 650;
var plotHeight = 250;
var gridOffsetX = svgWidth - plotWidth - 25;
var gridOffsetY = svgHeight - plotHeight - 20;

/*saves elements as global variables*/
function init() {
    var myDiv =document.getElementById("profilecurve") /*svg object*/
    while (myDiv.hasChildNodes()) {
        myDiv.removeChild(myDiv.lastChild);
    }


    svg =  document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttributeNS(null,"height",svgHeight);
    svg.setAttributeNS(null,"width",svgWidth);
    svg.setAttributeNS(null,"id","profilesvg");
    drawGrid(svg);
    myDiv.appendChild(svg);
    updateCurve();
}

function drawGrid(svg){
    var defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    var pattern = document.createElementNS("http://www.w3.org/2000/svg", "pattern");
    var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    var rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    var g = document.createElementNS("http://www.w3.org/2000/svg","g");

    var totalTime = parseFloat($('#totaltime').html());
    if (isNaN(totalTime)) { totalTime = 0; }

    path.setAttributeNS(null,"d","M 10 0 L 0 0 0 10");
    path.setAttributeNS(null,"fill","none");
    path.setAttributeNS(null,"stroke","gray");
    path.setAttributeNS(null,"stroke-width","1");
    pattern.setAttributeNS(null,"id","grid");
    pattern.setAttributeNS(null,"width","10");
    pattern.setAttributeNS(null,"height","10");
    pattern.setAttributeNS(null,"patternUnits","userSpaceOnUse");
    rect.setAttributeNS(null,"width",plotWidth+1);
    rect.setAttributeNS(null,"height",plotHeight+1);
    rect.setAttributeNS(null,"fill","url(#grid)");
    rect.setAttributeNS(null,"transform","translate("+gridOffsetX+","+gridOffsetY+")");
    g.setAttributeNS(null,"class","labels y-labels");
    for (var y=0;y<= plotHeight+50;y+=50){
        var text = document.createElementNS("http://www.w3.org/2000/svg","text");
        text.setAttributeNS(null,"x","0");
        text.setAttributeNS(null,"y",(svgHeight+30) - y);
        var textNode = document.createTextNode(y);
        text.appendChild(textNode);
        g.appendChild(text);
    }
    if(totalTime > 0){
        var ticks = totalTime / 6;
        for (var x=0, t = 0;x<= plotWidth;x+=(plotWidth/6), t += ticks){
            var text = document.createElementNS("http://www.w3.org/2000/svg","text");
            text.setAttributeNS(null,"x", x+gridOffsetX);
            text.setAttributeNS(null,"y",svgHeight);
            var textNode = document.createTextNode(Math.round(t));
            text.appendChild(textNode);
            g.appendChild(text);
        }
    } 
    svg.appendChild(g);
    pattern.appendChild(path);
    defs.appendChild(pattern);
    svg.appendChild(defs);
    svg.appendChild(rect);
}

function updateCurve(){
    var locs = [];
    $('#profileTable tr').each(function(row, tr){
        var time = $(tr).find('td:eq(1)').find('input').val();
        var temp = $(tr).find('td:eq(2)').find('input').val();
        if(row == 2){
            time = 0;
        }
        locs.push([time,temp]);
    });

    // get rid of headers
    locs.shift();
    locs.shift();
    locs.pop();

    var time = 0;  // Start with an offset of 30
    var totalTime = parseFloat($('#totaltime').html());
    //var increments = (plotWidth - (time*2))/totalTime;
    var increments = plotWidth /totalTime;
    
    for(var i=0;i<locs.length;i++){
        S[i] = createPath("blue");
        time += (parseFloat(locs[i][0])*increments);
        V[i] = createKnot(time+gridOffsetX, svgHeight-(parseFloat(locs[i][1])-30));
    }
    updateSplines();
}

/*creates and adds an SVG circle to represent a control point*/
function createCP(color,x,y)
{
  var C=document.createElementNS("http://www.w3.org/2000/svg","circle")
  C.setAttributeNS(null,"r",5)
  C.setAttributeNS(null,"cx",x)
  C.setAttributeNS(null,"cy",y)
  C.setAttributeNS(null,"fill",color)
  C.setAttributeNS(null,"stroke","black")
  C.setAttributeNS(null,"stroke-width","2")
  svg.appendChild(C)  
  return C
}

/*creates and adds an SVG path without defining the nodes*/
/*creates and adds an SVG circle to represent knots*/
function createKnot(x,y)
{
  var C=document.createElementNS("http://www.w3.org/2000/svg","circle")
  C.setAttributeNS(null,"r", 5)
  C.setAttributeNS(null,"cx",x)
  C.setAttributeNS(null,"cy",y)
  C.setAttributeNS(null,"fill","gold")
  C.setAttributeNS(null,"stroke","black")
  C.setAttributeNS(null,"stroke-width","2")
  svg.appendChild(C)  
  return C
}

/*creates and adds an SVG path without defining the nodes*/
function createPath(color,width)
{   
  width = (typeof width == 'undefined' ? "4" : width);
  var P=document.createElementNS("http://www.w3.org/2000/svg","path")
  P.setAttributeNS(null,"fill","none")
  P.setAttributeNS(null,"id","profilepath")
  P.setAttributeNS(null,"stroke",color)
  P.setAttributeNS(null,"stroke-width",width)
  svg.appendChild(P)
  return P
}

/*computes spline control points*/
function updateSplines()
{ 
  /*grab (x,y) coordinates of the control points*/
  x=new Array();
  y=new Array();
  for (i=0;i<4;i++)
  {
    /*use parseInt to convert string to int*/
    x[i]=parseInt(V[i].getAttributeNS(null,"cx"))
    y[i]=parseInt(V[i].getAttributeNS(null,"cy"))
  }
  
  /*computes control points p1 and p2 for x and y direction*/
  px = computeControlPoints(x);
  py = computeControlPoints(y);
  
  /*updates path settings, the browser will draw the new spline*/
  for (i=0;i<3;i++)
    S[i].setAttributeNS(null,"d",
      path(x[i],y[i],px.p1[i],py.p1[i],px.p2[i],py.p2[i],x[i+1],y[i+1]));

  /* Update our control points */
  for(i=0;i<controlPoints.length;i++){
    controlPoints[i][0].setAttributeNS(null,"cx",px.p1[i]);
    controlPoints[i][0].setAttributeNS(null,"cy",py.p1[i]);
    controlPoints[i][1].setAttributeNS(null,"cx",px.p2[i]);
    controlPoints[i][1].setAttributeNS(null,"cy",py.p2[i]);
  }
  return {px,py};
}

/*creates formated path string for SVG cubic path element*/
function path(x1,y1,px1,py1,px2,py2,x2,y2)
{
  return "M "+x1+" "+y1+" C "+px1+" "+py1+" "+px2+" "+py2+" "+x2+" "+y2;
}

/*computes control points given knots K, this is the brain of the operation*/
function computeControlPoints(K)
{
  p1=new Array();
  p2=new Array();
  n = K.length-1;
  
  /*rhs vector*/
  a=new Array();
  b=new Array();
  c=new Array();
  r=new Array();
  
  /*left most segment*/
  a[0]=0;
  b[0]=2;
  c[0]=1;
  r[0] = K[0]+2*K[1];
  
  /*internal segments*/
  for (i = 1; i < n - 1; i++)
  {
    a[i]=1;
    b[i]=4;
    c[i]=1;
    r[i] = 4 * K[i] + 2 * K[i+1];
  }
      
  /*right segment*/
  a[n-1]=2;
  b[n-1]=7;
  c[n-1]=0;
  r[n-1] = 8*K[n-1]+K[n];
  
  /*solves Ax=b with the Thomas algorithm (from Wikipedia)*/
  for (i = 1; i < n; i++)
  {
    m = a[i]/b[i-1];
    b[i] = b[i] - m * c[i - 1];
    r[i] = r[i] - m*r[i-1];
  }
 
  p1[n-1] = r[n-1]/b[n-1];
  for (i = n - 2; i >= 0; --i)
    p1[i] = (r[i] - c[i] * p1[i+1]) / b[i];
    
  /*we have p1, now compute p2*/
  for (i=0;i<n-1;i++)
    p2[i]=2*K[i+1]-p1[i+1];
  
  p2[n-1]=0.5*(K[n]+p1[n-1]);
  
  return {p1:p1, p2:p2};
}

/*code from http://stackoverflow.com/questions/442404/dynamically-retrieve-html-element-x-y-position-with-javascript*/
function getOffset( el ) 
{
    var _x = 0;
    var _y = 0;
    while( el && !isNaN( el.offsetLeft ) && !isNaN( el.offsetTop ) ) {
        _x += el.offsetLeft - el.scrollLeft;
        _y += el.offsetTop - el.scrollTop;
        el = el.offsetParent;
    }
    return { top: _y, left: _x };
}

/*       
  x = (1-t)*(1-t)*(1-t)*p0x + 3*(1-t)*(1-t)*t*p1x + 3*(1-t)*t*t*p2x + t*t*t*p3x;
  y = (1-t)*(1-t)*(1-t)*p0y + 3*(1-t)*(1-t)*t*p1y + 3*(1-t)*t*t*p2y + t*t*t*p3y;
*/
function pointCoords(){
  var output =  document.getElementById("output");
  var dist, p0x, p1x, p2x, p3x, p0y, p1y, p2y, p3y;

  for(i=0;i<3;i++){
    dist = parseInt(V[i+1].getAttributeNS(null,"cx")) - parseInt(V[i].getAttributeNS(null,"cx"));
    p0x = parseInt(V[i].getAttributeNS(null,"cx"));
    p3x = parseInt(V[i+1].getAttributeNS(null,"cx"));
    p0y = parseInt(V[i].getAttributeNS(null,"cy"));
    p3y = parseInt(V[i+1].getAttributeNS(null,"cy"));
    
    // Control points
    p1x = parseInt(controlPoints[i][0].getAttributeNS(null,"cx"));
    p2x = parseInt(controlPoints[i][1].getAttributeNS(null,"cx"));
    p1y = parseInt(controlPoints[i][0].getAttributeNS(null,"cy"));
    p2y = parseInt(controlPoints[i][1].getAttributeNS(null,"cy"));

    for(t=0.0; t< 1; t+= (1/dist)){
      x = (1-t)*(1-t)*(1-t)*p0x + 3*(1-t)*(1-t)*t*p1x + 3*(1-t)*t*t*p2x + t*t*t*p3x;
      y = (1-t)*(1-t)*(1-t)*p0y + 3*(1-t)*(1-t)*t*p1y + 3*(1-t)*t*t*p2y + t*t*t*p3y;
      // Normalize
      
      x -= 30;
      y = -1 * ((y - 65 - 500)/1.5);
      output.innerHTML = output.innerHTML + "x: " + x + " y: " + y + "<p>"
    }
  }
}

