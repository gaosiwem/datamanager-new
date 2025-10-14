import React, { Component } from 'react';
import ReactDOM from 'react-dom';
import {
    FormControl, Grid, InputLabel, TextField, Paper, Select,
    Table, TableBody, TableCell, TableContainer, TableFooter,
    TableHead, TablePagination, TableRow, Chip, CircularProgress,
    MenuItem, Button
} from "@material-ui/core";
import { ThemeProvider } from "@material-ui/styles";
import { createTheme } from '@material-ui/core/styles';
import fetchWrapper from "../../utilities/js/helpers/fetchWrapper";
import debounce from "lodash.debounce";
import slugify from "slugify";

class TabularView extends Component {
    constructor(props) {
        super(props);

        this.abortController = null;
        this.state = {
            rows: null,
            totalCount: 0,
            rowsPerPage: 20,
            currentPage: 0,
            selectedFilters: {},
            isLoading: false,
            downloadUrl: '',
            excludeColumns: new Set(['id', 'slug', 'intro', 'financialYear', 'government', 'budgetPhase']),
            titleMappings: {
                'name': 'Entity Name',
                'department': 'Relevant Department',
                'pfma': 'PFMA',
                'functiongroup1': 'Function Group',
                'amount': 'Projected Expenditure'
            }
        }

        this.debouncedFilterChange = debounce(this.applyFilterChange, 300);
    }

    componentDidMount() {
        window.addEventListener('popstate', () => this.setSelectedFiltersAndFetchAPIData());
        this.setSelectedFiltersAndFetchAPIData();
    }

    setSelectedFiltersAndFetchAPIData() {
        const params = new URLSearchParams(window.location.search);
        const selectedFilters = Object.fromEntries(params.entries());
        this.setState({ selectedFilters }, () => this.fetchAPIData(0));
    }

   applyFilterChange = (name, value) => {
    const selectedFilters = { ...this.state.selectedFilters };

    if (!value || value.trim() === "") {
        delete selectedFilters[name]; // remove empty filter
    } else {
        selectedFilters[name] = value;
    }

    const url = '?' + Object.entries(selectedFilters)
        .map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');

    history.pushState(null, '', url === '?' ? location.pathname : url);

    this.setState({ selectedFilters }, () => this.fetchAPIData(0));
}

    cancelAndInitAbortController() {
        if (this.abortController) this.abortController.abort();
        this.abortController = new AbortController();
    }

    getFinancialYear() {
        const path = window.location.pathname;
        const parts = path.split("/").filter(Boolean);
        const year = parts[parts.length - 1];
        return year;
    }

    fetchAPIData(pageToCall) {
        this.setState({ isLoading: true }, () => {
            this.setDownloadUrl();
            this.cancelAndInitAbortController();

            let year = this.getFinancialYear();
            let url = `${year}/api/v1/?page=${pageToCall + 1}`;

            Object.entries(this.state.selectedFilters).forEach(([key, value]) => {
                if (value !== null) url += `&${key}=${encodeURIComponent(value)}`;
            });

            fetchWrapper(url, this.abortController)
                .then(response => {
                    this.setState({
                        currentPage: pageToCall,
                        rows: response.results.items,
                        totalCount: response.count,
                        isLoading: false
                    });
                })
                .catch(console.warn);
        });
    }

    setDownloadUrl() {
        let year = this.getFinancialYear();
        
        let url = `${year}/public-entities.xlsx`;

        Object.entries(this.state.selectedFilters).forEach(([key, value], index) => {
            if (value !== null) {
                url += `${index === 0 ? '?' : '&'}${key}=${encodeURIComponent(value)}`;
            }
        });
        this.setState({ downloadUrl: url });
    }

    handleSort(field) {
        const { rows, sortField, sortDirection } = this.state;
        let direction = 'asc';
        if (sortField === field && sortDirection === 'asc') {
            direction = 'desc';
        }

        const sortedRows = [...rows].sort((a, b) => {
            let aVal = a[field];
            let bVal = b[field];

            // Handle objects
            if (typeof aVal === 'object') aVal = aVal.name || JSON.stringify(aVal);
            if (typeof bVal === 'object') bVal = bVal.name || JSON.stringify(bVal);

            // Handle numbers (like amount)
            if (!isNaN(aVal) && !isNaN(bVal)) {
                return direction === 'asc' ? aVal - bVal : bVal - aVal;
            }

            // Handle strings
            return direction === 'asc'
                ? String(aVal).localeCompare(String(bVal))
                : String(bVal).localeCompare(String(aVal));
        });

        this.setState({
            rows: sortedRows,
            sortField: field,
            sortDirection: direction
        });
    }

    renderTableHead() {
        if (!this.state.rows || this.state.rows.length === 0) return <div>No matching indicators found.</div>;

        return (
            <TableRow>
                {Object.keys(this.state.rows[0]).map((key, index) => {
                    if (this.state.excludeColumns.has(key)) return null;
                    return (
                        <TableCell
                            key={key}
                            onClick={() => this.handleSort(key)}
                            style={{ color: 'black', cursor: 'pointer', borderBottom: '1px solid #f2f2f2', fontWeight: 'bold' }}
                        >
                            {this.state.titleMappings[key] || key}
                        </TableCell>
                    )
                })}
            </TableRow>
        )
    }

    renderTableCells(row, index) {
        return (
            <TableRow key={index}>
                {Object.keys(row).map((key, i) => {
                    if (this.state.excludeColumns.has(key)) return null;
                    let value = typeof row[key] === 'object' ? row[key].name || JSON.stringify(row[key]) : row[key];
                    
                    let year = this.getFinancialYear();
                    // Make entity name and department clickable
                    if (key === 'name') {
                        value = <a href={`/public-entities/${year}/national/${row.slug}`} style={{ color: 'black', cursor: 'pointer' }}>{value}</a>;
                    }
                    if (key === 'department') {
                        
                        let domain = "https://vulekamali.gov.za"
                        value = <a href={`${domain}/${year}/national/departments/${slugify(row.department.name)}`} style={{ color: 'black', cursor: 'pointer' }}>{value}</a>;
                    }

                    if(key === 'amount') {
                        value = this.formatValue(row[key]);
                    }

                    return (
                        <TableCell key={`${index}_${i}`} title={value}  style={{ border: 'none' }}>
                            {value}
                        </TableCell>
                    )
                })}
            </TableRow>
        )
    }

    handlePageChange(event, newPage) {
        this.fetchAPIData(newPage);
    }

    renderPagination() {
        if (!this.state.rows) return <div style={{ height: '52px' }}></div>;

        return (
            <TablePagination
                count={this.state.totalCount}
                rowsPerPage={this.state.rowsPerPage}
                rowsPerPageOptions={[]}
                page={this.state.currentPage}
                onPageChange={(e, p) => this.handlePageChange(e, p)}
                component="div"
            />
        );
    }

    renderTable() {
        const tableTheme = createTheme({
            overrides: {
                MuiTablePagination: {
                    spacer: { flex: 'none' },
                    toolbar: { paddingLeft: '16px' }
                }
            }
        });

        return (
            <ThemeProvider theme={tableTheme}>
                <Button variant="outlined" href={this.state.downloadUrl} style={{ marginTop: 10, postion: 'relative', left: '82%', marginBottom: 10 }}>
                    Download as .xlsx
                </Button>
                <Paper>
                    {this.state.isLoading && <CircularProgress />}
                    {this.renderPagination()}
                    <TableContainer>
                        <Table sx={{ tableLayout: "fixed", width: "100%" }}>
                            <TableHead>{this.renderTableHead()}</TableHead>
                            <TableBody>
                                {this.state.rows && this.state.rows.map((row, index) => this.renderTableCells(row, index))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                    
                </Paper>
                
            </ThemeProvider>
        );
    }

    renderFilters() {
        return (
            <Grid container spacing={2} style={{ marginTop: 15 }}>
                <Grid item xs={12} sm={8} md={6} lg={4}>
                    <FormControl
                        variant="outlined"
                        size="small"
                        style={{
                            backgroundColor: 'white',
                            color: 'black',
                            width: '100%' // fill the Grid item
                        }}
                    >
                        <TextField
                            variant="outlined"
                            size="small"
                            label="Search public entities"
                            name="q"
                            onChange={e => this.debouncedFilterChange(e.target.name, e.target.value)}
                            style={{ width: '100%' }}
                        />
                    </FormControl>
                </Grid>
            </Grid>
        );
    }

    render() {
        return (
            <div>
                <div style={{paddingBottom: 15}}>
                    {this.renderFilters()}
                </div>
                {this.renderTable()}
            </div>
        );
    }

    formatValue(value) {
        if (value == null || isNaN(value)) return "R 0"; // Handle null/NaN safely

        const absValue = Math.abs(value);
        let formatted;

        if (absValue >= 1e12) {
            formatted = `R ${(absValue / 1e12).toFixed(1)} trillion`;
        } else if (absValue >= 1e9) {
            formatted = `R ${(absValue / 1e9).toFixed(1)} billion`;
        } else if (absValue >= 1e6) {
            formatted = `R ${(absValue / 1e6).toFixed(1)} million`;
        } else if (absValue >= 1e3) {
            formatted = `R ${(absValue / 1e3).toFixed(1)} thousand`;
        } else {
            formatted = `R ${absValue.toLocaleString()}`;
        }
        // Reapply negative sign if needed
        return value < 0 ? `- ${formatted}` : formatted;
        }
}

function scripts() {
    const parent = document.getElementById('js-initPublicEntityData');
    if (parent) ReactDOM.render(<TabularView />, parent);
}

export default scripts();