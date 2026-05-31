
document.addEventListener("DOMContentLoaded", function () {

  let budget_summary_data = document.getElementById("national-budget-summary-data");  

  if(budget_summary_data){   
  

  const data = JSON.parse(budget_summary_data.textContent);

  const functionData = JSON.parse(data.function_data);

  const functionSummary = functionData.reduce((acc, item) => {
    const value = Number(item.value) || 0; // ensure numeric, default 0
    if (acc[item.name]) {
      acc[item.name] += value;
    } else {
      acc[item.name] = value;
    }
    return acc;
  }, {});

  // Extract groups and values
  const functionGroups = Object.keys(functionSummary);
  const functionValues = Object.values(functionSummary);

  function formatCurrency(value) {
    if (value >= 1e12) return "R " + (value / 1e12).toFixed(2) + " Trillion";
    if (value >= 1e9) return "R " + (value / 1e9).toFixed(2) + " Billion";
    if (value >= 1e6) return "R " + (value / 1e6).toFixed(2) + " Million";
    if (value >= 1e3) return "R " + (value / 1e3).toFixed(2) + " Thousand";
    return "R " + value.toLocaleString();
  }

  const ctx1 = document.getElementById("functionGroupChart").getContext("2d");

const palette = [
  "#2B3BB0", // Deep Blue
  "#85294E", // Burgundy
  "#1A4641", // Teal Green
  "#27605C", // Sea Green
  "#F08B32", // Warm Orange
  "#4C362C", // Coffee Brown
  "#6A4D42", // Soft Brown
  "#B04A2B", // Burnt Sienna
  "#2B8AB0", // Ocean Blue
  "#A6A42F", // Olive Green
  "#5B2BB0", // Violet Purple
  "#B07A2B", // Golden Bronze
  "#2B6B50", // Forest Green
];

  new Chart(ctx1, {
    type: "pie",
    data: {
      labels: functionGroups,
      datasets: [
        {
          data: functionValues,
          backgroundColor: palette,
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      legend: {
        display: true,
        position: "left", // ✅ Works in Chart.js 2.7
        labels: {
          fontSize: 12,
          boxWidth: 20,
          padding: 15,
          fontColor: "#333",
        },
      },

      tooltips: {
        ...getSharedTooltipTheme(),
        callbacks: {
          title: function(tooltipItems, data) {
            const item = tooltipItems && tooltipItems.length ? tooltipItems[0] : null;
            return item ? data.labels[item.index] || "" : "";
          },
          label: function(tooltipItem, data) {
            const value =
              data.datasets[tooltipItem.datasetIndex].data[tooltipItem.index];
            return formatCurrency(value);
          },
        },
      },
      plugins: {
        datalabels: {
          color: "#fff",
          font: {
            weight: "bold",
            size: 11,
          },
          formatter: function(value) {
            return formatCurrency(value);
          },
        },
      },
    },
  });


  const ctx3 = document.getElementById("topSpendingChart").getContext("2d");

  const topItemsData = JSON.parse(data.top_items_data);

  const grouped = {};
  topItemsData.forEach((d) => {
    if (!grouped[d.name]) grouped[d.name] = 0;
    grouped[d.name] += d.value;
  });

  const sortedEntries = Object.entries(grouped)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  const topLabels = sortedEntries.map(([k]) => k);
  const topValues = sortedEntries.map(([_, v]) => v);  

    new Chart(ctx3, {
      type: "horizontalBar",
      data: {
        labels: topLabels,
        datasets: [
          {
            label: "Expenditure (R)",
            data: topValues.map(Number),
            backgroundColor: "#ad3c64",
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,

        layout: {
          // leave a little room so y-axis labels don't overlap gridlines
          padding: { left: 10, right: 10, top: 10, bottom: 10 },
        },

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
                // padding moves tick labels away from the axis/gridlines
                padding: 8,
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
              scaleLabel: {
                display: true,
                fontSize: 12,
              },
            },
          ],

          yAxes: [
            {
              ticks: {
                autoSkip: false,
                // move y labels a bit to avoid overlapping the left border
                padding: 6,
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
              var value = tooltipItem.xLabel;
              if (value >= 1e12)
                return "R " + (value / 1e12).toFixed(2) + " Trillion";
              if (value >= 1e9)
                return "R " + (value / 1e9).toFixed(2) + " Billion";
              if (value >= 1e6)
                return "R " + (value / 1e6).toFixed(2) + " Million";
              if (value >= 1e3)
                return "R " + (value / 1e3).toFixed(2) + " Thousand";
              return "R " + value.toLocaleString();
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



    const ctx4 = document.getElementById("yearlyDataChart").getContext("2d");

    let yearlyData = JSON.parse(data.yearly_data);
    // ====== LINE CHART ======
    const years = yearlyData.map((d) => d.financialYear);
    const totals = yearlyData.map((d) => d.year_total);

    new Chart(ctx4, {
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
              gridLines: { display: true, drawBorder: true },
            },
          ],
        },

        tooltips: {
          ...getSharedTooltipTheme(),
          callbacks: {
            label: function(tooltipItem, data) {
              var value = tooltipItem.yLabel;
              if (value >= 1e12)
                return "R " + (value / 1e12).toFixed(2) + " Trillion";
              if (value >= 1e9)
                return "R " + (value / 1e9).toFixed(2) + " Billion";
              if (value >= 1e6)
                return "R " + (value / 1e6).toFixed(2) + " Million";
              if (value >= 1e3)
                return "R " + (value / 1e3).toFixed(2) + " Thousand";
              return "R " + value.toLocaleString();
            },
          },
        },

        legend: {
          display: false, // ✅ Hides the dataset label legend
        },
      },
    });
  }

});

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
