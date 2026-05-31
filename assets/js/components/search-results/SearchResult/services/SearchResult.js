import React from 'react';
import getLandingResults from './getLandingResults.js';
import getFacetResults from './getFacetResults.js';
import SearchPage from './../presentation/SearchPage.jsx';

const VALID_TABS = ['all', 'departments', 'datasets'];

const normaliseTab = view => (VALID_TABS.includes(view) ? view : 'all');

export default class SearchPageContainer extends React.Component {
  constructor(props) {
    super(props);
    const { view } = this.props;
    const tab = normaliseTab(view || 'all');

    this.state = {
      tab,
      items: {},
      loading: true,
      error: false,
      loadingPage: false,
      page: 1,
    };

    this.static = {
      currentFetch: null,
    };

    this.events = {
      updateTab: this.updateTab.bind(this),
      addPage: this.addPage.bind(this),
    };
  }

  componentWillMount() {
    const { search: phrase, view = 'all', year } = this.props;
    const tab = normaliseTab(view);

    this.setState({
      loading: true,
      tab,
      error: false,
    });

    return this.getNewResults(() => this.getTabResults(phrase, tab, year));
  }


  getTabResults(phrase, tab, year, start = 0) {
    if (tab === 'all') {
      return getLandingResults(phrase, year);
    }

    return getFacetResults(phrase, tab, start, year);
  }


  getNewResults(callback) {
    if (this.static.currentFetch && !this.static.currentFetch.token.cancelled) {
      this.static.currentFetch.token.cancel();
    }

    this.static.currentFetch = callback();

    this.static.currentFetch.request
      .then(items => this.setState({
        items,
        error: false,
        loading: false,
      }))
      .catch((err) => {
        this.setState({
          error: true,
          loading: false,
        });
        console.warn(err);
      });
  }


  addPage() {
    const { tab, page, items } = this.state;
    const { search: phrase, year } = this.props;

    if (this.static.currentFetch && !this.static.currentFetch.token.cancelled) {
      this.static.currentFetch.token.cancel();
    }

    this.static.currentFetch = this.getTabResults(phrase, tab, year, page * 5);

    this.static.currentFetch.request
      .then((data) => {
        const mergedTab = {
          ...items[tab],
          items: [
            ...(items[tab].items || []),
            ...(data[tab].items || []),
          ],
        };

        this.setState({
          page: page + 1,
          items: {
            ...items,
            [tab]: mergedTab,
            count: data.count,
          },
        });
      })
      .catch((err) => {
        this.setState({
          error: true,
          loading: false,
        });
        console.warn(err);
      });
  }


  updateTab(newTab, scroll) {
    const { search: phrase, year, root } = this.props;
    const nextTab = normaliseTab(newTab);

    this.setState({
      tab: nextTab,
      loading: true,
      page: 1,
      items: null,
      error: false,
    });

    if (scroll) {
      root.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    const baseUrl = `/${year}/search-result?search=${encodeURI(phrase)}`;
    history.replaceState({}, '', nextTab === 'all' ? baseUrl : `${baseUrl}&view=${nextTab}`);

    return this.getNewResults(() => this.getTabResults(phrase, nextTab, year));
  }


  render() {
    const { search: phrase, year } = this.props;
    const { tab, items: response, loading, loadingPage, page, error } = this.state;

    const { updateTab, addPage } = this.events;

    return React.createElement(
      SearchPage,
      {
        phrase,
        page,
        response,
        tab,
        year,
        updateTab,
        loading,
        addPage,
        loadingPage,
        error,
      },
    );
  }
}
