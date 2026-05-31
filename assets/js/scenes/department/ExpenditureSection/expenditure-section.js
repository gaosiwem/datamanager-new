document.addEventListener("DOMContentLoaded", function() {
  const PHASE_METADATA = {
    "Main appropriation": {
      rank: 1,
      className: "main-appropriation",
      seriesType: "planned",
    },
    "Adjusted appropriation": {
      rank: 2,
      className: "adjusted-appropriation",
      seriesType: "planned",
    },
    "Audited Outcome": {
      rank: 3,
      className: "audited-outcome",
      seriesType: "historical",
    },
  };
  const historyData = document.getElementById("historyBar");
  const historyChart = d3.select("#historyBarGraph");
  const tooltip = d3.select("#historyBarTooltip");
  const phaseList = document.getElementById("expenditurePhaseList");
  const chartCard = document.querySelector(".ExpenditureChartCard");
  let resizeTimeout;
  let chartData = [];

  if (!historyData || !chartCard || historyChart.empty()) {
    return;
  }

  function formatFinancialYear(year) {
    if (!year || isNaN(year)) {
      return year;
    }

    return `${year}-${(year + 1).toString().slice(-2)}`;
  }

  function formatCurrencyValue(value) {
    const numericValue = Number(value);
    const absoluteValue = Math.abs(numericValue);

    if (absoluteValue >= 1e12) return `R ${Math.round(numericValue / 1e12).toLocaleString()} trillion`;
    if (absoluteValue >= 1e9) return `R ${Math.round(numericValue / 1e9).toLocaleString()} billion`;
    if (absoluteValue >= 1e6) return `R ${Math.round(numericValue / 1e6).toLocaleString()} million`;
    if (absoluteValue >= 1e3) return `R ${Math.round(numericValue / 1e3).toLocaleString()} thousand`;
    return `R ${Math.round(numericValue).toLocaleString()}`;
  }

  function formatGraphCurrency(value) {
    return formatCurrencyValue(value);
  }

  function getPhaseMetadata(budgetPhase) {
    return (
      PHASE_METADATA[budgetPhase] || {
        rank: 99,
        className: String(budgetPhase || "unknown")
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-+|-+$/g, ""),
        seriesType: "historical",
      }
    );
  }

  function normaliseDataset(rawDataset) {
    return (rawDataset.children || [])
      .map((item) => {
        const year = parseInt(item.Name || item.name, 10);
        const budgetPhase = item.BudgetPhase || item.budgetPhase || "";
        const phaseMetadata = getPhaseMetadata(budgetPhase);
        const seriesType = item.SeriesType || phaseMetadata.seriesType;
        const value = Number(item.Count || item.value || 0);

        return {
          year,
          phaseRank: phaseMetadata.rank,
          phaseClassName: phaseMetadata.className,
          yearLabel: formatFinancialYear(year),
          value,
          budgetPhase,
          seriesType,
          formattedValue: formatCurrencyValue(value),
          compactValue: formatGraphCurrency(value),
        };
      })
      .filter((item) => item.year && item.value >= 0)
      .sort((left, right) => {
        if (left.year !== right.year) {
          return left.year - right.year;
        }

        return left.phaseRank - right.phaseRank;
      });
  }

  function populatePhaseList(data) {
    if (!phaseList) {
      return;
    }

    phaseList.innerHTML = "";

    data.forEach((item) => {
      const phaseItem = document.createElement("div");
      phaseItem.className = `ExpenditurePhaseItem ExpenditurePhaseItem--${item.phaseClassName}`;

      const yearNode = document.createElement("span");
      yearNode.className = "ExpenditurePhaseYear";
      yearNode.textContent = item.yearLabel;

      const phaseNode = document.createElement("span");
      phaseNode.className = "ExpenditurePhaseLabel";
      phaseNode.textContent = item.budgetPhase;

      phaseItem.appendChild(yearNode);
      phaseItem.appendChild(phaseNode);
      phaseList.appendChild(phaseItem);
    });
  }

  function renderEmptyState(message, hint) {
    const width = Math.max(chartCard.clientWidth - 32, 320);
    const height = 280;

    historyChart.selectAll("*").remove();
    historyChart
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("width", width)
      .attr("height", height)
      .attr("preserveAspectRatio", "xMidYMid meet");

    historyChart
      .append("text")
      .attr("class", "ExpenditureEmptyState")
      .attr("x", width / 2)
      .attr("y", height / 2 - 10)
      .attr("text-anchor", "middle")
      .text(message);

    historyChart
      .append("text")
      .attr("class", "ExpenditureEmptyHint")
      .attr("x", width / 2)
      .attr("y", height / 2 + 18)
      .attr("text-anchor", "middle")
      .text(hint);
  }

  function renderChart(data) {
    if (!data.length) {
      renderEmptyState("No expenditure data available", "Please try again later.");
      return;
    }

    const width = Math.max(chartCard.clientWidth - 32, 320);
    const height = width >= 960 ? 420 : width >= 700 ? 380 : 340;
    const margin = {
      top: 24,
      right: width >= 700 ? 20 : 14,
      bottom: 56,
      left: width >= 700 ? 124 : 104,
    };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    historyChart.selectAll("*").remove();
    historyChart
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("width", width)
      .attr("height", height)
      .attr("preserveAspectRatio", "xMidYMid meet");

    const svg = historyChart
      .append("g")
      .attr("transform", `translate(${margin.left}, ${margin.top})`);

    const xScale = d3
      .scaleBand()
      .domain(data.map((item) => item.yearLabel))
      .range([0, innerWidth])
      .padding(width >= 700 ? 0.38 : 0.28);

    const yScale = d3
      .scaleLinear()
      .domain([0, (d3.max(data, (item) => item.value) || 0) * 1.12])
      .nice()
      .range([innerHeight, 0]);

    svg
      .append("g")
      .attr("class", "ExpenditureGrid")
      .call(
        d3
          .axisLeft(yScale)
          .ticks(width >= 700 ? 5 : 4)
          .tickSize(-innerWidth)
          .tickFormat("")
      );

    svg
      .append("g")
      .attr("class", "ExpenditureAxis ExpenditureAxis--y")
      .call(
        d3.axisLeft(yScale).ticks(width >= 700 ? 5 : 4).tickFormat((value) => formatGraphCurrency(value))
      );

    svg
      .append("g")
      .attr("class", "ExpenditureAxis ExpenditureAxis--x")
      .attr("transform", `translate(0, ${innerHeight})`)
      .call(d3.axisBottom(xScale));

    const bars = svg
      .selectAll(".ExpenditureBar")
      .data(data)
      .enter()
      .append("rect")
      .attr("class", (item) => `ExpenditureBar ExpenditureBar--${item.phaseClassName}`)
      .attr("x", (item) => xScale(item.yearLabel))
      .attr("y", (item) => yScale(item.value))
      .attr("width", xScale.bandwidth())
      .attr("height", (item) => innerHeight - yScale(item.value))
      .attr("rx", 10)
      .attr("ry", 10)
      .on("mouseover", function(item) {
        tooltip
          .style("display", "block")
          .html(
            `<strong>${item.yearLabel}</strong><br>${item.budgetPhase}<br>${item.formattedValue}`
          )
          .style("left", `${d3.event.pageX + 12}px`)
          .style("top", `${d3.event.pageY - 12}px`);
      })
      .on("mouseout", function() {
        tooltip.style("display", "none");
      });

    bars.raise();
  }

  try {
    chartData = normaliseDataset(JSON.parse(historyData.textContent));
    populatePhaseList(chartData);
    renderChart(chartData);
  } catch (error) {
    console.error("Historical expenditure chart parse error:", error);
    renderEmptyState("Unable to load chart", "Please try again in a moment.");
  }

  window.addEventListener("resize", function() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(function() {
      renderChart(chartData);
    }, 150);
  });
});
