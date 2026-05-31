document.addEventListener("DOMContentLoaded", function () {
    const PHASE_METADATA = {
        "Main appropriation": { rank: 1, color: "#ad3c64" },
        "Adjusted appropriation": { rank: 2, color: "#ee9f31" },
        "Final Appropriation": { rank: 3, color: "#ee9f31" },
        "Audit Outcome": { rank: 4, color: "#7bb344" },
        "Audited Outcome": { rank: 5, color: "#7bb344" },
    };

    const chartDataNode = document.getElementById("budgetActualData");
    const svgId = "budgetActualChart";
    const legendId = "legend";
    const tooltipSelector = ".ExpenditurePhaseSection-item--right .tooltip";
    const chartNode = d3.select(`#${svgId}`).node();
    const chartCard = chartNode ? chartNode.closest(".ExpenditureChartCard") : null;
    const chartContainer = chartNode ? chartNode.parentElement : null;
    let lastMeasuredWidth = 0;

    if (!chartDataNode || !chartNode || !chartCard || !chartContainer) {
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

    function formatGraphValue(value) {
        return formatValue(value);
    }

    function normalisePhase(phase) {
        return String(phase || "").trim();
    }

    function getPhaseMeta(phase) {
        return PHASE_METADATA[phase] || { rank: 99, color: "#7d7d7d" };
    }

    function renderEmptyState(message, hint) {
        const width = getChartWidth();
        const height = 280;
        const svg = d3.select(`#${svgId}`);

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

    function getChartWidth() {
        const containerWidth = chartContainer.getBoundingClientRect().width;
        const cardWidth = Math.max(chartCard.getBoundingClientRect().width - 32, 0);
        const measuredWidth = Math.max(containerWidth, cardWidth);

        return Math.max(Math.round(measuredWidth), 320);
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
                    compactValue: formatGraphValue(value),
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

    function renderLegend(phases) {
        const legend = d3.select(`#${legendId}`)
            .html("")
            .attr("class", "ExpenditureChartLegend");

        phases.forEach((phase) => {
            const legendItem = legend.append("div").attr("class", "ExpenditureLegendItem");

            legendItem.append("div")
                .attr("class", "ExpenditureLegendSwatch")
                .style("background-color", getPhaseMeta(phase).color);

            legendItem.append("span").text(phase);
        });
    }

    function createChart(data) {
        if (!data.length) {
            renderEmptyState("No expenditure data available", "Please try again later.");
            return;
        }

        const svg = d3.select(`#${svgId}`);
        const tooltip = d3.select(tooltipSelector);
        const phases = [...new Set(data.map((item) => item.budgetPhase))]
            .sort((left, right) => getPhaseMeta(left).rank - getPhaseMeta(right).rank);
        const axisLabels = {};

        data.forEach((item) => {
            axisLabels[item.key] = item.yearLabel;
        });

        const width = getChartWidth();
        const height = width >= 960 ? 420 : width >= 700 ? 380 : 340;
        const margin = {
            top: 24,
            right: width >= 700 ? 20 : 14,
            bottom: 56,
            left: width >= 700 ? 124 : 104,
        };
        const innerWidth = width - margin.left - margin.right;
        const innerHeight = height - margin.top - margin.bottom;

        svg.selectAll("*").remove();
        svg
            .attr("width", width)
            .attr("height", height)
            .attr("viewBox", `0 0 ${width} ${height}`)
            .attr("preserveAspectRatio", "xMidYMid meet");

        const xScale = d3.scaleBand()
            .domain(data.map((item) => item.key))
            .range([0, innerWidth])
            .padding(width >= 700 ? 0.38 : 0.28);

        const yScale = d3.scaleLinear()
            .domain([0, (d3.max(data, (item) => item.value) || 0) * 1.12])
            .nice()
            .range([innerHeight, 0]);

        const chartGroup = svg.append("g")
            .attr("transform", `translate(${margin.left}, ${margin.top})`);

        chartGroup.append("g")
            .attr("class", "ExpenditureGrid")
            .call(
                d3.axisLeft(yScale)
                    .ticks(width >= 700 ? 5 : 4)
                    .tickSize(-innerWidth)
                    .tickFormat("")
            );

        chartGroup.append("g")
            .attr("class", "ExpenditureAxis ExpenditureAxis--y")
            .call(
                d3.axisLeft(yScale)
                    .ticks(width >= 700 ? 5 : 4)
                    .tickFormat((value) => formatGraphValue(value))
            );

        chartGroup.append("g")
            .attr("class", "ExpenditureAxis ExpenditureAxis--x")
            .attr("transform", `translate(0, ${innerHeight})`)
            .call(d3.axisBottom(xScale).tickFormat((key) => axisLabels[key]));

        const bars = chartGroup.selectAll(".ExpenditureBar")
            .data(data)
            .enter()
            .append("rect")
            .attr("class", "ExpenditureBar")
            .style("cursor", "pointer")
            .attr("fill", (item) => item.phaseColor)
            .attr("x", (item) => xScale(item.key))
            .attr("y", (item) => yScale(item.value))
            .attr("width", xScale.bandwidth())
            .attr("height", (item) => innerHeight - yScale(item.value))
            .attr("rx", 10)
            .attr("ry", 10)
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

        bars.raise();
        renderLegend(phases);
    }

    try {
        const dataset = JSON.parse(chartDataNode.textContent);
        const chartData = normaliseDataset(dataset);

        function scheduleChartRender() {
            const nextWidth = getChartWidth();

            if (d3.select(`#${svgId}`).attr("width") && nextWidth === lastMeasuredWidth) {
                return;
            }

            lastMeasuredWidth = nextWidth;
            createChart(chartData);
            window.requestAnimationFrame(function () {
                createChart(chartData);
            });
            window.setTimeout(function () {
                createChart(chartData);
            }, 180);
            window.setTimeout(function () {
                createChart(chartData);
            }, 420);
        }

        scheduleChartRender();
        window.addEventListener("resize", scheduleChartRender);

        if (window.ResizeObserver) {
            new ResizeObserver(scheduleChartRender).observe(chartCard);
        }
    } catch (error) {
        console.error("Budget actual chart parse error:", error);
        renderEmptyState("Unable to load chart", "Please try again in a moment.");
    }
});
