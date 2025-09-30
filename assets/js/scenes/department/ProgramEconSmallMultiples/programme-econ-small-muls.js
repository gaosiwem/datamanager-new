let tooltip;

document.addEventListener("DOMContentLoaded", function() {
  const economicClassificationDropdown = document.getElementById(
    "economic-classification-dropdown"
  );
  const programmeDropdown = document.getElementById("programme-dropdown");
  const horizontalBarChart = d3.select("#horizontalBarChart");
  const tooltip = d3.select(".tooltip");

  // Constants for chart dimensions and styling
  const CHART_BAR_HEIGHT = 35;
  const CHART_MARGIN = { top: 30, right: 20, bottom: 30, left: 280 };
  const CHART_WIDTH = 600;
  const LABEL_TEXT_THRESHOLD = 80; // For bar label color logic

  /**
   * Parses the current URL to extract financial year, type, department, and province.
   * @returns {object} An object containing financialYear, type, department, and province.
   */
  function getUrlParts() {
    const currentUrl = new URL(window.location.href);
    const parts = currentUrl.pathname.split("/").filter(Boolean);

    const financialYear = parts[0];
    const type = parts[1];
    // Determine department and province based on type (national or provincial)
    const department = type === "national" ? parts[3] : parts[4];
    const province = type === "national" ? "" : parts[2];

    return { financialYear, type, department, province };
  }

  /**
   * Formats a numeric value into a human-readable currency string (e.g., R 1.2 billion).
   * @param {number} value - The numeric value to format.
   * @returns {string} The formatted currency string.
   */
  function formatCurrencyValue(value) {
    if (value >= 1e12) return `R ${(value / 1e12).toFixed(1)} trillion`;
    if (value >= 1e9) return `R ${(value / 1e9).toFixed(1)} billion`;
    if (value >= 1e6) return `R ${(value / 1e6).toFixed(1)} million`;
    if (value >= 1e3) return `R ${(value / 1e3).toFixed(1)} thousand`;
    return `R ${value.toLocaleString()}`;
  }

  /**
   * Wraps text labels for D3 axis to fit within a specified width.
   * @param {d3.Selection} text - The D3 selection of text elements to wrap.
   * @param {number} width - The maximum width for the text.
   */
  function wrapText(text, width) {
    text.each(function() {
      const textElement = d3.select(this);
      const words = textElement
        .text()
        .split(/\s+/)
        .reverse();
      let word;
      let line = [];
      let lineNumber = 0;
      const lineHeight = 1.1; // ems
      const y = textElement.attr("y");
      const dy = parseFloat(textElement.attr("dy") || 0);
      let tspan = textElement
        .text(null)
        .append("tspan")
        .attr("x", 0)
        .attr("y", y)
        .attr("dy", dy + "em");

      while ((word = words.pop())) {
        line.push(word);
        tspan.text(line.join(" "));
        if (tspan.node().getComputedTextLength() > width) {
          line.pop();
          tspan.text(line.join(" "));
          line = [word];
          tspan = textElement
            .append("tspan")
            .attr("x", 0)
            .attr("y", y)
            .attr("dy", ++lineNumber * lineHeight + dy + "em")
            .text(word);
        }
      }
    });
  }

  /**
   * Renders or updates the horizontal bar chart using D3.
   * @param {object} dataset - The data to visualize, expected to have a 'children' array.
   */
  function renderChart(dataset) {
    horizontalBarChart.selectAll("*").remove(); // Clear previous chart elements

    const numBars = dataset.children.length;
    const height = Math.max(numBars * CHART_BAR_HEIGHT, 200);
    const maxBarWidth = CHART_WIDTH - CHART_MARGIN.left - CHART_MARGIN.right;

    const svg = horizontalBarChart
      .attr("width", CHART_WIDTH)
      .attr("height", height + CHART_MARGIN.top + CHART_MARGIN.bottom)
      .append("g")
      .attr(
        "transform",
        `translate(${CHART_MARGIN.left}, ${CHART_MARGIN.top})`
      );

    // Prepare data: extract subprogrammes and format values
    const subprogrammes = dataset.children.map((d) => d.name);
    dataset.children.forEach((d) => {
      d.formatted_value = formatCurrencyValue(d.value);
    });

    const xScale = d3
      .scaleLinear()
      .domain([0, d3.max(dataset.children, (d) => d.value)])
      .range([0, maxBarWidth]);

    const yScale = d3
      .scaleBand()
      .domain(subprogrammes)
      .range([0, height])
      .padding(0.1);

    // Append Y-axis
    svg
      .append("g")
      .call(d3.axisLeft(yScale))
      .attr("class", "axis-label")
      .selectAll("text")
      .call(wrapText, CHART_MARGIN.left - 50); // Adjusted wrap width

    // Append bars
    svg
      .selectAll(".horizontalBar")
      .data(dataset.children)
      .enter()
      .append("rect")
      .attr("class", "horizontalBarChart") // Consider renaming to "horizontalBar" for consistency
      .attr("y", (d) => yScale(d.name))
      .attr("width", (d) => xScale(d.value))
      .attr("height", yScale.bandwidth())
      .on("mouseover", function(event, d) {
        const [relX, relY] = d3.pointer(event, svg.node());
        const svgRect = svg.node().getBoundingClientRect();

        // Calculate absolute position on the page (viewport position + scroll offset).
        // This is robust even if event.pageX/Y or clientX/Y are unreliable directly.
        // const xPos = svgRect.left + relX + window.scrollX;
        // const yPos = svgRect.top + relY + window.scrollY;
        // Show tooltip on mouseover
        tooltip
          .style("display", "block")
          .html(`<strong>${event.name}</strong><br>Value: ${event.value}`) // Format value in tooltip
          .style("left", `${d3.event.pageX + 10}px`)
          .style("top", `${d3.event.pageY - 10}px`);
      })
      .on("mouseout", () => {
        // Hide tooltip on mouseout
        tooltip.style("display", "none");
      });

    // Append value labels on bars
    svg
      .selectAll(".bar-label")
      .data(dataset.children)
      .enter()
      .append("text")
      .attr("class", "bar-label")
      .attr("x", (d) => {
        const barCurrentWidth = xScale(d.value);
        return barCurrentWidth < LABEL_TEXT_THRESHOLD
          ? barCurrentWidth + 8
          : barCurrentWidth - 8;
      })
      .attr("y", (d) => yScale(d.name) + yScale.bandwidth() / 2)
      .attr("dy", ".35em")
      .attr("text-anchor", (d) =>
        xScale(d.value) < LABEL_TEXT_THRESHOLD ? "start" : "end"
      )
      .text((d) => d.formatted_value)
      .style("fill", (d) =>
        xScale(d.value) < LABEL_TEXT_THRESHOLD ? "black" : "white"
      )
      .style("font-size", "11px");
  }

  /**
   * Fetches data for the chart based on selected filters and renders it.
   * Displays a "No data" message if the dataset is empty.
   */
  function fetchDataAndRenderChart() {
    horizontalBarChart.selectAll("*").remove(); // Clear previous chart
    const { financialYear, department, province } = getUrlParts();

    // Get the current selected values from the dropdowns
    const selectedEcon = economicClassificationDropdown.value;
    const selectedProg = programmeDropdown.value;

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
        if (dataset && dataset.children && dataset.children.length > 0) {
          renderChart(dataset);
        } else {
          horizontalBarChart
            .append("text")
            .attr("x", CHART_WIDTH / 2)
            .attr("y", 100)
            .attr("text-anchor", "middle")
            .text("No data available for the selected filters.");
        }
      })
      .catch((error) => {
        console.error("Error fetching chart data:", error);
        horizontalBarChart
          .append("text")
          .attr("x", CHART_WIDTH / 2)
          .attr("y", 100)
          .attr("text-anchor", "middle")
          .text("Error loading data. Please try again.");
      });
  }

  /**
   * Populates a given dropdown element with options fetched from a URL.
   * Sets the first item as selected by default.
   * @param {string} url - The URL to fetch dropdown data from.
   * @param {HTMLElement} dropdownElement - The dropdown element to populate.
   * @returns {Promise<void>} A promise that resolves when the dropdown is populated.
   */
  function populateDropdown(url, dropdownElement) {
    return fetch(url) // Return the promise from fetch
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        const items = typeof data === "string" ? JSON.parse(data) : data;

        if (!items || !Array.isArray(items) || items.length === 0) {
          console.warn(
            `No valid data received for dropdown at ${url}. Dropdown will remain empty.`
          );
          dropdownElement.innerHTML = ""; // Ensure no stale options
          return;
        }

        // Clear existing options
        dropdownElement.innerHTML = "";

        items.forEach((item) => {
          const option = document.createElement("option");
          option.value = item;
          option.textContent = item;
          dropdownElement.appendChild(option);
        });

        // Set the first item as selected
        if (dropdownElement.options.length > 0) {
          dropdownElement.value = dropdownElement.options[0].value;
        }
      })
      .catch((error) => {
        console.error(`Error populating dropdown from ${url}:`, error);
        dropdownElement.innerHTML =
          '<option value="">Error loading...</option>'; // Provide feedback
        // Re-throw the error so subsequent .then() or .catch() blocks can handle it
        throw error;
      });
  }

  // Initialize the application
  function initialize() {
    // Add event listeners for dropdown changes
    economicClassificationDropdown.addEventListener(
      "change",
      fetchDataAndRenderChart
    );
    programmeDropdown.addEventListener("change", fetchDataAndRenderChart);

    const { financialYear, department, province } = getUrlParts();

    // Populate economic classification dropdown
    populateDropdown(
      `/get_economicClassification/?financialYear=${encodeURIComponent(
        financialYear
      )}&department=${encodeURIComponent(
        department
      )}&province=${encodeURIComponent(province)}`,
      economicClassificationDropdown
    )
      .then(() => {
        // After the economic classification dropdown is populated,
        // populate the programme dropdown.
        // Note: If programme dropdown's initial content depends on the
        // selected economic classification, you might need to pass
        // economicClassificationDropdown.value here.
        // For now, keeping it as an empty econ filter as in the original.
        return populateDropdown(
          `/get_programmes?financialYear=${encodeURIComponent(
            financialYear
          )}&department=${encodeURIComponent(
            department
          )}&econ=${encodeURIComponent("")}&province=${encodeURIComponent(
            province
          )}`,
          programmeDropdown
        );
      })
      .then(() => {
        // After both dropdowns are populated and their first items are selected,
        // fetch and render initial chart data.
        fetchDataAndRenderChart();
      })
      .catch((error) => {
        console.error("Initialization failed:", error);
        // Handle overall initialization errors, e.g., show a message to the user
        horizontalBarChart
          .append("text")
          .attr("x", CHART_WIDTH / 2)
          .attr("y", 100)
          .attr("text-anchor", "middle")
          .text("Failed to initialize. Please check console for details.");
      });
  }

  //     // Utility: Format value for display
    function formatValue(value) {
        if (value >= 1e12) return `R ${(value / 1e12).toFixed(1)} trillion`;
        if (value >= 1e9) return `R ${(value / 1e9).toFixed(1)} billion`;
        if (value >= 1e6) return `R ${(value / 1e6).toFixed(1)} million`;
        if (value >= 1e3) return `R ${(value / 1e3).toFixed(1)} thousand`;
        return `R ${value.toLocaleString()}`;
    }

  // Call initialize when the DOM is ready
  initialize();
});








