document.addEventListener("DOMContentLoaded", function() {
  const treeMapDataElement = document.getElementById("treemap");
  const tooltip = d3.select("#treemap-tooltip");

  let dataset = { name: "Programmes", children: [] };
  let currentSubProgrammeData = { name: "Sub-programmes", children: [] };
  let activeProgrammeName = "";
  let activeSubProgrammeName = "";
  let resizeTimeout;

  if (!treeMapDataElement) {
    console.error("Treemap data element with ID 'treemap' not found!");
    return;
  }

  try {
    dataset = normaliseDataset(JSON.parse(treeMapDataElement.textContent));
    initialiseState();
    renderAll();

    window.addEventListener("resize", function() {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(renderAll, 150);
    });
  } catch (error) {
    console.error("JSON Parse Error or Treemap Initialization Error:", error);
    renderTreemap(
      "heatmap1",
      { name: "Programmes", children: [] },
      null,
      ""
    );
    renderTreemap(
      "heatmap2",
      { name: "Sub-programmes", children: [] },
      null,
      ""
    );
  }

  function normaliseDataset(rawDataset) {
    const children = Array.isArray(rawDataset.children)
      ? rawDataset.children.map((programme) => ({
          name: programme.Name || programme.name,
          value: Number(programme.Count || programme.value || 0),
          layoutValue: Math.pow(
            Math.max(Number(programme.Count || programme.value || 0), 1),
            0.4
          ),
          subprogrammes: Array.isArray(programme.children)
            ? programme.children.map((subprogramme) => ({
                name: subprogramme.Name || subprogramme.name,
                value: Number(subprogramme.Count || subprogramme.value || 0),
                layoutValue: Math.pow(
                  Math.max(Number(subprogramme.Count || subprogramme.value || 0), 1),
                  0.4
                ),
              }))
            : [],
        }))
      : [];

    return {
      name: rawDataset.Name || rawDataset.name || "Programmes",
      children,
    };
  }

  function initialiseState() {
    if (!dataset.children.length) {
      updateSummary(
        "selectedProgramme",
        "selectedProgrammeAmount",
        "No programme data available",
        0
      );
      updateSummary(
        "selectedSubprogramme",
        "selectedSubprogrammeAmount",
        "No sub-programme data available",
        0
      );
      return;
    }

    activeProgrammeName = "";
    activeSubProgrammeName = "";
    currentSubProgrammeData = buildAllSubProgrammeData();

    const totalSum = dataset.children.reduce(
      (sum, programme) => sum + programme.value,
      0
    );
    const totalSubProgrammeSum = currentSubProgrammeData.children.reduce(
      (sum, subProgramme) => sum + subProgramme.value,
      0
    );

    updateSummary(
      "selectedProgramme",
      "selectedProgrammeAmount",
      "All programmes",
      totalSum
    );
    updateSummary(
      "selectedSubprogramme",
      "selectedSubprogrammeAmount",
      "All sub-programmes",
      totalSubProgrammeSum
    );
  }

  function renderAll() {
    renderTreemap(
      "heatmap1",
      dataset,
      handleProgrammeSelection,
      activeProgrammeName
    );
    renderTreemap(
      "heatmap2",
      currentSubProgrammeData,
      handleSubProgrammeSelection,
      activeSubProgrammeName
    );
  }

  function buildSubProgrammeData(programmeName) {
    const selectedProgramme = dataset.children.find(
      (programme) => programme.name === programmeName
    );

    return {
      name: programmeName || "Sub-programmes",
      children: selectedProgramme ? selectedProgramme.subprogrammes : [],
    };
  }

  function buildAllSubProgrammeData() {
    const subProgrammes = dataset.children.reduce((items, programme) => {
      if (!Array.isArray(programme.subprogrammes)) {
        return items;
      }

      return items.concat(programme.subprogrammes);
    }, []);

    return {
      name: "All sub-programmes",
      children: subProgrammes,
    };
  }

  function handleProgrammeSelection(programmeName, programmeValue) {
    activeProgrammeName = programmeName;
    currentSubProgrammeData = buildSubProgrammeData(programmeName);
    activeSubProgrammeName = currentSubProgrammeData.children[0]
      ? currentSubProgrammeData.children[0].name
      : "";

    updateSummary(
      "selectedProgramme",
      "selectedProgrammeAmount",
      programmeName,
      programmeValue
    );

    if (activeSubProgrammeName) {
      const firstSubProgramme = currentSubProgrammeData.children[0];
      updateSummary(
        "selectedSubprogramme",
        "selectedSubprogrammeAmount",
        firstSubProgramme.name,
        firstSubProgramme.value
      );
    } else {
      updateSummary(
        "selectedSubprogramme",
        "selectedSubprogrammeAmount",
        "No sub-programme data available",
        0
      );
    }

    renderAll();
  }

  function handleSubProgrammeSelection(subProgrammeName, subProgrammeValue) {
    activeSubProgrammeName = subProgrammeName;
    updateSummary(
      "selectedSubprogramme",
      "selectedSubprogrammeAmount",
      subProgrammeName,
      subProgrammeValue
    );
    renderTreemap(
      "heatmap2",
      currentSubProgrammeData,
      handleSubProgrammeSelection,
      activeSubProgrammeName
    );
  }

  function updateSummary(nameId, amountId, name, value) {
    const nameElement = document.getElementById(nameId);
    const amountElement = document.getElementById(amountId);

    if (nameElement) {
      nameElement.textContent = name;
    }

    if (amountElement) {
      amountElement.textContent = formatValue(value);
    }
  }

  function formatValue(value) {
    if (value >= 1e12) {
      return `R ${(value / 1e12).toFixed(1)} trillion`;
    }
    if (value >= 1e9) {
      return `R ${(value / 1e9).toFixed(1)} billion`;
    }
    if (value >= 1e6) {
      return `R ${(value / 1e6).toFixed(1)} million`;
    }
    if (value >= 1e3) {
      return `R ${(value / 1e3).toFixed(1)} thousand`;
    }

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

  function createColorScale(items) {
    return d3
      .scaleOrdinal()
      .domain(items.map((item) => item.name))
      .range(["#2B3BB0", "#85294E", "#1A4641", "#27605C", "#F08B32", "#4C362C", "#6A4D42"]);
  }

  function shouldShowFullName(node) {
    const width = node.x1 - node.x0;
    const height = node.y1 - node.y0;

    return width >= 92 && height >= 42;
  }

  function shouldShowCompactName(node) {
    const width = node.x1 - node.x0;
    const height = node.y1 - node.y0;

    return width >= 36 && height >= 18;
  }

  function shouldShowValue(node) {
    const width = node.x1 - node.x0;
    const height = node.y1 - node.y0;

    return width >= 120 && height >= 72;
  }

  function getCompactLabel(name) {
    if (!name) {
      return "";
    }

    const parts = name
      .split(/[\s/-]+/)
      .map((part) => part.trim())
      .filter(Boolean);

    if (parts.length > 1) {
      return parts
        .slice(0, 3)
        .map((part) => part[0].toUpperCase())
        .join("");
    }

    return name.substring(0, 3).toUpperCase();
  }

  function getLabelFontSize(node, isCompact) {
    const width = node.x1 - node.x0;
    const height = node.y1 - node.y0;
    const baseSize = isCompact ? 8 : 12;

    return Math.max(Math.min(Math.min(width / 7, height / 2.4), baseSize), 7);
  }

  function renderEmptyState(svg, width, height, heading, hint) {
    svg
      .append("text")
      .attr("class", "treemapEmptyState")
      .attr("x", width / 2)
      .attr("y", height / 2 - 10)
      .attr("text-anchor", "middle")
      .text(heading);

    svg
      .append("text")
      .attr("class", "treemapEmptyStateHint")
      .attr("x", width / 2)
      .attr("y", height / 2 + 18)
      .attr("text-anchor", "middle")
      .text(hint);
  }

  function renderTreemap(containerId, data, onClickCallback, selectedName) {
    const container = document.getElementById(containerId);

    if (!container) {
      console.error(`Container with ID "${containerId}" not found for treemap rendering.`);
      return;
    }

    d3.select(`#${containerId} svg`).remove();

    const width = Math.max(container.clientWidth, 320);
    const height = Math.max(container.clientHeight, 320);

    const svg = d3
      .select(`#${containerId}`)
      .append("svg")
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("width", width)
      .attr("height", height)
      .attr("preserveAspectRatio", "xMidYMid meet");

    if (!data.children || !data.children.length) {
      renderEmptyState(
        svg,
        width,
        height,
        containerId === "heatmap2" ? "No programme selected" : "No data available",
        containerId === "heatmap2"
          ? "Choose a programme on the left to view sub-programmes."
          : "Select another item to explore this treemap."
      );
      return;
    }

    const root = d3
      .hierarchy(data)
      .sum((item) => Math.max(item.layoutValue || item.value || 0, 1))
      .sort((left, right) => right.value - left.value);

    d3
      .treemap()
      .size([width, height])
      .paddingOuter(6)
      .paddingTop(6)
      .paddingInner(4)
      .round(true)(root);

    const leaves = root.leaves();
    const color = createColorScale(leaves.map((leaf) => leaf.data));

    const nodes = svg
      .selectAll("g")
      .data(leaves)
      .enter()
      .append("g")
      .attr("transform", (node) => `translate(${node.x0},${node.y0})`);

    nodes
      .append("rect")
      .attr("class", (node) =>
        node.data.name === selectedName ? "node is-active" : "node"
      )
      .attr("width", (node) => Math.max(node.x1 - node.x0, 0))
      .attr("height", (node) => Math.max(node.y1 - node.y0, 0))
      .attr("rx", 10)
      .attr("ry", 10)
      .attr("fill", (node) => color(node.data.name))
      .attr("opacity", (node) => (selectedName && node.data.name !== selectedName ? 0.88 : 1))
      .on("mouseover", function(node) {
        d3.select(this).attr("opacity", 1);
        tooltip
          .style("display", "block")
          .html(`<strong>${node.data.name}</strong><br>${formatValue(node.data.value)}`)
          .style("left", `${d3.event.pageX + 10}px`)
          .style("top", `${d3.event.pageY - 10}px`);
      })
      .on("mouseout", function(node) {
        d3.select(this).attr(
          "opacity",
          selectedName && node.data.name !== selectedName ? 0.88 : 1
        );
        tooltip.style("display", "none");
      })
      .on("click", function(node) {
        if (onClickCallback) {
          onClickCallback(node.data.name, node.data.value);
        }
      });

    nodes.each(function(node) {
      const group = d3.select(this);
      const tileWidth = node.x1 - node.x0;
      const tileHeight = node.y1 - node.y0;
      const availableTextWidth = tileWidth - 24;

      if (!shouldShowCompactName(node)) {
        return;
      }

      const useCompactLabel = !shouldShowFullName(node);
      const labelText = useCompactLabel
        ? getCompactLabel(node.data.name)
        : truncateText(node.data.name, availableTextWidth);
      const labelFontSize = getLabelFontSize(node, useCompactLabel);

      const text = group
        .append("text")
        .attr("class", "treemapLabel")
        .attr("x", useCompactLabel ? tileWidth / 2 : 12)
        .attr("y", useCompactLabel ? Math.max(tileHeight / 2 + 3, 12) : 22)
        .attr("text-anchor", useCompactLabel ? "middle" : "start")
        .style("font-size", `${labelFontSize}px`);

      text
        .append("tspan")
        .text(labelText);

      if (!useCompactLabel && shouldShowValue(node)) {
        text
          .append("tspan")
          .attr("class", "treemapValue")
          .attr("x", 12)
          .attr("dy", 18)
          .text(formatValue(node.data.value));
      }
    });
  }
});
