import fetchWrapper from './../../../../utilities/js/helpers/fetchWrapper.js';
import highlightResults from './highlightResults.js';
import createPromiseToken from './../../../../utilities/js/helpers/createPromiseToken.js';
import parseStaticResponse from './parseStaticResponse.js';

const createEmptyResponse = () => ({
  count: 0,
  items: {
    departments: { count: 0, items: [], otherYears: [] },
    datasets: { count: 0, items: [], otherYears: [] },
    videos: null,
    glossary: null,
  },
});

export default function getLandingResults(phrase, year) {
  if (!phrase || phrase.trim() === '') {
    return createPromiseToken(Promise.resolve(createEmptyResponse()));
  }

  const request = new Promise((resolve, reject) => {
    const searchRequest = fetchWrapper(
      `/api/v1/search/?q=${encodeURIComponent(phrase)}&year=${encodeURIComponent(year)}`,
    );
    const staticRequest = fetchWrapper('/json/static-search.json')
      .catch(() => ({ videos: [], glossary: {} }));

    Promise.all([searchRequest, staticRequest])
      .then(([searchResults, staticContent]) => {
        const departments = highlightResults(searchResults.items.departments, phrase);
        const datasets = highlightResults(searchResults.items.datasets, phrase);
        const { videos, glossary } = parseStaticResponse(
          phrase,
          staticContent.videos || [],
          staticContent.glossary || {},
        );
        const staticCount = [videos, glossary].filter(Boolean).length;

        resolve(
          {
            items: {
              departments: {
                ...departments,
              },
              datasets,
              videos,
              glossary,
            },
            count: departments.count + datasets.count + staticCount,
          },
        );
      })
      .catch(reject);
  });

  return createPromiseToken(request);
}
