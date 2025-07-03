
let tooltip;
document.addEventListener("DOMContentLoaded", function () {
    let historyData = document.getElementById("historyBar");
    let dataset;

    if (historyData) {
        try {
            dataset = JSON.parse(historyData.textContent);               

            dataset.children = dataset.children.map(d => {
                let year = parseInt(d.Name || d.name); // Convert year to an integer
                return {
                    year: formatFinancialYear(year), // Convert year to "YYYY-YY" format
                    value: d.Count || d.value,
                    budgetPhase: d.BudgetPhase
                };
            });                

            dataset.children.forEach(d => {
                d.formatted_value = formatValue(d.value); // Format values
            });                

            populateBudgetPhase(dataset.children)

            // Set dimensions
            const margin = { top: 30, right: 50, bottom: 50, left: 80 },
                width = 700 - margin.left - margin.right,
                height = 400 - margin.top - margin.bottom;

            // Create the SVG container
            const svg = d3.select("#historyBarGraph")
                .attr("width", width + margin.left + margin.right)
                .attr("height", height + margin.top + margin.bottom)
                .append("g")
                .attr("transform", `translate(${margin.left}, ${margin.top})`);

            // Create scales
            const xScale = d3.scaleBand()
                .domain(dataset.children.map(d => d.year))
                .range([0, width])
                .padding(0.5); 

            const yScale = d3.scaleLinear()
                .domain([0, d3.max(dataset.children, d => d.value) * 1.1])
                .nice()
                .range([height, 0]);

            // Add X axis
            svg.append("g")
                .attr("class", "axis x-axis")
                .attr("transform", `translate(0, ${height})`)
                .call(d3.axisBottom(xScale));

            // Add Y axis with correct "B" for billions
            svg.append("g")
                .attr("class", "axis y-axis")
                .call(d3.axisLeft(yScale).tickFormat(d => formatYAxis(d)));

            // Tooltip
            const tooltip = d3.select(".tooltip");

            // Create bars
            svg
              .selectAll(".barChart")
              .data(dataset.children)
              .enter()
              .append("rect")
              .attr("class", "barChart")
              .attr("x", (d) => xScale(d.year))
              .attr("y", (d) => yScale(d.value))
              .attr("width", xScale.bandwidth())
              .attr("height", (d) => height - yScale(d.value))
              .attr("fill", "steelblue")
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
                    `<strong>${event.budgetPhase}</strong><br>Value: ${event.value}<br>Year: ${event.year}`
                  ) // Format value in tooltip
                  .style("left", `${d3.event.pageX + 10}px`)
                  .style("top", `${d3.event.pageY - 10}px`);
              })
              .on("mouseout", () => {
                // Hide tooltip on mouseout
                tooltip.style("display", "none");
              });

        } catch (error) {
            console.error("JSON Parse Error:", error);
            dataset = { name: "root", children: [{ name: "No Data", value: 0 }] };
        }
    } else {
        console.error("Treemap data not found!");
        dataset = { name: "root", children: [{ name: "No Data", value: 0 }] };
    }
});

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

// ✅ Tooltip Formatter
function formatValue(value) {
    return formatYAxis(value);
}

//Function to Format Year as "YYYY-YY"
function formatFinancialYear(year) {
    if(!year || isNaN(year)) return year;
    return `${year}-${(year + 1).toString().slice(-2)}`;
}

function populateBudgetPhase(dataset) {
    const tableBody = document.querySelector("#expenditureTable tbody");

    // Loop through items.real and create table rows
    dataset.forEach(item => {
        const row = document.createElement("tr");

        // Create financial year cell
        const yearCell = document.createElement("td");
        yearCell.classList.add("ExpenditureSection-cell");
        yearCell.textContent = item.year;
        row.appendChild(yearCell);

        // Create phase cell
        const phaseCell = document.createElement("td");
        phaseCell.classList.add("ExpenditureSection-cell");
        phaseCell.textContent = item.budgetPhase;
        row.appendChild(phaseCell);

        // Append row to table body
        tableBody.appendChild(row);
    });
}
