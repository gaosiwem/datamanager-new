// Declare tooltip globally so it's initialized once
let tooltip;

document.addEventListener("DOMContentLoaded", function() {

  let firstProgramme = ""; // Variable to hold the first programme for initial rendering

  const tooltip = d3.select("#tooltip");

  drawBubbleGraph();

  function drawBubbleGraph(selectedProgramme = "") {
    const rawData = document.getElementById("bubble_graph");
    let dataset;

    if (selectedProgramme === "") {
      const parts = getUrlParts();
      const { financialYear, department, province } = getFinancialInfo(parts);

      let firstProgramme = fetchAndRenderLegend(
        financialYear,
        department,
        province,
        getColorScale()
      );

      if (firstProgramme) {
        selectedProgramme = firstProgramme; // Set the first programme as the default selection
      }
    }

    let datasetData = parseDataset(rawData);

    dataset = {
      name: "root",
      children: datasetData.children.filter(
        (d) => d.Programme === selectedProgramme
      ),
    };
    updateLegendActiveState(selectedProgramme);

    const svgContainer = document.getElementById("bubble_graph_svg");
    if (!svgContainer) {
      console.error("SVG container with ID 'bubble_graph_svg' not found!");
      return;
    }

    if (rawData) {
      var width = 800,
        height = 600;
      var svg = d3
        .select("#bubble_graph_svg")
        .attr("width", width)
        .attr("height", height);

      // Remove all circles (bubbles)
      svg.selectAll("*").remove();

      var pack = d3
        .pack()
        .size([width, height])
        .padding(12);

      var root = d3.hierarchy(dataset).sum((d) => d.Count);
      var nodes = pack(root).leaves();

      const color = getColorScale();

      // Calculate min and max Count values from the *actual* nodes being rendered
      // This is important for accurate scaling, especially after filtering.
      const allCounts = nodes.map((d) => d.data.Count);
      const minCount = d3.min(allCounts);
      const maxCount = d3.max(allCounts);

      // Define a radius scale to control bubble sizes proportionally.
      // Using d3.scaleSqrt() is common for bubble charts as it maps values
      // to area visually more accurately than a linear scale.
      // Adjust the range [minRadius, maxRadius] to control the
      // smallest and largest bubble sizes displayed on the graph.
      const radiusScale = d3
        .scaleSqrt()
        .domain([minCount || 0, maxCount || 1]) // Handle cases with minCount/maxCount being undefined or zero
        .range([10, 100]); // Minimum and maximum radius in pixels. Adjust as needed.

      nodes.forEach((d) => {
        d.r = radiusScale(d.data.Count);
      });

      const simulation = d3
        .forceSimulation(nodes)
        .force("center", d3.forceCenter(width / 2, height / 2)) // Pulls nodes towards the center
        .force(
          "collide",
          d3.forceCollide().radius((d) => d.r + 2)
        ); // Prevents overlap, add a little padding

      const bubbles = renderBubbles(svg, nodes, color, radiusScale);

      const labels = renderLabels(svg, nodes, radiusScale);

      // Update positions on each tick of the simulation
      simulation.on("tick", () => {
        bubbles.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
        labels.attr("x", (d) => d.x).attr("y", (d) => d.y);
      });
      // --- End Force Simulation ---
    } else {
      console.error("bubble graph data not found!");
      dataset = { name: "root", children: [{ name: "No Data", value: 0 }] };
    }
  }

  function parseDataset(rawData) {
    try {
      return JSON.parse(rawData.textContent);
    } catch (error) {
      console.error("JSON Parse Error:", error);
      return { name: "root", children: [{ name: "No Data", value: 0 }] };
    }
  }

  function getUrlParts() {
    const currentUrl = window.location.href;
    // const parts = currentUrl.replace("https://vulekamali.gov.za/", "").split("/").filter(Boolean);
    const parts = currentUrl
      .replace("https://vulekamali.gov.za/", "")
      .split("/")
      .filter(Boolean);
    return parts;
  }

  function getFinancialInfo(parts) {
    const financialYear = parts[0];
    const type = parts[1];
    const department = type === "national" ? parts[3] : parts[4];
    const province = type === "national" ? "" : parts[2];
    return { financialYear, department, province };
  }

  function getColorScale() {
    return d3
      .scaleOrdinal()
      .domain([
        "Category1",
        "Category2",
        "Category3",
        "Category4",
        "Category5",
        "Category6",
        "Category7",
      ])
      .range([
        "#2B3BB0",
        "#85294E",
        "#1A4641",
        "#27605C",
        "#F08B32",
        "#4C362C",
        "#6A4D42",
      ]);
  }

  function truncateText(text, maxWidth) {
    if (!text) return "";
    let truncated = text;
    const avgCharWidth = 6;
    const maxChars = Math.floor(maxWidth / avgCharWidth);
    if (text.length > maxChars) {
      truncated = text.substring(0, maxChars - 2) + "...";

      if (truncated.startsWith("...")) {
        truncated = ""; // Remove leading "..."
      }
    }
    return truncated;
  }

  function showSelectedInfo(name='', value='', programme='', reset=false) {
    
    var selected = document.getElementById("selected-econ");
    var selectedValue = document.getElementById("selected-econ-value");
    var selectedProgramme = document.getElementById("selected-econ-programme");

    if(!reset && (!name || !value || !programme)) {
      // If reset is false and any of the values are empty, do not update
      selected.innerHTML = '';
      selectedValue.innerHTML = "";
      selectedProgramme.innerHTML = "";
    } else{
      selected.innerHTML = name;
      selectedValue.innerHTML = "R " + value.toLocaleString();
      selectedProgramme.innerHTML = programme;
    }
    
  }

  function renderBubbles(svg, nodes, color, radiusScale) {

    showSelectedInfo(true);

    return svg
      .selectAll("circle")
      .data(nodes)
      .enter()
      .append("circle")
      .attr("class", "bubble")
      .attr("cx", (d) => d.x)
      .attr("cy", (d) => d.y)
      .attr("r", (d) => radiusScale(d.data.Count))
      .attr("fill", (d) => color(d.data.Name))
      .style("cursor", "pointer")
      .on("click", function(event, d) {
        showSelectedInfo(
          event.data.Name,
          event.data.Count,
          event.data.Programme
        );
      }) // Add tooltip events
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
          .html(
            `<strong>${event.data.Name}</strong><br>Value: ${formatValue(
              event.data.Count
            )}`
          ) // Format value in tooltip
          .style("left", `${d3.event.pageX + 10}px`)
          .style("top", `${d3.event.pageY - 10}px`);
      })
      .on("mouseout", () => {
        // Hide tooltip on mouseout
        tooltip.style("display", "none");
      });
  }

  function renderLabels(svg, nodes, radiusScale) {
    return svg
      .selectAll("text")
      .data(nodes)
      .enter()
      .append("text")
      .attr("x", (d) => d.x)
      .attr("y", (d) => d.y)
      .text((d) => truncateText(d.data.Name, radiusScale(d.data.Count) * 2.0))
      .attr("dy", ".3em")
      .attr("text-anchor", "middle")
      .style(
        "font-size",
        (d) => Math.min(Math.max(radiusScale(d.data.Count) * 0.2, 6), 20) + "px"
      )
      .style("fill", "white")
      .style("pointer-events", "none")
      .style("cursor", "pointer");
  }

  function renderLegend(prog, color, firstProgramme = "") {
    var legendContainer = document.getElementById("programme-legend");
    prog.forEach((program) => {
      var legendItem = document.createElement("div");
      legendItem.classList.add("legend-item"); // Add class for styling
      legendItem.style.display = "flex";
      legendItem.style.alignItems = "center";
      legendItem.style.marginBottom = "12px";
      legendItem.style.cursor = "pointer"; // Add cursor pointer for interactivity

      var colorBox = document.createElement("div");
      colorBox.style.width = "10px";
      colorBox.style.height = "10px";
      colorBox.style.backgroundColor = color(program);
      colorBox.style.marginRight = "10px";
      colorBox.style.borderRadius = "50%";

      // --- NEW: Add click event listener to each legend item ---
      legendItem.addEventListener("click", function() {
        drawBubbleGraph(program);// Redraw the graph with the selected programme
         // Reset selected info
      });

      var label = document.createElement("span");
      label.textContent = program;

      legendItem.appendChild(colorBox);
      legendItem.appendChild(label);
      legendContainer.appendChild(legendItem);
    });

    if (firstProgramme) {
      drawBubbleGraph(firstProgramme);
    }
  }

  function fetchAndRenderLegend(financialYear, department, province, color) {
    d3.json(
      `/get_programmes?financialYear=${encodeURIComponent(
        financialYear
      )}&department=${encodeURIComponent(
        department
      )}&province=${encodeURIComponent(province)}&econ=${encodeURIComponent(
        ""
      )}`
    ).then((data) => {
      const prog = typeof data === "string" ? JSON.parse(data) : data;
      if (prog && prog.length > 0) {
        firstProgramme = prog[0]; // Store the first programme for initial graph rendering
      }
      if (!prog || prog.length === 0) {
        console.error("No data received");
        return;
      }
      renderLegend(prog, color, prog[0]);
    });

    return firstProgramme; // Return the first programme for initial graph rendering
  }

  function updateLegendActiveState(activeProgram) {
    const legendItems = document.querySelectorAll(".legend-item");
    legendItems.forEach((item) => {
      if (item.textContent === activeProgram) {
        item.classList.add("active");
      } else {
        item.classList.remove("active");
      }
    });
  }

  function formatValue(value) {
    if (value >= 1e12) {
      return `R ${(value / 1e12).toFixed(1).toLocaleString()} trillion`; // Trillions
    } else if (value >= 1e9) {
      return `R ${(value / 1e9).toFixed(1).toLocaleString()} billion`; // Billions
    } else if (value >= 1e6) {
      return `R ${(value / 1e6).toFixed(1).toLocaleString()} million`; // million
    } else if (value >= 1e3) {
      return `R ${(value / 1e3).toFixed(1).toLocaleString()} thousand`; // thousand
    } else {
      return "R " + value.toLocaleString(); // Default formatting
    }
  }
});
