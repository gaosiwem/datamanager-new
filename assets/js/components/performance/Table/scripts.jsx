import React, {Component} from 'react';
import ReactDOM from 'react-dom';
import {
    FormControl,
    Grid,
    InputLabel,
    TextField,
    Paper,
    Select,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableFooter,
    TableHead,
    TablePagination,
    TableRow,
    Chip,
    CircularProgress,
    Dialog,
    MenuItem,
    Button,
} from "@material-ui/core";
import {ThemeProvider} from "@material-ui/styles";
import {createTheme} from '@material-ui/core/styles';
import fetchWrapper from "../../../utilities/js/helpers/fetchWrapper";
import debounce from "lodash.debounce";

class TabularView extends Component {
    constructor(props) {
        super(props);

        this.resizeObserver = null;
        this.observedElements = [];
        this.abortController = null;

        this.state = {
            dataDisclaimerAcknowledged: false,
            modalOpen: false,
            rows: null,
            departments: null,
            financialYears: null,
            frequencies: null,
            governments: null,
            mtsfOutcomes: null,
            sectors: null,
            spheres: null,
            totalCount: 0,
            rowsPerPage: 20,
            currentPage: 0,
            selectedFilters: {},
            isLoading: false,
            downloadUrl: '',
            excludeColumns: new Set(['id', 'department']),
            titleMappings: {
                'indicator_name': 'Indicator name',
                'q1_target': 'Quarter 1 target',
                'q1_actual_output': 'Quarter 1 actual output',
                'q1_deviation_reason': 'Quarter 1 deviation reason',
                'q1_corrective_action': 'Quarter 1 corrective action',
                'q2_target': 'Quarter 2 target',
                'q2_actual_output': 'Quarter 2 actual output',
                'q2_deviation_reason': 'Quarter 2 deviation reason',
                'q2_corrective_action': 'Quarter 2 corrective action',
                'q3_target': 'Quarter 3 target',
                'q3_actual_output': 'Quarter 3 actual output',
                'q3_deviation_reason': 'Quarter 3 deviation reason',
                'q3_corrective_action': 'Quarter 3 corrective action',
                'q4_target': 'Quarter 4 target',
                'q4_actual_output': 'Quarter 4 actual output',
                'q4_deviation_reason': 'Quarter 4 deviation reason',
                'q4_corrective_action': 'Quarter 4 corrective action',
                'annual_target': 'Annual target',
                'annual_aggregate_output': 'Annual aggregate output',
                'annual_pre_audit_output': 'Annual pre-audit output',
                'annual_deviation_reason': 'Annual deviation reason',
                'annual_corrective_action': 'Annual corrective action',
                'annual_audited_output': 'Annual audited output',
                'sector': 'Sector',
                'programme_name': 'Programme name',
                'subprogramme_name': 'Subprogramme name',
                'frequency': 'Frequency',
                'type': 'Type',
                'subtype': 'Subtype',
                'mtsf_outcome': 'Mtsf outcome',
                'cluster': 'Cluster',
                'financial_year': 'Financial year',
                'department_name': 'Department name',
                'government_name': 'Government name',
                'sphere_name': 'Sphere name'
            }
        }
    }

    componentDidMount() {
        this.fetchAPIData(0);
        window.addEventListener('popstate', (event) => {
            this.setSelectedFiltersAndFetchAPIData();
        })

        this.setSelectedFiltersAndFetchAPIData();
        this.checkForLocalStorage();
    }

    checkForLocalStorage() {
        const ack = localStorage.getItem('data-disclaimer-acknowledged');
        this.setState({
            dataDisclaimerAcknowledged: ack === 'true',
            modalOpen: ack !== 'true'
        })
    }


    setSelectedFiltersAndFetchAPIData() {
        let selectedFilters = {};
        let params = new URLSearchParams(window.location.search);
        for (const key of params.keys()) {
            selectedFilters[key] = params.get(key);
        }

        document.getElementById('frm-textSearch').value = selectedFilters['q'] === undefined ? '' : selectedFilters['q'];

        this.setState({
            ...this.state, selectedFilters: selectedFilters
        }, () => {
            this.fetchAPIData(0);
        })
    }

    handleFilterChange(event) {
        const name = event.target.name;
        const value = event.target.value;

        let selectedFilters = this.state.selectedFilters;
        selectedFilters[name] = value;

        let url = '';
        Object.keys(selectedFilters)
            .filter(key => selectedFilters[key] !== null)
            .forEach((key, i) => {
                const value = selectedFilters[key];
                url += `${i === 0 ? '?' : '&'}${key}=${encodeURI(value)}`;
            })

        history.pushState(null, '', url === '' ? location.pathname : url)

        this.setState({
            ...this.state, selectedFilters: selectedFilters
        }, () => {
            this.fetchAPIData(0);
        })
    }

    cancelAndInitAbortController() {
        if (this.abortController !== null) {
            // this.abortController is null on the first request
            this.abortController.abort();
        }
        this.abortController = new AbortController();

    }

    fetchAPIData(pageToCall) {
        this.setState({
            ...this.state,
            isLoading: true
        }, () => {
            this.setDownloadUrl();
            this.cancelAndInitAbortController();

            this.unobserveElements();

            let url = `api/v1/eqprs/?page=${pageToCall + 1}`;

            // append filters
            Object.keys(this.state.selectedFilters).forEach((key) => {
                let value = this.state.selectedFilters[key];
                if (value !== null) {
                    url += `&${key}=${encodeURI(value)}`;
                }
            })

            fetchWrapper(url, this.abortController)
                .then((response) => {
                    this.setState({
                        ...this.state,
                        currentPage: pageToCall,
                        rows: response.results.items,
                        departments: response.results.facets['department_name'],
                        financialYears: response.results.facets['financial_year_slug'],
                        frequencies: response.results.facets['frequency'],
                        governments: response.results.facets['government_name'],
                        mtsfOutcomes: response.results.facets['mtsf_outcome'],
                        sectors: response.results.facets['sector'],
                        spheres: response.results.facets['sphere_name'],
                        totalCount: response.count,
                        isLoading: false
                    });
                })
                .then(() => {
                    this.handleObservers();
                })
                .catch((errorResult) => console.warn(errorResult));
        })
    }

    setDownloadUrl() {
        let url = 'performance-indicators.xlsx/';

        // append filters
        Object.keys(this.state.selectedFilters).forEach((key, index) => {
            let value = this.state.selectedFilters[key];
            if (value !== null) {
                let prefix = index === 0 ? '?' : '&';
                url += `${prefix}${key}=${encodeURI(value)}`;
            }
        })

        this.setState({
            ...this.state,
            downloadUrl: url
        });
    }

    renderTableHead() {
        if (this.state.rows.length > 0) {
            return (<TableRow>
                {Object.keys(this.state.rows[0]).map((key, index) => {
                    if (!this.state.excludeColumns.has(key)) {
                        if (key === 'indicator_name') {
                            return (<TableCell
                                key={index}
                                size={'small'}
                                className={'performance-table-head-cell indicator-column-head'}
                            >
                                <div className={'cell-content'}>
                                    {this.getTitleMapping(key)}
                                </div>
                            </TableCell>)
                        } else {
                            return (<TableCell
                                key={index}
                                size={'small'}
                                className={'performance-table-head-cell'}
                            >
                                <div className={'cell-content'}>
                                    {this.getTitleMapping(key)}
                                </div>
                            </TableCell>)
                        }
                    }
                })}
            </TableRow>)
        } else {
            return <div>No matching indicators found.</div>;
        }
    }

    renderTableCells(row, index) {
        const isAlternating = index % 2 !== 0;
        return (<TableRow
            key={`${this.state.currentPage}_${index}`}
        >
            {Object.keys(row).map((key, i) => {
                if (!this.state.excludeColumns.has(key)) {
                    if (key === 'indicator_name') {
                        return (<TableCell
                            key={`${this.state.currentPage}_${index}_${0}`}
                            className={isAlternating ? 'performance-indicator-cell alternate' : 'performance-indicator-cell'}
                            title={row[key]}
                        >
                            <div className={'cell-content'}>
                                {this.renderIndicatorColumn(row, index)}
                            </div>
                        </TableCell>)
                    } else {
                        return (<TableCell
                            key={`${this.state.currentPage}_${index}_${i}`}
                            className={isAlternating ? 'performance-table-cell alternate' : 'performance-table-cell'}
                            title={row[key]}
                        >
                            <div
                                className={'cell-content'}
                                id={`cell_${this.state.currentPage}_${index}_${i}`}
                            >
                                <input type="checkbox" id={`expanded_${this.state.currentPage}_${index}_${i}`}/>
                                <span style={{
                                    WebkitBoxOrient: 'vertical'
                                }}>{row[key]}</span>
                                <label
                                    htmlFor={`expanded_${this.state.currentPage}_${index}_${i}`}
                                    role={'button'}
                                >Read more</label>
                            </div>
                        </TableCell>)
                    }
                }
            })}
        </TableRow>)
    }

    handleReadMoreClick(e, i, index, text) {
        if (e.target.className === 'link-button') {
            const cellId = `cell_${this.state.currentPage}_${index}_${i}`;
            let element = document.getElementById(cellId);

            element.innerText = text;
        }
    }

    getTitleMapping(key) {
        const mapping = this.state.titleMappings[key];

        return mapping === undefined ? key : mapping;
    }

    renderIndicatorColumn(row, index) {
        const chips = [{
            key: "financial_year",
            value: row.department.government.sphere.financial_year.slug
        }, {
            key: "government_name",
            value: row.department.government.name
        }, {
            key: "department_name",
            value: row.department.name
        }];
        return (
            <div>
                <div className={'indicator-name'}>
                    {row['indicator_name']}
                </div>
                {
                    chips.map((chip, i) => {
                        return (
                            <Chip
                                key={`chip_${index}_${i}`}
                                label={chip.value}
                                title={chip.value}
                                className={'indicator-detail-chip'}
                                size={'small'}
                            />
                        )
                    })
                }
            </div>
        )
    }

    handlePageChange(event, newPage) {
        this.fetchAPIData(newPage);
    }

    renderPaginationAndTools() {
        return (
            <Grid container>
                <Grid item xs={6}>
                    {this.renderPagination()}
                </Grid>
                <Grid
                    item
                    container
                    xs={6}
                    justifyContent={'flex-end'}
                    style={{height: '40px'}}
                >
                    <Button
                        variant={'outlined'}
                        className={'download-btn'}
                        href={this.state.downloadUrl}
                    >
                        Download as .xlsx
                    </Button>
                </Grid>
            </Grid>
        );
    }

    renderPagination() {
        if (this.state.rows === null) {
            // empty pagination row
            return <div style={{height: '52px'}}></div>
        }

        return (
            <TablePagination
                colSpan={3}
                count={this.state.totalCount}
                rowsPerPage={this.state.rowsPerPage}
                rowsPerPageOptions={[]}
                page={this.state.currentPage}
                onPageChange={(event, newPage) => this.handlePageChange(event, newPage)}
                SelectProps={{
                    inputProps: {'aria-label': 'rows per page'}, native: true,
                }}
                component="div"
            />
        );
    }

    renderTableContainer() {
        if (this.state.rows === null) {
            return <div></div>
        }

        return (
            <TableContainer
                className={'performance-table-container'}
            >
                <Table
                    stickyHeader
                    aria-label={'simple table'}
                    size={'medium'}
                    className={'performance-table'}
                >
                    <TableHead
                        className={'performance-table-head'}
                    >
                        {this.renderTableHead()}
                    </TableHead>
                    <TableBody>
                        {this.state.rows.map((row, index) => this.renderTableCells(row, index))}
                    </TableBody>
                    <TableFooter>
                        <TableRow>
                        </TableRow>
                    </TableFooter>
                </Table>
            </TableContainer>
        )
    }

    renderTable() {
        const tableTheme = createTheme({
            overrides: {
                MuiTablePagination: {
                    spacer: {
                        flex: 'none'
                    }, toolbar: {
                        "padding-left": "16px"
                    }
                }
            }
        });
        return (
            <ThemeProvider theme={tableTheme}>
                {this.renderPaginationAndTools()}
                <Paper
                    className={'performance-table-paper'}
                >
                    {this.renderLoadingState()}
                    {this.renderTableContainer()}
                </Paper>
                {this.renderPagination()}
            </ThemeProvider>
        );
    }

    renderLoadingState() {
        if (!this.state.isLoading) {
            return;
        }

        const tableContainer = document.getElementById('js-initTabularView');
        const gifWidth = 40;
        const marginLeftVal = (tableContainer.clientWidth - gifWidth) / 2;

        return (
            <div className={'table-loading-state'}>
                <CircularProgress
                    className={'table-circular-progress'}
                    style={{marginLeft: marginLeftVal}}
                />
            </div>
        )
    }

    handleObservers() {
        const ps = document.querySelectorAll('.performance-table-cell span');
        if (this.resizeObserver === null) {
            this.resizeObserver = new ResizeObserver(entries => {
                for (let entry of entries) {
                    entry.target.classList[entry.target.scrollHeight * 0.95 > entry.contentRect.height ? 'add' : 'remove']('truncated');
                }
            })
        }

        ps.forEach(p => {
            this.observedElements.push(p);
            this.resizeObserver.observe(p);
        })
    }

    unobserveElements() {
        if (this.resizeObserver === null) {
            return;
        }

        this.observedElements.forEach(ele => {
            this.resizeObserver.unobserve(ele);
        })
        this.observedElements = [];
    }

    renderSearchField() {
        const debouncedHandleFilterChange = debounce((event) => this.handleFilterChange(event), 300);
        const persistedEventDeboundedHandler = (event) => {
            // https://reactjs.org/docs/legacy-event-pooling.html
            event.persist();
            debouncedHandleFilterChange(event);
        };

        return (<FormControl variant={'outlined'}
                             size={'small'}
                             style={{
                                 marginRight: '10px', marginTop: '15px', fontSize: '8px'
                             }}>
            <TextField variant="outlined"
                       size="small"
                       label="Search indicators"
                       inputProps={{
                           id: "frm-textSearch", name: "q"
                       }}
                       onChange={persistedEventDeboundedHandler}/>
        </FormControl>)
    }

    renderFilter(id, apiField, stateField, fieldLabel, blankLabel) {
        if (this.state[stateField] === null) {
            return <div></div>
        } else {
            return (
                <FormControl
                    variant={'outlined'}
                    size={'small'}
                    style={{
                        minWidth: '150px',
                        maxWidth: '250px',
                        marginRight: '10px',
                        marginTop: '15px',
                        fontSize: '8px'
                    }}
                    className={'filter-search'}
                >
                    <InputLabel htmlFor={`frm-${id}`} shrink>{fieldLabel}</InputLabel>
                    <Select
                        notched
                        label={fieldLabel}
                        inputProps={{
                            id: `frm-${id}`, name: apiField
                        }}
                        displayEmpty={true}
                        value={this.state.selectedFilters[apiField] === undefined ? null : this.state.selectedFilters[apiField]}
                        onChange={(event) => this.handleFilterChange(event)}
                    >
                        <MenuItem
                            value={null}
                            className={'filter-menu-item'}
                        >
                            <span className={'option-text blank-label'}>
                                {blankLabel}
                            </span>
                        </MenuItem>
                        {this.state[stateField].map((option, index) => {
                            return (
                                <MenuItem
                                    key={index}
                                    value={option[apiField]}
                                    className={'filter-menu-item'}
                                >
                                    {this.renderMenuItemText(option[apiField])}
                                    <Chip
                                        label={option['count']}
                                        className={'option-facet'}
                                    />
                                </MenuItem>
                            )
                        })}
                    </Select>
                </FormControl>
            )
        }
    }

    renderMenuItemText(text) {
        if (text == null || text.trim() === '') {
            return (
                <span
                    className={'option-text'}
                >
                    <i>Blank</i>
                </span>
            )
        } else {
            return (
                <span
                    className={'option-text'}
                >
                    {text}
                </span>
            )
        }
    }

    renderFilters() {
        return (<Grid container>
            {this.renderSearchField()}
            {this.renderFilter('financialYears', 'department__government__sphere__financial_year__slug', 'financialYears', 'Financial year', 'All financial years')}
            {this.renderFilter('sphere', 'department__government__sphere__name', 'spheres', 'Sphere', 'All spheres')}
            {this.renderFilter('government', 'department__government__name', 'governments', 'Government', 'All governments')}
            {this.renderFilter('department', 'department__name', 'departments', 'Department', 'All departments')}
            {this.renderFilter('frequency', 'frequency', 'frequencies', 'Frequency', 'All frequencies')}
            {this.renderFilter('sector', 'sector', 'sectors', 'Sectors', 'All sectors')}
            {this.renderFilter('mtsfOutcome', 'mtsf_outcome', 'mtsfOutcomes', 'MTSF Outcome', 'All outcomes')}
        </Grid>)
    }

    handleStorage() {
        localStorage.setItem('data-disclaimer-acknowledged', 'true');
        this.setState({
            ...this.state,
            dataDisclaimerAcknowledged: true,
            modalOpen: false
        })
    }

    renderLearnMoreButton() {
        return (
            <a
                className={'Button is-inline u-marginBottom10 performance-modal-button'}
                href={'https://performance.vulekamali.gov.za/stages/implementation-monitoring#3.2'}
                target={'_blank'}
            >
                Learn more about Quarterly Performance Reporting
            </a>
        )
    }

    renderDataSourceModal() {
        return (
            <Dialog
                open={this.state.modalOpen}
                container={() => document.getElementById('performance-table-container')}
                style={{position: 'absolute'}}
                BackdropProps={{
                    style: {position: 'absolute'}
                }}
                disableAutoFocus={true}
                disableEnforceFocus={true}
                className={'performance-modal'}
            >
                <Grid
                    className={'performance-modal-title'}
                >
                    Data disclaimer
                </Grid>
                <Grid
                    className={'performance-modal-content'}
                >
                    The Quarterly Performance Reporting (QPR) data (other than the Annual audited output field)
                    is pre-audited non financial data. This data is approved by the accounting officer of the
                    relevant organ of state before publication.
                </Grid>
                <Grid
                    className={'performance-modal-link'}
                >
                    <a
                        href="https://performance.vulekamali.gov.za/stages/implementation-monitoring#3.2"
                        target={'_blank'}
                    >Learn more about these performance indicators.</a>
                </Grid>
                <Grid>
                    <button
                        className={'Button is-inline u-marginBottom10 performance-modal-full performance-modal-button'}
                        onClick={() => this.handleStorage()}
                    >
                        Acknowledge and continue
                    </button>
                </Grid>
            </Dialog>
        )
    }

    renderLearnMore() {
        return (
            <Grid>
                {this.renderLearnMoreButton()}
                {this.renderDataSourceModal()}
            </Grid>
        )
    }

    render() {
        return (<div>
            {this.renderLearnMore()}
            {this.renderFilters()}
            {this.renderTable()}
        </div>);
    }
}

function scripts() {
    const parent = document.getElementById('js-initTabularView');
    if (parent) {
        ReactDOM.render(<TabularView
        />, parent)
    }
}


export default scripts();