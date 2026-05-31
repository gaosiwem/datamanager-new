let tooltip;

document.addEventListener("DOMContentLoaded", function() {
  let firstProgramme = "";
  let activeProgramme = "";
  let activeClassification = "";
  let resizeTimeout;

  const tooltip = d3.select("#tooltip");
  const programmeSelect = document.getElementById("bubble-programme-select");

  if (!programmeSelect) {
    return;
  }

  programmeSelect.addEventListener("change", function() {
    activeClassification = "";
    drawBubbleGraph(this.value);
  });

  drawBubbleGraph();

  function getChartDimensions() {
    const chartContainer = document.querySelector(".bubbleChartContainer");
    const availableWidth = chartContainer ? chartContainer.clientWidth : 0;
    const width = Math.max(280, Math.min(availableWidth || 600, 760));
    const height = Math.max(340, Math.min(580, Math.round(width * 0.72)));

    return { width, height };
  }

  function drawBubbleGraph(selectedProgramme = activeProgramme || firstProgramme) {
    const rawData = document.getElementById("bubble_graph");

    if (!rawData) {
      console.error("bubble graph data not found!");
      return;
    }

    if (selectedProgramme === "") {
      const { financialYear, department, province } = getUrlParts();
      fetchAndRenderProgrammes(financialYear, department, province);
      return;
    }

    const datasetData = parseDataset(rawData);
    const programmeItems = datasetData.children
      .filter((item) => item.Programme === selectedProgramme)
      .sort((left, right) => right.Count - left.Count);

    activeProgramme = selectedProgramme;
    setProgrammeControlValue(selectedProgramme);

    const { width, height } = getChartDimensions();
    const svg = d3
      .select("#bubble_graph_svg")
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("width", width)
      .attr("height", height)
      .attr("preserveAspectRatio", "xMidYMid meet");

    svg.selectAll("*").remove();

    if (!programmeItems.length) {
      renderEmptyState(svg, width, height);
      showSelectedInfo(null, selectedProgramme);
      return;
    }

    const dataset = { name: "root", children: programmeItems };
    const root = d3
      .hierarchy(dataset)
      .sum((item) => item.Count)
      .sort((left, right) => right.value - left.value);

    const chartPadding = Math.max(16, Math.round(width * 0.03));
    const pack = d3
      .pack()
      .size([width - chartPadding * 2, height - chartPadding * 2])
      .padding(Math.max(10, Math.round(width * 0.018)));

    const nodes = pack(root).leaves();
    const fillScale = d3
      .scaleOrdinal()
      .domain(nodes.map((node) => node.data.Name))
      .range([
        "#7bb344",
        "#ee9f31",
        "#ad3c64",
        "#557c2f",
        "#c27810",
        "#742843",
      ]);

    const selectedNode =
      nodes.find((node) => node.data.Name === activeClassification) || nodes[0];

    activeClassification = selectedNode.data.Name;

    const chartLayer = svg
      .append("g")
      .attr("transform", `translate(${chartPadding}, ${chartPadding})`);

    const bubbles = chartLayer
      .selectAll("circle")
      .data(nodes)
      .enter()
      .append("circle")
      .attr("class", "bubble")
      .attr("cx", (node) => node.x)
      .attr("cy", (node) => node.y)
      .attr("r", (node) => node.r)
      .style("cursor", "pointer")
      .on("click", function(node) {
        applyActiveState(node, bubbles, labels, fillScale);
      })
      .on("mouseover", function(node) {
        if (node.data.Name !== activeClassification) {
          d3.select(this).attr("opacity", 1);
        }

        tooltip
          .style("display", "block")
          .html(
            `<strong>${node.data.Name}</strong><br>${activeProgramme}<br>${formatValue(
              node.data.Count
            )}`
          )
          .style("left", `${d3.event.pageX + 12}px`)
          .style("top", `${d3.event.pageY - 14}px`);
      })
      .on("mouseout", function(node) {
        if (node.data.Name !== activeClassification) {
          d3.select(this).attr("opacity", 0.88);
        }

        tooltip.style("display", "none");
      });

    const labels = chartLayer
      .selectAll("text")
      .data(nodes)
      .enter()
      .append("text")
      .attr("class", "bubbleChartLabel")
      .attr("x", (node) => node.x)
      .attr("y", (node) => node.y)
      .attr("text-anchor", "middle")
      .attr("dy", ".35em")
      .style("pointer-events", "none");

    applyActiveState(selectedNode, bubbles, labels, fillScale);
  }

  function applyActiveState(selectedNode, bubbles, labels, fillScale) {
    activeClassification = selectedNode.data.Name;

    bubbles
      .attr("fill", (node) =>
        node.data.Name === activeClassification
          ? "#ad3c64"
          : fillScale(node.data.Count)
      )
      .attr("opacity", (node) =>
        node.data.Name === activeClassification ? 1 : 0.88
      );

    labels
      .text((node) =>
        shouldRenderLabel(node, activeClassification)
          ? truncateText(node.data.Name, node.r * 1.65)
          : ""
      )
      .style("font-size", (node) =>
        `${Math.min(Math.max(node.r * 0.16, 9), 16)}px`
      )
      .style("font-weight", (node) =>
        node.data.Name === activeClassification ? 700 : 500
      )
      .style("fill", "#ffffff");

    showSelectedInfo(selectedNode.data, activeProgramme);
  }

  function shouldRenderLabel(node, selectedName) {
    return node.data.Name === selectedName || node.r >= 34;
  }

  function renderEmptyState(svg, width, height) {
    svg
      .append("text")
      .attr("x", width / 2)
      .attr("y", height / 2 - 10)
      .attr("text-anchor", "middle")
      .attr("fill", "#4a4a4a")
      .style("font-size", "16px")
      .style("font-weight", "600")
      .text("No spending items available");

    svg
      .append("text")
      .attr("x", width / 2)
      .attr("y", height / 2 + 18)
      .attr("text-anchor", "middle")
      .attr("fill", "#979797")
      .style("font-size", "13px")
      .text("Try another programme to view spending classifications.");
  }

  function parseDataset(rawData) {
    try {
      return JSON.parse(rawData.textContent);
    } catch (error) {
      console.error("JSON Parse Error:", error);
      return { name: "root", children: [] };
    }
  }

  function getUrlParts() {
    const currentUrl = new URL(window.location.href);
    const parts = currentUrl.pathname.split("/").filter(Boolean);

    const financialYear = parts[0];
    const type = parts[1];
    const department = type === "national" ? parts[3] : parts[4];
    const province = type === "national" ? "" : parts[2];

    return { financialYear, type, department, province };
  }

  function truncateText(text, maxWidth) {
    if (!text) {
      return "";
    }

    const averageCharacterWidth = 6.4;
    const maxCharacters = Math.floor(maxWidth / averageCharacterWidth);

    if (text.length <= maxCharacters) {
      return text;
    }

    return `${text.substring(0, Math.max(maxCharacters - 3, 1))}...`;
  }

  function showSelectedInfo(itemData, programme) {
    const selected = document.getElementById("selected-econ");
    const selectedValue = document.getElementById("selected-econ-value");
    const selectedProgramme = document.getElementById("selected-econ-programme");

    selectedProgramme.textContent = programme || "No programme selected";

    if (!itemData) {
      selected.textContent = "No spending item selected";
      selectedValue.textContent = "Select a programme to begin.";
      return;
    }

    selected.textContent = itemData.Name;
    selectedValue.textContent = formatValue(itemData.Count);
  }

  function renderProgrammeSelect(programmes) {
    programmeSelect.innerHTML = "";

    programmes.forEach((programme) => {
      const option = document.createElement("option");
      option.value = programme;
      option.textContent = programme;
      programmeSelect.appendChild(option);
    });
  }

  function setProgrammeControlValue(programme) {
    if (programmeSelect.value !== programme) {
      programmeSelect.value = programme;
    }
  }

  function fetchAndRenderProgrammes(financialYear, department, province) {
    d3.json(
      `/get_programmes?financialYear=${encodeURIComponent(
        financialYear
      )}&department=${encodeURIComponent(
        department
      )}&province=${encodeURIComponent(province)}&econ=${encodeURIComponent("")}`
    ).then((data) => {
      const programmes = typeof data === "string" ? JSON.parse(data) : data;

      if (!programmes || !programmes.length) {
        console.error("No programme data received");
        showSelectedInfo(null, "");
        return;
      }

      firstProgramme = programmes[0];
      renderProgrammeSelect(programmes);
      setProgrammeControlValue(firstProgramme);
      drawBubbleGraph(firstProgramme);
    });
  }

  function formatValue(value) {
    if (value >= 1e12) {
      return `R ${(value / 1e12).toFixed(1).toLocaleString()} trillion`;
    }
    if (value >= 1e9) {
      return `R ${(value / 1e9).toFixed(1).toLocaleString()} billion`;
    }
    if (value >= 1e6) {
      return `R ${(value / 1e6).toFixed(1).toLocaleString()} million`;
    }
    if (value >= 1e3) {
      return `R ${(value / 1e3).toFixed(1).toLocaleString()} thousand`;
    }

    return `R ${value.toLocaleString()}`;
  }

  window.addEventListener("resize", function() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(function() {
      if (activeProgramme || firstProgramme) {
        drawBubbleGraph(activeProgramme || firstProgramme);
      }
    }, 150);
  });
});
