document.addEventListener("DOMContentLoaded", function () {

    function createTreeMapGraphs(dataId, containerId) {
        let treeMapData = document.getElementById(dataId);
        let dataset;

        if (treeMapData) {
            try {
                dataset = JSON.parse(treeMapData.textContent);
                dataset.children = dataset.children.map(d => ({
                    id: d.id || d.name,
                    name: d.Name || d.name,
                    value: d.Count || d.value,
                    url: d.url || null,
                    subprogrammes: d.children || []
                }));

                function createTreemap(containerId, data) {
                    const container = document.getElementById(containerId);
                    container.innerHTML = ""; // Clear previous SVG
                    const width = container.clientWidth;
                    const height = Math.min(width * 0.75, 500); // Maintain aspect ratio

                    const svg = d3.select(`#${containerId}`)
                                  .append("svg")
                                  .attr("width", width)
                                  .attr("height", height);

                    const tooltip = d3.select("#tooltip");

                    const root = d3
                      .hierarchy(data)
                      .sum((d) => Math.pow(d.value || 1, 0.4)) // Use a power scale to adjust rectangle sizes visually
                      .sort((a, b) => b.value - a.value);            

                    const treemap = d3.treemap()
                                      .size([width, height])
                                      .padding(4);

                    treemap(root);

                    const color = d3.scaleOrdinal()
                                    .domain(["Category1", "Category2", "Category3", "Category4", "Category5", "Category6", "Category7"])
                                    .range(["#2B3BB0", "#85294E", "#1A4641", "#27605C", "#F08B32", "#4C362C", "#6A4D42"]);

                    const nodes = svg.selectAll("g")
                                     .data(root.leaves())
                                     .enter().append("g")
                                     .attr("transform", d => `translate(${d.x0},${d.y0})`);

                    nodes.append("rect")
                         .attr("class", "node")
                         .attr("width", d => d.x1 - d.x0)
                         .attr("height", d => d.y1 - d.y0)
                         .attr("fill", d => color(d.data.name))
                         .on("mouseover", function (event, d) {
                              tooltip
                                .style("display", "block")
                                .html(
                                  `<strong>${event.data.name}</strong><br>Value: ${event.data.value}`
                                )
                                .style("left", `${d3.event.pageX + 10}px`) // Position tooltip relative to mouse
                                .style("top", `${d3.event.pageY - 10}px`);
                         })
                         .on("mouseout", () => tooltip.style("display", "none"))
                         .on("click", function(event, d) {
                                if (event.data.url) {
                                  window.location.href = event.data.url; // navigates to this detailed page
                                }
                        });     

                    nodes.append("text")
                         .attr("x", 5)
                         .attr("y", 20)
                         .attr("fill", "white")
                         .style("font-size", "12px")
                         .text(d => d.data.name);

                    nodes.append("text")
                         .attr("x", d => (d.x1 - d.x0) / 4)
                         .attr("y", d => (d.y1 - d.y0) / 1.5)
                         .attr("fill", "white")
                         .style("font-size", "12px")
                         .text(d => formatValues(d.data.value));
                }

                createTreemap(containerId, dataset);
            } catch (error) {
                console.error("JSON Parse Error:", error);
            }
        } else {
            console.error("Treemap data not found!");
        }
    }

    createTreeMapGraphs("consolidationData", "chart-consolidation");
    createTreeMapGraphs("nationalBudgetData", "chart-national-budget");
    createTreeMapGraphs("provincialBudgetData", "chart-provincial-budget");

    window.addEventListener("resize", () => {
        createTreeMapGraphs("consolidationData", "chart-consolidation");
        createTreeMapGraphs("nationalBudgetData", "chart-national-budget");
        createTreeMapGraphs("provincialBudgetData", "chart-provincial-budget");
    });

});

function formatValues(value) {
    if (value >= 1e12) {
        return `R ${(value / 1e12).toFixed(2).toLocaleString()} trillion`; // Trillions
    } else if (value >= 1e9) {
        return `R ${(value / 1e9).toFixed(2).toLocaleString()} billion`; // Billions
    } else if (value >= 1e6) {
        return `R ${(value / 1e6).toFixed(2).toLocaleString()} million`; // million
    } else if (value >= 1e3) {
        return `R ${(value / 1e3).toFixed(2).toLocaleString()} thousand`; // thousand
    } else {
        return 'R ' + value.toLocaleString(); // Default formatting
    }
}