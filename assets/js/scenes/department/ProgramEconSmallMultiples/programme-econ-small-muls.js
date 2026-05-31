document.addEventListener("DOMContentLoaded", function() {
  const economicClassificationDropdown = document.getElementById(
    "economic-classification-dropdown"
  );
  const programmeDropdown = document.getElementById("programme-dropdown");
  const chartSvg = d3.select("#horizontalBarChart");
  const tooltip = d3.select("#programme-econ-tooltip");
  const chartStage = document.querySelector(".programmeEconChartStage");
  const selectedProgramme = document.getElementById(
    "programme-econ-selected-programme"
  );
  const selectedClassification = document.getElementById(
    "programme-econ-selected-classification"
  );

  let resizeTimeout;

  if (
    !economicClassificationDropdown ||
    !programmeDropdown ||
    !chartStage ||
    !selectedProgramme ||
    !selectedClassification
  ) {
    return;
  }

  function getUrlParts() {
    const currentUrl = new URL(window.location.href);
    const parts = currentUrl.pathname.split("/").filter(Boolean);

    const financialYear = parts[0];
    const type = parts[1];
    const department = type === "national" ? parts[3] : parts[4];
    const province = type === "national" ? "" : parts[2];

    return { financialYear, department, province };
  }

  function formatCurrencyValue(value) {
    if (value >= 1e12) return `R ${(value / 1e12).toFixed(1)} trillion`;
    if (value >= 1e9) return `R ${(value / 1e9).toFixed(1)} billion`;
    if (value >= 1e6) return `R ${(value / 1e6).toFixed(1)} million`;
    if (value >= 1e3) return `R ${(value / 1e3).toFixed(1)} thousand`;
    return `R ${value.toLocaleString()}`;
  }

  function truncateText(text, maxWidth) {
    if (!text) {
      return "";
    }

    const averageCharacterWidth = 7;
    const maxCharacters = Math.max(Math.floor(maxWidth / averageCharacterWidth), 1);

    if (text.length <= maxCharacters) {
      return text;
    }

    return `${text.substring(0, Math.max(maxCharacters - 3, 1))}...`;
  }

  function wrapAxisTextToTwoLines(textSelection, width) {
    textSelection.each(function() {
      const textElement = d3.select(this);
      const originalText = textElement.text();
      const words = originalText.split(/\s+/).filter(Boolean);
      const x = textElement.attr("x") || 0;
      const y = textElement.attr("y");
      const dy = parseFloat(textElement.attr("dy") || 0);
      const lineHeight = 1.05;
      let line = [];
      let lineNumber = 0;
      let tspan = textElement
        .text(null)
        .append("tspan")
        .attr("x", x)
        .attr("y", y)
        .attr("dy", `${dy}em`);

      words.forEach((word, index) => {
        line.push(word);
        tspan.text(line.join(" "));

        if (tspan.node().getComputedTextLength() > width) {
          line.pop();

          if (lineNumber === 1) {
            const remainingWords = [word].concat(words.slice(index + 1));
            const currentText = line.length ? line.join(" ") : word;
            tspan.text(
              truncateText(
                `${currentText} ${remainingWords.join(" ")}`.trim(),
                width
              )
            );
            return;
          }

          tspan.text(line.join(" "));
          line = [word];
          lineNumber += 1;
          tspan = textElement
            .append("tspan")
            .attr("x", x)
            .attr("y", y)
            .attr("dy", `${lineNumber * lineHeight + dy}em`)
            .text(word);
        }
      });
    });
  }

  function updateSummary(programme, classification) {
    selectedProgramme.textContent = programme || "No programme selected";
    selectedClassification.textContent =
      classification || "No classification selected";
  }

  function getChartMetrics(itemCount) {
    const width = Math.max(chartStage.clientWidth || 720, 320);
    const leftMargin = width >= 820 ? 292 : width >= 640 ? 238 : 176;
    const rightMargin = width >= 640 ? 26 : 18;
    const margin = { top: 20, right: rightMargin, bottom: 24, left: leftMargin };
    const plotOffset = width >= 760 ? 42 : 32;
    const innerWidth = Math.max(width - margin.left - margin.right, 120);
    const barHeight = width >= 820 ? 42 : 38;
    const height = Math.max(itemCount * barHeight, 220);

    return { width, height, margin, innerWidth, barHeight, plotOffset };
  }

  function renderEmptyState(message, hint) {
    chartSvg.selectAll("*").remove();

    const { width, height } = getChartMetrics(1);

    chartSvg
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("width", width)
      .attr("height", height)
      .attr("preserveAspectRatio", "xMidYMid meet");

    chartSvg
      .append("text")
      .attr("class", "programmeEconEmptyState")
      .attr("x", width / 2)
      .attr("y", height / 2 - 10)
      .attr("text-anchor", "middle")
      .text(message);

    chartSvg
      .append("text")
      .attr("class", "programmeEconEmptyHint")
      .attr("x", width / 2)
      .attr("y", height / 2 + 18)
      .attr("text-anchor", "middle")
      .text(hint);
  }

  function renderChart(dataset) {
    chartSvg.selectAll("*").remove();

    const data = dataset.children
      .map((item) => ({
        name: item.name,
        value: Number(item.value || 0),
        formattedValue: formatCurrencyValue(Number(item.value || 0)),
      }))
      .sort((left, right) => right.value - left.value);

    if (!data.length) {
      renderEmptyState(
        "No data available",
        "Try another programme or economic classification."
      );
      return;
    }

    const { width, height, margin, innerWidth, plotOffset } = getChartMetrics(
      data.length
    );

    chartSvg
      .attr("viewBox", `0 0 ${width} ${height + margin.top + margin.bottom}`)
      .attr("width", width)
      .attr("height", height + margin.top + margin.bottom)
      .attr("preserveAspectRatio", "xMidYMid meet");

    const svg = chartSvg
      .append("g")
      .attr("transform", `translate(${margin.left}, ${margin.top})`);

    const xScale = d3
      .scaleLinear()
      .domain([0, d3.max(data, (item) => item.value) || 0])
      .nice()
      .range([0, innerWidth - plotOffset]);

    const plotArea = svg
      .append("g")
      .attr("transform", `translate(${plotOffset}, 0)`);

    const yScale = d3
      .scaleBand()
      .domain(data.map((item) => item.name))
      .range([0, height])
      .padding(0.18);

    plotArea
      .append("g")
      .attr("class", "programmeEconGrid")
      .call(
        d3
          .axisBottom(xScale)
          .ticks(width >= 760 ? 5 : 3)
          .tickSize(height)
          .tickFormat("")
      )
      .attr("transform", "translate(0,0)");

    svg
      .append("g")
      .attr("class", "programmeEconAxis")
      .call(
        d3
          .axisLeft(yScale)
          .tickSize(0)
          .tickPadding(width >= 760 ? 18 : 12)
      )
      .selectAll("text")
      .attr("x", width >= 760 ? -28 : -18)
      .style("font-size", width >= 760 ? "12px" : "11px")
      .style("font-weight", "500")
      .style("dominant-baseline", "middle")
      .call(wrapAxisTextToTwoLines, margin.left - 56)
      .append("title")
      .text((item) => item);

    const bars = plotArea
      .selectAll(".programmeEconBar")
      .data(data)
      .enter()
      .append("rect")
      .attr("class", "programmeEconBar")
      .attr("x", 0)
      .attr("y", (item) => yScale(item.name))
      .attr("width", (item) => xScale(item.value))
      .attr("height", yScale.bandwidth())
      .attr("rx", 8)
      .attr("ry", 8)
      .on("mouseover", function(item) {
        d3.select(this).attr("fill", "#557c2f");
        tooltip
          .style("display", "block")
          .html(`<strong>${item.name}</strong><br>${item.formattedValue}`)
          .style("left", `${d3.event.pageX + 10}px`)
          .style("top", `${d3.event.pageY - 10}px`);
      })
      .on("mouseout", function() {
        d3.select(this).attr("fill", "#7bb344");
        tooltip.style("display", "none");
      });

    plotArea
      .selectAll(".programmeEconValueLabel")
      .data(data)
      .enter()
      .append("text")
      .attr("class", "programmeEconValueLabel")
      .attr("x", (item) => {
        const barWidth = xScale(item.value);
        const estimatedLabelWidth = item.formattedValue.length * 6.5;
        return barWidth < estimatedLabelWidth + 16
          ? barWidth + 8
          : barWidth - 8;
      })
      .attr("y", (item) => yScale(item.name) + yScale.bandwidth() / 2)
      .attr("dy", ".35em")
      .attr("text-anchor", (item) =>
        xScale(item.value) < item.formattedValue.length * 6.5 + 16
          ? "start"
          : "end"
      )
      .style("fill", (item) =>
        xScale(item.value) < item.formattedValue.length * 6.5 + 16
          ? "#3f3f3f"
          : "#ffffff"
      )
      .text((item) => item.formattedValue);

    bars.raise();
    svg.selectAll(".programmeEconValueLabel").raise();
  }

  function fetchDataAndRenderChart() {
    const { financialYear, department, province } = getUrlParts();
    const selectedEcon = economicClassificationDropdown.value;
    const selectedProg = programmeDropdown.value;
    const selectedProgrammeText =
      programmeDropdown.options[programmeDropdown.selectedIndex] &&
      programmeDropdown.options[programmeDropdown.selectedIndex].text;
    const selectedClassificationText =
      economicClassificationDropdown.options[
        economicClassificationDropdown.selectedIndex
      ] &&
      economicClassificationDropdown.options[
        economicClassificationDropdown.selectedIndex
      ].text;

    const apiUrl = `/get_horizontal_bar_data?econ=${encodeURIComponent(
      selectedEcon
    )}&prog=${encodeURIComponent(
      selectedProg
    )}&financialYear=${encodeURIComponent(
      financialYear
    )}&province=${encodeURIComponent(province)}&department=${encodeURIComponent(
      department
    )}`;

    d3.json(apiUrl)
      .then((dataset) => {
        const count =
          dataset && dataset.children && Array.isArray(dataset.children)
            ? dataset.children.length
            : 0;

        updateSummary(selectedProgrammeText, selectedClassificationText);

        if (count > 0) {
          renderChart(dataset);
        } else {
          renderEmptyState(
            "No data available",
            "Try another programme or economic classification."
          );
        }
      })
      .catch((error) => {
        console.error("Error fetching chart data:", error);
        updateSummary(selectedProgrammeText, selectedClassificationText);
        renderEmptyState(
          "Error loading data",
          "Please try again in a moment."
        );
      });
  }

  function populateDropdown(url, dropdownElement) {
    return fetch(url)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        const items = typeof data === "string" ? JSON.parse(data) : data;

        dropdownElement.innerHTML = "";

        if (!items || !Array.isArray(items) || !items.length) {
          return;
        }

        items.forEach((item) => {
          const option = document.createElement("option");
          option.value = item;
          option.textContent = item;
          dropdownElement.appendChild(option);
        });

        if (dropdownElement.options.length > 0) {
          dropdownElement.value = dropdownElement.options[0].value;
        }
      });
  }

  function initialize() {
    const { financialYear, department, province } = getUrlParts();

    economicClassificationDropdown.addEventListener(
      "change",
      fetchDataAndRenderChart
    );
    programmeDropdown.addEventListener("change", fetchDataAndRenderChart);

    window.addEventListener("resize", function() {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(fetchDataAndRenderChart, 150);
    });

    populateDropdown(
      `/get_economicClassification/?financialYear=${encodeURIComponent(
        financialYear
      )}&department=${encodeURIComponent(
        department
      )}&province=${encodeURIComponent(province)}`,
      economicClassificationDropdown
    )
      .then(() =>
        populateDropdown(
          `/get_programmes?financialYear=${encodeURIComponent(
            financialYear
          )}&department=${encodeURIComponent(
            department
          )}&econ=${encodeURIComponent("")}&province=${encodeURIComponent(
            province
          )}`,
          programmeDropdown
        )
      )
      .then(fetchDataAndRenderChart)
      .catch((error) => {
        console.error("Initialization failed:", error);
        renderEmptyState(
          "Failed to initialize",
          "Please refresh the page and try again."
        );
      });
  }

  initialize();
});
