document.addEventListener("DOMContentLoaded", function() {
  let treeMapDataElement = document.getElementById("treemap");
  let dataset; // This will hold the parsed data for the main treemap
  let currentSubProgrammeData = null; // To hold data for the sub-programme treemap

  if (treeMapDataElement) {
    try {
      // Parse the initial dataset from the hidden div
      dataset = JSON.parse(treeMapDataElement.textContent);

      // Normalize the main programme data structure
      dataset.children = dataset.children.map((d) => ({
        name: d.Name || d.name,
        value: d.Count || d.value,
        subprogrammes:
          d.children && Array.isArray(d.children)
            ? d.children.map((sub) => ({
                name: sub.Name || sub.name,
                value: sub.Count || sub.value,
              }))
            : [], // Ensure subprogrammes are also normalized
      }));

      // ✅ Function to format large numbers into human-readable currency
      function formatValue(value) {
        if (value >= 1e12) {
          return `R ${(value / 1e12).toFixed(1)} trillion`; // Trillions
        } else if (value >= 1e9) {
          return `R ${(value / 1e9).toFixed(1)} billion`; // Billions
        } else if (value >= 1e6) {
          return `R ${(value / 1e6).toFixed(1)} million`; // Millions
        } else if (value >= 1e3) {
          return `R ${(value / 1e3).toFixed(1)} thousand`; // Thousands
        } else {
          return `R ${value.toLocaleString()}`; // Default formatting
        }
      }

      /**
       * Renders or updates a D3.js treemap.
       * @param {string} containerId - The ID of the HTML element where the treemap will be rendered.
       * @param {object} data - The data for the treemap (root object with children).
       * @param {function} [onClickCallback=null] - Callback function executed on node click.
       * Receives the name of the clicked programme.
       */
      function renderTreemap(containerId, data, onClickCallback = null) {
        const container = document.getElementById(containerId);
        if (!container) {
          console.error(
            `Container with ID "${containerId}" not found for treemap rendering.`
          );
          return;
        }

        // Clear any existing SVG to prevent multiple overlapping charts on resize/update
        d3.select(`#${containerId} svg`).remove();

        const width = container.clientWidth;
        const height = container.clientHeight;

        const svg = d3
          .select(`#${containerId}`)
          .append("svg")
          .attr("width", width)
          .attr("height", height);

        const tooltip = d3.select("#tooltip");

        // Create the D3 hierarchy, sum values, and sort
        const root = d3
          .hierarchy(data)
          .sum((d) => Math.pow(d.value || 1, 0.4)) // Use a power scale to adjust rectangle sizes visually
          .sort((a, b) => b.value - a.value);

        // Initialize the treemap layout
        const treemap = d3
          .treemap()
          .size([width, height])
          .padding(3);
        treemap(root);

        // Define a color scale for different categories/programmes
        const color = d3
          .scaleOrdinal()
          .domain([
            "Category1",
            "Category2",
            "Category3",
            "Category4",
            "Category5",
            "Category6",
            "Category7",
          ]) // Example domains, adjust as needed
          .range([
            "#2B3BB0",
            "#85294E",
            "#1A4641",
            "#27605C",
            "#F08B32",
            "#4C362C",
            "#6A4D42",
          ]);

        // Create a group for each leaf node (rectangle)
        const nodes = svg
          .selectAll("g")
          .data(root.leaves())
          .enter()
          .append("g")
          .attr("transform", (d) => `translate(${d.x0},${d.y0})`);

        // Append the rectangle for each node
        nodes
          .append("rect")
          .attr("class", "node")
          .attr("width", (d) => d.x1 - d.x0)
          .attr("height", (d) => d.y1 - d.y0)
          .attr("fill", (d) => color(d.data.name)) // Color based on node name
          .on("mouseover", function(event, d) {
            // Show tooltip on mouseover with formatted name and value
            tooltip
              .style("display", "block")
              .html(
                `<strong>${event.data.name}</strong><br>Value: ${formatValue(
                  event.data.value
                )}`
              )
              .style("left", `${d3.event.pageX + 10}px`) // Position tooltip relative to mouse
              .style("top", `${d3.event.pageY - 10}px`);
          })
          .on("mouseout", () => {
            // Hide tooltip on mouseout
            tooltip.style("display", "none");
          })
          .on("click", function(event, d) {
            // If a click callback is provided, execute it
            if (onClickCallback) {
              const selectedProgrammeElement = document.getElementById(
                "selectedProgramme"
              );
              const selectedProgrammeAmountElement = document.getElementById(
                "selectedProgrammeAmount"
              );

              if (selectedProgrammeElement) {
                selectedProgrammeElement.innerHTML = event.data.name;
              }
              if (selectedProgrammeAmountElement) {
                selectedProgrammeAmountElement.innerHTML = formatValue(
                  event.data.value
                );
              }
              onClickCallback(event.data.name); // Pass the clicked programme's name to the callback
            } else {
              // This branch is for the sub-programme treemap
              const selectedSubProgrammeElement = document.getElementById(
                "selectedSubprogramme"
              );
              const selectedSubprogrammeAmountElement = document.getElementById(
                "selectedSubprogrammeAmount"
              );

              if (selectedSubProgrammeElement) {
                selectedSubProgrammeElement.innerHTML = event.data.name;
              }
              if (selectedSubprogrammeAmountElement) {
                selectedSubprogrammeAmountElement.innerHTML = formatValue(
                  event.data.value
                );
              }
            }
          });

        // Append text label for the programme/sub-programme name
        nodes
          .append("text")
          .attr("x", 5)
          .attr("y", 20)
          .attr("fill", "white")
          .style("font-size", "12px")
          .text((d) => d.data.name); // Display the name of the current node

        // Append text label for the formatted value
        nodes
          .append("text")
          .attr("x", (d) => (d.x1 - d.x0) / 12) // Position value text
          .attr("y", (d) => (d.y1 - d.y0) / 1.2)
          .attr("fill", "white")
          .style("font-size", "12px")
          .text((d) => formatValue(d.data.value)); // Display the formatted value
      }

      /**
       * Updates the sub-programme treemap based on the selected main programme.
       * @param {string} programmeName - The name of the main programme selected.
       */
      function updateSubProgrammeTreemap(programmeName) {
        const selectedProgramme = dataset.children.find(
          (d) => d.name === programmeName
        );
        currentSubProgrammeData = {
          name: programmeName, // Root name for the sub-treemap
          children: selectedProgramme ? selectedProgramme.subprogrammes : [],
        };

        // Render the sub-programme treemap
        renderTreemap("heatmap2", currentSubProgrammeData);
      }

      /**
       * Handles window resizing by re-rendering both treemaps.
       */
      function resizeCharts() {
        // Re-render the main treemap (heatmap1)
        renderTreemap("heatmap1", dataset, updateSubProgrammeTreemap);

        // Re-render the sub-programme treemap (heatmap2) if a programme was previously selected
        if (currentSubProgrammeData) {
          renderTreemap("heatmap2", currentSubProgrammeData);
        } else {
          // If no sub-programme is selected, clear heatmap2 and reset its labels
          d3.select("#heatmap2 svg").remove();
          const selectedSubProgramme = document.getElementById(
            "selectedSubprogramme"
          );
          const selectedSubprogrammeAmount = document.getElementById(
            "selectedSubprogrammeAmount"
          );
          if (selectedSubProgramme)
            selectedSubProgramme.innerHTML = "Select a Programme";
          if (selectedSubprogrammeAmount)
            selectedSubprogrammeAmount.innerHTML = "R 0";
        }
      }

      // Initial rendering of the main treemap
      renderTreemap("heatmap1", dataset, updateSubProgrammeTreemap);

      // Initial rendering of the sub-programme treemap (empty or default state)
      // You might want to initialize with a placeholder or the first programme's data
      // For now, it will be empty until a main programme is clicked
      const selectedProgrammeElement = document.getElementById(
        "selectedProgramme"
      );
      if (selectedProgrammeElement && dataset.children.length > 0) {
        // Initialize heatmap2 with the first programme's sub-data or a default
        updateSubProgrammeTreemap(dataset.children[0].name);
      } else {
        renderTreemap("heatmap2", { name: "Sub-Programmes", children: [] });
      }

      // Calculate and display the total sum of all programmes
      const totalSum = dataset.children.reduce(
        (sum, programme) => sum + programme.value,
        0
      );
      const selectedProgrammeAmountElement = document.getElementById(
        "selectedProgrammeAmount"
      );
      if (selectedProgrammeAmountElement) {
        selectedProgrammeAmountElement.innerHTML = formatValue(totalSum);
      }

      // Listen for window resize events to make the treemaps responsive
      window.addEventListener("resize", resizeCharts);
    } catch (error) {
      console.error("JSON Parse Error or Treemap Initialization Error:", error);
      // Fallback dataset in case of parsing error
      dataset = {
        name: "root",
        children: [{ name: "No Data Available", value: 0 }],
      };
      renderTreemap("heatmap1", dataset); // Render main treemap with error data
      renderTreemap("heatmap2", { name: "Sub-Programmes", children: [] }); // Render empty sub-treemap
    }
  } else {
    console.error("Treemap data element with ID 'treemap' not found!");
    dataset = {
      name: "root",
      children: [{ name: "No Data Available", value: 0 }],
    };
    renderTreemap("heatmap1", dataset); // Render main treemap with error data
    renderTreemap("heatmap2", { name: "Sub-Programmes", children: [] }); // Render empty sub-treemap
  }
});
