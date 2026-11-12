import React from 'react';
import ReactDOM from 'react-dom';

import ResponsiveChart from '../../components/universal/ResponsiveChart/index.jsx';


const graphUrl = '/api/division-revenue/graphs/';
const chartIds = {
  spheres: 'embed-allocation-of-equitable-share-by-sphere',
  provinces: 'embed-allocation-of-equitable-share-to-provinces',
  municipalities: 'embed-allocation-of-equitable-share-to-municipalities',
};


const chartItems = rows => rows.reduce((result, row) => ({
  ...result,
  [row.label]: [row.amount_rands],
}), {});


const renderChart = (node, items) => {
  ReactDOM.render(
    <ResponsiveChart items={items} type="bar" />,
    node,
  );
};


const clearAndShow = (node, message) => {
  ReactDOM.unmountComponentAtNode(node);
  node.textContent = message;
};


const addSelect = (container, labelText, choices, onChange) => {
  const control = document.createElement('label');
  control.className = 'DivisionRevenueChart-filter';
  control.appendChild(document.createTextNode(labelText));
  const select = document.createElement('select');
  choices.forEach(({value, label}) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    select.appendChild(option);
  });
  select.addEventListener('change', event => onChange(event.target.value));
  control.appendChild(select);
  container.appendChild(control);
  return select;
};


const renderMunicipalities = (container, rows) => {
  if (!rows.length) {
    clearAndShow(container, 'Municipal allocations are not available for this bill.');
    return;
  }

  container.innerHTML = '';
  const controls = document.createElement('div');
  controls.className = 'DivisionRevenueChart-filters';
  const chart = document.createElement('div');
  container.appendChild(controls);
  container.appendChild(chart);

  const provinces = [...new Set(rows.map(row => row.province))].sort();
  const categories = [...new Set(rows.map(row => row.category))].sort();
  let province = provinces[0];
  let category = '';
  const update = () => {
    const topMunicipalities = rows
      .filter(row => row.province === province && (!category || row.category === category))
      .sort((first, second) => second.amount_rands - first.amount_rands)
      .slice(0, 10);
    const items = topMunicipalities.reduce((result, row) => ({
      ...result,
      [`${row.name} — ${row.category_label}`]: [row.amount_rands],
    }), {});
    renderChart(chart, items);
  };

  addSelect(
    controls,
    'Province',
    provinces.map(value => ({value, label: value})),
    (value) => { province = value; update(); },
  );
  addSelect(
    controls,
    'Municipality type',
    [{value: '', label: 'All types'}].concat(categories.map(value => ({
      value,
      label: rows.find(row => row.category === value).category_label,
    }))),
    (value) => { category = value; update(); },
  );
  update();
};


const initialise = () => {
  const containers = Object.keys(chartIds).reduce((result, key) => ({
    ...result,
    [key]: document.getElementById(chartIds[key]),
  }), {});
  if (!Object.values(containers).some(Boolean)) return;

  Object.values(containers).filter(Boolean).forEach(node => clearAndShow(node, 'Loading chart...'));
  fetch(graphUrl)
    .then(response => {
      if (!response.ok) throw new Error(`Graph data request failed (${response.status})`);
      return response.json();
    })
    .then((data) => {
      if (containers.spheres) renderChart(containers.spheres, chartItems(data.allocation_by_sphere));
      if (containers.provinces) renderChart(containers.provinces, chartItems(data.allocation_to_provinces));
      if (containers.municipalities) renderMunicipalities(containers.municipalities, data.allocation_to_municipalities);
    })
    .catch((error) => {
      console.error('Unable to load Division of Revenue graphs:', error);
      Object.values(containers).filter(Boolean).forEach(node => (
        clearAndShow(node, 'The Division of Revenue chart data could not be loaded.')
      ));
    });
};


if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initialise);
} else {
  initialise();
}
