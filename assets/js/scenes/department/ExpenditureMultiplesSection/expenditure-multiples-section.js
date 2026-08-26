document.addEventListener("DOMContentLoaded", function () {
    const PHASE_METADATA = {
        "Main appropriation": { rank: 1, color: "#ad3c64" },
        "Adjusted appropriation": { rank: 2, color: "#ee9f31" },
        "Final Appropriation": { rank: 3, color: "#ee9f31" },
        "Revised estimate": { rank: 4, color: "#3b82b6" },
        "Audit Outcome": { rank: 5, color: "#7bb344" },
        "Audited Outcome": { rank: 5, color: "#7bb344" },
        "Audited outcome": { rank: 5, color: "#7bb344" },
    };

    const chartDataNode = document.getElementById("chartData");
    const cards = Array.from(
        document.querySelectorAll(".ExpenditureMultiplesSectionContent .ExpenditureMultiplesChartCard, .ExpenditureMultiplesSectionContent .Card")
    );

    if (!chartDataNode || !cards.length) {
        return;
    }

    function formatFinancialYear(yearValue) {
        const year = parseInt(yearValue, 10);

        if (Number.isNaN(year)) {
            return String(yearValue || "");
        }

        return `${year}-${(year + 1).toString().slice(-2)}`;
    }

    function formatValue(value) {
        const numericValue = Number(value);
        const absoluteValue = Math.abs(numericValue);

        if (absoluteValue >= 1e12) {
            return `R ${Math.round(numericValue / 1e12).toLocaleString()} trillion`;
        }

        if (absoluteValue >= 1e9) {
            return `R ${Math.round(numericValue / 1e9).toLocaleString()} billion`;
        }

        if (absoluteValue >= 1e6) {
            return `R ${Math.round(numericValue / 1e6).toLocaleString()} million`;
        }

        if (absoluteValue >= 1e3) {
            return `R ${Math.round(numericValue / 1e3).toLocaleString()} thousand`;
        }

        return `R ${Math.round(numericValue).toLocaleString()}`;
    }

    function normalisePhase(phase) {
        return String(phase || "").trim();
    }

    function getPhaseMeta(phase) {
        return PHASE_METADATA[phase] || { rank: 99, color: "#7d7d7d" };
    }

    function normaliseDataset(rawDataset) {
        return (rawDataset.children || [])
            .map((item, index) => {
                const rawYear = item.name || item.Name;
                const year = parseInt(rawYear, 10);
                const value = Number(item.value || item.Count || 0);
                const budgetPhase = normalisePhase(item.budgetPhase || item.BudgetPhase);
                const phaseMeta = getPhaseMeta(budgetPhase);

                return {
                    key: `${rawYear}-${budgetPhase}-${index}`,
                    year: Number.isNaN(year) ? null : year,
                    yearLabel: formatFinancialYear(rawYear),
                    value,
                    budgetPhase,
                    phaseRank: phaseMeta.rank,
                    phaseColor: phaseMeta.color,
                    formattedValue: formatValue(value),
                };
            })
            .filter((item) => item.value >= 0)
            .sort((left, right) => {
                if (left.year !== right.year) {
                    return (left.year || 0) - (right.year || 0);
                }

                return left.phaseRank - right.phaseRank;
            });
    }

    function renderLegend(legendNode, phases) {
        if (!legendNode) {
            return;
        }

        legendNode.innerHTML = "";

        phases.forEach((phase) => {
            const item = document.createElement("div");
            item.className = "ExpenditureMultiplesLegendItem";

            const swatch = document.createElement("span");
            swatch.className = "ExpenditureMultiplesLegendSwatch";
            swatch.style.backgroundColor = getPhaseMeta(phase).color;

            const label = document.createElement("span");
            label.textContent = phase;

            item.appendChild(swatch);
            item.appendChild(label);
            legendNode.appendChild(item);
        });
    }

    function renderEmptyState(svg, width, message, hint) {
        const height = 280;

        svg.selectAll("*").remove();
        svg
            .attr("viewBox", `0 0 ${width} ${height}`)
            .attr("width", width)
            .attr("height", height)
            .attr("preserveAspectRatio", "xMidYMid meet");

        svg.append("text")
            .attr("class", "ExpenditureEmptyState")
            .attr("x", width / 2)
            .attr("y", height / 2 - 10)
            .attr("text-anchor", "middle")
            .text(message);

        svg.append("text")
            .attr("class", "ExpenditureEmptyHint")
            .attr("x", width / 2)
            .attr("y", height / 2 + 18)
            .attr("text-anchor", "middle")
            .text(hint);
    }

    function createChartRenderer(card, chartIndex, data) {
        const svg = d3.select(`#budgetActualChart_${chartIndex + 1}`);
        const legendNode = document.getElementById(`legend_${chartIndex + 1}`);
        const tooltip = d3.select(card.querySelector(".tooltip"));
        const chartContainer = card.querySelector(".ExpenditureMultiplesChartCanvas") || card.querySelector(".chart-container");
        let lastMeasuredWidth = 0;

        if (svg.empty() || !chartContainer) {
            return null;
        }

        const phases = [...new Set(data.map((item) => item.budgetPhase))]
            .sort((left, right) => getPhaseMeta(left).rank - getPhaseMeta(right).rank);

        function getChartWidth() {
            const containerWidth = chartContainer.getBoundingClientRect().width;
            const cardWidth = Math.max(card.getBoundingClientRect().width - 32, 0);
            const measuredWidth = Math.max(containerWidth, cardWidth);

            return Math.max(Math.round(measuredWidth), 320);
        }

        function renderChart() {
            const width = getChartWidth();

            if (!data.length) {
                renderEmptyState(svg, width, "No programme expenditure data available", "Please try again later.");
                return;
            }

            const height = width >= 640 ? 320 : 280;
            const margin = {
                top: 18,
                right: width >= 640 ? 16 : 10,
                bottom: 54,
                left: width >= 640 ? 126 : 104,
            };
            const innerWidth = width - margin.left - margin.right;
            const innerHeight = height - margin.top - margin.bottom;
            const years = [...new Set(data.map((item) => item.yearLabel))];

            svg.selectAll("*").remove();
            svg
                .attr("viewBox", `0 0 ${width} ${height}`)
                .attr("width", width)
                .attr("height", height)
                .attr("preserveAspectRatio", "xMidYMid meet");

            const chartGroup = svg.append("g")
                .attr("transform", `translate(${margin.left}, ${margin.top})`);

            const x0 = d3.scaleBand()
                .domain(years)
                .range([0, innerWidth])
                .padding(width >= 640 ? 0.22 : 0.16);

            const x1 = d3.scaleBand()
                .domain(phases)
                .range([0, x0.bandwidth()])
                .padding(0.12);

            const y = d3.scaleLinear()
                .domain([0, (d3.max(data, (item) => item.value) || 0) * 1.12])
                .nice()
                .range([innerHeight, 0]);

            chartGroup.append("g")
                .attr("class", "ExpenditureGrid")
                .call(
                    d3.axisLeft(y)
                        .ticks(width >= 640 ? 4 : 3)
                        .tickSize(-innerWidth)
                        .tickFormat("")
                );

            chartGroup.append("g")
                .attr("class", "ExpenditureAxis ExpenditureAxis--y")
                .call(
                    d3.axisLeft(y)
                        .ticks(width >= 640 ? 4 : 3)
                        .tickFormat((tickValue) => formatValue(tickValue))
                );

            chartGroup.append("g")
                .attr("class", "ExpenditureAxis ExpenditureAxis--x")
                .attr("transform", `translate(0, ${innerHeight})`)
                .call(d3.axisBottom(x0));

            chartGroup.selectAll(".ExpenditureBar")
                .data(data)
                .enter()
                .append("rect")
                .attr("class", "ExpenditureBar")
                .style("cursor", "pointer")
                .attr("fill", (item) => item.phaseColor)
                .attr("x", (item) => x0(item.yearLabel) + x1(item.budgetPhase))
                .attr("y", (item) => y(item.value))
                .attr("width", x1.bandwidth())
                .attr("height", (item) => innerHeight - y(item.value))
                .attr("rx", 8)
                .attr("ry", 8)
                .on("mouseover", function (item) {
                    const chartBounds = chartContainer.getBoundingClientRect();
                    const pointerEvent = d3.event;
                    const left = pointerEvent.clientX - chartBounds.left + 12;
                    const top = pointerEvent.clientY - chartBounds.top - 12;

                    tooltip
                        .style("display", "block")
                        .html(
                            `<strong>${item.yearLabel}</strong><br>${item.budgetPhase}<br>${item.formattedValue}`
                        )
                        .style("left", `${left}px`)
                        .style("top", `${top}px`);
                })
                .on("mousemove", function () {
                    const chartBounds = chartContainer.getBoundingClientRect();
                    const pointerEvent = d3.event;
                    const left = pointerEvent.clientX - chartBounds.left + 12;
                    const top = pointerEvent.clientY - chartBounds.top - 12;

                    tooltip
                        .style("left", `${left}px`)
                        .style("top", `${top}px`);
                })
                .on("mouseout", function () {
                    tooltip.style("display", "none");
                });

            renderLegend(legendNode, phases);
        }

        function scheduleRender() {
            const nextWidth = getChartWidth();

            if (svg.attr("width") && nextWidth === lastMeasuredWidth) {
                return;
            }

            lastMeasuredWidth = nextWidth;
            renderChart();
            window.requestAnimationFrame(renderChart);
        }

        scheduleRender();

        if (window.ResizeObserver) {
            new ResizeObserver(scheduleRender).observe(card);
        }

        return scheduleRender;
    }

    let dataset;

    try {
        dataset = JSON.parse(chartDataNode.textContent);
    } catch (error) {
        console.error("Programme expenditure chart parse error:", error);
        return;
    }

    const renderers = cards
        .map((card, index) => createChartRenderer(card, index, normaliseDataset(dataset[index] || {})))
        .filter(Boolean);

    if (!renderers.length) {
        return;
    }

    window.addEventListener("resize", function () {
        window.setTimeout(function () {
            renderers.forEach((render) => render());
        }, 120);
    });
});
