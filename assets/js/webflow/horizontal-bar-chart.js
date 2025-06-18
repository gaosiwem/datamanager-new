/*======================================
var options = {
    width: 500,
    marginLeft: 100,
    barHeight: 20,
    barSpace: 5,
    groupSpace: 30,
    ticks: 5,
    filterKey: undefined,
    groupKey: undefined, 
    nameKey: undefined,
    valuekey: undefined,
    urlkey: undefined,
    filterLabel: "Choose a Filter Item:",
    fontFace: 'auto',
    fontSize: 12
    minValue: 0,
    maxValue: 100,  // default = max(data)
    barUnit: undefined, // 'K' 'M', 'B'
    xAxisUnit: undefined, // 'K' 'M', 'B'
    colors:undefined // example: ['#111','#222','#333']
}
=======================================*/

//var horizonalBarChart = (selector, data, options) => new HorizonalBarChart(selector, data, options);

class HorizontalBarChart{
   
    constructor(selector, data, options){
        
        var options = options || {};
        this._selector = selector || undefined;          
        this._data = data || undefined;
        this._barHeight = options.barHeight || 20;
        this._barSpace = options.barSpace || 5;
        this._groupSpace = options.groupSpace || 30;
        this._width = options.width || 500;
        this._marginLeft = options.marginLeft || 100;
        this._filterLabel = options.filterLabel || 'Choose a Filter Item:';
        this._fontFace = options.fontFace || 'auto';
        this._fontSize = options.fontSize || 12;
        this.margin = { top: 0, right: 30, bottom: 20, left: this._marginLeft };
        this._ticks = options.ticks || 5;
        this._filterKey = options.filterKey || undefined;
        this._groupKey = options.groupKey || undefined;
        this._nameKey = options.nameKey || undefined;
        this._valueKey = options.valueKey || undefined;
        this._urlKey = options.urlKey || undefined;
        this._minValue = options.minValue || 0;
        this._maxValue = options.maxValue;
        if(this._data && this._valueKey){
            if(!this._maxValue){
                this._maxValue = 1.5 * d3.max(this._data, d => d[this._valueKey]);
            }
            this.sum = this.getSum(this._data, this._valueKey);
        }
        this._barUnit = options.barUnit || undefined;
        this._xAxisUnit = options.xAxisUnit || undefined;
        this._colors = options.colors || undefined;
        this.tooltip = d3.select("body").append("div")
                                        .attr("class", "toolTip")
                                        .attr("id","custom-toolTip")
                                        .style('font-family', this._fontFace);
                                        //.style('font-size', this._fontSize + 'px');
        this.createChart();
    }
    
    createChart(){
        if(this._selector && this._data && this._nameKey && this._valueKey){
            //var container = d3.select(this._selector);
            var container = document.getElementById(this._selector);
            container.innerHTML = '';

            if(this._filterKey){
                var filter_items = this.getFilterItems(this._data, this._filterKey);
                if(filter_items.length >0){
                    var chart_header_div = document.createElement("div");
                    chart_header_div.setAttribute("class", "chart-header");
                    
                    var filter_label = document.createElement("div");
                    filter_label.setAttribute("class", "filter-label");
                    filter_label.style.fontFamily = this._fontFace;
                    //filter_label.style.fontSize = this._fontSize + 'px';

                    filter_label.innerHTML = this._filterLabel;
                    chart_header_div.append(filter_label);
            
                    var selectElement = document.createElement("select");
                    selectElement.setAttribute("class", "select-list");
                    selectElement.style.fontFamily = this._fontFace;
                    //selectElement.style.fontSize = this._fontSize + 'px';

                    filter_items.forEach((item)=>{
                        var option = document.createElement("option");
                        option.value = item;
                        option.text = item;
                        selectElement.appendChild(option);
                    });

                    chart_header_div.appendChild(selectElement);
                    container.append(chart_header_div);
                    
                    selectElement.addEventListener('change', (event) => {
                        var filter_value = event.target.value;
                        this.drawFilterChart(filter_value);
                    });
                }
            }

            var chart_content_div = document.createElement("div");
            chart_content_div.setAttribute("class", "chart-content");

            container.append(chart_content_div);

            if(filter_items && filter_items.length>0){
                this.drawFilterChart(filter_items[0]);
            }else{
                this.drawChart(this._data);
            }
        }
    }

    drawFilterChart(filter_value){
        var filter_data = this._data.filter((item)=>{
            return item[this._filterKey] == filter_value;
        });
        this.drawChart(filter_data);
    }

    drawChart(chart_data){
        if(this._groupKey){
            var group_data = this.getGroupBy(chart_data, this._groupKey);
            var group_keys = Object.keys(group_data);
            if(group_keys.length > 0){
                this.drawGroupChart(chart_data);
            }else{
                this.drawSingleChart(chart_data);
            }
        }else{
           this.drawSingleChart(chart_data);
        }
    }

    drawGroupChart(chart_data){
        var group_data = this.getGroupBy(chart_data, this._groupKey);
        var group_keys = Object.keys(group_data);
        group_keys.sort((a,b)=>d3.ascending(a, b));
        var group_count= group_keys.length; 
        var height = chart_data.length * (this._barHeight +this._barSpace) + group_count * this._groupSpace + 10 + this.margin.top + this.margin.bottom;
        var chart_container = d3.select('.chart-content');
        chart_container.selectAll("*").remove();
        var chart = chart_container.append('svg')
          .style('width', '100%')
          .attr('viewBox', `0 0 ${this._width} ${height}`);
        var xScale = d3.scaleLinear()
          .range([0, this._width - this.margin.left - this.margin.right])
          .domain([this._minValue, this._maxValue]);
         // add the x Axis
         var xAxis = chart.append("g")
                          .attr("class", "grid")
                          .style('font-family', this._fontFace)
                          .style('font-size', this._fontSize + 'px')
                          .style('font-weight', 500)
                          .attr("transform", `translate(${this.margin.left}, ${height - this.margin.bottom})`)
                          .call(d3.axisBottom(xScale)
                                .ticks(this._ticks)
                                .tickSizeInner([-height])
                                .tickSizeOuter([0])
                                .tickPadding([10])
                                .tickFormat(d =>{ 
                                    return this.getLabelFormat(d,this._xAxisUnit);
                                }));       
        var color = d3.scaleOrdinal()
          .range(d3.schemeCategory10)  // 20, 20b, 20c
          .domain(chart_data.map(d => d[this._valueKey]));

        var y = 0;
        group_keys.forEach((group_key)=>{
           var group_items = group_data[group_key];
           group_items.sort((a,b)=>d3.ascending(a[this._nameKey], b[this._nameKey]));
           chart.append('text')
                .attr('class', 'item-label')
                .attr('alignment-baseline', 'middle')
                .attr('x', 0)
                .attr('y', y + this._groupSpace/2)
                .style('font-family', this._fontFace)
                .style('font-size', this._fontSize + 'px')
                .style('font-weight', 'bold')
                .text(group_key);
           y+=this._groupSpace;
           group_items.forEach(item=>{
               chart.append('rect')
                    .attr('class', '.label-bar')
                    .attr('fill', '#f8f8f8')
                    .attr('height',this._barHeight)
                    .attr('width', this.margin.left-5)
                    .attr('x', 0)
                    .attr('y', y)
                    .attr('rx', 2)
                    .attr('rx', 2)    
               chart.append('text')
                    .attr('class', 'item-label')
                    .attr('alignment-baseline', 'middle')
                    .attr('x', 5)
                    .attr('y', y +this._barHeight/2)
                    .style('font-family', this._fontFace)
                    .style('font-size', this._fontSize + 'px')
                    //.style('font-weight', 'bold')
                    .text(item[this._nameKey]);
               
               chart.data([item])
                    .append('rect')
                    .attr('class', 'bar')
                    .attr('fill', d=>{
                        if(this._colors){
                            return this.getColor(d[this._valueKey]);
                        }else{
                            return color(item[this._valueKey]);
                        }
                     })
                    .attr('height',this._barHeight)
                    .attr('width',0)
                    .attr('x', this.margin.left + 1)
                    .attr('y', y)
                    .on("mouseover", d=>this.onMouseOver(d))
                    .on("mouseout", d=>this.tooltip.style("display", "none"))
                    .on("click", d=>this.onMouseClick(d))
                    .transition()
                    .duration(500)
                    .attr("width", xScale(item[this._valueKey]));

               var percent = item[this._valueKey]/this.sum*100;
               var bar_text = chart.append('text')
                    .attr('class', 'bar-label')
                    .attr('alignment-baseline', 'middle')
                    .attr('x', this.margin.left + 5)
                    .attr('y', y +this._barHeight/2 + 4)
                    .style('font-family', this._fontFace)
                    .style('font-size', this._fontSize + 'px')
                    .style('font-weight', '500')
                    
                bar_text.append("tspan").text(this.getLabelFormat(item[this._valueKey], this._barUnit));
                bar_text.append("tspan").style("fill", "lightgray").text(` (${percent.toFixed(2)}%)`);
                bar_text.transition().duration(500).attr('x', xScale(item[this._valueKey]) + this.margin.left + 5)
                 
                y+=this._barHeight +this._barSpace;    
           });
        });
    }

    drawSingleChart(chart_data){
        chart_data.sort((a,b)=>d3.ascending(a[this._nameKey], b[this._nameKey]));

        var height = chart_data.length * (this._barHeight +this._barSpace) + 10 + this.margin.top + this.margin.bottom;
        var chart_container = d3.select('.chart-content');
        chart_container.selectAll("*").remove();
        var chart = chart_container.append('svg')
          .style('width', '100%')
          .attr('viewBox', `0 0 ${this._width} ${height}`);
        var xScale = d3.scaleLinear()
          .range([0, this._width - this.margin.left - this.margin.right])
          .domain([this._minValue, this._maxValue]);
        var yScale = d3.scaleBand()
          .range([0, height - 10 - this.margin.top - this.margin.bottom])
          .domain(chart_data.map(d => d[this._nameKey]));
        
        var color = d3.scaleOrdinal()
          .range(d3.schemeCategory10)
          .domain(chart_data.map(d => d[this._valueKey]));
        
        // add the x Axis
        var xAxis = chart.append("g")
            .attr("class", "grid")
            .style('font-family', this._fontFace)
            .style('font-size', this._fontSize + 'px')
            .style('font-weight', 500)
            .attr("transform", `translate(${this.margin.left}, ${height - this.margin.bottom})`)
            .call(d3.axisBottom(xScale)
                    .ticks(this._ticks)
                    .tickSizeInner([-height])
                    .tickSizeOuter([0])
                    .tickPadding([10])
                    .tickFormat(d =>{ 
                        return this.getLabelFormat(d,this._xAxisUnit);
                    }));     
        /*
        const yAxis = chart.append('g')
          .call(d3.axisLeft(yScale))
          .attr('transform', `translate(${margin.left}, ${margin.top})`);
        */
    
        chart.selectAll('.label-bar')
            .data(chart_data)
            .enter()
            .append('rect')
            .attr('class', '.label-bar')
            .attr('fill', '#f8f8f8')
            .attr('height',this._barHeight)
            .attr('width', this.margin.left-5)
            .attr('x', 0)
            .attr('y', d => yScale(d[this._nameKey]))
            .attr('rx', 2)
            .attr('rx', 2)    
        
        chart.selectAll('.item-label')
            .data(chart_data)
            .enter()
            .append('text')
            .attr('class', 'item-label')
            .attr('alignment-baseline', 'middle')
            .attr('x', 5)
            .attr('y', d => yScale(d[this._nameKey]) +this._barHeight/2)
            .style('font-family', this._fontFace)
            .style('font-size', this._fontSize + 'px')
            //.style('font-weight', 'bold')
            .text(d => d[this._nameKey]);
    
        chart.selectAll('.bar')
            .data(chart_data)
            .enter()
            .append('rect')
            .attr('class', 'bar')
            .attr('fill', d => {
                if(this._colors){
                    return this.getColor(d[this._valueKey]);
                }else{
                    return color(d[this._valueKey])
                }
             })
            .attr('height',this._barHeight)
            //.attr('width', d => xScale(d[this._valueKey]))
            .attr('x', this.margin.left + 1)
            .attr('y', d => yScale(d[this._nameKey]))
            .attr("width", 0)//this is the initial value
            .on("mouseover", d=>this.onMouseOver(d))
            .on("mouseout", d=>this.tooltip.style("display", "none"))
            .on("click", d => this.onMouseClick(d))
            .transition()
            .duration(500)
            //.delay((d,i) => i*100)
            .attr("width", d => xScale(d[this._valueKey]))
            
        var bar_text = chart.selectAll('.bar-label')
                            .data(chart_data)
                            .enter()
                            .append('text')
                            .attr('class', 'bar-label')
                            .attr('alignment-baseline', 'middle')
                            .attr('x', this.margin.left + 5)
                            .attr('y', d => yScale(d[this._nameKey]) +this._barHeight/2 + 4)
                            .style('font-family', this._fontFace)
                            .style('font-size', this._fontSize + 'px')
                            .style('font-weight', '500')
        bar_text.append("tspan").text(d => { return this.getLabelFormat(d[this._valueKey], this._barUnit); });
        bar_text.append("tspan")
                .style("fill", "lightgray")
                .text(d => {
                    var percent = d[this._valueKey]/this.sum*100
                    return ` (${percent.toFixed(2)}%)`;
                });
        bar_text.transition().duration(500).attr('x', d => xScale(d[this._valueKey]) + this.margin.left + 5)
    }
    getFilterItems(array, key){
       var result = [];
       array.forEach(element => {
           if(result.indexOf(element[key]) == -1){
              result.push(element[key]);
           }
       });
       result.sort((a,b)=>d3.ascending(a, b));
       return result;
    }
    getGroupBy(array, key){
        return array.reduce((result, currentValue) => {
            (result[currentValue[key]] = result[currentValue[key]] || []).push(currentValue);
            //console.log(result);
            return result;
        }, {});
    }
    getSum(data, value_key){
        return d3.sum(data, function(d) {
            return d[value_key];
        });
    }
    getLabelFormat(value, unit){
        var result;
        switch (unit) {
            case 'K':
                value = value/1000;
                value = value > 0 ? parseInt(value) : value.toFixed(2)
                result = 'R' + value + 'K';
                break;
            case 'M':
                value = value/1000000;
                value = value > 0 ? parseInt(value) : value.toFixed(2)
                result = 'R' + value + 'M';
                break;
            case 'B':
                value = value/1000000000;
                value = value > 0 ? parseInt(value) : value.toFixed(2)
                result = 'R' + value + 'B';
                break;     
            default:
                value = value > 0 ? parseInt(value):value.toFixed(2)
                result = 'R' + value;
                break;
        }
        if(value < 0.01){
            return 'R0' 
        }else{
            return result;
        }       
    }
    onMouseOver(d){
        var tooltip_html=['<table><tbody>'];
        if(this._filterKey){
            tooltip_html.push(`<tr><td>${this._filterKey}</td><td>${d[this._filterKey]}</td></tr>`);
        }
        if(this._groupKey){
            tooltip_html.push(`<tr><td>${this._groupKey}</td><td>${d[this._groupKey]}</td></tr>`);
        }
        tooltip_html.push(`<tr><td>${this._nameKey}</td><td>${d[this._nameKey]}</td></tr>`);
        tooltip_html.push(`<tr><td>${this._valueKey}</td><td>${d[this._valueKey]}</td></tr>`);
        tooltip_html.push('</tbody></table>');
        this.tooltip.html(tooltip_html.join(''))
                    .style("display", "inline-block")
                    .style("left", d3.event.pageX - document.getElementById('custom-toolTip').offsetWidth/2 + "px")
                    .style("top", d3.event.pageY - document.getElementById('custom-toolTip').offsetHeight - 30 + "px");
    }
    onMouseClick(d){
        if(this._urlKey){
            if(d[this._urlKey]){
                window.open(d[this._urlKey], "_blank");
            }
        }
    }
    getColor(value){
       for(var i=0;i<this._colors.length;i++){
          var a = this._maxValue/this._colors.length*i;
          var b = this._maxValue/this._colors.length*(i+1);
          if(value >= a && value < b){
             return this._colors[i];
          }
       }
       return '#000';
    }

    select(newValue){
        this._selector = newValue;
        this.createChart();
        return this;
    }
    
    data(newValue){
        this._data = newValue;
        if(this._data && this._valueKey){
            if(!this._maxValue){
                this._maxValue = 1.5 * d3.max(this._data, d => d[this._valueKey]);
            }
            this.sum = this.getSum(this._data, this._valueKey);
        }
        this.createChart();
        return this;
    }

    nameKey(newValue){
        this._nameKey = newValue;
        this.createChart();
        return this;
    }

    valueKey(newValue){
        this._valueKey = newValue;
        if(this._data && this._valueKey){
            if(!this._maxValue){
                this._maxValue = 1.5 * d3.max(this._data, d => d[this._valueKey]);
            }
            if(!this.sum){
                this.sum = this.getSum(this._data, this._valueKey);
            }
        }
        this.createChart();
        return this;
    }
    filterKey(newValue){
        this._filterKey = newValue;
        this.createChart();
        return this;
    }
    filterLabel(newValue){
        this._filterLabel = newValue;
        this.createChart();
        return this;
    }
    groupKey(newValue){
        this._groupKey = newValue;
        this.createChart();
        return this;
    }
    urlKey(newValue){
        this._urlKey = newValue;
        return this;
    }
    barUnit(newValue){
        this._barUnit = newValue;
        this.createChart();
        return this;
    }
    xAxisUnit(newValue){
        this._xAxisUnit = newValue;
        this.createChart();
        return this;
    }
    minValue(newValue){
        this._minValue = newValue;
        this.createChart();
        return this;
    }
    maxValue(newValue){
        this._maxValue = newValue;
        this.createChart();
        return this;
    }
    colors(newValue){
        this._colors = newValue;
        this.createChart();
        return this;
    }
    width(newValue){
        this._width = newValue;
        this.createChart();
        return this;
    }
    marginLeft(newValue){
        this._marginLeft = newValue;
        this.createChart();
        return this;
    }
    barHeight(newValue){
        this._barHeight = newValue;
        this.createChart();
        return this;
    }
    barSpace(newValue){
        this._barSpace = newValue;
        this.createChart();
        return this;
    }
    groupSpace(newValue){
        this._groupSpace = newValue;
        this.createChart();
        return this;
    }
    ticks(newValue){
        this._ticks = newValue;
        this.createChart();
        return this;
    }
    fontFace(newValue){
        this._fontFace = newValue;
        document.getElementById("custom-toolTip").style.fontFamily = this._fontFace;
        this.createChart();
        return this;
    }
    fontSize(newValue){
        this._fontSize = newValue;
        //document.getElementById("custom-toolTip").style.fontSize = this._fontSize + 'px';
        this.createChart();
        return this;
    }
}