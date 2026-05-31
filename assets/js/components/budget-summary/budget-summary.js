document.addEventListener("DOMContentLoaded", function() {
  const instances = Array.prototype.slice.call(
    document.querySelectorAll("[data-budget-summary-treemap]")
  );

  if (!instances.length || !window.d3) {
    return;
  }

  const renderers = instances.map(createBudgetSummaryTreemap).filter(Boolean);
  let resizeTimeout;

  window.addEventListener("resize", function() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(function() {
      renderers.forEach(function(render) {
        render();
      });
    }, 150);
  });
});

function createBudgetSummaryTreemap(root) {
  const dataElement = document.getElementById(root.getAttribute("data-data-id"));
  const treemapContainer = root.querySelector('[data-role="treemap"]');
  const tooltip = d3.select(root.querySelector('[data-role="tooltip"]'));
  const summaryName = root.querySelector('[data-role="summary-name"]');
  const summaryValue = root.querySelector('[data-role="summary-value"]');
  const defaultName = root.getAttribute("data-default-name") || "All items";
  const emptyName = root.getAttribute("data-empty-name") || "No data available";

  let dataset = { name: "Budget summary", children: [] };
  let lastWidth = 0;
  let lastHeight = 0;

  if (!dataElement || !treemapContainer) {
    return null;
  }

  try {
    dataset = normaliseDataset(JSON.parse(dataElement.textContent));
    updateSummary(defaultName, getTotal(dataset.children));
    renderTreemap();
  } catch (error) {
    console.error("Budget summary treemap initialization error:", error);
    dataset = { name: emptyName, children: [] };
    updateSummary(emptyName, 0);
    renderTreemap();
  }

  if (window.ResizeObserver) {
    const resizeObserver = new ResizeObserver(function() {
      const bounds = treemapContainer.getBoundingClientRect();
      const nextWidth = Math.max(Math.floor(bounds.width), 1);
      const nextHeight = Math.max(Math.floor(bounds.height), 280);

      if (nextWidth !== lastWidth || nextHeight !== lastHeight) {
        renderTreemap();
      }
    });

    resizeObserver.observe(treemapContainer);
  }

  return renderTreemap;

  function normaliseDataset(rawDataset) {
    const children = Array.isArray(rawDataset.children)
      ? rawDataset.children.map(function(item) {
          const value = Number(item.Count || item.value || 0);

          return {
            id: item.id || item.name || item.Name,
            name: item.Name || item.name || "Unspecified",
            value: value,
            layoutValue: Math.pow(Math.max(value, 1), 0.4),
            url: item.url || null,
          };
        })
      : [];

    return {
      name: rawDataset.Name || rawDataset.name || "Budget summary",
      children: children,
    };
  }

  function updateSummary(name, value) {
    if (summaryName) {
      summaryName.textContent = name;
    }

    if (summaryValue) {
      summaryValue.textContent = formatValue(value);
    }
  }

  function getTotal(items) {
    return items.reduce(function(sum, item) {
      return sum + Number(item.value || 0);
    }, 0);
  }

  function renderTreemap() {
    d3.select(treemapContainer).select("svg").remove();

    const bounds = treemapContainer.getBoundingClientRect();
    const width = Math.max(Math.floor(bounds.width), 1);
    const height = Math.max(Math.floor(bounds.height), 280);
    lastWidth = width;
    lastHeight = height;

    const svg = d3
      .select(treemapContainer)
      .append("svg")
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("width", "100%")
      .attr("height", "100%")
      .attr("preserveAspectRatio", "xMidYMid meet");

    if (!dataset.children.length) {
      renderEmptyState(svg, width, height, emptyName);
      return;
    }

    const rootNode = d3
      .hierarchy(dataset)
      .sum(function(item) {
        return Math.max(item.layoutValue || item.value || 0, 1);
      })
      .sort(function(left, right) {
        return right.value - left.value;
      });

    d3
      .treemap()
      .size([width, height])
      .paddingOuter(6)
      .paddingTop(6)
      .paddingInner(4)
      .round(true)(rootNode);

    const leaves = rootNode.leaves();
    const color = createColorScale(leaves.map(function(leaf) {
      return leaf.data;
    }));

    const nodes = svg
      .selectAll("g")
      .data(leaves)
      .enter()
      .append("g")
      .attr("transform", function(node) {
        return `translate(${node.x0},${node.y0})`;
      });

    nodes
      .append("rect")
      .attr("class", "node")
      .attr("width", function(node) {
        return Math.max(node.x1 - node.x0, 0);
      })
      .attr("height", function(node) {
        return Math.max(node.y1 - node.y0, 0);
      })
      .attr("rx", 10)
      .attr("ry", 10)
      .attr("fill", function(node) {
        return color(node.data.name);
      })
      .on("mouseover", function(node) {
        d3.select(this).attr("opacity", 0.92);
        tooltip
          .style("display", "block")
          .html(`<strong>${escapeHtml(node.data.name)}</strong><br>${formatValue(node.data.value)}`)
          .style("left", `${d3.event.pageX + 10}px`)
          .style("top", `${d3.event.pageY - 10}px`);
      })
      .on("mouseout", function() {
        d3.select(this).attr("opacity", 1);
        tooltip.style("display", "none");
      })
      .on("click", function(node) {
        if (node.data.url) {
          window.location.href = node.data.url;
        }
      });

    nodes.each(function(node) {
      renderNodeLabel(d3.select(this), node);
    });
  }

  function renderEmptyState(svg, width, height, heading) {
    svg
      .append("text")
      .attr("class", "treemapEmptyState")
      .attr("x", width / 2)
      .attr("y", height / 2 - 10)
      .attr("text-anchor", "middle")
      .text(heading);
  }

}

function createColorScale(items) {
  return d3
    .scaleOrdinal()
    .domain(items.map(function(item) {
      return item.name;
    }))
    .range(["#2B3BB0", "#85294E", "#1A4641", "#27605C", "#F08B32", "#4C362C", "#6A4D42"]);
}

function renderNodeLabel(group, node) {
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

  text.append("tspan").text(labelText);

  if (!useCompactLabel && shouldShowValue(node)) {
    text
      .append("tspan")
      .attr("class", "treemapValue")
      .attr("x", 12)
      .attr("dy", 18)
      .text(formatValue(node.data.value));
  }
}

function formatValue(value) {
  const numericValue = Number(value);
  const absoluteValue = Math.abs(numericValue);

  if (!Number.isFinite(numericValue)) {
    return value;
  }

  if (absoluteValue >= 1e12) {
    return `R ${(numericValue / 1e12).toFixed(1)} trillion`;
  }
  if (absoluteValue >= 1e9) {
    return `R ${(numericValue / 1e9).toFixed(1)} billion`;
  }
  if (absoluteValue >= 1e6) {
    return `R ${(numericValue / 1e6).toFixed(1)} million`;
  }
  if (absoluteValue >= 1e3) {
    return `R ${(numericValue / 1e3).toFixed(1)} thousand`;
  }

  return `R ${Math.round(numericValue).toLocaleString()}`;
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
    .map(function(part) {
      return part.trim();
    })
    .filter(Boolean);

  if (parts.length > 1) {
    return parts
      .slice(0, 3)
      .map(function(part) {
        return part[0].toUpperCase();
      })
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

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
