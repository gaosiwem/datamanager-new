import React, { Component } from "react";
import ReactDOM from "react-dom";
import {
  FormControl,
  InputLabel,
  TextField,
  Select,
  MenuItem,
  Chip,
  Button,
  CircularProgress,
} from "@material-ui/core";
import fetchWrapper from "../../utilities/js/helpers/fetchWrapper";
import debounce from "lodash.debounce";
import slugify from "slugify";
import "../../../scss/components/public-entity-budgets/index.scss";

const rootRelativePath = (path) => {
  if (!path) return "";
  return `/${String(path).replace(/^\/+/, "")}`;
};

/**
 * Card-based list view for Public Entities.
 * Uses existing backend response shape:
 *   { count, results: { items: [...], facets: { department_name: [...] } } }
 */
class PublicEntityCardList extends Component {
  constructor(props) {
    super(props);

    this.abortController = null;

    this.state = {
      // Data
      rows: [],
      totalCount: 0,
      rowsPerPage: 10,
      currentPage: 0,

      // Facets
      departments: [],

      // Filters
      selectedFilters: {},

      // UI state
      isLoading: false,
      hasLoadedOnce: false,
      downloadUrl: "",

      // Sort (client-side)
      sortKey: "name",
      sortDir: "asc",
    };

    this.debouncedFilterChange = debounce(this.applyFilterChange, 300);
  }

  componentDidMount() {
    window.addEventListener("popstate", this.onPopState);
    this.setSelectedFiltersAndFetchAPIData();
  }

  componentWillUnmount() {
    window.removeEventListener("popstate", this.onPopState);
    if (this.abortController) this.abortController.abort();
  }

  onPopState = () => {
    this.setSelectedFiltersAndFetchAPIData();
  };

  setSelectedFiltersAndFetchAPIData() {
        const params = new URLSearchParams(window.location.search);
        const allParams = Object.fromEntries(params.entries());

        const sortKey = allParams.sort || "name";
        const sortDir = allParams.dir || "asc";

        delete allParams.sort;
        delete allParams.dir;
        delete allParams.page;

        this.setState(
            { selectedFilters: allParams, sortKey, sortDir },
            () => this.fetchAPIData(0)
        );
    }

  cancelAndInitAbortController() {
    if (this.abortController) this.abortController.abort();
    this.abortController = new AbortController();
  }

  getFinancialYear() {
    const path = window.location.pathname;
    const parts = path.split("/").filter(Boolean);
    return parts[parts.length - 1];
  }

  applyFilterChange = (name, value) => {
    const selectedFilters = { ...this.state.selectedFilters };

    if (value === null || value === undefined || String(value).trim() === "") {
        delete selectedFilters[name];
    } else {
        selectedFilters[name] = value;
    }

    const params = new URLSearchParams();

    // add filters
    Object.entries(selectedFilters).forEach(([k, v]) => {
        params.set(k, v);
    });

    // preserve sort and dir
    params.set("sort", this.state.sortKey || "name");
    params.set("dir", this.state.sortDir || "asc");

    history.pushState(null, "", `?${params.toString()}`);

    this.setState({ selectedFilters }, () => this.fetchAPIData(0));
    };


  getSortArrow = (key) => {
  if (this.state.sortKey !== key) return "";
  return this.state.sortDir === "asc" ? " ▲" : " ▼";
};

setSort = (key) => {
    this.setState(
        (prev) => {
        if (prev.sortKey === key) {
            return { sortDir: prev.sortDir === "asc" ? "desc" : "asc" };
        }
        return { sortKey: key, sortDir: "asc" };
        },
        () => {
        // update URL + refetch page 1
        const params = new URLSearchParams();

        Object.entries(this.state.selectedFilters).forEach(([k, v]) => {
            params.set(k, v);
        });

        params.set("sort", this.state.sortKey);
        params.set("dir", this.state.sortDir);

        history.pushState(null, "", `?${params.toString()}`);
        this.fetchAPIData(0);
        }
    );
    };


  handleFilterChange = (event) => {
    const { name, value } = event.target;
    this.applyFilterChange(name, value);
  };

  handleSearchChange = (event) => {
    this.debouncedFilterChange(event.target.name, event.target.value);
  };

  fetchAPIData(pageToCall) {
    this.setState({ isLoading: true }, () => {
      this.setDownloadUrl();
      this.cancelAndInitAbortController();

      const year = this.getFinancialYear();

      // Keep your existing API path
      let url = `${year}/api/v1/?page=${pageToCall + 1}`;

      url += `&sort=${encodeURIComponent(this.state.sortKey)}&dir=${encodeURIComponent(this.state.sortDir)}`;

      Object.entries(this.state.selectedFilters).forEach(([key, value]) => {
        if (value !== null && value !== undefined && String(value).trim() !== "") {
          url += `&${encodeURIComponent(key)}=${encodeURIComponent(value)}`;
        }
      });

      fetchWrapper(url, this.abortController)
        .then((response) => {
          const results = response && response.results ? response.results : {};
          const items = results.items && Array.isArray(results.items) ? results.items : [];
          const facets = results.facets ? results.facets : {};

          this.setState({
            currentPage: pageToCall,
            rows: items,
            totalCount: response && typeof response.count === "number" ? response.count : 0,
            departments: facets.department_name || [],
            isLoading: false,
            hasLoadedOnce: true,
          });
        })
        .catch((err) => {
          console.warn(err);
          this.setState({ isLoading: false, hasLoadedOnce: true });
        });
    });
  }

  setDownloadUrl() {
    const year = this.getFinancialYear();
    let url = `${year}/public-entities.xlsx`;

    const params = [];
    Object.entries(this.state.selectedFilters).forEach(([key, value]) => {
      if (value !== null && value !== undefined && String(value).trim() !== "") {
        params.push(`${encodeURIComponent(key)}=${encodeURIComponent(value)}`);
      }
    });

    if (params.length) url += `?${params.join("&")}`;
    this.setState({ downloadUrl: url });
  }

  // Client-side sort to match your chips
  getSortedRows() {
        const rows = Array.isArray(this.state.rows) ? [...this.state.rows] : [];

        const getDeptName = (r) => {
            if (!r || !r.department) return "";
            if (typeof r.department === "object" && r.department !== null) return r.department.name || "";
            return String(r.department);
        };

        const getFG = (r) => (r && r.functiongroup1 ? String(r.functiongroup1) : "");
        const getName = (r) => (r && r.name ? String(r.name) : "");

        // amount may come back as "123.45" or 123.45
        const getAmount = (r) => {
            if (!r) return 0;
            const v = r.amount;
            const n = typeof v === "number" ? v : Number(String(v).replace(/,/g, ""));
            return Number.isFinite(n) ? n : 0;
        };

        const { sortKey, sortDir } = this.state;
        const mul = sortDir === "desc" ? -1 : 1;

        rows.sort((a, b) => {
            let cmp = 0;

            if (sortKey === "department") cmp = getDeptName(a).localeCompare(getDeptName(b));
            else if (sortKey === "functiongroup1") cmp = getFG(a).localeCompare(getFG(b));
            else if (sortKey === "amount") cmp = getAmount(a) - getAmount(b);
            else cmp = getName(a).localeCompare(getName(b)); // default: name

            if (cmp === 0) cmp = (a.id || 0) - (b.id || 0); // stable tie-breaker
            return cmp * mul;
        });

        return rows;
    }

  getSortArrow(key) {
        if (this.state.sortKey !== key) return "";
        return this.state.sortDir === "asc" ? " ▲" : " ▼";
    }

  setSort(key) {
    this.setState((prev) => {
        if (prev.sortKey === key) {
        return { sortDir: prev.sortDir === "asc" ? "desc" : "asc" };
        }
        return { sortKey: key, sortDir: "asc" };
    });
   }

  // Pagination helpers (server-side pagination)
  canGoPrev() {
    return this.state.currentPage > 0;
  }

  canGoNext() {
    const { currentPage, rowsPerPage, totalCount } = this.state;
    return (currentPage + 1) * rowsPerPage < totalCount;
  }

  goPrev = () => {
    if (this.state.isLoading) return;
    if (!this.canGoPrev()) return;
    this.fetchAPIData(this.state.currentPage - 1);
  };

  goNext = () => {
    if (this.state.isLoading) return;
    if (!this.canGoNext()) return;
    this.fetchAPIData(this.state.currentPage + 1);
  };

  jumpToPage = () => {
    if (this.state.isLoading) return;

    const val = this.state.gotoPageInput;
    const num = parseInt(val, 10);
    if (isNaN(num)) return;

    const totalPages = Math.max(1, Math.ceil(this.state.totalCount / this.state.rowsPerPage));
    const pageIndex = Math.min(Math.max(num - 1, 0), totalPages - 1);
    this.fetchAPIData(pageIndex);
  };

  renderDepartmentFilter() {
    const options = Array.isArray(this.state.departments) ? this.state.departments : [];

    return (
      <FormControl variant="outlined" size="small" style={{ width: "100%" }}>
        <InputLabel shrink>Department</InputLabel>
        <Select
            notched
            label="Department"
            displayEmpty
            value={
                this.state.selectedFilters["department__name"] === undefined
                ? ""
                : this.state.selectedFilters["department__name"]
            }
            onChange={(e) => this.applyFilterChange("department__name", e.target.value)}
            >
            <MenuItem value="">
                <span style={{ color: "#64748b" }}>All departments</span>
            </MenuItem>

            {options.map((opt, idx) => {
                const name = opt && opt["department__name"] ? String(opt["department__name"]) : "";
                const count = opt && opt.count ? opt.count : 0;

                return (
                <MenuItem key={idx} value={name}>
                    <span style={{ flex: 1 }}>{name}</span>
                    <Chip size="small" label={count} />
                </MenuItem>
                );
            })}
            </Select>

      </FormControl>
    );
  }

  renderSortChips() {
  const active = (k) => (this.state.sortKey === k ? "active" : "");

  return (
    <div className="pe-sort-section">
      <div className="pe-sort-label">Sort by</div>
      <div className="pe-sort-chips">
        <button
          type="button"
          className={`pe-chip-button ${active("name")}`}
          onClick={() => this.setSort("name")}
        >
          Entity Name{this.getSortArrow("name")}
        </button>

        <button
          type="button"
          className={`pe-chip-button ${active("department")}`}
          onClick={() => this.setSort("department")}
        >
          Department{this.getSortArrow("department")}
        </button>

        <button
          type="button"
          className={`pe-chip-button ${active("functiongroup1")}`}
          onClick={() => this.setSort("functiongroup1")}
        >
          Function Group{this.getSortArrow("functiongroup1")}
        </button>

        <button
          type="button"
          className={`pe-chip-button ${active("amount")}`}
          onClick={() => this.setSort("amount")}
        >
          Expenditure{this.getSortArrow("amount")}
        </button>
      </div>
      <div className="pe-sort-divider" />
      <div className="pe-sort-chips">
        <div className="pe-header-controls">
            <button
                type="button"
                className={`pe-chip-button`}
                onClick={() => window.open(this.state.downloadUrl, "_blank")}
                >
          Download as Excel
        </button>
          {/* <Button variant="outlined" href={this.state.downloadUrl}>
            Download as .xlsx
          </Button> */}
        </div>
      </div>
    </div>
  );
}


  renderCard(item, idx) {
    const year = this.getFinancialYear();

    const entityName = item && item.name ? String(item.name) : "";
    const pfma = item && item.pfma ? String(item.pfma) : "-";
    const functiongroup1 = item && item.functiongroup1 ? String(item.functiongroup1) : "-";
    const amount = item && item.amount ? String(item.amount) : "0.00";

    const deptName =
      item && item.department
        ? typeof item.department === "object"
          ? item.department.name
          : String(item.department)
        : "";
    const deptSlug =
      item && item.department && typeof item.department === "object"
        ? item.department.slug
        : slugify(String(deptName));
    const deptPath =
      item && item.department && typeof item.department === "object"
        ? rootRelativePath(item.department.url_path)
        : "";

    const entityUrl = `/public-entities/${year}/national/${item.slug}`;
    const deptUrl = deptName
      ? deptPath || `/${year}/national/departments/${deptSlug}`
      : null;

      const formatValues = (value) => {
        const n = Number(value) || 0;
        const abs = Math.abs(n);

        const fmt = (x) =>
        x.toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

        if (abs >= 1e12) return `R ${fmt(n / 1e12)} trillion`;
        if (abs >= 1e9)  return `R ${fmt(n / 1e9)} billion`;
        if (abs >= 1e6)  return `R ${fmt(n / 1e6)} million`;
        if (abs >= 1e3)  return `R ${fmt(n / 1e3)} thousand`;

        return `R ${n.toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    };

    return (
      <div key={idx} className="pe-card">
        <div className="pe-card-title">
          <a href={entityUrl}>{entityName}</a>
        </div>

        <div className="pe-card-content">
          <div className="pe-card-field">
            <div className="pe-card-label">Relevant Department</div>
            {deptUrl ? (
              <a href={deptUrl} className="pe-card-value">
                {deptName}
              </a>
            ) : (
              <div className="pe-card-value">{deptName || "-"}</div>
            )}
          </div>

          <div className="pe-card-grid">
            <div className="pe-card-field">
              <div className="pe-card-label">PFMA</div>
              <div className="pe-card-value">{pfma}</div>
            </div>

            <div className="pe-card-field">
              <div className="pe-card-label">Function Group</div>
              <div className="pe-card-value">{functiongroup1}</div>
            </div>
          </div>
          <div className="pe-card-field">
            <div className="pe-card-label">Projected Expenditure</div>
            <div className="pe-card-value">{formatValues(amount)}</div>
          </div>
        </div>
      </div>
    );
  }

  renderPager() {
    const { currentPage, rowsPerPage, totalCount, isLoading } = this.state;

    const start = totalCount === 0 ? 0 : currentPage * rowsPerPage + 1;
    const end = Math.min(totalCount, (currentPage + 1) * rowsPerPage);
    const totalPages = Math.max(1, Math.ceil(totalCount / rowsPerPage));

    return (
      <div className="pe-pager-box">
        <div className="pe-pager-header">
          <div className="pe-pager-title">Page View</div>
          <div className="pe-pager-info">
            Showing <span className="highlight">{start}-{end}</span> of{" "}
            <span className="highlight">{totalCount}</span> entities
          </div>
        </div>

        <div className="pe-pager-controls">
          <button
            type="button"
            className={`pe-pager-button ${this.canGoPrev() && !isLoading ? "active" : ""}`}
            disabled={!this.canGoPrev() || isLoading}
            onClick={this.goPrev}
          >
            ‹ Prev
          </button>

          <div className="pe-page-numbers">
            <div className="pe-page-number current">{currentPage + 1}</div>
            <div className="pe-page-separator">of</div>
            <div className="pe-page-number">{totalPages}</div>
          </div>

          <button
            type="button"
            className={`pe-pager-button ${this.canGoNext() && !isLoading ? "active" : ""}`}
            disabled={!this.canGoNext() || isLoading}
            onClick={this.goNext}
          >
            Next ›
          </button>
        </div>

        <div className="pe-pager-divider">
          <label className="pe-go-to-label">Go to page</label>

          <input
            type="number"
            className="pe-page-input"
            value={this.state.gotoPageInput || ""}
            onChange={(e) => this.setState({ gotoPageInput: e.target.value })}
          />

          <button type="button" className="pe-jump-button" onClick={this.jumpToPage}>
            Jump
          </button>
        </div>

        <div className="pe-export-container">
          <a href={this.state.downloadUrl} className="pe-export-link">
            Export XLSX
          </a>
        </div>
      </div>
    );
  }

  renderTopControls() {
    return (
      <div className="pe-top-controls">
        <div className="pe-filter-wrapper">
          <div className="pe-search-field">
            <FormControl variant="outlined" size="small" style={{ width: "100%" }}>
              <TextField
                variant="outlined"
                size="small"
                label="Search public entities"
                name="q"
                onChange={this.handleSearchChange}
                style={{ width: "100%" }}
              />
            </FormControl>
          </div>

          <div className="pe-filter-field">{this.renderDepartmentFilter()}</div>

          <div>
            {this.state.isLoading ? (
              <div className="pe-loading-indicator">
                <CircularProgress size={18} />
                <span>Loading</span>
              </div>
            ) : null}
          </div>
        </div>

        {this.renderSortChips()}
      </div>
    );
  }

  render() {
    const cards = Array.isArray(this.state.rows) ? this.state.rows : [];

    return (
      <div className="pe-card-list">
        {this.renderTopControls()}

        <div className="pe-cards-grid">
          {!this.state.hasLoadedOnce ? (
            <div className="pe-empty-state">Loading...</div>
          ) : cards.length === 0 ? (
            <div className="pe-empty-state">No matching indicators found.</div>
          ) : (
            cards.map((item, idx) => this.renderCard(item, idx))
          )}
        </div>

        {this.renderPager()}

        <div className="pe-spacer" />
      </div>
    );
  }
}

function scripts() {
  const parent = document.getElementById("js-initPublicEntityData");
  if (parent) ReactDOM.render(<PublicEntityCardList />, parent);
}

export default scripts();
