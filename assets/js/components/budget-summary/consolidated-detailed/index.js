let tooltip;
document.addEventListener("DOMContentLoaded", function () {

  let category = document.getElementById("category-data");
  
  let dataset;
  const config = {
     width: 700,
     height: 200,
     margin: { top: 40, right: 80, bottom: 100, left: 80 },
   };

  if (category) {
    try {
          dataset = JSON.parse(category.textContent); 
          let ctx = document.getElementById("categoryBarChart").getContext("2d");
          // ✅ Adjusted margins (more bottom space for angled labels)
  
          drawBarGraph(dataset, ctx);

          let econ = document.getElementById("econ-data");
          if (econ) {
            let econDataset = JSON.parse(econ.textContent);
            let ctxEcon = document
              .getElementById("econBarChart")
              .getContext("2d");
            drawBarGraph(econDataset, ctxEcon);
          }

          let programmes = document.getElementById("programmes-data");
          if(programmes){
            let programmeDataset = JSON.parse(programmes.textContent);
            let ctxProg = document.getElementById("programmesBarChart").getContext("2d");
            drawBarGraph(programmeDataset, ctxProg);
          }
          
          drawLineChart();
          
        } catch (error) {
      console.error("JSON Parse Error:", error);
      dataset = { name: "root", children: [{ name: "No Data", value: 0 }] };
    }
  } else {
    console.error("Treemap data not found!");
    dataset = { name: "root", children: [{ name: "No Data", value: 0 }] };
  }
});


function drawBarGraph(dataset, ctx) {

  const names = dataset.map((d) => d.name);
  const values = dataset.map((d) => d.value);

  new Chart(ctx, {
    type: "horizontalBar", // ✅ Chart.js 2.x uses 'horizontalBar' instead of indexAxis: 'y'
    data: {
      labels: names,
      datasets: [
        {
          label: "Expenditure (R)",
          data: values.map(Number),
          backgroundColor: "#ad3c64",
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        xAxes: [
          {
            ticks: {
              beginAtZero: true,
              callback: function(value) {
                if (value >= 1e12) return "R " + value / 1e12 + " Trillion";
                if (value >= 1e9) return "R " + value / 1e9 + " Billion";
                if (value >= 1e6) return "R " + value / 1e6 + " Million";
                if (value >= 1e3) return "R " + value / 1e3 + " Thousand";
                return "R " + value.toLocaleString();
              },
            },
            gridLines: {
              display: true,
              drawOnChartArea: true, // make sure lines are drawn across the chart area
              drawTicks: true,
              drawBorder: true,
              offsetGridLines: false, // important: align gridlines with tick positions
              color: "#e0e0e0",
              lineWidth: 1,
            },
            scaleLabel: { display: false },
          },
        ],
        yAxes: [
          {
            ticks: {
              autoSkip: false,
            },
            gridLines: {
              display: true,
              drawOnChartArea: true, // horizontal gridlines across chart area
              drawTicks: true,
              offsetGridLines: false,
              color: "#f5f5f5",
              lineWidth: 1,
            },
            scaleLabel: {
              display: true,
              fontSize: 12,
            },
          },
        ],
      },
      tooltips: {
        ...getSharedTooltipTheme(),
        callbacks: {
          label: function(tooltipItem) {
            return formatTooltipCurrency(tooltipItem.xLabel);
          },
        },
      },
      legend: { display: false },
      animation: {
        duration: 800,
        easing: "easeOutQuart",
      },
    },
  });
}

function drawLineChart(){

    let yearly = document.getElementById("yearly-data");

    if(yearly) {

      let yearlyDataset = JSON.parse(yearly.textContent);
      // ====== LINE CHART ======
      const years = yearlyDataset.map((d) => d.financialYear);
      const totals = yearlyDataset.map((d) => d.year_total);
      var ctx = document.getElementById("yearlyLineChart").getContext("2d");

      new Chart(ctx, {
        type: "line",
        data: {
          labels: years, // e.g. ["2018", "2019", "2020"]
          datasets: [
            {
              data: totals.map(Number), // ensure numbers
              backgroundColor: "#ad3c64",
              fill: false,
              lineTension: 0.3,
              pointRadius: 3,
              pointHoverRadius: 5,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,

          scales: {
            yAxes: [
              {
                gridLines: {
                  display: true, // ✅ Show horizontal lines
                  drawBorder: true, // Keep Y-axis line
                  color: "rgba(200, 200, 200, 0.3)", // Soft grid color
                },
                ticks: {
                  beginAtZero: true,
                  callback: function(value) {
                    if (value >= 1e12) return "R " + value / 1e12 + " Trillion";
                    if (value >= 1e9) return "R " + value / 1e9 + " Billion";
                    if (value >= 1e6) return "R " + value / 1e6 + " Million";
                    if (value >= 1e3) return "R " + value / 1e3 + " Thousand";
                    return "R " + value.toLocaleString();
                  },
                },
                gridLines: { display: true },
              },
            ],
            xAxes: [
              {
                gridLines: { display: false, drawBorder: true },
              },
            ],
          },

          tooltips: {
            ...getSharedTooltipTheme(),
            callbacks: {
              label: function(tooltipItem, data) {
                return formatTooltipCurrency(tooltipItem.yLabel);
              },
            },
          },

          legend: {
            display: false, // ✅ Hides the dataset label legend
          },
        },
      });
    }

  }

// function drawLineChart(data, xScale, config) {
//   const { width, height, margin } = config;
//   const svg = d3
//     .select("#yearlyLineChart")
//     .attr("width", width + margin.left + margin.right)
//     .attr("height", height + margin.top + margin.bottom)
//     .append("g")
//     .attr("transform", `translate(${margin.left}, ${margin.top})`);

//   const tooltip = d3.select(".tooltip");

//   const chartWidth = width - margin.left - margin.right;
//   const chartHeight = height - margin.top - margin.bottom;

//   // ✅ Fix: X scale should be based on years, not values
//   const x = d3
//     .scaleBand()
//     .domain(data.map((d) => d.financialYear))
//     .range([0, chartWidth])
//     .padding(0.3);

//   // ✅ Fix: Y scale should be based on year_total (numeric)
//   const y = d3
//     .scaleLinear()
//     .domain([0, d3.max(data, (d) => d.year_total) * 1.1])
//     .nice()
//     .range([chartHeight, 0]);

//   // ✅ X Axis
//   svg
//     .append("g")
//     .attr("transform", `translate(0, ${chartHeight})`)
//     .call(d3.axisBottom(x))
//     .selectAll("text")
//     .attr("transform", "rotate(-45)")
//     .style("text-anchor", "end")
//     .attr("dx", "-0.6em")
//     .attr("dy", "0.3em")
//     .style("font-size", "12px");

//   // ✅ Y Axis
//   svg.append("g").call(d3.axisLeft(y).tickFormat((d) => formatYAxis(d)));

//   // ✅ Line Generator
//   const line = d3
//     .line()
//     .x((d) => x(d.financialYear) + x.bandwidth() / 2)
//     .y((d) => y(d.year_total))
//     .curve(d3.curveMonotoneX);

//   // ✅ Draw Line
//   svg
//     .append("path")
//     .datum(data)
//     .attr("fill", "none")
//     .attr("stroke", "#ff7f0e")
//     .attr("stroke-width", 2.5)
//     .attr("d", line);

//   // ✅ Points on the line
//   svg
//     .selectAll(".dot")
//     .data(data)
//     .enter()
//     .append("circle")
//     .attr("class", "dot")
//     .attr("cx", (d) => x(d.financialYear) + x.bandwidth() / 2)
//     .attr("cy", (d) => y(d.year_total))
//     .attr("r", 4)
//     .attr("fill", "#ff7f0e")
//     .on("mousemove", function(event, d) {
//       tooltip
//         .style("display", "block")
//         .html(
//           `<strong>${formatFinancialYear(
//             parseInt(d.financialYear)
//           )}</strong><br>Value: ${formatYAxis(d.year_total)}`
//         )
//         .style("left", event.pageX + 10 + "px")
//         .style("top", event.pageY - 28 + "px");
//     })
//     .on("mouseout", () => tooltip.style("display", "none"));
// }

// ✅ Custom Y-axis Formatter (Shows "B" for Billions)
function formatYAxis(value) {
  if (value >= 1e12) {
    return `R ${(value / 1e12).toFixed(1)} trillion`;
  } else if (value >= 1e9) {
    return `R ${(value / 1e9).toFixed(1)} billion`;
  } else if (value >= 1e6) {
    return `R ${(value / 1e6).toFixed(1)} million`;
  } else if (value >= 1e3) {
    return `R ${(value / 1e3).toFixed(1)} thousand`;
  } else {
    return "R" + value.toLocaleString();
  }
}

function formatTooltipCurrency(value) {
  const numericValue = Number(value);
  const absoluteValue = Math.abs(numericValue);

  if (!Number.isFinite(numericValue)) {
    return value;
  }

  if (absoluteValue >= 1e12) {
    return `R ${Math.round(numericValue / 1e12).toLocaleString()} trillion`;
  }

  if (absoluteValue >= 1e9) {
    return `R ${Math.round(numericValue / 1e9).toLocaleString()} billion`;
  }

  if (absoluteValue >= 1e6) {
    return `R ${Math.round(numericValue / 1e6).toLocaleString()} million`;
  }

  if (absoluteValue >= 1e3) {
    return `R ${Math.round(numericValue / 1e3).toLocaleString()} thousand`;
  }

  return `R ${Math.round(numericValue).toLocaleString()}`;
}

function getSharedTooltipTheme() {
  return {
    enabled: false,
    custom: createDepartmentTooltip,
    backgroundColor: "#fff",
    titleFontColor: "#3f3f3f",
    bodyFontColor: "#3f3f3f",
    borderColor: "#d2d2d2",
    borderWidth: 1,
    xPadding: 12,
    yPadding: 10,
    caretPadding: 10,
    cornerRadius: 10,
    displayColors: false,
    titleMarginBottom: 2,
    bodySpacing: 2,
    titleFontFamily: "Roboto, sans-serif",
    bodyFontFamily: "Roboto, sans-serif",
    titleFontStyle: "bold",
    bodyFontStyle: "normal",
  };
}

function createDepartmentTooltip(tooltipModel) {
  const chart = this._chart;
  const canvas = chart.canvas;
  let tooltipEl = document.getElementById(`${canvas.id}-tooltip`);

  if (!tooltipEl) {
    tooltipEl = document.createElement("div");
    tooltipEl.id = `${canvas.id}-tooltip`;
    tooltipEl.className = "tooltip DepartmentGraphTooltip BudgetSummaryDetailTooltip";
    canvas.parentNode.appendChild(tooltipEl);
  }

  if (tooltipModel.opacity === 0) {
    tooltipEl.style.display = "none";
    return;
  }

  const title = tooltipModel.title && tooltipModel.title.length
    ? `<strong>${tooltipModel.title.join(" ")}</strong>`
    : "";
  const body = tooltipModel.body
    ? tooltipModel.body.map((item) => item.lines.join("<br>")).join("<br>")
    : "";
  const position = canvas.getBoundingClientRect();

  tooltipEl.innerHTML = title && body ? `${title}<br>${body}` : title || body;
  tooltipEl.style.display = "block";
  tooltipEl.style.left = `${position.left + window.pageXOffset + tooltipModel.caretX + 10}px`;
  tooltipEl.style.top = `${position.top + window.pageYOffset + tooltipModel.caretY - 10}px`;
}

// ✅ Tooltip Formatter
function formatValue(value) {
  return formatYAxis(value);
}

// ✅ Format Year as "YYYY-YY"
function formatFinancialYear(year) {
  if (!year || isNaN(year)) return year;
  return `${year}-${(year + 1).toString().slice(-2)}`;
}

function populateBudgetPhase(dataset) {
  const tableBody = document.querySelector("#expenditureTable tbody");

  dataset.forEach((item) => {
    const row = document.createElement("tr");

    const yearCell = document.createElement("td");
    yearCell.classList.add("ExpenditureSection-cell");
    yearCell.textContent = item.year;
    row.appendChild(yearCell);

    const phaseCell = document.createElement("td");
    phaseCell.classList.add("ExpenditureSection-cell");
    phaseCell.textContent = item.budgetPhase;
    row.appendChild(phaseCell);

    tableBody.appendChild(row);
  });
}

