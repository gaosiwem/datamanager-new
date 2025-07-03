
let tooltip;
document.addEventListener("DOMContentLoaded", function () {
    let chartData = document.getElementById("budgetActualData");
    let dataset;

    try {
        dataset = JSON.parse(chartData.textContent);
        if (!dataset) {
            throw new Error("Invalid data structure");
        }

        const svgId = `budgetActualChart`;
        const legendId = `legend`;

        const categories = [...new Set(dataset.children.map(d => d.name))];
        const subcategories = [...new Set(dataset.children.map(d => d.budgetPhase.trim()))];

        dataset.children.forEach(d => {
                d.formatted_value = formatValue(d.value); // Format values
            });

        const colorScale = d3.scaleOrdinal()
            .domain(subcategories)
            .range(["#F2DAE0","#E4B5C0", "#D392A1","#C46D83"]);

        function createChart() {
            const width = window.innerWidth * 0.45 // Adjusted for two charts
            const height = window.innerHeight * 0.6;
            const margin = { top: 50, right: 50, bottom: 60, left: 100 };

            d3.select(`#${svgId}`).selectAll("*").remove();

            const svg = d3.select(`#${svgId}`)
                .attr("width", width)
                .attr("height", height);

            // 🔹 Uniform spacing between groupings and bars
            const x0 = d3.scaleBand()
                .domain(categories)
                .range([margin.left, width - margin.right])
                .padding(0.15); // 🔹 Keeps consistent spacing

            const x1 = d3.scaleBand()
                .domain(subcategories)
                .range([0, x0.bandwidth()])
                .padding(0.1); // 🔹 Ensures consistent subcategory bar width

            const y = d3.scaleLinear()
                .domain([0, d3.max(dataset.children, d => d.value)])
                .nice()
                .range([height - margin.bottom, margin.top]);

            const chartGroup = svg.append("g");

            // ✅ X Axis
            chartGroup.append("g")
                .attr("transform", `translate(0, ${height - margin.bottom})`)
                .call(d3.axisBottom(x0))
                .attr("class", "axis-label");

            // ✅ Y Axis with "B" for billions

            chartGroup.append("g")
                .attr("transform", `translate(${margin.left}, 0)`)
                .call(d3.axisLeft(y).tickFormat(d => formatYAxis(d)))
                .attr("class", "axis-label");

            const tooltip = d3.select(".tooltip");

            // ✅ Create grouped bars (ensuring uniform formatting)
            const categoryGroups = chartGroup.selectAll(".category-group")
                .data(categories)
                .enter().append("g")
                .attr("transform", d => `translate(${x0(d)},0)`);

            categoryGroups
              .selectAll(".bar")
              .data((d) => dataset.children.filter((item) => item.name === d))
              .enter()
              .append("rect")
              .attr("class", "bar")
              .attr("x", (d) => x1(d.budgetPhase.trim()))
              .attr("y", (d) => y(d.value))
              .attr("width", x1.bandwidth())
              .attr("height", (d) => height - margin.bottom - y(d.value))
              .attr("fill", (d) => colorScale(d.budgetPhase.trim()))
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
                    `<strong>${event.budgetPhase}</strong><br>Value: ${event.value}<br>Year: ${event.name}`
                  ) // Format value in tooltip
                  .style("left", `${d3.event.pageX + 10}px`)
                  .style("top", `${d3.event.pageY - 10}px`);
              })
              .on("mouseout", () => {
                // Hide tooltip on mouseout
                tooltip.style("display", "none");
              });

                
            // ✅ Updated legend
            const legendContainer = d3.select(`#${legendId}`).html("");

            subcategories.forEach(sub => {
                const legendItem = legendContainer.append("div").attr("class", "legend");
                legendItem.append("div")
                    .attr("class", "legend-box")
                    .style("background-color", colorScale(sub));
                legendItem.append("span").text(sub);
            });
        }

        createChart();
        window.addEventListener("resize", createChart);
    }
    catch (error) {
        console.error("JSON Parse Error:", error);
    }
});

// ✅ Custom Y-axis Formatter (Shows "B" for Billions)
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
        return 'R ' + value.toLocaleString(); // Default formatting
    }
}

        // ✅ Custom Y-axis Formatter (Shows "B" for Billions)
function formatYAxis(value) {
    if (value >= 1e12) {
        return `R ${(value / 1e12).toFixed(1).toLocaleString()} trillion`; // Trillions
    } else if (value >= 1e9) {
        return `R ${(value / 1e9).toFixed(1).toLocaleString()} billion`; // Billions
    } else if (value >= 1e6) {
        return `R ${(value / 1e6).toFixed(1).toLocaleString()} million`; // million
    } else if (value >= 1e3) {
        return `R ${(value / 1e3).toFixed(1).toLocaleString()} thousand`; // thousand
    } else {
        return "R" + value.toLocaleString(); // Default formatting
    }
}
