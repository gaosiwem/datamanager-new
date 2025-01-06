import $ from 'jquery';
import { HorizontalBarChart } from 'vulekamali-visualisations/src/charts/bar/horizontal-bar-chart/horizontal-bar-chart';

const allocationBySphereId = "embed-allocation-of-equitable-share-by-sphere";
const allocationToProvincesId = "embed-allocation-of-equitable-share-to-provinces";
const allocationToMunicipalitiesId = "embed-allocation-of-equitable-share-to-municipalities";

const sphereColor = {
  "national": "#377ac6",
  "provincial": "#aad029",
  "local": "#eb164d",
};


const sphereLabel = {
  "national": "National",
  "provincial": "Provincial",
  "local": "Local",
};
const sphereUrl = {
  "national": "/2020-21/departments",
  "provincial": "#embed-allocation-of-equitable-share-to-provinces",
  "local": "#embed-allocation-of-equitable-share-to-municipalities",
};

const municipalityTypeLabel = {
  "local": "Local municipalities",
  "district": "District municipalities",
  "metro": "Metropolitan municipalities",
};

$(document).ready(function() {
  const sphereChartContainer = $("#" + allocationBySphereId);
  if (sphereChartContainer.length) {
    initAllocationBySphere(sphereChartContainer);
  }
  const provinceChartContainer = $("#" + allocationToProvincesId);
  if (provinceChartContainer.length) {
    initAllocationsToProvinces(provinceChartContainer);
  }
  const municipalityChartContainer = $("#" + allocationToMunicipalitiesId);
  if (municipalityChartContainer.length) {
    initAllocationsToMunicipalities(municipalityChartContainer);
  }
});

function initAllocationBySphere(sphereChartContainer) {
  sphereChartContainer.text("Loading...");
  const ckanUrl = $("body").data("ckan-url");

  getDataset(ckanUrl)
    .then(function(data) {
      const datasets = data.result.results;
      sortDatasetsFinYear(datasets);
      const latestAllocations = getLatestAllocations(datasets);
      if (latestAllocations !== null) {
        return getAllocationBySpherePromise(ckanUrl, latestAllocations);
      } else {
        throw "Data resource not found";
      }
    })
    .then(function(data) {
      drawAllocationBySphereChart(data.result.records);
      $(`#${allocationBySphereId}`).append(`Source: ${getSourceLink(this.dataset)}`);
    })
    .fail(function(jqXHR) {
      console.error("Error getting data for chart:", jqXHR);
      sphereChartContainer.text("Error getting data for chart");
    });
};

function getDataset(ckanUrl) {
  const packageSearchUrl = `${ckanUrl}/api/action/package_search`;
  const searchParams = {
    "q": "",
    "fq": '+organization:"national-treasury"' +
      'groups:"division-of-revenue-bills"',
  };
  return $.get(packageSearchUrl, searchParams);
}

function getSourceLink(dataset) {
  const url = `/datasets/${dataset.groups[0].name}/${dataset.name}`;
  return `<a href="${url}">${dataset.title}</a>`;
}

/**
 * Returns {resource: ..., dataset: ...} or null if none found.
 */
function getLatestAllocations(datasets) {
  let allocationsResource = null;
  let allocationsDataset = null;
  datasets.forEach(function (dataset) {
    dataset.resources.forEach(function (resource) {
      if (resource.name === "Allocation of Equitable Share") {
        allocationsResource = resource;
        allocationsDataset = dataset;
      }
    });
  });

  if (allocationsResource) {
    return {
      dataset: allocationsDataset,
      resource: allocationsResource,
    };
  } else {
    return null;
  }
}

function sortDatasetsFinYear(datasets) {
  datasets.sort((a, b) => {
    const yearA = a.financial_year.length && a.financial_year[0] || null;
    const yearB = b.financial_year.length && b.financial_year[0] || null;
    if (yearA < yearB)
      return -1;
    else if (yearA === yearB)
      return 0;
    else
      return 1;
  });
}

function getAllocationBySpherePromise(ckanUrl, allocations) {
  const sqlQuery = `\
SELECT sum(amount_rand_thousand) as amount_rand_thousand, sphere \
FROM "${allocations.resource.id}" \
GROUP BY sphere \
ORDER BY sphere`;
  const data = {"sql": sqlQuery};
  const queryUrl = `${ckanUrl}/api/3/action/datastore_search_sql`;
  return $.get({url: queryUrl, data: data, context: allocations});
}

function drawAllocationBySphereChart(items) {
  const chartItems = items.map(item => (
    {
      "Sphere": sphereLabel[item.sphere],
      "color": sphereColor[item.sphere],
      "Allocation": parseFloat(item.amount_rand_thousand) * 1000,
      "url": sphereUrl[item.sphere],
    }
  ));

  new HorizontalBarChart()
    .select(allocationBySphereId)
    .data(chartItems)
    .nameKey("Sphere")
    .valueKey("Allocation")
    .xAxisUnit('B')
    .barUnit('B')
    .urlKey("url")
    .reDraw();
}

function initAllocationsToProvinces(container) {
  container.text("Loading...");
  const ckanUrl = $("body").data("ckan-url");

  getDataset(ckanUrl)
    .then(function(data) {
      const datasets = data.result.results;
      sortDatasetsFinYear(datasets);
      const latestAllocations = getLatestAllocations(datasets);
      if (latestAllocations !== null) {
        return getAllocationsToProvincesPromise(ckanUrl, latestAllocations);
      } else {
        throw "Data resource not found";
      }
    })
    .then(function(data) {
      drawAllocationsToProvincesChart(data.result.records);
      $(`#${allocationToProvincesId}`).append(`Source: ${getSourceLink(this.dataset)}`);
    })
    .fail(function(jqXHR) {
      console.error("Error getting data for chart:", jqXHR);
      container.text("Error getting data for chart");
    });
};

function getAllocationsToProvincesPromise(ckanUrl, allocations) {
  const sqlQuery = `\
SELECT sum(amount_rand_thousand) as amount_rand_thousand, geo_code, geo_name \
FROM "${allocations.resource.id}" \
WHERE "sphere" = 'provincial' \
GROUP BY geo_code, geo_name`;
  const data = {"sql": sqlQuery};
  const queryUrl = `${ckanUrl}/api/3/action/datastore_search_sql`;
  return $.get({url: queryUrl, data: data, context: allocations});
}

function drawAllocationsToProvincesChart(items) {
  const chartItems = items.map(item => (
    {
      "Province": item.geo_name,
      "color": sphereColor["provincial"],
      "Allocation": parseFloat(item.amount_rand_thousand) * 1000,
      "url": "/2020-21/departments",
    }
  ));

  new HorizontalBarChart()
    .select(allocationToProvincesId)
    .data(chartItems)
    .nameKey("Province")
    .valueKey("Allocation")
    .xAxisUnit('B')
    .barUnit('B')
    .urlKey("url")
    .reDraw();
}

function initAllocationsToMunicipalities(container) {
  container.text("Loading...");
  const ckanUrl = $("body").data("ckan-url");

  getDataset(ckanUrl)
    .then(function(data) {
      const datasets = data.result.results;
      sortDatasetsFinYear(datasets);
      const latestAllocations = getLatestAllocations(datasets);
      if (latestAllocations !== null) {
        return getAllocationsToMunicipalitiesPromise(ckanUrl, latestAllocations);
      } else {
        throw "Data resource not found";
      }
    })
    .then(function(data) {
      drawAllocationsToMunicipalitiesChart(data.result.records);
      $(`#${allocationToMunicipalitiesId}`).append(`Source: ${getSourceLink(this.dataset)}`);
    })
    .fail(function(jqXHR) {
      console.error("Error getting data for chart:", jqXHR);
      container.text("Error getting data for chart");
    });
};

function getAllocationsToMunicipalitiesPromise(ckanUrl, allocations) {
  const sqlQuery = `\
SELECT sum(amount_rand_thousand) as amount_rand_thousand, geo_code, geo_name, \
municipality_type, parent_name \
FROM "${allocations.resource.id}" \
WHERE "sphere" = 'local' \
GROUP BY geo_code, geo_name, municipality_type, parent_name`;
  const data = {"sql": sqlQuery};
  const queryUrl = `${ckanUrl}/api/3/action/datastore_search_sql`;
  return $.get({url: queryUrl, data: data, context: allocations});
}

function drawAllocationsToMunicipalitiesChart(items) {
  const chartItems = items.map(item => (
    {
      "Municipality type": municipalityTypeLabel[item.municipality_type],
      "Municipality": item.geo_name,
      "Province": item.parent_name,
      "color": sphereColor["local"],
      "Allocation": parseFloat(item.amount_rand_thousand) * 1000,
      "url": muniUrl(item),
    }
  ));

  new HorizontalBarChart()
    .select(allocationToMunicipalitiesId)
    .data(chartItems)
    .nameKey("Municipality")
    .valueKey("Allocation")
    .filterKey("Province")
    .filterLabel("Select province:")
    .groupKey("Municipality type")
    .xAxisUnit('M')
    .barUnit('M')
    .urlKey("url")
    .reDraw();
}

function muniUrl(item) {
  
  let slug;
  if (item.municipality_type === "district")
    slug = `district-${item.geo_code}`;
  else
    slug = `municipality-${item.geo_code}`;
  return `https://municipalmoney.gov.za/profiles/${slug}`;
}
