import fetchWrapper from './../../../../utilities/js/helpers/fetchWrapper.js';
import highlightResults from './highlightResults.js';
import createPromiseToken from './../../../../utilities/js/helpers/createPromiseToken.js';

export default function getFacetResults(phrase, facet, start = 0, year) {
  if (!phrase || phrase.trim() === '') {
    return createPromiseToken(Promise.resolve({ count: 0, [facet]: { count: 0, items: [] } }));
  }

  const request = new Promise((resolve, reject) => {
    const url = `/api/v1/search/facet/?q=${encodeURIComponent(phrase)}&year=${encodeURIComponent(year)}&view=${encodeURIComponent(facet)}&start=${start}`;
    const innerRequest = fetchWrapper(url);

    innerRequest
      .then((data) => {
        const output = highlightResults(data[facet], phrase);

        resolve({
          count: output.count,
          [facet]: output,
        });
      })
      .catch(reject);
  });

  return createPromiseToken(request);
}
